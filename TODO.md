# TODO / Deferred Work

Tracked items that are deliberately not done yet, with enough context to pick
up later. Add to this list rather than letting "what's left" live only in chat
or commit messages.

## Correctness / semantics decisions (need a real-vault judgement call)

### HDBSCAN runs Euclidean distance on non-unit vectors

`VaultContext.get_clusters()` and `ClusterAnalyser` (and
`embedding_metrics`) run `sklearn.cluster.HDBSCAN` with its **default
Euclidean metric**. When this item was written they clustered the raw 387-dim
session embeddings, whose norms vary (≈ 0.90–1.04), so Euclidean distance was
not a monotone function of cosine distance and cluster boundaries were partly
*magnitude*-shaped, while every other part of the engine (`neighbours`,
`similarity`, `find_similar`) defines "semantic closeness" as **cosine**.

**Status update:** clustering now uses only the 384 meaning dimensions
(`semantic_vectors.py`). The bundled model ends in a `Normalize` module
(`models/all-MiniLM-L6-v2/modules.json`), so every meaning vector is a unit
vector scaled by the 0.9 semantic weight; with equal norms, Euclidean distance
is monotone in cosine. The concern now applies only to injected or
non-normalising embeddings. Re-check before acting on the fix below.

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

## Evidence-gated infrastructure ideas

- [ ] Share only the pure HDBSCAN partitioning rule between metrics and
  `VaultContext`; keep their caches and history-writing responsibilities
  separate.
- [ ] Evaluate cosine versus Euclidean clustering on real vaults before
  changing it.
- [ ] Measure how often the bundled model's 256-token truncation loses
  meaningful content before proposing chunking.
- [ ] Add exact model-artifact identity to cache provenance before changing
  models.
- [ ] Measure repeated model construction during invocation, then inject one
  command-scoped model if the cost is real. Do not introduce a process-global
  singleton.

## Engineering hardening (mechanical, lower-risk)

- **`OMP_NUM_THREADS` etc.** — done for encode() via threadpoolctl; if any
  other native-thread hotspot appears, scope it the same way rather than
  re-introducing global env mutation.
- **All-geists contract suite + vault builder** — one parametrised test over
  the geist registry (list-of-Suggestion, correct `geist_id`, no journal
  refs, same-seed determinism) so every new geist is auto-covered. The vault
  builder now exists (`tests/fixtures/helpers.py::VaultBuilder`). Mutation
  testing was considered and rejected ("Prove a Test Can Fail, Without
  Mutation Testing" in LESSONS_LEARNED.md); the firing and hygiene gates
  cover "code runs, assertions absent" instead.
- **Lift `Suggestion` invariants into `__post_init__`** (non-empty text,
  `notes: list[str]`, non-empty `geist_id`) and delete the per-file
  `isinstance`/`hasattr` assertion blocks.
- **`datetime.now()` test sweep** — remaining fixtures should pin the session
  date (session season is a stored calendar feature, and age-, anniversary- and
  season-based geists read the date; wall-clock fixtures drift).
- **Property tests** for the markdown/Tracery/filtering trust boundaries.


## Specified-but-not-built — remaining (see specs/SPEC_STATUS.md for full ledger)

Fixed this round: exclude_paths + filtering/timeout/session config wiring,
enabled_modules allowlist, real connected-component stat, claim/hypothesis
harvesters, docs/CONFIGURATION.md, bandit in CI, spec-sync + dead-link guards.

Remaining, lower-value:
- **Amend the spec** (not bugs - reconcile the doc): embeddings.*, tracery.*,
  logging.* config keys; geist_execution.execution_mode; 5s->30s timeout;
  invoke preview-by-default. SPEC_STATUS.md records each; edit the spec text.
- **Historical `--session-id` references** — keep historical specifications
  clearly labelled; current operational docs use `--date` and implicit sync.
- Betweenness-centrality bridge stat; "most productive day" temporal pattern -
  defer; mark in STATS_COMMAND_SPEC.md.

## Notes

- Pre-1.0 API consistency pass: **done** (neighbours spelling, `count`
  parameters, typed `get_clusters()`, `obsidian_link` → `link_text`) — see
  CHANGELOG breaking-changes.
- Auto-disable after N failures: **done** via the `geist_status` table +
  `GeistStatusStore` (persistent, consecutive-failure semantics).
- Acceptance-criteria drift gate: **done**. `scripts/check_phase_completion.py`
  now *runs* every machine-verifiable criterion (no ✅-trust, no silent drop),
  is wired into `validate.sh` and CI, and `specs/acceptance_criteria.md` is
  reconciled. The verifier reports current AUTO/MANUAL counts; the MANUAL entries are the honest ledger
  of criteria without a dedicated automated test - a standing backlog if anyone
  wants to convert perf/journal-writer/session-date items into real tests.
