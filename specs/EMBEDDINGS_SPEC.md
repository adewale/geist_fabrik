# Embeddings Specification

**Status**: Current, normative description of the Python implementation.
**Version**: 1.1
**Last verified**: 2026-09-12
**Scope**: Model inputs, temporal features, weighting, cache identity, and persisted vectors.

This specification describes implemented behavior, replacing the earlier design's
clamped age, unweighted concatenation, and content-hash-only cache. The
[reference implementation](../src/geistfabrik/embeddings.py),
[constants](../src/geistfabrik/config.py), and
[database schema](../src/geistfabrik/schema.py) are the sources to check when
changing this contract. Proposed extensions below are explicitly non-normative.

## Representation

A session embedding contains 387 coordinates:

| Coordinates | Stored values |
| --- | --- |
| 0–383 | 384 semantic coordinates multiplied by 0.9 |
| 384 | Note age in years multiplied by 0.1 |
| 385 | Creation-day seasonal sine multiplied by 0.1 |
| 386 | Session-day seasonal sine multiplied by 0.1 |

The combined vector is not subsequently normalized. Similarity therefore requires
cosine normalization; a raw dot product is not generally its cosine similarity.

## Semantic encoding

The default model is `all-MiniLM-L6-v2`. GeistFabrik loads the bundled snapshot
when usable, with the configured offline policy governing any model fallback.
The bundled [module configuration](../models/all-MiniLM-L6-v2/modules.json)
contains a transformer, pooling, and a Normalize module.

The application passes note content directly to `model.encode()`, requesting
NumPy output. Tokenization and truncation belong to the model; the bundled
sentence-transformer configuration uses a maximum sequence length of 256.
The application neither truncates note strings first nor independently
L2-normalizes the returned vectors. The bundled model supplies normalization
through its module pipeline; arbitrary injected models must not be assumed to
produce unit vectors.

Regular notes use their stored full Markdown content, including frontmatter.
Virtual date-collection entries use their stored entry content. There is no
session-dependent semantic reinterpretation step: unchanged content with a valid
cache entry reuses the same semantic vector.

`compute_batch_semantic(texts, batch_size=8)` and session encoding use batching;
the session default is `DEFAULT_BATCH_SIZE = 8`. Hardware and model versions can
affect numerical results, so cross-language parity should use the same model
snapshot and compare with a suitable floating-point tolerance.

## Semantic cache

The cache has one row per note path. Its validity marker is the default model
name followed by a colon and the SHA-256 digest of the content's UTF-8 bytes:

```python
content_hash = hashlib.sha256(note.content.encode("utf-8")).hexdigest()
model_version = f"{MODEL_NAME}:{content_hash}"
```

Lookup requires both fields:

```sql
SELECT embedding FROM embeddings
WHERE note_path = ? AND model_version = ?;
```

The implemented schema is:

```sql
CREATE TABLE embeddings (
    note_path TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model_version TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    FOREIGN KEY (note_path) REFERENCES notes(path) ON DELETE CASCADE
);
```

There is no `content_hash` column or cross-path content-addressed cache. Identical
content in two different note paths does not share one cache row.
`model_version` is a model-name/content marker, not a digest of model weights.

During `Session.compute_embeddings()`, cache hits reuse semantic vectors;
misses are encoded in a batch and upserted. All notes receive recomputed temporal
features and newly composed session vectors. Sync currently invalidates a note's
semantic cache row when that source is reprocessed, so an unchanged-content
filesystem update can still cause re-encoding; reuse requires a surviving,
matching cache entry.

## Temporal features

Let `created` be the note's creation datetime and `session_date` the session
datetime. Virtual entries use their entry date as their creation datetime.

### Note age

```python
age_days = (session_date - created).days
note_age = age_days / 365.0
```

This uses the integer `timedelta.days` component, not fractional elapsed days.
Age is unbounded: it is not clamped to [0, 1], and a replay before creation can
produce a negative value. For example, 730 elapsed days produces 2.0 before
weighting and 0.2 in coordinate 384.

### Seasonal coordinates

```python
creation_season = math.sin(2 * math.pi * created.timetuple().tm_yday / 365.0)
session_season = math.sin(2 * math.pi * session_date.timetuple().tm_yday / 365.0)
temporal = np.array([note_age, creation_season, session_season])
```

The denominator is exactly 365.0, including leap years. Day of year is 1-based
and can reach 366. There is one sine coordinate per date, with no cosine partner.
These values are smooth annual signals in [-1, 1], not categorical seasons:
the sine peaks around early April, not at the summer solstice, and distinct
dates can have equal sine values.

## Weighting and composition

The session pipeline uses `DEFAULT_SEMANTIC_WEIGHT = 0.9`:

```python
semantic_weight = 0.9
temporal_weight = 1.0 - semantic_weight
combined = np.concatenate([
    semantic * semantic_weight,
    temporal * temporal_weight,
])
stored = combined.astype(np.float32)
```

These are coordinate scaling factors, not a guarantee that 90% of a cosine
score comes from semantics. In particular, unbounded age can eventually make
the temporal contribution large.

The direct `EmbeddingComputer.compute_temporal_embedding()` helper accepts a
`semantic_weight` argument with the same default. It returns the NumPy
concatenation without forcing float32; the session persistence boundary performs
that cast. The CLI session pipeline uses the default weight.

## Session persistence and ownership

The current relevant tables are:

```sql
CREATE TABLE sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    vault_state_hash TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE session_embeddings (
    session_id INTEGER NOT NULL,
    note_path TEXT NOT NULL,
    embedding BLOB NOT NULL,
    cluster_label TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (note_path) REFERENCES notes(path) ON DELETE CASCADE,
    PRIMARY KEY (session_id, note_path)
);

CREATE INDEX idx_session_embeddings_path ON session_embeddings(note_path);
```

A date identifies one canonical session (`YYYY-MM-DD`); recomputing that date
replaces its vectors rather than appending another snapshot. Historical rows
survive same-path content updates, but deleting a note cascades to its history.

Encoding occurs before the owned write transaction. Before committing, the
session verifies that its inputs still match the current database snapshot;
a concurrent change raises `ConcurrentVaultChangeError` instead of publishing
stale embeddings. The session hash, semantic upserts, session-vector replacement,
and retention pruning are committed together.

Retention keeps the configured number of most recent other sessions plus the
current session. The CLI default is 730; 0 retains all. Pruning removes historical
embedding rows, leaving session metadata and suggestion history.

### Binary format

Persistence uses `array.astype(np.float32).tobytes()` and reads with
`np.frombuffer(blob, dtype=np.float32)`. This is native-endian float32, which is
little-endian on the supported mainstream deployment machines; the schema does
not record an endianness marker. A cross-architecture importer must account for
the originating byte order.

- Semantic vector: 384 × 4 = 1,536 bytes.
- Session vector: 387 × 4 = 1,548 bytes.

These sizes exclude SQLite rows, indexes, and other storage overhead.

## Similarity and public query examples

For vectors A and B, cosine similarity is
`dot(A, B) / (norm(A) * norm(B))`. The low-level
`cosine_similarity()` returns 0 for a zero vector, rejects mismatched shapes or
non-finite values, and clips numerical overshoot to [-1, 1]. VaultContext's
similarity APIs clip scores to [0, 1].

```python
from geistfabrik.embeddings import find_similar_notes

# Within a geist, vault is the provided VaultContext.
def nearest(vault, note):
    scored_notes = vault.neighbours(note, count=5, return_scores=True)
    query = vault.get_embedding(note.path)
    if query is None:
        return scored_notes, []
    scored_paths = find_similar_notes(
        query,
        vault.get_all_embeddings(),
        count=5,
        exclude_paths={note.path},
    )
    return scored_notes, scored_paths
```

Use `count=` for these APIs. `VaultContext.get_all_embeddings()` provides the
session's mapping; there is no `Session.get_all_embeddings()` method.

## Reference validation values

For a note created at midnight on 2023-06-15 and a session at midnight on
2025-01-15:

| Feature | Before weighting | Stored coordinate, approximately |
| --- | --- | --- |
| Age | 580 / 365 = 1.589041096 | 0.158904110 |
| Creation season (day 166) | 0.280230675 | 0.028023068 |
| Session season (day 15) | 0.255353295 | 0.025535330 |

No fabricated semantic test vector is specified. Compare real model output
against the reference implementation with the same model snapshot. Formula,
cache, and serialization regression coverage lives in
[embedding tests](../tests/unit/test_embeddings.py) and
[property tests](../tests/unit/test_property_embeddings.py).

## Non-normative extensions

Approximate search indexes, quantization, alternate models, weight configuration
in CLI sessions, and different temporal features require explicit future
implementation and compatibility decisions. Semantic reuse for unchanged notes
and device-aware batch encoding are already implemented.

See [temporal examples](../docs/TEMPORAL_EMBEDDINGS_EXAMPLES.md) for an explanatory
companion and [configuration](../docs/CONFIGURATION.md) for supported settings.
