# GeistFabrik spec

## Overview

GeistFabrik (German for "spirit factory") is the system; geists are the generative prompts within it. This Python-based divergence engine for Obsidian vaults generates creative suggestions through both code and Tracery grammars.

## Core Principles

- **Muses, not oracles** – suggestions are provocative, not prescriptive
- **Questions, not answers** – generate "What if...?" not "Here's how"
- **Sample, don't rank** – avoid preferential attachment by random sampling
- **Intermittent invocation** – deliberate user engagement, not continuous background process
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

GeistFabrik uses a **single SQLite database** at `<vault>/_geistfabrik/vault.db` for all persistence needs: notes, links, embeddings, metadata, and execution history.

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
   vault = Vault(vault_path, vault_path / "_geistfabrik/vault.db")
   vault.sync()  # Incremental: only process changed files

2. Geist Execution:
   ctx = VaultContext(vault, seed=today)
   suggestions = []
   for geist in active_geists:
       suggestions.extend(geist.suggest(ctx))  # All queries hit SQLite

3. Output:
   write_journal(suggestions)  # To vault's "geist journal/YYYY-MM-DD.md"
   record_run(date, geist_id, suggestions)  # To geist_runs table
```

#### Benefits

- **Fast startup** - First run computes everything, subsequent runs only process changes
- **Efficient queries** - SQL indexes make graph operations instant
- **Vector search** - sqlite-vec optimized for nearest-neighbor queries
- **Single file** - Entire vault intelligence in `_geistfabrik/vault.db`
- **Portable** - Copy .db file with vault, everything works
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
            # Weight semantic and temporal equally (50/50) until we gather usage data
            semantic_weight = 0.5
            temporal_weight = 0.5

            semantic_scaled = semantic * semantic_weight
            temporal_scaled = np.array(temporal_features) * temporal_weight

            embedding = np.concatenate([semantic_scaled, temporal_scaled])
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

`<vault>/_geistfabrik/metadata_inference/` modules export:

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

`<vault>/_geistfabrik/vault_functions/` modules export decorated functions:

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
1. Add metadata module (metadata_inference/)
   → Computes "novelty" property

2. Add vault function (vault_functions/)
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

Located in `<vault>/_geistfabrik/geists/code/`, exporting:

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """
    Receive rich VaultContext with embeddings, metadata, and utilities.
    Return 0-N suggestions based on vault analysis.
    """
```

**Example**: A geist using the rich context:

```python
# <vault>/_geistfabrik/geists/code/connection_finder.py
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

Located in `<vault>/_geistfabrik/geists/tracery/`, using enhanced Tracery:

```yaml
type: geist-tracery
id: question_challenger
tracery:
  origin: "#prompt# [[#question#]]?"
  prompt: ["What assumes the opposite of", "Who benefits from", "When is the answer to"]
  question: ["$vault.find_questions(1)"]
```

### Journal Management

Each session creates a discrete note at `<vault>/geist journal/YYYY-MM-DD.md`:

```markdown
# GeistFabrik Session – 2025-01-15

## connection_finder ^g20250115-001
[[Project Planning]] × [[Fermentation]] – what if they follow the same cycles?

## columbo ^g20250115-002
I think you're lying about your claim in [[Democracy Note]] that "direct democracy scales"
because your [[Scaling Systems]] note argues that coordination costs grow superlinearly
with group size, and your [[Athens]] note describes how Athenian democracy only worked
with 30,000 citizens. Either democracy doesn't scale, or you've changed your definition
of "scale," or there's a missing piece about how modern technology changes coordination costs.

## session_drift ^g20250115-003
Your understanding of [[emergence]] shifted significantly between last session and this one...
```

**Properties**:
- Each session is linkable: `[[geist journal/2025-01-15]]`
- Block IDs follow format: `^gYYYYMMDD-NNN` (date-based + sequential)
- **Variable-length suggestions** - Each geist determines appropriate length for its suggestion
- Sessions can be revisited, linked, or embedded like any other note

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
<vault>/
├── _geistfabrik/
│   ├── vault.db                 # SQLite database (everything)
│   │                            # - notes, links, tags
│   │                            # - embeddings (sqlite-vec)
│   │                            # - computed metadata
│   │                            # - geist execution history
│   │                            # - block reference tracking
│   ├── config.yaml              # Vault-specific settings
│   ├── geists/
│   │   ├── code/                # Code geists
│   │   │   ├── __init__.py
│   │   │   ├── collider.py
│   │   │   ├── skeptic.py
│   │   │   └── ...
│   │   └── tracery/             # Tracery geists
│   │       ├── connections.yaml
│   │       ├── inversions.yaml
│   │       └── ...
│   ├── metadata_inference/      # Metadata inference modules
│   │   ├── __init__.py
│   │   ├── complexity.py
│   │   ├── sentiment.py
│   │   └── ...
│   └── vault_functions/         # Custom vault functions
│       ├── __init__.py
│       ├── contrarian.py
│       ├── temporal.py
│       └── ...
├── geist journal/               # Output: session notes
│   └── 2025-01-15.md
└── (user's notes)
```

### Configuration

```yaml
# <vault>/_geistfabrik/config.yaml

vault:
  path: "/path/to/obsidian/vault"
  database: "./_geistfabrik/vault.db"

embeddings:
  enabled: true
  model: "sentence-transformers/all-MiniLM-L6-v2"  # Offline model
  dimensions: 384
  temporal_features: true
  semantic_weight: 0.5  # 50/50 split until we gather usage data
  temporal_weight: 0.5

boundaries:
  exclude_paths: ["People/", "Private/", "Archive/"]

session:
  default_suggestions: 5  # For default mode
  novelty_window_days: 60
  diversity_threshold: 0.85

quality:
  min_length: 10       # Minimum suggestion text length
  max_length: 2000     # Maximum suggestion text length
  check_repetition: true

geist_execution:
  timeout: 5           # Seconds before timeout
  max_failures: 3      # Disable geist after N failures
  execution_mode: "serial"  # Only serial supported

filtering:
  # All options available with easy swapping
  strategies: ["boundary", "novelty", "diversity", "quality"]

  # Boundary enforcement
  boundary:
    enabled: true

  # Novelty checking
  novelty:
    enabled: true
    method: "embedding_similarity"  # or "text_match"
    threshold: 0.85

  # Diversity within batch
  diversity:
    enabled: true
    method: "embedding_similarity"
    threshold: 0.85

  # Quality baseline
  quality:
    enabled: true
    checks: ["length", "repetition", "structure"]

tracery:
  max_depth: 10
  enable_vault_functions: true

metadata_inference:
  # Modules loaded in this order
  enabled_modules: ["complexity", "sentiment", "temporal"]
  cache_per_session: true
  verify_on_launch: true

vault_functions:
  enabled_modules: ["contrarian", "questions", "mood"]

logging:
  benchmark: true      # Log execution times
  errors: true
  test_commands: true  # Log test commands for failures
  log_file: "./_geistfabrik/geistfabrik.log"
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

### Complete Execution Flow

```python
def invoke_session(date: datetime, mode: str = "default"):
    """Complete session invocation flow"""

    # 1. Initialize vault and sync filesystem
    vault = Vault(vault_path="~/Documents/MyVault",
                  db_path="~/Documents/MyVault/_geistfabrik/vault.db")

    start_time = time.time()
    vault.sync()  # Incremental: only process changed files
    sync_time = time.time() - start_time
    log_benchmark("vault_sync", sync_time)

    # 2. Create session and compute embeddings
    start_time = time.time()
    session = Session(date, vault)
    session.compute_embeddings()  # Stores in session_embeddings table
    embedding_time = time.time() - start_time
    log_benchmark("compute_embeddings", embedding_time)

    # 3. Create VaultContext with session reference
    ctx = VaultContext(vault, session, seed=date)

    # 4. Load and execute all geists (serially)
    start_time = time.time()
    all_suggestions = []
    geists = load_all_geists()
    executor = GeistExecutor(timeout=5)  # 5 second default timeout

    for geist in geists:
        geist_start = time.time()
        try:
            suggestions = executor.execute_with_timeout(geist, ctx)
            all_suggestions.extend(suggestions)
            geist_time = time.time() - geist_start
            log_benchmark(f"geist_{geist.id}", geist_time)
        except GeistTimeoutError:
            log_error(geist.id, "Timeout after 5 seconds")
            increment_failure_count(geist.id)
        except Exception as e:
            log_error(geist.id, str(e))
            log_test_command(geist.id, date)  # Log command to reproduce
            increment_failure_count(geist.id)

    execution_time = time.time() - start_time
    log_benchmark("geist_execution", execution_time)

    # 5. Filter suggestions
    start_time = time.time()
    filtered = filter_suggestions(all_suggestions, date, vault)
    filter_time = time.time() - start_time
    log_benchmark("filtering", filter_time)

    # 6. Sample based on mode
    final = select_suggestions(filtered, mode, date)

    # 7. Write to journal
    write_session_journal(date, final, mode)

    # 8. Record in database
    record_session(date, geists, all_suggestions, filtered, final)

    total_time = time.time() - session_start_time
    log_benchmark("total_session", total_time)

class GeistExecutor:
    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    def execute_with_timeout(self, geist, ctx):
        """Execute geist with timeout"""
        import signal

        def timeout_handler(signum, frame):
            raise GeistTimeoutError(f"Geist {geist.id} exceeded {self.timeout}s")

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.timeout)

        try:
            suggestions = geist.suggest(ctx)
            signal.alarm(0)  # Cancel alarm
            return suggestions
        except GeistTimeoutError:
            raise
        finally:
            signal.alarm(0)

def increment_failure_count(geist_id: str):
    """Track failures and disable geist after N failures"""
    count = db.execute(
        "SELECT failure_count FROM geist_status WHERE geist_id = ?",
        (geist_id,)
    ).fetchone()

    new_count = (count[0] if count else 0) + 1

    db.execute("""
        INSERT OR REPLACE INTO geist_status (geist_id, failure_count, disabled)
        VALUES (?, ?, ?)
    """, (geist_id, new_count, new_count >= 3))  # Disable after 3 failures

    if new_count >= 3:
        print(f"⚠️  Geist '{geist_id}' disabled after 3 failures")

def log_test_command(geist_id: str, date: datetime):
    """Log command to reproduce session that caused failure"""
    cmd = f"geistfabrik test {geist_id} --date {date.isoformat()}"
    log_file = Path("./_geistfabrik/error.log")
    with log_file.open('a') as f:
        f.write(f"{datetime.now()}: Test command: {cmd}\n")
```

### Geist Testing & Development

```bash
# Test a single geist with arbitrary vault and session
$ geistfabrik test my_geist --vault ~/test-vault --date 2025-01-15

Testing geist: my_geist
Loading vault: ~/test-vault... done (247 notes)
Loading session: 2025-01-15... done
Computing embeddings... done
Running geist...

Generated 3 suggestions:
  1. [my_geist] [[Note A]] × [[Note B]] - what if...
  2. [my_geist] [[Note C]] × [[Note D]] - consider...
  3. [my_geist] [[Note E]] has shifted...

Execution time: 0.23s
Success!

# Test with specific session ID
$ geistfabrik test my_geist --session-id 42

# Test with verbose output
$ geistfabrik test my_geist --verbose

# Test all geists
$ geistfabrik test-all --vault ~/test-vault
```

### Vault State Hash

```python
class Vault:
    def compute_state_hash(self) -> str:
        """
        Compute hash of vault content for determinism checking.
        Only includes note content (including frontmatter), not modification times.
        This ensures vault portability across machines.
        """
        file_hashes = []
        for md_file in self.vault_path.rglob("*.md"):
            if self.should_exclude(md_file):
                continue

            # Hash only content (including frontmatter), not mtime
            with open(md_file, 'rb') as f:
                content = f.read()

            file_hash = hashlib.sha256(content).hexdigest()
            file_hashes.append((str(md_file), file_hash))

        # Sort for deterministic ordering
        file_hashes.sort()

        # Hash the hashes
        combined = ''.join(h for _, h in file_hashes)
        state_hash = hashlib.sha256(combined.encode()).hexdigest()

        return state_hash
```

### Quality Filtering

Quality is determined by user-configurable global defaults. Individual geists can implement their own quality checks and return a sentinel value if results aren't good enough.

```python
def filter_quality(suggestions: List[Suggestion], config: dict) -> List[Suggestion]:
    """Global quality filtering with configurable thresholds"""
    min_length = config.get('min_length', 10)
    max_length = config.get('max_length', 2000)

    quality = []
    recent_texts = set()

    for suggestion in suggestions:
        text = suggestion.text.strip()

        # Length checks
        if len(text) < min_length:
            continue
        if len(text) > max_length:
            continue

        # Repetition check (exact duplicates within batch)
        if text in recent_texts:
            continue
        recent_texts.add(text)

        # Basic validation
        if not suggestion.geist_id:
            continue
        if not suggestion.notes:
            continue

        quality.append(suggestion)

    return quality

# Geists can implement own quality bar
def suggest(vault: VaultContext) -> List[Suggestion]:
    suggestions = generate_suggestions(vault)

    # Geist-specific quality check
    if not meets_my_quality_bar(suggestions):
        return []  # Sentinel: no good suggestions this time

    return suggestions
```

### Metadata Module Management

```python
class MetadataSystem:
    def __init__(self, config: dict):
        self.config = config
        self.modules = {}
        self.load_order = config.get('metadata_inference', {}).get('enabled_modules', [])
        self.verify_and_load()

    def verify_and_load(self):
        """Load modules in config order with conflict detection"""
        provided_keys = {}  # Track which module provides which keys

        for module_name in self.load_order:
            module_path = Path(f"./_geistfabrik/metadata_inference/{module_name}.py")

            if not module_path.exists():
                print(f"⚠️  Module {module_name} not found, skipping")
                continue

            try:
                # Load module
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                if not hasattr(module, 'infer'):
                    print(f"✗ Module {module_name} has no infer() function")
                    continue

                # Test run to detect provided keys
                test_note = Note(...)  # Minimal test note
                test_result = module.infer(test_note, None)

                # Check for conflicts
                for key in test_result.keys():
                    if key in provided_keys:
                        raise ConflictError(
                            f"Key '{key}' provided by both "
                            f"'{provided_keys[key]}' and '{module_name}'"
                        )
                    provided_keys[key] = module_name

                self.modules[module_name] = module.infer
                print(f"✓ Loaded metadata module: {module_name}")

            except ConflictError as e:
                print(f"✗ Conflict detected: {e}")
                sys.exit(1)
            except Exception as e:
                print(f"✗ Failed to load {module_name}: {e}")
                sys.exit(1)

    def infer_all(self, note: Note, vault: VaultContext, session_id: int) -> Dict:
        """Run all modules and cache results for session"""
        # Check cache first
        cached = self.get_cached(note.path, session_id)
        if cached is not None:
            return cached

        # Compute metadata
        metadata = {}
        for module_name in self.load_order:
            if module_name not in self.modules:
                continue
            try:
                result = self.modules[module_name](note, vault)
                metadata.update(result)
            except Exception as e:
                print(f"⚠️  {module_name} failed for {note.path}: {e}")

        # Cache for session
        self.cache_metadata(note.path, session_id, metadata)

        return metadata
```

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
        for module in Path("./_geistfabrik/vault_functions").glob("*.py"):
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

## Appendix: Ambitious Implementable Geists

These geists use only embeddings and graph analysis (no external knowledge required). They represent advanced but achievable patterns within the current architecture.

### Island Hopper

**Concept**: Find notes that could bridge disconnected clusters

```python
def suggest(vault: VaultContext):
    """Find notes that could bridge disconnected graph clusters"""
    clusters = vault.find_clusters(min_size=3, max_size=10)
    suggestions = []

    for cluster in clusters:
        # Find notes semantically near cluster but not in it
        boundary_notes = []
        for note in vault.notes():
            if note in cluster:
                continue

            # Average similarity to cluster members
            similarities = [vault.similarity(note, c) for c in cluster]
            avg_sim = sum(similarities) / len(similarities)

            # Close enough to bridge, not so close it should be in cluster
            if 0.5 < avg_sim < 0.8:
                boundary_notes.append((note, avg_sim))

        if boundary_notes:
            bridge = max(boundary_notes, key=lambda x: x[1])[0]
            cluster_sample = vault.sample(list(cluster), k=2)
            suggestions.append(Suggestion(
                text=f"[[{bridge.title}]] could bridge your cluster of "
                     f"[[{cluster_sample[0].title}]], [[{cluster_sample[1].title}]]...",
                notes=[bridge.title] + [n.title for n in cluster_sample],
                geist_id="island_hopper"
            ))

    return vault.sample(suggestions, k=3)
```

### Hidden Hub

**Concept**: Semantically central notes that aren't well-linked

```python
def suggest(vault: VaultContext):
    """Find notes that are semantically important but under-connected"""
    suggestions = []

    for note in vault.notes():
        # Actual link count
        link_count = len(note.links) + len(vault.get_backlinks(note))

        # Semantic centrality
        neighbors = vault.neighbors(note, k=50)
        semantic_centrality = len(neighbors)

        # High semantic centrality, low graph centrality
        if semantic_centrality > 20 and link_count < 5:
            suggestions.append(Suggestion(
                text=f"[[{note.title}]] is semantically related to {semantic_centrality} "
                     f"notes but only has {link_count} links—hidden hub?",
                notes=[note.title],
                geist_id="hidden_hub"
            ))

    return vault.sample(suggestions, k=3)
```

### Bridge Hunter

**Concept**: Find semantic paths through graph deserts

```python
def suggest(vault: VaultContext):
    """Find semantic paths where no graph path exists"""
    pairs = vault.unlinked_pairs(k=20)
    suggestions = []

    for note_a, note_b in pairs:
        # Find semantic path using embeddings
        path = vault.semantic_path(note_a, note_b, max_hops=5)

        if path and len(path) > 2:
            path_str = " → ".join([f"[[{n.title}]]" for n in path])
            suggestions.append(Suggestion(
                text=f"Semantic bridge from [[{note_a.title}]] to [[{note_b.title}]]: {path_str}",
                notes=[n.title for n in path],
                geist_id="bridge_hunter"
            ))

    return vault.sample(suggestions, k=2)
```

### Density Inversion

**Concept**: Detect mismatches between link structure and semantic structure

```python
def suggest(vault: VaultContext):
    """Find dense links with sparse meaning, or vice versa"""
    suggestions = []

    for note in vault.notes():
        neighbors = vault.get_graph_neighbors(note)
        if len(neighbors) < 3:
            continue

        # Graph density (how interconnected are neighbors?)
        edges = sum(1 for n1 in neighbors for n2 in neighbors
                   if vault.has_link(n1, n2))
        graph_density = edges / (len(neighbors) * (len(neighbors) - 1))

        # Semantic density (how similar are neighbors?)
        similarities = [vault.similarity(n1, n2)
                       for n1 in neighbors for n2 in neighbors if n1 != n2]
        semantic_density = sum(similarities) / len(similarities)

        # Flag inversions
        if graph_density > 0.7 and semantic_density < 0.3:
            suggestions.append(Suggestion(
                text=f"[[{note.title}]]: tightly linked neighbors are semantically "
                     f"scattered—coherent topic?",
                notes=[note.title],
                geist_id="density_inversion"
            ))
        elif graph_density < 0.3 and semantic_density > 0.7:
            suggestions.append(Suggestion(
                text=f"[[{note.title}]]: semantically similar neighbors aren't linked—"
                     f"missing connections?",
                notes=[note.title],
                geist_id="density_inversion"
            ))

    return vault.sample(suggestions, k=2)
```

### Vocabulary Expansion

**Concept**: Track semantic space coverage over time

```python
def suggest(vault: VaultContext):
    """Measure how much semantic territory your notes explore"""
    # Requires temporal embeddings
    recent_sessions = vault.get_recent_sessions(n=5)
    if len(recent_sessions) < 3:
        return []

    coverage_by_session = []
    for session in recent_sessions:
        embeddings = session.get_all_embeddings()

        # Measure dispersion (standard deviation from centroid)
        centroid = np.mean(embeddings, axis=0)
        distances = [np.linalg.norm(e - centroid) for e in embeddings]
        coverage = np.std(distances)

        coverage_by_session.append((session.date, coverage))

    recent = coverage_by_session[-1][1]
    older = coverage_by_session[-3][1]

    if recent < older * 0.8:  # Significant convergence
        return [Suggestion(
            text=f"Your recent notes explore less semantic territory than before—"
                 f"converging on specific topics?",
            notes=[],
            geist_id="vocabulary_expansion"
        )]
    elif recent > older * 1.2:  # Significant divergence
        return [Suggestion(
            text=f"Your recent notes cover more semantic ground than before—"
                 f"branching into new areas?",
            notes=[],
            geist_id="vocabulary_expansion"
        )]

    return []
```

## Future Features

### Session Embedding Pruning

As sessions accumulate, storage of embeddings grows. A pruning strategy will selectively keep embeddings to manage storage:

**Pruning Policy**:
- Always keep first session (baseline)
- Keep last N sessions (e.g., 20) for recent history
- Keep one session per month for historical snapshots
- Keep sessions where average embedding shift exceeds threshold (significant changes)

**Storage Impact**:
- Without pruning: 1.5MB per session × unlimited sessions
- With pruning: ~30MB for typical usage (keeping ~20 sessions worth of embeddings)

**Implementation**: `geistfabrik prune` command to manually trigger, or automatic pruning when threshold exceeded.

### Incremental Vault State Hashing

Current implementation rehashes entire vault content on each invocation to detect changes. For large vaults (10K+ notes), this can be slow.

**Optimization**: Only rehash files that have changed since last invocation by tracking file modification times and maintaining a hash cache.

**Benefit**: Reduces sync time from O(n) to O(changed files), particularly important for large vaults with infrequent changes.

**Trade-off**: Adds complexity and cache management. Defer until performance data shows need.

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
