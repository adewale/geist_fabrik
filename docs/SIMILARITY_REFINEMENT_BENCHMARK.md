# Shared semantic primitives: refinement measurements

This follow-up reduces the cost of canonical neighbourhoods and unchanged
embedding computation introduced in the [first pass](SIMILARITY_PRIMITIVES_BENCHMARK.md).
It preserves that pass's canonical scoring, stable tie policy and sampling.
It adds no dependency, approximation or semantic coverage cap.

## Method

Baseline: `201acf98162ee03272783143249106425cf19836`. Both revisions already
have prepared-state APIs, so both benchmark invocations use `--phase after`.
The runtime file manifests identify the exact measured candidate; the receipt
links them to the final source commit. The harness asserts that source does
not change during each measurement. The final before/after harness hashes match.
Preliminary measurements made before the final resource cleanup are excluded.

All 17 feature cases use the same fixtures, Python 3.12 environment, NumPy and
bundled MiniLM model, with seed 20261018 and one BLAS thread. Each has five
timed samples and a separate traced-allocation sample in its own process.
Model construction and prepared fixtures are outside timing except where those
are the feature being measured. Hashing numerical output is outside timing.
Raw samples, reachable owned state, work counters and process RSS accompany
medians. Traced allocation and lifetime peak RSS measure different things;
RSS includes imports, models, fixtures and native allocations. Neither is a
complete attribution of memory to one operation. MiB means 1,048,576 bytes.

Corpus replays use application thread settings, all 32 smoke/standard snapshots
and only the first two large snapshots. Timings are workload observations,
not confidence intervals or promises of whole-application speedup. Final
measurements run sequentially. A standard baseline that overlapped the focused
lifecycle regression is replaced with an isolated replay in the final evidence.

## All feature measurements

| Feature | Time before → after, ms | Peak traced allocation before → after, MiB | Process peak RSS before → after, MiB |
| --- | ---: | ---: | ---: |
| Prepare 10,000 × 384 rows (cold) | 104.450 → 161.951 | 62.383 → 62.408 | 898.3 → 902.4 |
| Canonical 1,000 × 1,000 scores | 139.232 → 177.987 | 7.669 → 7.669 | 836.4 → 833.6 |
| Certified 1,000 × 1,000 threshold | 43.873 → 58.690 | 4.955 → 5.079 | 825.6 → 825.1 |
| Fully ambiguous 256 × 256 threshold | 10.261 → 9.947 | 3.752 → 3.815 | 822.9 → 821.4 |
| 1,000 corresponding pairs | 0.539 → 0.533 | 0.010 → 0.010 | 817.8 → 820.1 |
| 20 queries × 10,000, top 10 | 30.352 → 17.381 | 5.063 → 4.192 | 942.2 → 944.3 |
| Canonical mean, 1,000 rows | 152.210 → 142.355 | 0.020 → 0.018 | 821.8 → 819.3 |
| Mean threshold, 1,000 rows | 19.693 → 10.635 | 1.839 → 1.833 | 821.6 → 822.1 |
| Canonical surprisal, 1,000 rows | 110.656 → 82.082 | 8.883 → 8.382 | 831.0 → 829.6 |
| Stream threshold pairs, 1,000 rows | 43.540 → 30.192 | 1.688 → 1.734 | 822.0 → 819.1 |
| Stream scored top 10 pairs, 1,000 rows | 41.963 → 32.510 | 1.685 → 1.730 | 819.6 → 821.7 |
| 112 text requests, 64 unique | 372.454 → 338.626 | 1.941 → 1.941 | 919.6 → 916.8 |
| Label four clusters twice | 413.087 → 466.484 | 0.443 → 0.441 | 908.4 → 907.8 |
| Novelty + diversity, 72 candidates | 838.020 → 859.891 | 1.581 → 1.581 | 922.9 → 925.3 |
| Exact duplicate/zero threshold, 256 rows | 10.559 → 0.203 | 2.580 → 0.815 | 822.9 → 817.8 |
| Duplicate/zero top-k, 20 × 256 | 9.317 → 0.645 | 0.680 → 0.205 | 824.1 → 817.7 |
| Unchanged Session, 1,000 notes | 21.188 → 1.618 | 3.587 → 0.132 | 835.8 → 836.7 |

## Work and memory effects

Partial top-k selection sorts only the winning frontier. Certified bounds also
prune against the existing canonical kth winner. A later exact tie loses by
collection order; nonidentity ambiguous ties still require canonical scoring.
Surprisal/churn request indices directly rather than materializing Python
score tuples. Collision-verified root IDs accelerate identity handling;
distinct nonzero root populations need only overlap correction between views.

Exact duplicate/zero tiles bypass BLAS and canonical refinement. The harness's
legacy `fast_pairs` counter counts cells presented to the estimate API, even
when this shortcut avoids multiplication. It must not be interpreted as actual
BLAS work. The resource owner forbids the real NumPy numeric kernels on this
population, and public work diagnostics report zero numeric pairs.

Unchanged computation keeps its accepted exact input manifest and database
change token. It skips inference, vector combination/serialization, backend
invalidation and writer-lock acquisition. The 1,000-note fixture changes
**2,001 SQLite row changes to zero** and preserves backend identity. Reopened Sessions
still validate and compose inputs; conditional UPSERTs avoid rewriting identical
BLOBs and preserve labels. A vector, membership or hash change clears every
label because the partition describes the whole population.
Both revisions already encode zero texts on this unchanged path; the new gain
comes from avoiding composition, serialization, writes and projection reloads.

The 1,000-note Session fixture's reachable owned state increases from
4.853 to 5.140 MiB. The exact manifest retains text references while its Session is open and adds
metadata proportional to note count. It is released on Session.close, including
when the embedding computer is injected. This is an O(N) input comparison,
not a filesystem watcher or constant-time check. A new Session cannot inherit
the in-memory accepted token. Unrelated connection writes conservatively force
full validation; external commits reject the stale Session. Retention-setting
changes also invalidate the shortcut. All persistent changes remain atomic.
Separate CLI processes do not inherit this token. The same-Session latency gain
therefore does not describe command startup; conditional writes still avoid
rewriting identical vectors when a Session is reopened.

The explicit exact-cell mask adds temporary allocation to ordinary threshold
work. Completely ambiguous nonidentity thresholds still pay for both kernels.
The extra mask is a deliberate cost, not a claim that every feature improves.
Salted process-local hash keys remain collision-checked and never persist.
Reachable owned prepared state for 10,000 rows changes from 31.305 to 31.253 MiB; the warmed backend changes from 48.331 to 48.279 MiB. This is a metadata-size reduction, not a reduction in the normalized float64 payload.

Alternating ABBA mean follow-up (30 timed samples per revision): before median 145.650 ms, range 137.408–165.742 ms, after median 131.698 ms, range 127.058–146.591 ms.

Alternating ABBA follow-up for variable cold/dense timings (30 timed samples per revision):

| Feature | Median before → after, ms | Before range, ms | After range, ms |
| --- | ---: | ---: | ---: |
| prepare | 166.925 → 78.304 | 97.294–527.494 | 65.510–431.518 |
| canonical_matrix | 138.561 → 136.301 | 128.718–230.421 | 127.402–179.929 |
| threshold_matrix | 44.417 → 45.246 | 41.152–53.204 | 41.863–51.406 |

The five-sample table is retained intact. Its candidate cold samples span 93.2–739.6 ms. The alternating follow-up tests timing stability with unchanged source and fixtures; it does not establish a whole-application speedup. Extra threshold masks still account for the measured allocation increase regardless of timing variation.

First computation in a new Session, with persistent semantic vectors already
cached and no model inference (ABBA order, 14 timed samples per revision):

| Notes | Time before → after, ms | Peak traced allocation before → after, MiB | SQLite changes before → after |
| --- | ---: | ---: | ---: |
| 1,000 | 20.749 → 22.454 | 3.587 → 3.786 | 1,001 → 1,001 |
| 10,000 | 211.503 → 245.267 | 38.299 → 40.288 | 10,001 → 10,001 |

This separates manifest/persistence work from encoder variability. A new
Session still composes and inserts its population: zero-write/early-return
claims apply to unchanged accepted state, not first-time insertion. The probe
source and raw samples are losslessly archived. Its output digests agree.
Allocation columns are medians of two separate traced trials per revision.

The 10,000-note new-Session case costs 33.8 ms more (16.0%) and about 1.99 MiB
more traced allocation. Capturing the exact manifest and checking conditional
persistence add work before any reuse can pay it back. A caller that computes
once per Session pays this setup cost; repeated unchanged calls amortize it.

## Corpus results

| Corpus | Snapshots | Attention shift, s | Surprisal, s | Unchanged embedding check, s |
| --- | ---: | ---: | ---: | ---: |
| smoke (128 initial notes) | 32 | 1.625 → 0.814 | 0.368 → 0.308 | 0.452 → 0.104 |
| standard (1,000 initial notes) | 32 | 14.367 → 9.968 | 3.881 → 4.012 | 2.675 → 0.658 |
| large (10,000 initial notes) | 2 | 0.000 → 0.000 | 22.164 → 14.873 | 1.770 → 0.861 |

| Corpus | Unchanged SQLite changes | Process peak RSS, MiB |
| --- | ---: | ---: |
| smoke | 11,184 → 0 | 1005.4 → 998.7 |
| standard | 74,048 → 0 | 1083.4 → 1068.4 |
| large | 40,608 → 0 | 1287.4 → 1282.8 |

Standard-corpus surprisal is 3.4% slower in this replay, despite the isolated
and large-corpus gains. These runs do not isolate the cause of that small
reversal. The complete measurements retain it rather than claiming every
workload improved. Process RSS differences likewise include model/runtime
variation and are not attributable entirely to the changed primitives.

Each revision completed **924 successful executor calls** across these profiles.
No lexical finding or suggestion changed, including observed-additions prompts.
Stable semantic controls remained unchanged. Initial embedding inference still
dominates much of the replay. Corpus no-op timing includes loading notes from
SQLite; the isolated 1,000-note case already owns its input Note list. Their
speedup ratios describe different boundaries.

The old original-directory and Kepano lexical-only controls remain documented
in the first-pass report. They were not rerun here: this pass changes semantic
primitives and Session persistence, while the lexical detector/index is unchanged.
The large temporal probe covers two snapshots, not the complete 32-snapshot
trajectory. This is a scale check with full smoke/standard temporal coverage.

All fourteen measured geist/mode execution totals (seconds, before → after):

| Geist | Smoke | Standard | Large (2 snapshots) |
| --- | ---: | ---: | ---: |
| word_burst | 0.510 → 0.455 | 1.403 → 1.455 | 0.154 → 0.347 |
| concept_drift | 4.589 → 3.842 | 12.804 → 12.368 | 0.777 → 0.555 |
| attention_shift | 1.625 → 0.814 | 14.367 → 9.968 | 0.000 → 0.000 |
| temporal_drift | 3.760 → 3.387 | 20.499 → 17.872 | 9.659 → 10.285 |
| recent_focus | 0.181 → 0.202 | 0.783 → 0.664 | 0.217 → 0.300 |
| seasonal_patterns | 0.155 → 0.127 | 0.208 → 0.152 | 0.019 → 0.018 |
| temporal_clustering | 0.052 → 0.042 | 0.485 → 0.594 | 0.223 → 0.261 |
| this_time_last_year | 0.005 → 0.005 | 0.010 → 0.008 | 0.002 → 0.002 |
| density_inversion | 0.012 → 0.014 | 0.028 → 0.023 | 0.002 → 0.002 |
| concept_cluster | 0.095 → 0.072 | 0.153 → 0.213 | 0.020 → 0.019 |
| bridge_builder | 0.364 → 0.541 | 0.421 → 1.342 | 0.059 → 0.051 |
| method_scrambler | 2.378 → 1.266 | 3.314 → 2.702 | 0.143 → 0.191 |
| surprisal | 0.368 → 0.308 | 3.881 → 4.012 | 22.164 → 14.873 |
| word_burst:observed_additions | 0.172 → 0.145 | 0.586 → 0.719 | 0.000 → 0.001 |

Stage totals (seconds, before → after):

| Stage | Smoke | Standard | Large (2 snapshots) |
| --- | ---: | ---: | ---: |
| Initial/changed embedding computation | 36.412 → 39.486 | 253.412 → 238.163 | 226.172 → 234.948 |
| Context construction | 0.215 → 0.164 | 1.437 → 0.899 | 0.604 → 0.668 |
| Changed corpus sync | 5.203 → 5.073 | 31.338 → 30.563 | 38.192 → 41.593 |
| Unchanged corpus sync | 1.458 → 1.404 | 11.668 → 11.020 | 5.842 → 5.636 |

Attention shift abstains in the two-snapshot large probe because it needs more history. Encoder/model, clustering and lexical algorithms are unchanged in this pass; variations in their totals and process RSS are observations, not isolated causal speedups or memory savings.


## Numerical and output checks

All numerical output digests match the baseline, including canonical
surprisal values and top-k result ordering. The preparation result's reachable
owned-byte count changes with metadata representation; unchanged-session
results deliberately change their write count and backend-retention outcome.
Those are the only differing result fields in the feature reports.

All **60,172 persisted embedding rows** match byte for byte across the
three replay comparisons, including temporal channels; joined row counts equal
both databases' row counts. Both history modes' lexical findings and all
suggestion lists match. Fresh injected float64 semantic results intentionally
round to the persistent float32 representation *before* composition, fixing an
uncached/cache discrepancy. The bundled model already returns float32, so its
corpus output bytes do not change.


## Verification and reproducibility

`scripts/validate.sh` completed successfully in 432.6
seconds, including strict mypy/ty, lint/security/database checks, unit and
integration suites, acceptance criteria, branch coverage, workflow lint and
installed-wheel real-model offline inference. The full log and status are
archived with the raw measurements. The gate passed **1,913 unit tests, 81 integration tests, 155/155 automated criteria and 82.58% branch coverage**, with one existing unit skip. Platform-specific GitHub jobs remain
separate from this Linux validation.

An earlier gate attempt passed unit/integration/acceptance checks but could not
fetch workflow-lint and build dependencies under network isolation. The final
gate runs with dependency-download access; installed-wheel inference itself is
still checked offline. The earlier failed log/status are also archived.

| Changed test owner | Tests | Pytest suite, s | Command wall, s |
| --- | ---: | ---: | ---: |
| tests/unit/test_embeddings.py | 56 | 0.703 | 7.341 |
| tests/unit/test_vector_primitives.py | 54 | 4.660 | 11.096 |

These are local costs, not measured CI runner seconds. Process startup/imports
are included in wall time. Hypothesis remains the existing Python PBT engine;
Hegel supplies adversarial, domain and surface guidance. Independent reviewers
read production contracts without tests or measurements; the Openclaw audit
keeps numerical and storage/lifecycle contracts at their primary owners.

Changed-line footprint relative to `201acf9` (not a quality score):

| Area | Added lines | Removed lines |
| --- | ---: | ---: |
| Production | 334 | 80 |
| Tests | 346 | 19 |
| Benchmark harness | 76 | 4 |


Reproduce the 17 feature cases with the current harness and locked environment:

```bash
git worktree add --detach ../geist-primitives-regressions-before 201acf98162ee03272783143249106425cf19836
.venv/bin/python scripts/benchmark_similarity_primitives.py \
  --source ../geist-primitives-regressions-before --phase after --trials 5 --output /tmp/refinement-before.json
.venv/bin/python scripts/benchmark_similarity_primitives.py \
  --source . --phase after --trials 5 --output /tmp/refinement-after.json
```

Materialize model LFS files in each checkout. For corpus runs, select each
package source with PYTHONPATH and run `scripts/benchmark_temporal_geists.py`
with `--real-embeddings --similarity-suite`, a fresh owned vault and the unchanged
smoke/standard manifest; add `--snapshot-limit 2` for large. Run performance
measurements sequentially. The lossless receipt and raw reports in
`benchmarks/results/similarity_refinement_*` retain source/harness hashes,
individual samples, output comparisons and validation status.


The [contract guide](SIMILARITY_PRIMITIVES.md) explains the enclosure and pruning
arguments; the [test audit](SIMILARITY_PRIMITIVES_TEST_AUDIT.md) records blind
review findings, owner boundaries, baseline failures and resource proof.
