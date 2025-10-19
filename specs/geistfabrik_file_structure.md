# GeistFabrik File Structure

This document explains the purpose of each file and folder in the GeistFabrik system.

## Summary

| Component | Type | User Edits? | Purpose |
|-----------|------|-------------|---------|
| `vault.db` | SQLite DB | No | Vault intelligence cache |
| `config.yaml` | Config | Yes | Vault-specific settings |
| `geists/code/` | Python code | Yes | Code geists (advanced) |
| `geists/tracery/` | YAML | Yes | Tracery geists (accessible) |
| `metadata_inference/` | Python modules | Yes | Extend note properties |
| `vault_functions/` | Python modules | Yes | Query utilities + Tracery bridge |
| `geist journal/` | Markdown notes | No* | Geist output (can annotate) |

*Users don't create these files, but can edit/annotate them after generation.

## Proposed Structure

```
MyVault/
├── _geistfabrik/
│   ├── vault.db
│   ├── config.yaml
│   ├── geists/
│   │   ├── tracery/
│   │   └── code/
│   ├── metadata_inference/
│   └── vault_functions/
├── geist journal/
│   └── 2025-01-15.md
└── (user's notes)
```

---

## _geistfabrik/ Folder

**Purpose:** Houses all GeistFabrik system data and user-extensible components for a specific vault.

**Why underscore prefix:**
- Sorts to the top of Obsidian's file explorer
- Visually signals "system folder" that users can collapse and ignore during daily use
- Easy to find when needed for configuration or adding geists

---

### `vault.db` (SQLite Database)

**Why it exists:**
- Stores parsed note data (titles, paths, content, links, tags, dates)
- Stores graph relationships (links table with source/target)
- Stores vector embeddings (384-dim semantic + 3-dim temporal via sqlite-vec)
- Stores computed metadata for each note
- Stores geist execution history (which suggestions were generated when)
- Stores block reference mappings
- Stores session data for temporal embedding tracking
- Enables fast queries (graph operations, semantic search, metadata filtering)

**Why vault-specific:**
- Each vault has different notes, different graph structure
- Embeddings are vault-specific
- Avoids conflicts between multiple vaults

**Why SQLite:**
- Single-file portability
- Fast indexed queries
- sqlite-vec extension for vector similarity search
- Incremental updates (only reprocess changed files)

---

### `config.yaml` (Configuration File)

**Why it exists:**
- Vault-specific settings (which paths to exclude from processing)
- Embedding configuration (model, weights between semantic/temporal)
- Session settings (default suggestions count, novelty window)
- Quality filtering thresholds (min/max length)
- Geist execution settings (timeout, max failures before disable)
- Filter configuration (enable/disable specific filters, thresholds)
- Module configuration (which metadata/function modules to load)

**Why vault-specific:**
- Different vaults may need different exclusion paths
- Different users may want different quality thresholds
- Allows per-vault customization while having global defaults

---

### `geists/` Folder

**Purpose:** Groups all geist definitions in one place, regardless of implementation type.

**Why grouped:**
- Users understand "all geists live here"
- Clear organization: simple (Tracery) vs advanced (Python)
- Natural progression: start with Tracery, graduate to code geists

---

### `geists/code/` Folder (Python Code Geists)

**Why it exists:**
- Houses Python files that implement code geists
- Each geist exports: `suggest(vault: VaultContext) -> List[Suggestion]`
- Code geists have full programmatic access to vault data

**What goes here:**
- `connection_finder.py` - Find semantically similar unlinked notes
- `columbo.py` - Detect contradictions between notes
- `session_drift.py` - Track how note understanding evolves
- `island_hopper.py` - Find notes that could bridge clusters
- etc.

**Why vault-specific:**
- Allows project-specific geists (e.g., academic vault has citation-pattern geists)
- User can version control custom geists with their vault
- Different vaults can have different geist configurations

**Why user-extensible:**
- Core principle: extensibility at every layer
- Users develop their own pattern recognition logic
- Community can share geists

---

### `geists/tracery/` Folder (Tracery Geists)

**Why it exists:**
- Houses YAML files that define Tracery grammar-based geists
- Lower barrier to entry than Python code
- Declarative pattern generation

**What goes here:**
- `question_challenger.yaml` - Generate questions about existing notes
- `temporal_mirror.yaml` - Connect old and new notes
- `scale_shifter.yaml` - Generate scale-shifting prompts
- etc.

**Example format:**
```yaml
type: geist-tracery
id: question_challenger
tracery:
  origin: "#prompt# [[#question#]]?"
  prompt: ["What assumes the opposite of", "Who benefits from"]
  question: ["$vault.find_questions(1)"]
```

**Why vault-specific:**
- Different vaults may need different prompting styles
- Domain-specific Tracery grammars (academic vs creative writing)

**Why separate from code geists:**
- Different skill requirements (grammar design vs Python coding)
- Easier for non-programmers to create geists
- Clearer separation of concerns

---

### `metadata_inference/` Folder (Metadata Inference Modules)

**Why the longer name:**
- Explicit about purpose: these modules *infer* additional properties
- Distinguishes from frontmatter metadata in notes
- Clear that this is active computation, not passive storage

**Why it exists:**
- Houses Python modules that compute additional properties about notes
- Each module exports: `infer(note: Note, vault: VaultContext) -> Dict`
- Extends what the system "knows" about each note beyond raw data

**What goes here:**
- `complexity.py` - Calculate reading complexity, concept density
- `sentiment.py` - Analyze mood/tone of note
- `temporal.py` - Compute staleness, seasonal patterns

**Example:**
```python
def infer(note: Note, vault: VaultContext) -> Dict:
    return {
        "reading_time": len(note.content.split()) / 200,
        "link_density": len(note.links) / max(1, len(note.content.split())),
        "has_tasks": "- [ ]" in note.content
    }
```

**Why user-extensible:**
- Different domains need different metadata (code complexity vs argument strength)
- Users can add domain-specific intelligence
- Metadata accumulates in VaultContext, not Note objects (keeps Note simple)

**Critical architectural point:**
- Metadata modules compute properties
- Functions (below) expose them to Tracery geists
- This separation allows metadata to evolve without changing core data structures

---

### `vault_functions/` Folder (Vault Functions)

**Why the longer name:**
- Explicit about purpose: functions that operate on the vault
- Clear these are utilities available to Tracery as `$vault.function_name()`
- Distinguishes from general Python functions

**Why it exists:**
- Houses Python modules with `@vault_function` decorated functions
- Functions query/filter vault data in specific ways
- Automatically available in Tracery as `$vault.function_name()`

**What goes here:**
- Built-in: `sample_notes(k)`, `neighbors(note, k)`, `old_notes(k)`, etc.
- Custom: `contrarian_to(note)`, `notes_by_mood(mood)`, `complex_notes(threshold)`

**Example:**
```python
@vault_function("contrarian_to")
def find_contrarian(vault: VaultContext, note_title: str, k=3):
    """Find notes that might disagree with given note"""
    note = vault.get_note(note_title)
    similarities = [(n, vault.similarity(note, n)) for n in vault.notes()]
    contrarian = sorted(similarities, key=lambda x: x[1])[:k]
    return [n for n, _ in contrarian]
```

**Why it's the bridge to Tracery:**
- Code geists can access metadata directly: `vault.metadata(note)`
- Tracery geists can only call functions: `$vault.function_name()`
- Every metadata dimension needs a function to be Tracery-accessible

**Why user-extensible:**
- Different query patterns needed for different thinking styles
- Functions encapsulate complex vault operations
- Reusable across multiple geists

---

## geist journal/ Folder

**Purpose:** Houses the OUTPUT of GeistFabrik - the generated suggestions

**Why it exists:**
- Each session creates one note: `YYYY-MM-DD.md`
- Contains suggestions from geists for that date
- These are actual Obsidian notes users can link to, embed, annotate

**What's inside:**
```markdown
# GeistFabrik Session – 2025-01-15

## connection_finder ^g20250115-001
[[Project Planning]] × [[Fermentation]] – what if they follow the same cycles?

## columbo ^g20250115-002
I think you're lying about [[Democracy Note]]...
```

**Why separate folder:**
- Keeps sessions organized chronologically
- Can be linked: `[[geist journal/2025-01-15]]`
- Can be embedded: `![[geist journal/2025-01-15#columbo]]`

**Why "journal" not "sessions":**
- More natural: "the geist journal"
- Reads well in links
- Singular feels right - it's one journal with multiple entries
- Won't conflict with user's personal journal
- Natural archive of GeistFabrik's suggestions over time

**Why in vault root, not inside _geistfabrik/:**
- These ARE notes - part of user's knowledge graph
- Users might want to link to them from other notes
- Makes them first-class vault citizens

---

## Architectural Questions

**Key Questions This Raises:**

1. **Does everything need to be vault-local?** Could some be global?
2. **Do sessions belong inside _geistfabrik/ or outside?**
3. **Should geists/metadata_inference/vault_functions have global defaults that can be overridden locally?**

### Consideration: Vault-Local vs Global

**Current Design: Vault-Local**
- All system files live in `MyVault/_geistfabrik/`
- Each vault is self-contained and portable
- Custom geists can be version-controlled with vault
- Different vaults can have completely different configurations

**Alternative: Hybrid Approach**
```
MyVault/
├── _geistfabrik/
│   ├── vault.db              # Always vault-local
│   └── config.yaml           # References global or local geists
├── geist journal/
└── (notes)

~/Documents/geistfabrik-extensions/  # Optional global library
├── geists/
│   ├── tracery/
│   └── code/
├── metadata_inference/
└── vault_functions/
```

**Config could specify search paths:**
```yaml
# _geistfabrik/config.yaml
geists:
  search_paths:
    - "./geists"                  # Vault-local first
    - "~/Documents/geistfabrik-extensions/geists"  # Global fallback
```

**Benefits of hybrid:**
- Database and sessions stay with vault (portable)
- General-purpose geists can be shared across vaults
- Project-specific geists stay with their vault
- Users choose: all-local, all-global, or mixed

### Consideration: Obsidian Visibility

**Current choice: Underscore prefix `_geistfabrik/`**

**Why underscore:**
- ✅ Sorts to top of file explorer (easy to find when needed)
- ✅ Visual signal of "system folder" (users can mentally ignore)
- ✅ Fully visible in both Finder and Obsidian
- ✅ Users can collapse folder for daily use
- ✅ No special settings needed

**Alternative considered: Dot prefix `.geistfabrik/`**
- Would hide from Obsidian by default
- Requires Cmd+Shift+. in Finder to see
- Less discoverable for new users
- Not chosen because visibility + sorting is better UX

**Output folder: No prefix `geist journal/`**
- These ARE notes - part of knowledge graph
- Users want to see these daily
- Links read naturally: `[[geist journal/2025-01-15]]`

### Consideration: Sessions Folder Location

**Option A: Outside _geistfabrik/ (Current)**
```
MyVault/
├── _geistfabrik/          # System
├── geist journal/         # Output
└── Notes/
```

**Option B: Inside _geistfabrik/**
```
MyVault/
├── _geistfabrik/
│   ├── vault.db
│   ├── config.yaml
│   ├── geists/
│   └── journal/           # Output here
└── Notes/
```

**Recommendation: Keep journal outside (Option A)**
- Sessions are first-class notes, not system files
- More discoverable
- Natural to link to from other notes
- Signals that these are part of the knowledge graph
