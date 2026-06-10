# Spec ↔ Implementation Status (reconciliation ledger)

Single source of truth for "did we build what the spec promised". Every config
key in `geistfabrik_spec.md`'s config.yaml block, plus the other concrete spec
promises, has a status here. **`tests/unit/test_spec_config_sync.py` fails CI if
a spec config key is not listed below** — so an aspirational spec edit can no
longer drift silently into "specified but never built". When you change a spec,
update this ledger in the same PR.

Status vocabulary:
- **BUILT** — implemented as specified.
- **BUILT-DIFFERENTLY** — implemented, but shape/name/location diverges from the
  spec (the spec should eventually be amended to match).
- **NOT-WIRED** — a default exists in code but the config key does not drive it
  (changing it in config.yaml has no effect).
- **NOT-BUILT** — no implementation; recommend amending the spec.
- **DEFERRED** — intentionally post-1.0 (see referenced doc).

## config.yaml keys (geistfabrik_spec.md ~830-905)

| key | status | note |
|---|---|---|
| `vault.path` | BUILT-DIFFERENTLY | CLI vault argument / auto-detect, not config |
| `vault.database` | BUILT-DIFFERENTLY | fixed `_geistfabrik/vault.db` path |
| `embeddings.enabled` | NOT-BUILT | embeddings always on; amend spec |
| `embeddings.model` | NOT-BUILT | hardcoded `MODEL_NAME`; model-swap is out of scope (dims/cache) |
| `embeddings.dimensions` | NOT-BUILT | hardcoded `SEMANTIC_DIM=384` |
| `embeddings.temporal_features` | NOT-BUILT | always on |
| `embeddings.semantic_weight` | BUILT-DIFFERENTLY | constant `DEFAULT_SEMANTIC_WEIGHT=0.9`, not spec's 0.5; not config-driven |
| `embeddings.temporal_weight` | BUILT-DIFFERENTLY | derived as `1 - semantic_weight` |
| `boundaries.exclude_paths` | BUILT-DIFFERENTLY | implemented as `filtering.boundary.exclude_paths` |
| `session.default_suggestions` | BUILT | `session.default_suggestions` → `--count` default |
| `session.novelty_window_days` | BUILT-DIFFERENTLY | moved to `filtering.novelty.window_days` |
| `session.diversity_threshold` | BUILT-DIFFERENTLY | moved to `filtering.diversity.threshold` |
| `quality.min_length` | BUILT-DIFFERENTLY | moved to `filtering.quality.min_length` |
| `quality.max_length` | BUILT-DIFFERENTLY | moved to `filtering.quality.max_length` |
| `quality.check_repetition` | BUILT-DIFFERENTLY | always on in `filter_quality`; not a config toggle |
| `geist_execution.timeout` | BUILT | config-then-`--timeout`-override |
| `geist_execution.max_failures` | BUILT | drives geist_status disable threshold |
| `geist_execution.execution_mode` | NOT-BUILT | only serial exists; amend spec |
| `filtering.strategies` | NOT-WIRED | order fixed in `get_default_filter_config`; not user-config-driven |
| `filtering.boundary.enabled` | BUILT | honoured by `filter_boundary` |
| `filtering.novelty.enabled` | NOT-WIRED | default on; no config toggle plumbed |
| `filtering.novelty.method` | NOT-WIRED | `embedding_similarity`/`text_match` exist; default only |
| `filtering.novelty.threshold` | BUILT | `filtering.novelty.threshold` |
| `filtering.diversity.enabled` | NOT-WIRED | default on |
| `filtering.diversity.method` | NOT-WIRED | default only |
| `filtering.diversity.threshold` | BUILT | `filtering.diversity.threshold` |
| `filtering.quality.enabled` | NOT-WIRED | default on |
| `filtering.quality.checks` | NOT-WIRED | length+repetition always run |
| `tracery.max_depth` | NOT-BUILT | hardcoded `max_depth=50`; amend spec |
| `tracery.enable_vault_functions` | NOT-BUILT | always enabled |
| `metadata_inference.enabled_modules` | BUILT-DIFFERENTLY | flattened to top-level `enabled_modules` (shared with vault_functions) |
| `metadata_inference.cache_per_session` | BUILT-DIFFERENTLY | always cached (`_metadata_cache`); not a toggle |
| `metadata_inference.verify_on_launch` | NOT-BUILT | conflicts detected at load regardless |
| `vault_functions.enabled_modules` | BUILT-DIFFERENTLY | flattened to top-level `enabled_modules` |
| `logging.benchmark` | NOT-BUILT | timings via `--debug`/`GeistExecutionProfile`, not persisted |
| `logging.errors` | BUILT-DIFFERENTLY | console + `geist_status.last_error`; no `errors` toggle |
| `logging.test_commands` | BUILT-DIFFERENTLY | repro command embedded in console error text |
| `logging.log_file` | NOT-BUILT | no file logging; amend spec (console only) |

Live config keys NOT in the spec (added since): `enabled_modules`,
`session_embedding_retention`, `clustering.*`, `vector_search.*`,
`date_collection.*` — these are documented in `docs/example_config.yaml`.

## Other concrete spec promises

| item | spec | status |
|---|---|---|
| `geist_status` failure-persistence table | geistfabrik_spec.md:1090 | BUILT (schema v8) |
| `session_embeddings.cluster_label` | (cluster_evolution_tracker) | BUILT (schema v7) |
| GraphPatternFinder showcase geists (structural holes / path length / bridges) | reuse_abstractions_spec.md:1120 | BUILT (examples/geists/code/) |
| `_geistfabrik/error.log` + file logging | geistfabrik_spec.md:1107 | NOT-BUILT — superseded by console hints + `geist_status.last_error`; amend spec |
| Real connected-components stat | STATS_COMMAND_SPEC.md:181 | BUILT (uses GraphPatternFinder.find_connected_components) |
| `claim_harvester` / `hypothesis_harvester` geists | reuse_abstractions_spec.md (items 12-13) | BUILT (bundled default geists) |
| Betweenness-centrality bridge stat; "most productive day" temporal pattern | STATS_COMMAND_SPEC.md:217 | NOT-BUILT — defer; mark in spec |
| `geistfabrik sync` / `query` commands; `--session-id` | JOURNAL_FILES.md:746,797 | NOT-BUILT — amend docs (sync is implicit; `--date` covers query) |
| docs/CONFIGURATION.md | several | BUILT |
| docs/TROUBLESHOOTING.md (+ other named docs) | several | NOT-BUILT — write before 1.0 |
| bandit security scan | acceptance_criteria.md:498 | BUILT (CI + validate.sh, B608 skipped w/ rationale) |
| mkdocs build | acceptance_criteria.md:495 | NOT-BUILT — plain-markdown docs; amend AC |
| Unlocked-geist list items 1,2,5-10,15-21,23,24,30 | reuse_abstractions_spec.md:1088 | DEFERRED — list is "possible", not promised; mark aspirational |
| Cluster functions (contrarian/temporal/bridge/tag_clusters) | tracery_research.md:845 | DEFERRED — post-1.0 |
| HDBSCAN cosine metric | TODO.md | DEFERRED — needs real-vault evaluation |
| Timeout default 5s | geistfabrik_spec.md:856 | BUILT-DIFFERENTLY — 30s (production data); amend spec |
| invoke write-by-default | spec/vision | BUILT-DIFFERENTLY — preview-by-default + `--write` (safer) |
