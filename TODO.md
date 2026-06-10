# TODO / Deferred Work

Tracked items that are deliberately not done yet, with enough context to pick
up later. Add to this list rather than letting "what's left" live only in chat
or commit messages.

## Correctness / semantics decisions (need a real-vault judgement call)

### HDBSCAN runs Euclidean distance on non-unit vectors

`VaultContext.get_clusters()` and `ClusterAnalyser` (and
`embedding_metrics`) run `sklearn.cluster.HDBSCAN` with its **default
Euclidean metric** over the raw 387-dim session embeddings. Those vectors are
**not unit-norm** (measured norms ≈ 0.90–1.04), so Euclidean distance is not a
monotone function of cosine distance — meaning cluster boundaries are partly
*magnitude*-shaped, while every other part of the engine (`neighbours`,
`similarity`, `find_similar`) defines "semantic closeness" as **cosine**. Two
notes the rest of the system treats as near can therefore land in different
clusters.

- **Fix is one line** — either `HDBSCAN(..., metric="cosine")` (newer sklearn)
  or L2-normalise the matrix before `fit_predict` (Euclidean on unit vectors
  *is* monotone in cosine).
- **Why it's deferred:** this **changes existing cluster outputs** — cluster
  membership, labels, `session_embeddings.cluster_label` history, and the
  `stats` clustering metrics. Per the "quality > speed / measure before you
  change" lesson, **this needs to be verified against a real vault** (compare
  cluster quality — silhouette, label coherence, and eyeballed groupings —
  before vs after on an actual user vault, not synthetic/stub data) before
  committing to the change. Treat as a deliberate, evaluated decision, not a
  drive-by fix.
- Files: `src/geistfabrik/vault_context.py` (`get_clusters`),
  `src/geistfabrik/clustering_analysis.py` (`_cluster_hdbscan`),
  `src/geistfabrik/embedding_metrics.py`.

## Engineering hardening (mechanical, lower-risk)

- **`OMP_NUM_THREADS` etc.** — done for encode() via threadpoolctl; if any
  other native-thread hotspot appears, scope it the same way rather than
  re-introducing global env mutation.
- **All-geists contract suite + vault builder** — one parametrised test over
  the geist registry (list-of-Suggestion, correct `geist_id`, no journal
  refs, same-seed determinism) so every new geist is auto-covered; plus a
  `make_vault_context()` builder to replace per-file vault plumbing.
- **Lift `Suggestion` invariants into `__post_init__`** (non-empty text,
  `notes: list[str]`, non-empty `geist_id`) and delete the per-file
  `isinstance`/`hasattr` assertion blocks.
- **`datetime.now()` test sweep** — remaining fixtures should pin the session
  date (session-season is an embedding feature; wall-clock fixtures drift).
- **Nightly mutation testing** (`mutmut`) on `filtering.py`, `vault_context.py`,
  `tracery.py`, and a sample of geists — the tool that mechanically detects
  "code runs, assertions absent" (how the dead geists shipped green).
- **Property tests** for the markdown/Tracery/filtering trust boundaries.


## Specified-but-not-built — remaining (see specs/SPEC_STATUS.md for full ledger)

Fixed this round: exclude_paths + filtering/timeout/session config wiring,
enabled_modules allowlist, real connected-component stat, claim/hypothesis
harvesters, docs/CONFIGURATION.md, bandit in CI, spec-sync + dead-link guards.

Remaining, lower-value:
- **Amend the spec** (not bugs - reconcile the doc): embeddings.*, tracery.*,
  logging.* config keys; geist_execution.execution_mode; 5s->30s timeout;
  invoke preview-by-default. SPEC_STATUS.md records each; edit the spec text.
- **Wire check_phase_completion.py into CI and make it RUN acceptance checks**
  (today it skips items the spec marks done - the root cause of the drift).
- **`geistfabrik sync`/`query` commands, `--session-id`** - amend docs (sync is
  implicit; --date covers query) or add trivial aliases.
- Betweenness-centrality bridge stat; "most productive day" temporal pattern -
  defer; mark in STATS_COMMAND_SPEC.md.

## Notes

- Pre-1.0 API consistency pass: **done** (neighbours spelling, `count`
  parameters, typed `get_clusters()`, `obsidian_link` → `link_text`) — see
  CHANGELOG breaking-changes.
- Auto-disable after N failures: **done** via the `geist_status` table +
  `GeistStatusStore` (persistent, consecutive-failure semantics).
