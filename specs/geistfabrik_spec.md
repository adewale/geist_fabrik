# GeistFabrik spec

## Overview

GeistFabrik (German for "spirit factory") is the system; geists are the generative prompts within it. This Python-based divergence engine for Obsidian vaults generates creative suggestions through both code and Tracery grammars.

## Core Principles

- **Muses, not oracles** – suggestions are provocative, not prescriptive
- **Questions, not answers** – generate "What if...?" not "Here's how"
- **Sample, don't rank** – avoid preferential attachment by random sampling
- **Ritual, not routine** – deliberate engagement like tarot, not automatic consumption like feeds
- **Local-first** – no network required; embeddings computed locally
- **Deterministic randomness** – same date + vault = same output
- **Never destructive** – read-only access to user notes
- **Extensible at every layer** – metadata, functions, and geists

## Architecture

### Data Structures

#### Note

```python
@dataclass
class Note:
    """Immutable representation of a vault note"""
    path: str           # Relative path in vault
    title: str          # Note title
    content: str        # Full markdown content
    links: List[Link]   # Outgoing [[links]]
    tags: List[str]     # #tags found in note
    created: datetime   # File creation time
    modified: datetime  # Last modification time
```

Notes are lightweight, immutable data structures. All derived intelligence (metadata, graph metrics, semantic properties) lives in VaultContext, not in Note objects.

#### Suggestion

```python
@dataclass
class Suggestion:
    """A geist-generated provocation"""
    text: str           # 1-2 sentence suggestion
    notes: List[str]    # Referenced note titles  
    geist_id: str       # Identifier of creating geist
    title: str = None   # Optional suggested note title
```

### Two-Layer Vault Understanding

#### Layer 1: Vault (Raw Data)

The `Vault` class provides raw, read-only access to Obsidian vault data and manages SQLite synchronization:

```python
class Vault:
    """Raw vault data access and SQLite sync"""
    def __init__(self, vault_path: Path, db_path: Path):
        self.vault_path = vault_path
        self.db = sqlite3.connect(db_path)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def sync(self):
        """Incrementally update database with changed files"""
        # Parse changed markdown files
        # Update notes, links, tags tables
        # Compute embeddings for new/modified notes
        # Invalidate stale metadata
    
    def all_notes(self) -> List[Note]:
        """Load all notes from database"""
    
    def get_note(self, path: str) -> Note:
        """Retrieve specific note"""
```

**Responsibilities**:
- Parse Markdown files and extract structure
- Handle date-collection notes (split into atomic entries)
- Resolve block references (`^blockid`)
- Track transclusions (`![[note]]`) without executing them
- Sync filesystem changes to SQLite incrementally
- Compute embeddings using sentence-transformers

#### Layer 2: VaultContext (Rich Execution Context)

The `VaultContext` class wraps the raw vault with intelligence and utilities. This is what **geists actually receive** - a rich context providing deep understanding of the vault:

```python
class VaultContext:
    """Rich execution context for geists"""
    def __init__(self, vault: Vault, seed: int):
        self.vault = vault
        self.db = vault.db
        self.rng = Random(seed)  # Deterministic randomness
    
    # Direct vault access (delegated)
    def notes(self) -> List[Note]:
        return self.vault.all_notes()
    
    def get_note(self, path: str) -> Note:
        return self.vault.get_note(path)
    
    def read(self, note: Note) -> str:
        return note.content
    
    # Semantic search (sqlite-vec)
    def neighbors(self, note: Note, k: int) -> List[Note]:
        """Find k semantically similar notes"""
    
    def similarity(self, a: Note, b: Note) -> float:
        """Calculate semantic similarity between notes"""
    
    # Graph operations (SQL)
    def unlinked_pairs(self, k: int) -> List[Tuple[Note, Note]]:
        """Find note pairs with no links between them"""
    
    def orphans(self, k: int) -> List[Note]:
        """Find notes with no links"""
    
    def hubs(self, k: int) -> List[Note]:
        """Find most-linked-to notes"""
    
    def links_between(self, a: Note, b: Note) -> List[Link]:
        """Find all links between two notes"""
    
    # Temporal queries
    def old_notes(self, k: int) -> List[Note]:
        """Find least recently modified notes"""
    
    def recent_notes(self, k: int) -> List[Note]:
        """Find most recently modified notes"""
    
    # Metadata access (user-extensible)
    def metadata(self, note: Note) -> Dict:
        """Retrieve all inferred metadata for a note"""
    
    # Deterministic sampling
    def sample(self, items: List, k: int) -> List:
        """Deterministically sample k items"""
    
    def random_notes(self, k: int) -> List[Note]:
        """Sample k random notes"""
    
    # Dynamic function calls
    def call_function(self, name: str, **kwargs) -> Any:
        """Call registered vault function"""
```

**What Makes VaultContext "Rich"**:
- **Pre-computed embeddings** for semantic operations
- **Metadata inference system** - extensible properties beyond raw files
- **Function registry** - core + user functions available uniformly
- **Deterministic randomness** - same seed = same results
- **Convenient utilities** - sampling, clustering, graph queries
- **Caching layer** - consistent results within a run

**Design Philosophy**: Geists shouldn't worry about the mechanics of vault parsing, embedding computation, or metadata inference. VaultContext provides a **ready-to-use intelligence layer** so geists can focus purely on creative pattern recognition and suggestion generation. The context does the heavy lifting; geists do the thinking.

### Persistence Layer (SQLite + sqlite-vec)

GeistFabrik uses a **single SQLite database** at `~/.geistfabrik/vault.db` for all persistence needs: notes, links, embeddings, metadata, and execution history.

#### Why SQLite?

- **Single file** - entire vault state in one portable database
- **Fast queries** - indexed graph operations, metadata filtering
- **Vector search** - sqlite-vec extension for semantic similarity
- **Incremental updates** - only reprocess changed files
- **Offline** - no network dependencies
- **Portable** - works identically across platforms

#### Database Schema

```sql
-- Core note data
CREATE TABLE notes (
    path TEXT PRIMARY KEY,
    title TEXT,
    content TEXT,
    created TIMESTAMP,
    modified TIMESTAMP,
    word_count INTEGER,
    hash TEXT  -- For change detection
);

-- Graph structure
CREATE TABLE links (
    source_path TEXT,
    target_path TEXT,
    link_type TEXT,  -- 'link', 'embed', 'block-ref'
    FOREIGN KEY (source_path) REFERENCES notes(path),
    FOREIGN KEY (target_path) REFERENCES notes(path)
);
CREATE INDEX idx_links_source ON links(source_path);
CREATE INDEX idx_links_target ON links(target_path);

-- Vector embeddings (sqlite-vec extension)
CREATE VIRTUAL TABLE note_embeddings USING vec0(
    path TEXT PRIMARY KEY,
    title_embedding FLOAT[384],
    content_embedding FLOAT[384]
);

-- Computed metadata (flexible JSON storage)
CREATE TABLE metadata (
    note_path TEXT,
    key TEXT,
    value TEXT,  -- JSON encoded
    computed_at TIMESTAMP,
    FOREIGN KEY (note_path) REFERENCES notes(path),
    PRIMARY KEY (note_path, key)
);
CREATE INDEX idx_metadata_key ON metadata(key);

-- Geist execution history
CREATE TABLE geist_runs (
    date DATE,
    geist_id TEXT,
    suggestions TEXT,  -- JSON array of suggestions
    PRIMARY KEY (date, geist_id)
);

-- Block reference tracking
CREATE TABLE block_refs (
    block_id TEXT PRIMARY KEY,
    note_path TEXT,
    created_date DATE,
    FOREIGN KEY (note_path) REFERENCES notes(path)
);

-- Tags (denormalized for query performance)
CREATE TABLE tags (
    note_path TEXT,
    tag TEXT,
    FOREIGN KEY (note_path) REFERENCES notes(path),
    PRIMARY KEY (note_path, tag)
);
CREATE INDEX idx_tags_tag ON tags(tag);
```

#### Sync Process

The Vault class syncs filesystem changes to the database incrementally:

```python
class Vault:
    def sync(self):
        """Incrementally update database with changed files"""
        for md_file in self.vault_path.rglob("*.md"):
            file_hash = self.hash_file(md_file)
            
            # Check if file changed since last sync
            cached = self.db.execute(
                "SELECT hash FROM notes WHERE path = ?", 
                (str(md_file),)
            ).fetchone()
            
            if cached and cached[0] == file_hash:
                continue  # No change, skip
            
            # Parse and update
            note = self.parse_markdown(md_file)
            self.upsert_note(note, file_hash)
            self.update_embeddings(note)
            self.invalidate_metadata(note.path)
        
        self.db.commit()
    
    def update_embeddings(self, note: Note):
        """Compute and store embeddings using sentence-transformers"""
        title_emb = self.embedding_model.encode(note.title)
        content_emb = self.embedding_model.encode(
            note.content[:1000]  # Truncate long content
        )
        
        self.db.execute("""
            INSERT OR REPLACE INTO note_embeddings 
            (path, title_embedding, content_embedding)
            VALUES (?, ?, ?)
        """, (note.path, title_emb.tolist(), content_emb.tolist()))
```

#### VaultContext Queries SQLite

All VaultContext operations query the database:

```python
def neighbors(self, note: Note, k: int) -> List[Note]:
    """Semantic search using sqlite-vec"""
    embedding = self.db.execute(
        "SELECT content_embedding FROM note_embeddings WHERE path = ?",
        (note.path,)
    ).fetchone()[0]
    
    paths = self.db.execute("""
        SELECT path 
        FROM note_embeddings 
        WHERE content_embedding MATCH ?
          AND path != ?
        ORDER BY distance 
        LIMIT ?
    """, (embedding, note.path, k)).fetchall()
    
    return [self.get_note(p[0]) for p in paths]

def unlinked_pairs(self, k: int) -> List[Tuple[Note, Note]]:
    """Find note pairs with no link between them"""
    pairs = self.db.execute("""
        SELECT a.path, b.path
        FROM notes a, notes b
        WHERE a.path < b.path
          AND NOT EXISTS (
            SELECT 1 FROM links 
            WHERE (source_path = a.path AND target_path = b.path)
               OR (source_path = b.path AND target_path = a.path)
          )
        ORDER BY RANDOM()
        LIMIT ?
    """, (k,)).fetchall()
    
    return [(self.get_note(a), self.get_note(b)) for a, b in pairs]
```

#### Execution Flow

```
1. Startup:
   vault = Vault(vault_path, "~/.geistfabrik/vault.db")
   vault.sync()  # Incremental: only process changed files
   
2. Geist Execution:
   ctx = VaultContext(vault, seed=today)
   suggestions = []
   for geist in active_geists:
       suggestions.extend(geist.suggest(ctx))  # All queries hit SQLite
   
3. Output:
   write_journal(suggestions)  # To vault's "Geist Journal.md"
   record_run(date, geist_id, suggestions)  # To geist_runs table
```

#### Benefits

- **Fast startup** - First run computes everything, subsequent runs only process changes
- **Efficient queries** - SQL indexes make graph operations instant
- **Vector search** - sqlite-vec optimized for nearest-neighbor queries
- **Single file** - Entire vault intelligence in `~/.geistfabrik/vault.db`
- **Portable** - Copy .db file, everything works
- **Deterministic** - Same vault state = same query results
- **No external services** - Embeddings computed locally via sentence-transformers

### Temporal Embeddings

GeistFabrik computes a fresh set of embeddings for all notes **at each session invocation**. This enables tracking how your understanding of notes evolves over time, even when note content doesn't change.

#### Architecture

```python
class Session:
    def __init__(self, date: datetime, vault: Vault):
        self.date = date
        self.session_id = self.generate_session_id(date)
        self.embeddings = self.compute_session_embeddings(vault)
        
    def compute_session_embeddings(self, vault: Vault):
        """Compute time-aware embeddings for all notes"""
        for note in vault.notes():
            # Semantic embedding (384 dims)
            semantic = self.embed_model.encode(note.content)
            
            # Temporal features (3 dims)
            age_at_session = (self.date - note.created).days
            temporal_features = [
                age_at_session / 1000,        # Note age
                get_season(note.created) / 4,  # Season written
                get_season(self.date) / 4,     # Season of session
            ]
            
            # Combined embedding (387 dims)
            embedding = np.concatenate([semantic, temporal_features])
            self.store_embedding(note.path, embedding, self.session_id)
```

#### Storage Schema

```sql
CREATE TABLE sessions (
    session_id INTEGER PRIMARY KEY,
    session_date TIMESTAMP,
    vault_state_hash TEXT
);

CREATE TABLE session_embeddings (
    session_id INTEGER,
    note_path TEXT,
    embedding FLOAT[387],  -- 384 semantic + 3 temporal
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (note_path) REFERENCES notes(path),
    PRIMARY KEY (session_id, note_path)
);

CREATE INDEX idx_session_embeddings_path ON session_embeddings(note_path);
```

#### What This Enables

Temporal embeddings unlock two powerful dimensions:

**Versioned Embeddings** - Compare how the same note embeds across sessions
- Track interpretive shifts even when content is unchanged
- Your understanding evolves; temporal embeddings capture this

**Time-Aware Embeddings** - Temporal context becomes part of semantic meaning
- Notes naturally cluster by era
- Seasonal and temporal patterns emerge automatically

#### Geists Unlocked by Temporal Embeddings

**Session Drift** - Understanding evolution
- Compares embeddings of same notes across sessions
- "Your understanding of [[emergence]] shifted significantly between last session and this one"
- Detects semantic drift even for unchanged notes

**Hermeneutic Instability** - Unstable interpretation
- Identifies notes that re-embed differently each session despite no content changes
- "[[This note]] has been interpreted differently in each of your last 5 sessions—meaning unsettled?"
- High embedding variance = actively evolving understanding

**Temporal Clustering** - Automatic periods
- Notes naturally cluster by era due to temporal features
- "Your Q2-2023 notes form a distinct semantic cluster separate from Q4-2023"
- Discovers intellectual "seasons" without manual tagging

**Anachronism Detector** - Temporal outliers
- Finds notes that feel out of their time
- "This recent note semantically resembles your 2022 thinking, not your 2025 thinking"
- Suggests revisiting old ideas or circling back

**Seasonal Patterns** - Rhythmic thinking
- Temporal features reveal seasonal writing patterns
- "You consistently write about [[mortality]] in December sessions"
- Annual, seasonal, or weekly rhythms emerge

**Concept Drift** - How concepts evolve
- Tracks embedding trajectory of notes about the same concept across sessions
- "Your [[emergence]] notes migrated from [[mechanism]] cluster to [[relationality]] cluster"
- Maps intellectual journeys over time

**Convergent Evolution** - Parallel development
- Identifies notes developing toward each other across sessions
- "[[Note A]] and [[Note B]] have been converging semantically for 6 months—time to link?"
- Suggests connections at the moment of convergence

**Divergent Evolution** - Growing apart
- Finds linked notes whose embeddings diverge over sessions
- "These linked notes were similar when connected but have semantically diverged"
- Questions whether old connections still hold

#### Storage & Performance

**Storage cost:**
- ~387 floats × 4 bytes = ~1.5KB per note per session
- 1000 notes × 20 sessions = ~30MB
- Manageable with periodic pruning (keep first, last N, significant changes)

**Computation cost:**
- Full vault re-embedding each session
- 1000 notes × 0.1s = ~100s per session
- Acceptable for ritual invocation pattern

**Querying:**
```python
# Compare note across sessions
def get_embedding_history(note_path: str):
    return db.execute("""
        SELECT session_id, embedding 
        FROM session_embeddings 
        WHERE note_path = ?
        ORDER BY session_id
    """, (note_path,))

# Find notes with high interpretive velocity
def interpretive_velocity(threshold: float):
    return db.execute("""
        SELECT note_path, VARIANCE(embedding) as velocity
        FROM session_embeddings
        GROUP BY note_path
        HAVING velocity > ?
    """, (threshold,))
```

### Extensibility Architecture

GeistFabrik is extensible at three dimensions, each building on the last:

**Architectural Principle**: As the system evolves, new explicit and inferred metadata expands through the **VaultContext** layer, not the Note class. Notes remain lightweight, immutable data structures representing vault files. The intelligence—metadata inference, semantic analysis, graph metrics—lives in VaultContext where it can be contextual, computed lazily, and extended without changing the core data model.

**Why This Matters**:
- Metadata is contextual (depends on vault state, embeddings, other notes)
- Multiple contexts can analyze the same notes differently
- Notes stay simple: `Note(title, path, content, links, created, modified)`
- Intelligence accumulates in VaultContext: `vault.metadata(note)` runs all inference modules
- Future metadata expansions don't require Note schema changes

#### Dimension 1: Metadata Inference

`~/.geistfabrik/Metadata/` modules export:

```python
def infer(note: Note, vault: VaultContext) -> Dict:
    """Infer additional metadata about a note"""
    return {
        "reading_time": len(note.content.split()) / 200,
        "complexity": calculate_complexity(note),
        "mood": sentiment_analysis(note.content),
        "is_question": note.title.endswith("?"),
        "has_tasks": "- [ ]" in note.content,
        "link_density": len(note.links) / max(1, len(note.content.split()))
    }
```

**Example: Data vs. Intelligence Separation**

```python
# Note: Pure data structure (what IS in the vault)
note = Note(
    title="Machine Learning Ethics",
    path="Notes/ML-Ethics.md",
    content="...",
    links=[Link("AI Safety"), Link("Bias")],
    created=datetime(2024, 3, 15),
    modified=datetime(2024, 8, 20)
)

# VaultContext: Intelligence layer (what we INFER)
vault = VaultContext(...)
meta = vault.metadata(note)
# Returns: {
#   "reading_time": 4.5,
#   "complexity": 0.73,
#   "mood": "analytical",
#   "staleness": 0.65,
#   "in_degree": 12,  # Requires full vault graph
#   "semantic_cluster": 7  # Requires embeddings
# }
```

As GeistFabrik evolves, new metadata types (graph centrality, semantic novelty, temporal patterns) are added as inference modules, not as Note properties.

#### Dimension 2: Vault Functions

`~/.geistfabrik/Functions/` modules export decorated functions:

```python
from geistfabrik import vault_function

@vault_function("find_questions")
def find_question_notes(vault: VaultContext, k=5):
    """Find notes that are phrased as questions"""
    questions = [n for n in vault.notes() 
                 if vault.metadata(n).get("is_question", False)]
    return vault.sample(questions, k)

@vault_function("contrarian_to")
def find_contrarian(vault: VaultContext, note_title: str, k=3):
    """Find notes that might disagree with given note"""
    note = vault.get_note(note_title)
    all_notes = vault.notes()
    similarities = [(n, vault.similarity(note, n)) for n in all_notes]
    contrarian = sorted(similarities, key=lambda x: x[1])[:k]
    return [n for n, _ in contrarian]

@vault_function("notes_by_mood")
def notes_by_mood(vault: VaultContext, mood: str, k=10):
    """Find notes matching a mood"""
    matching = [n for n in vault.notes() 
                if vault.metadata(n).get("mood") == mood]
    return vault.sample(matching, k)
```

**Critical Architectural Role**: Vault functions are the **bridge between metadata and Tracery**. 

- **Code geists**: Can directly access `vault.metadata(note)` for any property
- **Tracery geists**: Can only call vault functions with simple string arguments

This means **every metadata dimension requires a corresponding function** to be Tracery-accessible:

```python
# Metadata exists but Tracery can't access it...
vault.metadata(note) → {"complexity": 0.85, "staleness": 0.92}

# ...until we create vault functions:
@vault_function("by_complexity")
def by_complexity(vault: VaultContext, level: str, k=10):
    matching = []
    for note in vault.notes():
        meta = vault.metadata(note)
        complexity = meta.get("complexity", 0.5)
        if level == "high" and complexity > 0.7:
            matching.append(note)
        elif level == "low" and complexity < 0.3:
            matching.append(note)
    return vault.sample(matching, k)
```

**Extensibility Flow**:

```
1. Add metadata module (Metadata/)
   → Computes "novelty" property

2. Add vault function (Functions/)
   → @vault_function("novel_notes")
   → Filters by novelty threshold

3. Automatically available in Tracery
   → $vault.novel_notes(0.9, 3)
```

#### Dimension 3: Tracery Function Bridge

All registered vault functions automatically available in Tracery:

```yaml
type: geist-tracery
id: mood_connector
tracery:
  origin: "[[#happy#]] and [[#sad#]] might be about #theme#"
  happy: ["$vault.notes_by_mood('positive', 1)"]
  sad: ["$vault.notes_by_mood('negative', 1)"]
  theme: ["the same journey", "necessary opposites", "false dichotomies"]
```

### Geist Types

#### Code Geists

Located in `~/.geistfabrik/Extensions/`, exporting:

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """
    Receive rich VaultContext with embeddings, metadata, and utilities.
    Return 0-N suggestions based on vault analysis.
    """
```

**Example**: A geist using the rich context:

```python
# ~/.geistfabrik/Extensions/connection_finder.py
def suggest(vault: VaultContext):
    """Use semantic search and sampling utilities"""
    pairs = vault.unlinked_pairs(k=10)  # Graph operation
    suggestions = []
    
    for note_a, note_b in pairs:
        # Check if they're semantically similar despite no link
        similarity = vault.similarity(note_a, note_b)
        
        if similarity > 0.7:  # Embeddings comparison
            suggestions.append(Suggestion(
                text=f"[[{note_a.title}]] × [[{note_b.title}]] – surprisingly similar ({similarity:.2f})",
                notes=[note_a.title, note_b.title],
                geist_id="connection_finder"
            ))
    
    return vault.sample(suggestions, k=2)  # Deterministic sampling
```

#### Tracery Geists

Located in `~/.geistfabrik/Prompts/`, using enhanced Tracery:

```yaml
type: geist-tracery
id: question_challenger
tracery:
  origin: "#prompt# [[#question#]]?"
  prompt: ["What assumes the opposite of", "Who benefits from", "When is the answer to"]
  question: ["$vault.find_questions(1)"]
```

### Journal Management

**Format undecided** - two options under consideration:

#### Option 1: Single File, Reverse Chronological

The Geist Journal at `<vault>/Geist Journal.md` is a single file with newest entries first:

```markdown
# 2025-01-16

## connection_finder ^g004
[[Machine Learning]] × [[Bread Baking]] – what if they follow the same patience?

## columbo ^g005  
I think you're lying about your claim in [[Democracy Note]] that "direct democracy scales" 
because your [[Scaling Systems]] note argues that coordination costs grow superlinearly...

---

# 2025-01-15

## connection_finder ^g001
[[Project Planning]] × [[Fermentation]] – what if they follow the same cycles?
```

#### Option 2: Folder of Session Notes

Each session creates a discrete note at `<vault>/GeistFabrik Sessions/YYYY-MM-DD.md`:

```markdown
# GeistFabrik Session – 2025-01-15

## connection_finder ^g001
[[Project Planning]] × [[Fermentation]] – what if they follow the same cycles?

## columbo ^g002
I think you're lying about your claim in [[Democracy Note]]...
```

Advantages: Each session is linkable (`[[GeistFabrik Sessions/2025-01-15]]`), easier to revisit specific sessions.

#### Common Properties

Both formats include:
- Date heading
- Geist identifier as subheading
- Stable block IDs for deep-linking
- **Variable-length suggestions** - Each geist determines appropriate length for its suggestion

**Duplicate Prevention**: System queries `geist_runs` table to check if suggestions for a given date have already been generated.

### Execution Pipeline

1. **Execute All Geists**: Every geist runs each session, generating suggestions tagged with `geist_id`
2. **Filter**:
   - Boundary enforcement (exclude_paths)
   - Novelty check (avoid recent suggestions via `geist_runs` table)
   - Diversity filter (remove near-duplicate suggestions using embedding similarity)
   - Quality baseline (well-formed suggestions)
3. **Sample or Select** (based on invocation mode):
   - Default: Random sample of ~5 suggestions
   - Geist mode: All suggestions from specified geist(s)
   - Full mode: All filtered suggestions
4. **Output**: Write to journal with geist identifiers

### Invocation Modes

GeistFabrik supports multiple invocation modes, all deterministic (same inputs = same output):

```bash
# Default mode: filtered + sampled (~5 suggestions)
$ geistfabrik invoke

# Single geist: all suggestions from one geist (post-filter)
$ geistfabrik invoke --geist columbo

# Subset: all suggestions from specific geists (post-filter)
$ geistfabrik invoke --geists columbo,drift,skeptic

# Full firehose: all filtered suggestions, no sampling (50-200+)
$ geistfabrik invoke --full

# Replay: regenerate a specific session
$ geistfabrik invoke --date 2025-01-15
```

**Determinism**: Same vault state + date + mode produces identical output. Vault state hash stored with each session to detect when regeneration is needed.

### File Structure

```
~/.geistfabrik/
├── vault.db                 # SQLite database (everything)
│                            # - notes, links, tags
│                            # - embeddings (sqlite-vec)
│                            # - computed metadata
│                            # - geist execution history
│                            # - block reference tracking
├── Extensions/              # Code geists
│   ├── __init__.py
│   ├── collider.py
│   ├── skeptic.py
│   └── ...
├── Prompts/                # Tracery geists
│   ├── connections.yaml
│   ├── inversions.yaml
│   └── ...
├── Metadata/              # Metadata inference modules
│   ├── __init__.py
│   ├── complexity.py
│   ├── sentiment.py
│   └── ...
└── Functions/             # Custom vault functions
    ├── __init__.py
    ├── contrarian.py
    ├── temporal.py
    └── ...

<vault>/
└── Geist Journal.md        # Output: reverse-chronological suggestions
```

### Configuration

```yaml
# ~/.geistfabrik/config.yaml

vault:
  path: "/path/to/obsidian/vault"
  database: "~/.geistfabrik/vault.db"

embeddings:
  enabled: true
  model: "sentence-transformers/all-MiniLM-L6-v2"  # Offline model
  dimensions: 384
  temporal_features: true  # Add temporal context to embeddings
  
boundaries:
  exclude_paths: ["People/", "Private/", "Archive/"]
  
session:
  default_suggestions: 5  # For default mode
  novelty_window_days: 60
  diversity_threshold: 0.85
  
tracery:
  max_depth: 10
  enable_vault_functions: true
  
metadata:
  enabled_modules: ["complexity", "sentiment", "temporal"]
  
functions:
  enabled_modules: ["contrarian", "questions", "mood"]

sync:
  on_startup: true  # Always sync before running geists
```

## Built-in Components

### Core Vault Functions

```python
# Always available in Tracery
$vault.sample_notes(k)           # Random k notes
$vault.unlinked_pairs(k)         # k unlinked note pairs
$vault.neighbors(title, k)       # k similar notes
$vault.old_notes(k)              # k least recently touched
$vault.tagged(tag, k)            # k notes with tag
$vault.recent_notes(k)           # k most recently modified
$vault.orphans(k)                # k notes with no links
$vault.hubs(k)                   # k most linked-to notes
```

### Example Extended Functions

```python
# User-added functions
$vault.find_questions(k)         # Notes phrased as questions
$vault.contrarian_to(title, k)   # Potentially opposing notes
$vault.notes_by_mood(mood, k)    # Sentiment-filtered notes
$vault.by_complexity(level, k)   # Complexity-filtered notes
```

### Example Metadata Inference

```python
# complexity.py
def infer(note: Note, vault: VaultContext) -> Dict:
    return {
        "flesch_kincaid": calculate_fk_score(note.content),
        "unique_concepts": len(set(note.links)),
        "depth": estimate_conceptual_depth(note, vault)
    }

# temporal.py  
def infer(note: Note, vault: VaultContext) -> Dict:
    return {
        "day_of_week": note.created.strftime("%A"),
        "season": get_season(note.created),
        "age_days": (datetime.now() - note.created).days,
        "staleness": calculate_staleness(note, vault)
    }
```

## Initial Geist Set

GeistFabrik ships with ~20 geists covering:

**Basic Patterns:**
- **Concept collision** - Unlinked pairs with semantic similarity
- **Assumption challenging** - Notes that make implicit assumptions
- **Pattern finding** - Repeated themes across unconnected notes
- **Question expansion** - Notes phrased as questions paired with potential answers
- **Orphan resurrection** - Isolated notes that might connect to recent work
- **Hub diversification** - Highly-linked notes paired with their opposites

**Temporal Patterns** (require temporal embeddings):
- **Session Drift** - Understanding evolution between sessions
- **Hermeneutic Instability** - Notes with unstable interpretation
- **Temporal Clustering** - Automatic intellectual periods
- **Anachronism Detector** - Notes that feel temporally displaced
- **Seasonal Patterns** - Rhythmic thinking patterns
- **Concept Drift** - How concepts evolve over time
- **Convergent Evolution** - Notes developing toward each other
- **Divergent Evolution** - Linked notes growing semantically apart

**Advanced Patterns:**
- **Antithesis generation** - Contrarian viewpoints to existing notes
- **Scale shifting** - Same concept at different levels of abstraction
- **Method scrambling** - SCAMPER technique applied to note connections

**Aspirational:**
- **Columbo** - Detects contradictions: "I think you're lying about $CLAIM because $EVIDENCE"

Each comes in both code and Tracery versions where appropriate.

## Implementation Notes

### Function Registration

```python
# Automatic discovery and registration
class FunctionRegistry:
    def __init__(self):
        self.functions = {}
        self.load_builtin_functions()
        self.discover_user_functions()
    
    def discover_user_functions(self):
        """Load all @vault_function decorated functions"""
        for module in Path("~/.geistfabrik/Functions").glob("*.py"):
            mod = import_module(module)
            for name, func in inspect.getmembers(mod):
                if hasattr(func, '_vault_function'):
                    self.register(func._vault_function_name, func)
    
    def make_tracery_context(self, vault: VaultContext):
        """Create $vault.* namespace for Tracery"""
        return {f"vault.{name}": partial(func, vault)
                for name, func in self.functions.items()}
```

### Example Extended Tracery Geist

```yaml
type: geist-tracery
id: temporal_mirror
tracery:
  origin: "#timeframe# you wrote [[#old_note#]]. Today's [[#new_note#]] #relationship#"
  timeframe: ["#months# months ago", "#years# years ago"]
  months: ["3", "6", "9", "12"]
  years: ["1", "2", "5"]
  old_note: ["$vault.old_notes(1)"]
  new_note: ["$vault.recent_notes(1)"]
  relationship:
    - "might be the answer you were looking for"
    - "contradicts everything you believed then"
    - "shows how far you've traveled"
    - "suggests you're walking in circles"
```

## Success Metrics

### Technical Performance
- Handles 100+ geists via rotation
- Fast startup via incremental SQLite sync (only process changed files)
- Sub-second queries for graph operations and semantic search
- 5-minute effort to add new capabilities at any layer
- Single journal file grows chronologically without duplicates
- Complete vault intelligence in single portable database file

### Qualitative Experience
GeistFabrik succeeds when it generates:
- **Surprise** - "I never would have thought to connect these"
- **Delight** - Reading the journal feels like opening a gift
- **Serendipity** - The right suggestion at the unexpected moment
- **Divergence** - Suggestions pull thinking in new directions, not toward conclusions
- **Novelty** - Fresh perspectives on familiar notes
- **Questions** - "What if...?" not "Here's the answer"
- **Play** - Engaging with suggestions feels exploratory, not obligatory

The system asks different questions than you would ask yourself.

### Failure Modes
- Suggestions become predictable or repetitive
- User feels obligated to act on every suggestion
- Setup/configuration becomes burdensome
- System requires constant tuning to stay useful
- Suggestions feel random rather than provocative
- Journal becomes a checklist instead of a source of wonder