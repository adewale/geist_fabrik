# Configuration (`_geistfabrik/config.yaml`)

Every key GeistFabrik actually reads, with its default. `geistfabrik init`
writes a starter file; unknown top-level keys are ignored with a warning.

The full historical spec schema (some of it aspirational) lives in
`specs/geistfabrik_spec.md`; **what is actually wired is recorded in
`specs/SPEC_STATUS.md`** and enforced by `tests/unit/test_spec_config_sync.py`.

## Example

```yaml
# Which geists run (omitted = enabled). Disable with false.
default_geists:
  pattern_finder: true
  congruence_mirror: false

# Allowlist of metadata-inference / vault-function modules under _geistfabrik/
# (empty = load all). A module not listed here is not loaded.
enabled_modules: []

# Geist execution
geist_execution:
  timeout: 30          # seconds per geist (overridden by --timeout)
  max_failures: 3      # disable after N consecutive failures (persisted)

# Suggestion filtering pipeline
filtering:
  boundary:
    exclude_paths: ["Private/", "People/"]  # folders whose notes never surface
  novelty:
    window_days: 60     # look-back for "have I seen this before?"
    threshold: 0.85     # cosine similarity above which a suggestion is stale
  diversity:
    threshold: 0.85     # near-duplicate cutoff within one session
  quality:
    min_length: 10
    max_length: 2000

# Session output
session:
  default_suggestions: 5   # default-mode count (overridden by --count)

# Storage: keep temporal embeddings for the N most recent sessions (0 = all).
session_embedding_retention: 730

# Clustering / cluster labelling
clustering:
  labeling_method: keybert   # or "tfidf"
  min_cluster_size: 5
  n_label_terms: 4

# Vector search backend
vector_search:
  backend: in-memory         # or "sqlite-vec" (needs the [vector-search] extra)

# Date-collection (journal) note splitting
date_collection:
  enabled: true
  min_sections: 2
  date_threshold: 0.5
  exclude_files: []          # glob patterns, e.g. "Templates/*.md"
```

## Resolution order

- **Timeout / count**: explicit CLI flag (`--timeout`, `--count`) wins; otherwise
  the config value; otherwise the built-in default (30s, 5).
- **`exclude_paths`**: the boundary filter drops any suggestion that references a
  note whose path (or, for journal entries, source file) is under one of these
  folder prefixes. This is the privacy control — notes under `Private/` etc.
  never appear in suggestions.

## Notes on divergence from the spec

A few spec keys are deliberately not config-driven (see `SPEC_STATUS.md`):
embeddings model/dimensions/weights are fixed constants; `tracery.max_depth` is
hardcoded; logging is console-based (no `logging.log_file`); filtering
strategy *order* and per-filter `enabled`/`method` toggles are not exposed.
