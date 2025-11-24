# GeistFabrik Architecture Analysis

**Date**: 2025-11-24
**Version**: 0.9.0 (Beta)

---

## Executive Summary

GeistFabrik employs a **clean layered architecture** with excellent separation of concerns. The two-layer design (Vault + VaultContext) enables easy testing, extensibility, and maintainability. The codebase demonstrates mature architectural patterns including Strategy, Adapter, Registry, and Pipeline patterns.

**Architecture Grade: A**

---

## 1. Module Dependency Graph

### Core Module Structure

```
┌────────────────────────────────────────────────────────────────────┐
│                         CLI (cli.py)                                │
│                    Entry point / Orchestrator                       │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────────┐
│ GeistExecutor │    │ Filtering     │    │ JournalWriter     │
│               │    │               │    │                   │
│ Loads/runs    │    │ 4-stage       │    │ Writes session    │
│ geists        │    │ pipeline      │    │ notes             │
└───────┬───────┘    └───────┬───────┘    └───────────────────┘
        │                    │
        │                    │
        ▼                    ▼
┌────────────────────────────────────────────────────────────────────┐
│                    VaultContext (Layer 2)                           │
│                                                                     │
│  Rich API: semantic search, graph ops, metadata, sampling          │
│  Works with Note objects exclusively                                │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────────┐
│ Session       │    │ FunctionReg   │    │ MetadataSystem    │
│ (embeddings)  │    │ (vault funcs) │    │ (inference)       │
└───────┬───────┘    └───────────────┘    └───────────────────┘
        │
        ▼
┌────────────────────────────────────────────────────────────────────┐
│                       Vault (Layer 1)                               │
│                                                                     │
│  Raw data: file parsing, SQLite sync, Note object creation         │
│  Read-only access to filesystem                                     │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│                    SQLite Database                                  │
│                                                                     │
│  Tables: notes, links, tags, embeddings, sessions                  │
│  File: <vault>/_geistfabrik/vault.db                               │
└────────────────────────────────────────────────────────────────────┘
```

### Import Dependencies Matrix

| Module | Depends On |
|--------|------------|
| `models.py` | (none - foundation) |
| `config.py` | (none - constants) |
| `schema.py` | (none - SQL) |
| `markdown_parser.py` | models |
| `vault.py` | models, schema, markdown_parser |
| `embeddings.py` | config, models |
| `vector_search.py` | config |
| `vault_context.py` | config, embeddings, models, vault |
| `function_registry.py` | (TYPE_CHECKING: vault_context) |
| `metadata_system.py` | models |
| `tracery.py` | models, vault_context |
| `filtering.py` | config, embeddings, models |
| `geist_executor.py` | models, vault_context |
| `journal_writer.py` | models |
| `cli.py` | (nearly everything) |

**Key Insight**: The dependency graph is acyclic with clear layers. `models.py` and `config.py` are foundation modules with no internal dependencies.

---

## 2. The Two-Layer Architecture

### Layer 1: Vault (Data Access)

**Purpose**: Raw file system access and SQLite persistence

**Responsibilities**:
- Parse Markdown files (frontmatter, links, tags)
- Create immutable `Note` objects
- Sync filesystem changes to SQLite incrementally
- Manage database schema and migrations

**Key Characteristics**:
```python
@dataclass(frozen=True)
class Note:
    path: str
    title: str
    content: str
    links: List[Link]
    tags: List[str]
    created: datetime
    modified: datetime
    # ... virtual entry fields
```

- Notes are **immutable** (frozen dataclass)
- Notes are **lightweight** (no computed properties)
- **All intelligence lives in VaultContext**, not Note

**File**: `src/geistfabrik/vault.py` (~900 lines)

### Layer 2: VaultContext (Intelligence)

**Purpose**: Rich API for geist execution

**Responsibilities**:
- Semantic search (via embeddings)
- Graph operations (backlinks, orphans, hubs)
- Metadata inference integration
- Deterministic random sampling
- Vault function registry

**Key API Surface**:
```python
class VaultContext:
    # Vault access
    def notes() -> List[Note]
    def get_note(path) -> Note
    def read(note) -> str

    # Semantic search
    def neighbours(note, k) -> List[Note]
    def similarity(a, b) -> float
    def batch_similarity(set_a, set_b) -> ndarray

    # Graph operations
    def backlinks(note) -> List[Note]
    def orphans(k) -> List[Note]
    def hubs(k) -> List[Note]
    def unlinked_pairs(k) -> List[Tuple[Note, Note]]

    # Temporal queries
    def old_notes(k) -> List[Note]
    def recent_notes(k) -> List[Note]

    # Metadata
    def metadata(note) -> Dict[str, Any]

    # Sampling
    def sample(items, k) -> List
    def random_notes(k) -> List[Note]
```

**File**: `src/geistfabrik/vault_context.py` (~1100 lines)

### Layer Boundary Enforcement

From CLAUDE.md:
> "Geists MUST use VaultContext methods, NEVER direct SQL"

This is enforced through:
1. VaultContext abstractions hide database schema
2. Geists receive VaultContext, not database connections
3. Documented guidelines in CLAUDE.md

---

## 3. Design Patterns Identified

### 3.1 Strategy Pattern (Vector Search)

**Location**: `src/geistfabrik/vector_search.py`

```python
class VectorSearchBackend(ABC):
    @abstractmethod
    def load_embeddings(self, session_date: str) -> None: ...
    @abstractmethod
    def find_similar(self, query: ndarray, k: int) -> List[Tuple[str, float]]: ...
    @abstractmethod
    def get_similarity(self, path_a: str, path_b: str) -> float: ...

class InMemoryVectorBackend(VectorSearchBackend):
    """Pure Python, fast for small vaults"""

class SqliteVecBackend(VectorSearchBackend):
    """Native SQL vectors, scales to large vaults"""
```

**Benefit**: Users can switch backends via configuration without code changes.

### 3.2 Adapter Pattern (Tracery Bridge)

**Location**: `src/geistfabrik/function_registry.py`

The FunctionRegistry adapts between:
- **Tracery** (string-based I/O)
- **VaultContext** (Note object-based)

```python
@vault_function("sample_notes")
def sample_notes(vault: VaultContext, k: int = 5) -> List[str]:
    """Adapter: Note objects → bracketed link strings"""
    notes = vault.notes()
    sampled = vault.sample(notes, k)
    return [f"[[{note.obsidian_link}]]" for note in sampled]
```

**Data Flow**:
```
Tracery Grammar → $vault.sample_notes(3) → FunctionRegistry
    → VaultContext.notes() → [Note objects]
    → Adapter → ["[[Title A]]", "[[Title B]]", "[[Title C]]"]
```

### 3.3 Registry Pattern (Functions)

**Location**: `src/geistfabrik/function_registry.py`

```python
_GLOBAL_REGISTRY: Dict[str, Callable[..., Any]] = {}

@vault_function("name")
def my_function(vault: VaultContext, ...):
    """Decorator registers function globally"""
```

**Used For**:
- Built-in vault functions (sample_notes, hubs, orphans, etc.)
- User-defined vault functions
- Tracery `$vault.*` calls

### 3.4 Pipeline Pattern (Filtering)

**Location**: `src/geistfabrik/filtering.py`

```
Raw Suggestions → Boundary Filter → Novelty Filter → Diversity Filter → Quality Filter → Final
```

Each filter:
1. Receives suggestions from previous stage
2. Applies its logic
3. Passes remaining suggestions to next stage

```python
class SuggestionFilter:
    def filter(self, suggestions: List[Suggestion]) -> List[Suggestion]:
        # 1. Boundary: referenced notes must exist
        suggestions = self._apply_boundary(suggestions)

        # 2. Novelty: avoid recent duplicates
        suggestions = self._apply_novelty(suggestions)

        # 3. Diversity: remove near-duplicates
        suggestions = self._apply_diversity(suggestions)

        # 4. Quality: enforce minimum standards
        suggestions = self._apply_quality(suggestions)

        return suggestions
```

### 3.5 Template Method Pattern (Geist Execution)

**Location**: `src/geistfabrik/geist_executor.py`

All geists follow a template:
```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    # 1. Query vault for data
    notes = vault.notes()

    # 2. Process/analyze
    candidates = [n for n in notes if some_condition(n)]

    # 3. Create suggestions
    return [Suggestion(text=..., notes=..., geist_id=...) for ...]
```

The executor handles:
- Timeout enforcement (signal-based)
- Error catching and logging
- Failure tracking and disabling

### 3.6 Lazy Loading Pattern

**Location**: `src/geistfabrik/embeddings.py`

```python
class EmbeddingComputer:
    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load model on first access"""
        if self._model is None:
            self._model = SentenceTransformer(...)
        return self._model
```

**Benefits**:
- Model only loaded when needed
- Faster startup for commands that don't need embeddings
- Memory efficient for testing

### 3.7 Named Constants Pattern (Similarity Levels)

**Location**: `src/geistfabrik/similarity_analysis.py`

```python
class SimilarityLevel:
    """Semantic names for magic numbers"""
    VERY_HIGH = 0.80  # Near-duplicates
    HIGH = 0.65       # Clearly related
    MODERATE = 0.50   # Thematic overlap
    WEAK = 0.35       # Tangentially related
    NOISE = 0.15      # Mostly unrelated
```

**Usage**:
```python
# Instead of: if similarity > 0.65:
if similarity > SimilarityLevel.HIGH:
```

**Benefits**:
- Self-documenting code
- Single point of change for threshold tuning
- Consistent vocabulary across geists

---

## 4. Data Flow Analysis

### Invoke Command Flow

```
1. CLI (cli.py)
   │
   ├─→ Vault.sync()          # Incremental filesystem → SQLite
   │
   ├─→ Session.compute_embeddings()  # Generate temporal embeddings
   │
   ├─→ VaultContext(vault, session)  # Create intelligence layer
   │
   ├─→ GeistExecutor.load_geists()   # Discover and load geists
   │
   ├─→ GeistExecutor.execute_all()   # Run each geist with timeout
   │   │
   │   └─→ geist.suggest(vault_context) → List[Suggestion]
   │
   ├─→ SuggestionFilter.filter()     # 4-stage pipeline
   │
   ├─→ select_suggestions()          # Deterministic sampling
   │
   └─→ JournalWriter.write()         # Create session note
```

### Embedding Flow

```
Note Content → sentence-transformers → 384-dim semantic
                                              │
Note Metadata → temporal_features() → 3-dim temporal
                                              │
                                              ▼
                            Concatenate → 387-dim temporal embedding
                                              │
                                              ▼
                            Store in session_embeddings table
                                              │
                                              ▼
                            Load into VectorSearchBackend
                                              │
                                              ▼
                            VaultContext.similarity(a, b)
```

### Tracery Geist Flow

```
YAML Grammar Definition
        │
        ▼
TraceryEngine.expand("#origin#")
        │
        ├─→ Symbol expansion: #note# → random choice from list
        │
        ├─→ Function call: $vault.hubs(5) → FunctionRegistry.call()
        │   │
        │   └─→ VaultContext.hubs(5) → [Note objects]
        │       │
        │       └─→ Adapter → ["[[Hub A]]", "[[Hub B]]", ...]
        │
        ├─→ Modifiers: #word.capitalize# → "Word"
        │
        └─→ Final expanded string → Suggestion
```

---

## 5. Extensibility Mechanisms

GeistFabrik provides **three dimensions of extensibility**:

### 5.1 Metadata Inference

**Location**: `<vault>/_geistfabrik/metadata_inference/*.py`

```python
# complexity.py
def infer(note: Note, vault: VaultContext) -> Dict[str, Any]:
    return {
        "reading_time_minutes": len(note.content.split()) / 200,
        "lexical_diversity": len(set(words)) / len(words),
    }
```

**Mechanism**: Dynamic module loading via `importlib.util`

**Flow**:
```
MetadataLoader.load_modules() → discover *.py → validate infer() → register
VaultContext.metadata(note) → MetadataLoader.infer_all(note) → merged dict
```

### 5.2 Vault Functions

**Location**: `<vault>/_geistfabrik/vault_functions/*.py`

```python
from geistfabrik import vault_function

@vault_function("find_questions")
def find_questions(vault: VaultContext, k: int = 5) -> List[str]:
    questions = [n for n in vault.notes() if "?" in n.title]
    return [f"[[{q.obsidian_link}]]" for q in vault.sample(questions, k)]
```

**Available as**: `$vault.find_questions(k=3)` in Tracery

### 5.3 Custom Geists

**Code Geists**: `<vault>/_geistfabrik/geists/code/*.py`
```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    # Full Python with VaultContext API
    ...
```

**Tracery Geists**: `<vault>/_geistfabrik/geists/tracery/*.yaml`
```yaml
type: geist-tracery
id: my_geist
tracery:
  origin: "What about #note#?"
  note: "$vault.sample_notes(1)"
```

---

## 6. Coupling and Cohesion Assessment

### Module Cohesion (High)

| Module | Cohesion | Assessment |
|--------|----------|------------|
| `models.py` | High | Only data structures |
| `vault.py` | High | Only file I/O and sync |
| `vault_context.py` | High | Only query operations |
| `filtering.py` | High | Only filtering logic |
| `embeddings.py` | Medium | Combines computation + session management |
| `cli.py` | Low | Orchestrator (expected) |

### Module Coupling

**Low Coupling Strengths**:
- `models.py` has zero internal dependencies
- Clear layer boundaries (Vault → VaultContext → Geists)
- TYPE_CHECKING guards prevent import cycles

**Coupling Concerns**:
- `cli.py` imports 11 internal modules (orchestrator pattern, acceptable)
- `vault_context.py` depends on 4 modules (expected for facade)

### Dependency Inversion

**Good Examples**:
```python
# VaultContext accepts injected Session (DI)
class VaultContext:
    def __init__(self, vault: Vault, session: Session, ...):
        self.session = session  # Injected, not created

# EmbeddingComputer accepts optional model (DI for testing)
class EmbeddingComputer:
    def __init__(self, model_name: str, model: Optional[SentenceTransformer] = None):
        self._model = model  # Can inject mock/stub
```

---

## 7. Architecture Strengths

### 7.1 Clean Layer Separation
- Vault (I/O) → VaultContext (Intelligence) → Geists (Creativity)
- Each layer has clear responsibilities
- Layer violations documented and prevented

### 7.2 Immutable Data Model
- `Note` objects are frozen dataclasses
- Prevents accidental mutation
- Enables caching and parallel processing

### 7.3 Deterministic Randomness
- Session date seeds RNG
- Same date + vault = same suggestions
- Enables reproducible sessions and debugging

### 7.4 Pluggable Backends
- Vector search backend is swappable
- Configuration-driven backend selection
- Consistent interface across implementations

### 7.5 Three-Dimensional Extensibility
- Metadata, Functions, and Geists all extensible
- Dynamic module loading for user code
- Clear extension points with validation

---

## 8. Architecture Recommendations

### 8.1 Consider Command Pattern for CLI

Current orchestration is procedural in `cli.py`. Consider:
```python
class InvokeCommand:
    def execute(self) -> int: ...

class InitCommand:
    def execute(self) -> int: ...
```

**Benefit**: Easier testing of individual commands.

### 8.2 Extract Session Management

`embeddings.py` handles both embedding computation AND session management. Consider:
```
embeddings.py → EmbeddingComputer only
session.py → Session class (new file)
```

**Benefit**: Single Responsibility Principle.

### 8.3 Add Interface for Geists

Currently geists are convention-based (`def suggest(vault)`). Consider:
```python
class Geist(Protocol):
    def suggest(self, vault: VaultContext) -> List[Suggestion]: ...
```

**Benefit**: Type checking, IDE support, explicit contract.

### 8.4 Document Extension Loading Security Model

Dynamic module loading (`importlib.util`) runs arbitrary Python. While this is intentional for extensibility, the trust model should be documented in a SECURITY.md.

---

## 9. Conclusion

GeistFabrik's architecture demonstrates:

- **Mature layering** with clear Vault → VaultContext → Geist hierarchy
- **Appropriate patterns** (Strategy, Adapter, Registry, Pipeline)
- **Good cohesion** within modules
- **Reasonable coupling** with clear dependency direction
- **Strong extensibility** through three documented mechanisms

The architecture is well-suited for its purpose: a local-first, extensible divergence engine for Obsidian vaults. The design decisions prioritize:
1. Read-only safety
2. Deterministic reproducibility
3. User extensibility
4. Testability

**Overall Assessment**: Production-ready architecture with minor improvement opportunities.

---

*Generated by Claude Code architecture analysis*
