# Lifecycle repair evidence

The [repair explanation](../../../docs/WORD_BURST_LIFECYCLE_REPAIRS.md) describes
contracts, tradeoffs and limitations. Measurements in this directory bind their
runtime source hashes and input manifests; an uncommitted source hash is not
silently relabelled as another revision.

## Revisions and interpretation

Measured production bytes are committed at
`c624c2e57ccbda3b02b2090405c980f481e328d6`; controls use
`b8e0ddb217092299d821bdd4d89b7e82fb824ef4`. `runtime-manifest.json`
contains every final production Python hash. Some raw reports recorded Git HEAD
as the baseline while the repaired files were uncommitted: their source hashes,
not that incidental HEAD value, identify the measured implementation.
`summary.json` maps those bytes to the later source commit. The evidence commit
only adds reports and documentation.

Timings are one sequential trial per arm with numerical library threads limited
to one. They are descriptive, not statistically significant speedup claims.
Fresh unrestricted analysis processes provide the comparable time/RSS controls.
Post-executor verification retains additional finding arrays and is not a fair
memory comparison. Default-budget invocation peaks are reported separately.
Peak RSS includes the Python runtime and loaded libraries.

## Receipts

- [Summary](summary.json), [production hashes](runtime-manifest.json) and
  [artifact hashes](artifact-sha256.json).
- `selection-{before,after}.json.xz`: same 12-week fixture and 30 seeds.
  Native generated Markdown: [before](before.md), [after](after.md).
- `stress-triples-{before,after}.json.xz`: actual default-timeout executor runs.
  `unbounded-{before,after}.json.xz`: fresh isolated unrestricted controls.
- `narrative-{dated_cohorts,observed_additions}-{before,after}.json.xz`:
  actual offline CLI, filtering, selection and writes, all 45 bundled geists.
- `temporal-{smoke,standard,large}-after.json.xz`: real embeddings and the
  13-geist temporal/similarity suite, with both word-burst modes. Smoke and
  standard cover 32 snapshots; large covers only the first two.
- `public-kepano.json.xz`: ten-note public snapshot, all 45 bundled geists.
  Its five obsolete managed-plugin examples are excluded from the fresh
  notes-only copy; the original fixture is unchanged. Word-burst abstains
  because the selected window has no eligible documents.
- `history-review.json.xz`, `analysis-review.json.xz`: independently authored
  implementation-only probes, results and final verdicts. Intermediate failing
  results remain labelled. The final analysis review covers hash `6fa9cbc7…`;
  the earlier test audit covers the equivalent preceding guard `5160b5da…`.
- `validation-final.json` and `test-logs.json.xz`: full validation and regression
  receipts. Baseline failures were inspected as intended assertions, not setup
  or import errors. The old implementation lacks the new checkpoint API, so
  unsupported calls were not counted as defect reproductions.
- [Unrated usefulness packet](usefulness-review/review.md): 12 partially masked
  comparisons, as-of-session contexts, blank rating sheet and answer key.
  Fictional coherence does not establish usefulness for an authentic owner.

Decode a receipt with `xz -dc <file.json.xz>`. The review/reproducer archives
are JSON objects mapping filenames to complete text; ordinary reports are
their original JSON documents.

## Reproduction and fixture boundaries

`reproducers.json.xz` retains the exact workspace harnesses. They use absolute
paths for the preserved corpora and old checkout; adapt those paths when moving
them. No private vault, SQLite database, model cache or credential is bundled.
The repository's `scripts/evaluate_narrative_vault.py` and
`scripts/benchmark_temporal_geists.py` remain the principal corpus entrypoints.
Use `--real-embeddings --similarity-suite` for the temporal run and
`--snapshot-limit 2` for its measured large prefix. The narrative authoring
inputs must be compiled before replay; their frozen compiled manifest matches
SHA-256 `4dfd127db8611992eed861f237f4a170a018c17dda4d94be39daa8a4c266424b`.

The stress fixture has 10,000 unchanged Markdown files (46,637,507 bytes),
821,664 dictionary terms and 104 weekly bins. It was prepared using production
extraction version 7. The retained synthetic cohort-date overlay was reapplied
after a full sync correctly removed database-only dates. Analysis measurements
exclude corpus setup, extraction and embedding inference. Identical analysis
inputs hash to
`f799ad3746caa9d41e9398ce0e10a700473ff6ac4dbda1bca2c1bb50853aeadc`.
The fixture's dates are benchmark metadata, not authentic historical claims.

Failed orchestration attempts (missing harness import path, using uncompiled
narrative inputs and trying to initialize over an existing managed directory)
are classified in `run-notes.json`. Their corrected reruns are the reported
measurements. Initial sandbox dependency-download failures were followed by a
complete validation run with public dependency downloads enabled.

Resuming optional trigrams repeats population collection and loses local series
caches: 97.85 seconds over four default-budget invocations versus 39.27 seconds
unrestricted. Collection/backfill/evidence binding are not cooperatively
checkpointed. A larger explicit timeout can still be necessary, and changing
inputs invalidate progress. The single-policy fixture does not measure storage
growth from retaining several policy histories. Trigrams remain optional.
