# GeistFabrik Architecture

This document provides a visual overview of the GeistFabrik architecture, showing the layering and data flow.

```
════════════════════════════════════════════════════════════════════════════
                         GEISTFABRIK ARCHITECTURE
         "Muses, not oracles" - Divergence engine for Obsidian vaults
════════════════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────────────────┐
│                            USER INVOCATION                                │
│                                                                           │
│  $ geistfabrik invoke [--geist X] [--full] [--date YYYY-MM-DD]          │
│                                                                           │
│  Creates session → Runs all geists → Filters → Samples → Outputs        │
└─────────────────────────────────┬────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                       SESSION ORCHESTRATOR                                │
│                                                                           │
│  1. Compute embeddings for this session (temporal + semantic)            │
│  2. Execute ALL geists (parallel, 5s timeout each)                       │
│  3. Apply filtering (boundary/novelty/diversity/quality)                 │
│  4. Sample ~5 suggestions (deterministic, date-seeded)                   │
│  5. Write to geist journal/YYYY-MM-DD.md                                 │
└───────────────────────┬──────────────────────┬───────────────────────────┘
                        │                      │
            ┌───────────┴─────────┐      ┌─────┴──────────────┐
            ▼                     ▼      ▼                    ▼
┌──────────────────────┐  ┌────────────────────────┐  ┌──────────────────┐
│   CODE GEISTS        │  │   TRACERY GEISTS       │  │  BUILT-IN GEISTS │
│                      │  │                        │  │                  │
│ _geistfabrik/geists/ │  │ _geistfabrik/geists/   │  │ (system-provided)│
│   code/*.py          │  │   tracery/*.yaml       │  │                  │
│                      │  │                        │  │                  │
│ def suggest(vault):  │  │ type: geist-tracery    │  │                  │
│   # vault is         │  │ tracery:               │  │                  │
│   # VaultContext     │  │   origin: "#template#" │  │                  │
│   notes = vault      │  │   hubs: "$vault.hubs() │  │                  │
│     .neighbours(n)   │  │          .map(title)"  │  │                  │
│   # notes are        │  │                        │  │                  │
│   # List[Note]       │  │ Uses FunctionRegistry  │  │                  │
│   return suggestions │  │ for $vault.* calls     │  │                  │
└──────────┬───────────┘  └────────┬───────────────┘  └────────┬─────────┘
           │                       │                            │
           └───────────────────────┴────────────────────────────┘
                                   │
                                   │ ALL GEISTS RECEIVE
                                   ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                   LAYER 2: VaultContext                                  ┃
┃              (Rich Execution Context for Geists)                         ┃
┃                                                                          ┃
┃  WHAT GEISTS RECEIVE: A fully-powered intelligence layer                ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ VAULT ACCESS (returns Note objects)                             │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  • notes() -> List[Note]          All notes in vault            │   ┃
┃  │  • get_note(path) -> Note         Get specific note             │   ┃
┃  │  • read(note) -> str              Read note.content             │   ┃
┃  │  • resolve_link_target(target)    Resolve [[wikilink]] to Note  │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ SEMANTIC SEARCH (uses embeddings from session)                  │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  • neighbours(note, k) -> List[Note]   Semantically similar     │   ┃
┃  │  • similarity(a, b) -> float           Cosine similarity         │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ GRAPH OPERATIONS (SQL queries → Note objects)                   │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  • backlinks(note) -> List[Note]      Notes linking here        │   ┃
┃  │  • orphans(k) -> List[Note]           Unlinked notes            │   ┃
┃  │  • hubs(k) -> List[Note]              Most-linked notes         │   ┃
┃  │  • unlinked_pairs(k) -> List[Tuple]   Similar but unlinked      │   ┃
┃  │  • links_between(a, b) -> List[Link]  Connections between       │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ TEMPORAL QUERIES (SQL → Note objects)                           │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  • old_notes(k) -> List[Note]         Least recently modified   │   ┃
┃  │  • recent_notes(k) -> List[Note]      Most recently modified    │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ METADATA ACCESS (extensible properties)                         │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  • metadata(note) -> Dict             All inferred properties   │   ┃
┃  │    Returns: {word_count, link_count, complexity, sentiment...}  │   ┃
┃  │    (Built-in + user-defined metadata modules)                   │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ DETERMINISTIC SAMPLING (date-seeded RNG)                        │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  • sample(items, k) -> List           Deterministic sample      │   ┃
┃  │  • random_notes(k) -> List[Note]      Random notes              │   ┃
┃  │    (Same date + vault = same results)                           │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ FUNCTION REGISTRY (for Tracery bridge + extensibility)          │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  • call_function(name, **kwargs)      Dynamic function calls    │   ┃
┃  │  • register_function(name, func)      Add new functions         │   ┃
┃  │    (Converts Note objects ↔ strings for Tracery)                │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────────┐
│ METADATA         │ │ VAULT FUNCTIONS  │ │ FUNCTION REGISTRY    │
│ INFERENCE        │ │                  │ │                      │
├──────────────────┤ ├──────────────────┤ ├──────────────────────┤
│ _geistfabrik/    │ │ _geistfabrik/    │ │ Built-in functions:  │
│  metadata_       │ │  vault_functions/│ │                      │
│  inference/*.py  │ │                  │ │ @vault_function()    │
│                  │ │ @vault_function  │ │  def hubs(vault, k): │
│ def infer(note,  │ │  def func(vault, │ │   # SQL → Notes      │
│    vault) -> Dict│ │    **kwargs):    │ │   return notes       │
│                  │ │   # Note-based   │ │                      │
│ Adds properties  │ │   logic          │ │ Adapts for Tracery:  │
│ to metadata():   │ │   return result  │ │ Notes → ".title"     │
│  • complexity    │ │                  │ │ (string-based I/O)   │
│  • sentiment     │ │ Available as:    │ │                      │
│  • reading_time  │ │ $vault.func()    │ │ $vault.hubs(k=5)     │
│  • custom...     │ │ in Tracery       │ │  .map(title)         │
└──────────────────┘ └──────────────────┘ └──────────────────────┘
         │                 │                         │
         └─────────────────┴─────────────────────────┘
                           │
                           ▼ Delegates to
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                     LAYER 1: Vault                                       ┃
┃                 (Raw Data Access - Read-Only)                            ┃
┃                                                                          ┃
┃  WHAT VAULT DOES: Parses files → Creates Note objects → Syncs SQLite   ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ FILE PARSING                                                     │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  • Parse Markdown (frontmatter, content, links, tags)           │   ┃
┃  │  • Extract [[wikilinks]], ![[embeds]], #tags                    │   ┃
┃  │  • Track file timestamps (created, modified, mtime)             │   ┃
┃  │  • Handle block references (^blockid)                           │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ NOTE OBJECT CREATION                                            │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  @dataclass(frozen=True)                                        │   ┃
┃  │  class Note:                                                    │   ┃
┃  │    path: str          # "path/to/note.md"                       │   ┃
┃  │    title: str         # "Note Title"                            │   ┃
┃  │    content: str       # Full markdown text                      │   ┃
┃  │    links: List[Link]  # [[wikilinks]] found                     │   ┃
┃  │    tags: List[str]    # #tags found                             │   ┃
┃  │    created: datetime  # File creation                           │   ┃
┃  │    modified: datetime # Last edit                               │   ┃
┃  │                                                                  │   ┃
┃  │  ✓ Immutable (frozen dataclass)                                 │   ┃
┃  │  ✓ Lightweight (no computed properties)                         │   ┃
┃  │  ✓ All intelligence lives in VaultContext, not Note            │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ SQLITE SYNCHRONIZATION                                          │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  • sync() - Incremental updates (only changed files)            │   ┃
┃  │  • all_notes() -> List[Note]  (from SQLite)                     │   ┃
┃  │  • get_note(path) -> Note     (from SQLite)                     │   ┃
┃  │  • resolve_link_target(target) -> Note (by path OR title)       │   ┃
┃  │                                                                  │   ┃
┃  │  Database: <vault>/_geistfabrik/vault.db                        │   ┃
┃  │    Tables: notes, links, tags, embeddings, sessions             │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┃  ┌─────────────────────────────────────────────────────────────────┐   ┃
┃  │ EMBEDDINGS (via sentence-transformers)                          │   ┃
┃  ├─────────────────────────────────────────────────────────────────┤   ┃
┃  │  • Model: all-MiniLM-L6-v2 (384 dimensions)                     │   ┃
┃  │  • Temporal features (3 dims): note age, creation season,       │   ┃
┃  │    session season                                               │   ┃
┃  │  • Fresh computation each session (temporal drift tracking)     │   ┃
┃  │  • Stored in SQLite via sqlite-vec extension                    │   ┃
┃  └─────────────────────────────────────────────────────────────────┘   ┃
┃                                                                          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                                 │
                                 ▼ Reads from
┌──────────────────────────────────────────────────────────────────────────┐
│                    OBSIDIAN VAULT (Filesystem)                            │
│                                                                           │
│  • *.md files                      Markdown notes                        │
│  • [[wikilinks]]                   Cross-references                      │
│  • #tags, frontmatter              Metadata                              │
│  • _geistfabrik/                   System directory                      │
│    ├── vault.db                    SQLite database                       │
│    ├── geists/                     User geists                           │
│    │   ├── code/*.py               Python geists                         │
│    │   └── tracery/*.yaml          Tracery geists                        │
│    ├── metadata_inference/*.py     Metadata modules                      │
│    ├── vault_functions/*.py        Custom functions                      │
│    └── config.yaml                 Configuration                         │
│  • geist journal/                  Session output                        │
│    └── YYYY-MM-DD.md               Daily suggestions                     │
└─────────────────────────────────┬─────────────────────────────────────────┘
                                  │
                                  ▼ Writes to
┌──────────────────────────────────────────────────────────────────────────┐
│                         SESSION OUTPUT                                    │
│                                                                           │
│  geist journal/2025-10-21.md                                             │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │ # 2025-10-21 Geist Session                                         │ │
│  │                                                                    │ │
│  │ What if [[Note A]] and [[Note B]] were connected? They're         │ │
│  │ semantically similar but in different parts of your vault.        │ │
│  │ ^g20251021-001                                                    │ │
│  │ *geist: bridge_builder*                                           │ │
│  │                                                                    │ │
│  │ Consider revisiting [[Old Note]] - it hasn't been touched in     │ │
│  │ 6 months but relates to your current work on [[Recent Topic]].   │ │
│  │ ^g20251021-002                                                    │ │
│  │ *geist: temporal_drift*                                           │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  • ~5 suggestions per session (filtered + sampled)                       │
│  • Block IDs: ^gYYYYMMDD-NNN (embeddable in other notes)                │
│  • Geist attribution for transparency                                    │
│  • Linkable like any Obsidian note                                       │
└───────────────────────────────────────────────────────────────────────────┘


════════════════════════════════════════════════════════════════════════════
                           KEY ARCHITECTURAL POINTS
════════════════════════════════════════════════════════════════════════════

DATA FLOW (Bottom-up):
  Files → Vault (parses → Note objects) → VaultContext (Note objects +
  intelligence) → Geists (receive VaultContext) → Suggestions → Session note

LAYERING PRINCIPLE:
  • LAYER 1 (Vault): I/O, parsing, SQLite sync, embedding computation
    → Produces: Note objects (immutable, lightweight)

  • LAYER 2 (VaultContext): Intelligence, utilities, caching
    → Provides: Semantic search, graph ops, metadata, sampling
    → All methods return Note objects (not raw data)

  • GEISTS: Creativity and pattern recognition
    → Receive: VaultContext instance
    → Access: Note objects via vault.notes(), vault.neighbours(), etc.
    → Return: List[Suggestion]

WHAT GEISTS CAN ACCESS:
  ✓ Full Note objects (path, title, content, links, tags, timestamps)
  ✓ All VaultContext methods (semantic search, graph queries, metadata)
  ✓ Direct content reading via note.content or vault.read(note)
  ✗ Direct filesystem I/O (Vault layer handles this)
  ✗ Markdown parsing (Vault layer handles this)
  ✗ Modifying notes (read-only guarantee)

THREE-DIMENSIONAL EXTENSIBILITY:
  1. Metadata Inference  → Adds properties to vault.metadata(note)
  2. Vault Functions     → Adds methods available as $vault.func() in Tracery
  3. Geists              → Adds new suggestion generators

TRACERY ↔ VAULTCONTEXT BRIDGE:
  • FunctionRegistry provides adapter layer
  • Vault functions work with Note objects internally
  • Return strings for Tracery consumption (usually note.title)
  • Example: $vault.hubs(k=5).map(title) → List of note titles

PERSISTENCE:
  • Single SQLite file: <vault>/_geistfabrik/vault.db
  • Incremental sync (only changed files reprocessed)
  • Temporal embeddings (fresh each session for drift tracking)
  • sqlite-vec extension for vector similarity search
```

## Summary

GeistFabrik uses a two-layer architecture:

1. **Vault (Layer 1)**: Raw data access - parses Markdown files, creates immutable Note objects, syncs to SQLite, computes embeddings
2. **VaultContext (Layer 2)**: Rich intelligence layer - provides semantic search, graph operations, metadata access, and sampling utilities

Geists receive a VaultContext instance and work with Note objects to generate creative suggestions. The system maintains strict read-only access to user notes, only writing session outputs to `geist journal/` directory.
