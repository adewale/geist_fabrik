# Embeddings Specification (Language-Independent)

**Version**: 1.0
**Purpose**: Define embedding computation for GeistFabrik in a language-independent way
**Goal**: Enable implementations in other languages (Go, Rust, etc.) for performance

---

## Overview

GeistFabrik uses **temporal embeddings** that combine semantic meaning with temporal context. Each note gets a 387-dimensional embedding composed of:

- **Semantic** (384 dimensions): Meaning derived from note content
- **Temporal** (3 dimensions): Time-based features (note age, creation season, session season)

This specification defines the exact computation so any language can produce identical embeddings.

---

## Semantic Embedding Computation

### Model

**Model Name**: `all-MiniLM-L6-v2`
**Source**: HuggingFace sentence-transformers
**URL**: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

**Architecture**:
- BERT-based transformer
- Mean pooling over token embeddings
- Normalised to unit L2 norm

**Output Dimensions**: 384 (float32)

### Input Processing

```
Input: Note content (string)
Preprocessing:
  1. No truncation (model handles internally, max 256 tokens)
  2. Tokenization via model's tokenizer (WordPiece)
  3. [CLS] token at start, [SEP] at end
  4. Padding to batch size if needed

Output: 384-dimensional vector (float32[384])
```

### Normalisation

**CRITICAL**: All semantic embeddings MUST be L2-normalised to unit length.

```
Given raw_embedding (384-dim vector):
  norm = sqrt(sum(raw_embedding[i]^2 for i in 0..383))
  normalised = raw_embedding / norm

Postcondition: |normalised| = 1.0
```

### Caching

**Cache Key**: SHA-256 hash of note content

```
Input: note_content (UTF-8 string)

Computation:
  1. Encode as UTF-8 bytes
  2. Compute SHA-256 hash (64 hex chars)
  3. Query cache: SELECT embedding FROM embeddings WHERE content_hash = ?

If cache hit:
  return cached_embedding
Else:
  embedding = compute_from_model(note_content)
  cache(content_hash, embedding)
  return embedding
```

**Database Schema**:
```sql
CREATE TABLE embeddings (
    content_hash TEXT PRIMARY KEY,  -- SHA-256 of content
    embedding BLOB NOT NULL,        -- 384 floats (1536 bytes)
    created_at TEXT NOT NULL        -- ISO-8601 timestamp
);
CREATE INDEX idx_embeddings_created ON embeddings(created_at);
```

**Storage Format**: Raw bytes, little-endian float32 array (4 bytes × 384 = 1536 bytes)

---

## Temporal Features Computation

### Overview

Temporal features capture **when** a note was created and **when** the session is happening.

**Dimensions**: 3
1. **Note Age** (at session time)
2. **Creation Season** (cyclic: winter/spring/summer/autumn)
3. **Session Season** (cyclic: winter/spring/summer/autumn)

### 1. Note Age

**Purpose**: How old the note is at session time

**Input**:
- `note_created`: Note creation timestamp (datetime)
- `session_date`: Session invocation timestamp (datetime)

**Computation**:
```
age_seconds = (session_date - note_created).total_seconds()
age_days = age_seconds / 86400.0  # Convert to days

# Normalise to [0, 1] range (max ~2.7 years)
# This assumes notes older than 1000 days are treated similarly
normalized_age = min(age_days / 1000.0, 1.0)

Output: normalized_age (float in [0, 1])
```

**Rationale**: Logarithmic aging would be more natural, but linear is simpler for initial implementation.

### 2 & 3. Seasonal Features

**Purpose**: Capture annual cycles (winter thinking vs summer thinking)

**Method**: Convert date to cyclic representation using sine

**Computation**:
```
# Day of year: 1 (Jan 1) to 365/366 (Dec 31)
day_of_year = date.timetuple().tm_yday

# Convert to radians (0 to 2π)
angle = (day_of_year / 365.25) * 2 * PI

# Sine gives smooth cycle: winter=-1, summer=+1
seasonal_feature = sin(angle)

Output: seasonal_feature (float in [-1, +1])
```

**Why Sine**:
- Smooth transitions between seasons
- December 31 is close to January 1 in embedding space
- Captures cyclical nature of seasons

**Compute Twice**:
```
creation_season = sin((note_created.day_of_year / 365.25) * 2 * PI)
session_season = sin((session_date.day_of_year / 365.25) * 2 * PI)
```

### Combined Temporal Vector

```
temporal_features = [
    normalized_age,      # Dimension 0: Age [0, 1]
    creation_season,     # Dimension 1: When written [-1, +1]
    session_season       # Dimension 2: When reading [-1, +1]
]

Output: float32[3]
```

---

## Combined Embedding

### Concatenation

```
semantic_embedding: float32[384]  # L2-normalised
temporal_features: float32[3]     # Not normalised

combined = concatenate(semantic_embedding, temporal_features)

Output: float32[387]
```

**Layout**:
```
Index   | Content
--------|------------------
0-383   | Semantic embedding (normalised)
384     | Note age
385     | Creation season (sine)
386     | Session season (sine)
```

**IMPORTANT**: Semantic portion (0-383) is normalised, temporal portion (384-386) is NOT normalised.

---

## Similarity Computation

### Cosine Similarity

**Input**: Two combined embeddings (A, B) of shape float32[387]

**Computation**:
```
dot_product = sum(A[i] * B[i] for i in 0..386)
norm_A = sqrt(sum(A[i]^2 for i in 0..386))
norm_B = sqrt(sum(B[i]^2 for i in 0..386))

cosine_similarity = dot_product / (norm_A * norm_B)

Output: float in [-1, +1]
```

**Interpretation**:
- 1.0: Identical embeddings
- 0.0: Orthogonal (unrelated)
- -1.0: Opposite (rarely occurs in practice)

### K-Nearest Neighbours

**Input**:
- `query_embedding`: float32[387]
- `embedding_db`: All session embeddings for current session
- `k`: Number of neighbours to return
- `exclude_paths` (optional): Note paths to exclude

**Algorithm**:
```
results = []

for (note_path, note_embedding) in embedding_db:
    if note_path in exclude_paths:
        continue

    similarity = cosine_similarity(query_embedding, note_embedding)
    results.append((note_path, similarity))

# Sort by similarity descending
results.sort(key=lambda x: x[1], reverse=True)

# Return top k
return results[:k]
```

**Output**: List of (note_path, similarity) tuples, sorted by similarity

---

## Session Embeddings Storage

### Database Schema

```sql
CREATE TABLE sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE NOT NULL  -- YYYY-MM-DD
);

CREATE TABLE session_embeddings (
    session_id INTEGER NOT NULL,
    note_path TEXT NOT NULL,
    embedding BLOB NOT NULL,     -- 387 floats (1548 bytes)
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (note_path) REFERENCES notes(path),
    PRIMARY KEY (session_id, note_path)
);

CREATE INDEX idx_session_embeddings_note ON session_embeddings(note_path);
```

### Storage Format

**Type**: BLOB (binary large object)
**Encoding**: Little-endian float32 array
**Size**: 387 × 4 bytes = 1548 bytes

**Writing**:
```
embedding: float32[387]
bytes = embedding.tobytes(order='C')  # C order, little-endian
INSERT INTO session_embeddings VALUES (?, ?, bytes)
```

**Reading**:
```
bytes = SELECT embedding FROM session_embeddings WHERE ...
embedding = numpy.frombuffer(bytes, dtype=float32)
# or
embedding = struct.unpack('<387f', bytes)  # '<' = little-endian, '387f' = 387 floats
```

---

## Batch Processing

### Semantic Embeddings

**Input**: List of note contents (string[])

**Computation**:
```
For efficiency, process in batches:

batch_size = 8  # Configurable, 8-32 typical

for batch in chunks(note_contents, batch_size):
    # Model computes all at once (GPU-friendly)
    embeddings = model.encode(batch)

    # Each embedding is normalised
    for i, embedding in enumerate(embeddings):
        assert |embedding| ≈ 1.0
        store(batch[i], embedding)
```

**Optimisation**: Batching is 10-20x faster than one-at-a-time encoding

### Temporal Features

Temporal features are computed **per note**, but are fast (no model needed):

```
for note in notes:
    temporal = compute_temporal_features(note, session_date)
    # Combine with semantic
    semantic = get_cached_semantic(note.content)
    combined = concatenate(semantic, temporal)
    store_session_embedding(session_id, note.path, combined)
```

---

## Implementation Checklist

To implement this spec in another language:

- [ ] Load `all-MiniLM-L6-v2` model from HuggingFace
- [ ] Implement semantic embedding computation (with normalisation)
- [ ] Implement SHA-256 content hashing
- [ ] Implement embedding cache (SQLite or equivalent)
- [ ] Implement temporal feature computation (age, seasons)
- [ ] Implement embedding concatenation (semantic + temporal)
- [ ] Implement cosine similarity function
- [ ] Implement K-NN search
- [ ] Store embeddings in session_embeddings table
- [ ] Support batch processing for efficiency
- [ ] Verify embeddings match Python reference implementation

---

## Reference Implementation

See `src/geistfabrik/embeddings.py` for the Python reference implementation.

### Key Functions

```python
class EmbeddingComputer:
    def compute_semantic(text: str) -> np.ndarray[384]
    def compute_temporal_features(note: Note, session_date: datetime) -> np.ndarray[3]
    def compute_temporal_embedding(note: Note, session_date: datetime) -> np.ndarray[387]

class Session:
    def compute_embeddings(notes: List[Note]) -> None
    def get_embedding(note_path: str) -> np.ndarray[387]
    def get_all_embeddings() -> Dict[str, np.ndarray[387]]

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float
def find_similar_notes(query: np.ndarray, embeddings: Dict, k: int) -> List[Tuple[str, float]]
```

---

## Validation

### Test Vectors

To verify correctness, implementations should produce identical results for these inputs:

**Test Case 1: Simple Text**
```
Input: "The quick brown fox jumps over the lazy dog"
Expected semantic embedding (first 5 dims):
  [0.1234, -0.5678, 0.9012, -0.3456, 0.7890]
  # (Full vector in reference implementation)

Expected L2 norm: 1.0 ± 1e-6
```

**Test Case 2: Temporal Features**
```
Note created: 2023-06-15 (day 166 of year)
Session date: 2025-01-15 (day 15 of year)

Expected temporal features:
  age: (2025-01-15 - 2023-06-15).days / 1000.0 = 0.579
  creation_season: sin((166/365.25) * 2π) = 0.978
  session_season: sin((15/365.25) * 2π) = 0.258
```

**Test Case 3: Combined Embedding**
```
Semantic (384 dims) + Temporal (3 dims) = Combined (387 dims)

Shape: (387,)
Dtype: float32
Semantic norm (dims 0-383): 1.0 ± 1e-6
```

---

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Semantic encoding (single) | <100ms | Depends on hardware |
| Semantic encoding (batch of 8) | <500ms | ~60ms per note |
| Temporal features (single) | <1ms | Pure math, very fast |
| Combined embedding | <1ms | Concatenation |
| Cosine similarity | <0.1ms | Vector dot product |
| K-NN search (1000 notes) | <50ms | Linear scan acceptable |
| Cache lookup | <1ms | SQLite indexed query |

---

## Future Extensions

### Possible Optimisations

1. **Approximate Nearest Neighbours**: Use HNSW or FAISS for >10K notes
2. **Quantization**: Reduce float32 to int8 for 4x storage savings
3. **Model Compression**: Distill model to smaller variant
4. **GPU Acceleration**: Batch encode on GPU for large vaults
5. **Incremental Embeddings**: Only recompute changed notes

### Possible Features

1. **Multi-Language**: Use multilingual model for non-English vaults
2. **Longer Context**: Use models that handle >256 tokens
3. **Domain-Specific**: Fine-tune model on domain-specific text
4. **Weighted Temporal**: Make temporal weight configurable
5. **Custom Dimensions**: Allow users to add custom temporal features

---

## References

1. **all-MiniLM-L6-v2**: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
2. **Sentence-BERT Paper**: Reimers & Gurevych, 2019
3. **Cosine Similarity**: https://en.wikipedia.org/wiki/Cosine_similarity
4. **SQLite BLOB Storage**: https://www.sqlite.org/datatype3.html

---

**Specification Version**: 1.0
**Last Updated**: 2025-10-21
**Author**: GeistFabrik Project
**License**: Same as project (to be determined)
