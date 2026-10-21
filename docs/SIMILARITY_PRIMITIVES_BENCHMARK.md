# Shared semantic primitives: matched before/after measurements

The change replaces repeated normalization, identity lookup and full-matrix
reductions with immutable prepared state, batched queries, certified BLAS
comparisons and streamed reductions. It also shares a bounded exact-text
inference cache between sessions, labelling and filtering. This report records
benefits, costs and numerical/output effects together.

## Method and scope

Baseline: `32f9d0dba57dff1ebe983de4d894a7bffe443f92`. The changed runtime's exact
per-file SHA-256 manifest is in the raw after report and summary. Both revisions
use the same Python 3.12 environment, libraries and bundled CPU MiniLM model on
an Intel Xeon Platinum 8573C host. NumPy supplies BLAS; no new dependency or
approximate search engine is introduced.

Each of the 14 microbenchmarks runs in a separate process, with one BLAS thread,
seed 20261018, five timed repetitions and a separate allocation measurement.
The table reports median elapsed time. Prepared fixtures are outside the timed
region unless preparation itself is the measured feature. Numerical output
hashing is outside timing; the text-cache case includes requested output
materialization. Model loading is outside the inference/filter/label regions.
Those three cases perform actual bundled-model inference with a fresh computer
per repetition, so they measure reuse within a workload rather than an
artificially pre-filled cache. Raw timings are archived, not just medians.

Peak traced allocation is measured by `tracemalloc` around the operation. It
includes tracked NumPy buffers but does not account for every native model,
BLAS or allocator allocation. Process peak RSS is a separate lifetime high-water
mark, including imports, fixtures, the model, earlier repetitions and native
libraries. It cannot attribute an RSS change to the timed operation. Reported
MiB use 1,048,576 bytes. The 1 MiB score-tile budget is not an operation-wide
memory bound.

Real-corpus replays are sequential single runs using application thread settings
(OpenBLAS reported five threads). These are matched workload observations, not
confidence intervals or a promise of a proportional whole-application speedup.
The synthetic corpus manifests are unchanged. Smoke and standard replay all
32 snapshots; the 10,000-note temporal scale probe replays only the first two.

## All primitive features

| Feature | Time before → after, ms | Peak traced allocation before → after, MiB | Process peak RSS before → after, MiB |
| --- | ---: | ---: | ---: |
| Prepare 10,000 × 384 rows (cold) | 56.937 → 97.777 | 88.435 → 62.383 | 934.5 → 911.8 |
| Canonical 1,000 × 1,000 scores | 133.549 → 128.258 | 15.259 → 7.669 | 858.1 → 841.5 |
| Certified 1,000 × 1,000 threshold | 130.059 → 46.280 | 15.259 → 4.955 | 845.8 → 835.4 |
| Fully ambiguous 256 × 256 threshold | 6.975 → 9.877 | 1.001 → 3.752 | 834.8 → 832.9 |
| 1,000 corresponding pairs | 128.540 → 0.411 | 15.259 → 0.010 | 849.8 → 829.9 |
| 20 queries × 10,000, top 10 | 274.809 → 14.234 | 1.476 → 5.063 | 953.0 → 951.7 |
| Canonical mean, 1,000 rows | 136.530 → 134.603 | 19.066 → 0.020 | 852.6 → 831.4 |
| Mean threshold, 1,000 rows | 138.676 → 18.540 | 19.066 → 1.839 | 851.6 → 830.8 |
| Canonical surprisal, 1,000 rows | 24.134 → 100.698 | 35.242 → 8.883 | 875.9 → 841.0 |
| Stream threshold pairs, 1,000 rows | 182.462 → 37.364 | 15.259 → 1.688 | 850.1 → 831.2 |
| Stream scored top 10 pairs, 1,000 rows | 193.425 → 38.456 | 15.259 → 1.685 | 846.5 → 829.9 |
| 112 text requests, 64 unique | 663.128 → 318.692 | 1.858 → 1.941 | 937.7 → 929.3 |
| Label four clusters twice | 512.184 → 495.277 | 0.354 → 0.443 | 921.8 → 917.5 |
| Novelty + diversity, 72 candidates | 1200.262 → 782.428 | 1.930 → 1.581 | 938.2 → 936.8 |

Cold preparation is 1.72× slower: it constructs reusable identity/zero indexes
and immutable ownership. Its retained state falls from 58.99 to 31.31 MiB for
10,000 × 384 rows because the old object retained both normalized floats and
per-row identity payloads. The warmed 10,000-vector backend's owned state falls
from 90.07 to 48.33 MiB; this includes raw vectors, prepared directions and
indexes, not just the score tile. These are reachable-object byte counts with
shared buffers counted once, distinct from RSS and from the cache quota.

Batching trades temporary memory for throughput: the neighbour workload uses
5.06 MiB rather than 1.48 MiB of peak traced allocation. It normalizes 20 queries
in both versions, but identity-index work drops from 200,000 rows to 20, and
canonical rescoring drops from 200,000 pairs to 400. The remaining 200,000
estimates use BLAS. Canonical full-matrix scores still calculate all requested
pairs; the compatibility API does not silently change its score contract.

The deliberately ambiguous threshold workload runs both kernels for every
65,536 pair and is 1.42× slower, with higher temporary allocation. This is the
correct fallback cost. Canonical surprisal is 4.17× slower in this microbenchmark
while reducing peak allocation from 35.24 to 8.88 MiB. Its old independent
BLAS/argpartition policy was cheaper; the new path certifies neighbour selection,
returns canonical scores and stabilizes ties. Exact top-k with a completely tied
frontier can require scoring every candidate. Bounded tiles constrain working
memory, not worst-case arithmetic or the size of requested outputs.

The streamed scalar mean saves memory rather than materially accelerating its
fixed-order arithmetic. Mean decisions can use certified estimates when far
from the threshold. Threshold pair enumeration and scored top-k discovery avoid
retaining full matrices; the latter keeps a stable standard-library top-k heap.

## Text reuse and side effects

| Workload | Encoded texts before → after | Model calls before → after | Live accounted cache after |
| --- | ---: | ---: | ---: |
| Repeated text requests | 112 → 64 | 2 → 1 | 124,574 bytes |
| Four cluster labels, twice | 156 → 91 | 12 → 8 | 175,739 bytes |
| Novelty + diversity | 272 → 192 | 4 → 3 | 371,840 bytes |

The text cache has an 8 MiB default accounted retention quota per computer,
including text keys, row payload and a metadata allowance. This is not a whole
Python-object or RSS limit. Exact text remains in RAM until eviction/clear/close;
there is no new text persistence. Oversized rows are returned without retention.
Cache budget reductions evict immediately, model identity changes invalidate
state, and returned arrays cannot mutate retained payloads.

All canonical matrix, paired, top-k, threshold-mask, enumerated-pair and scored
pair output digests match in the microbenchmarks. The mean and its decision
match on this fixture. All 43,008 returned float32 coordinates in the repeated
text case match bitwise; labels match; filtering retains the same nine prompts
in the same order. Surprisal changes 599 of 1,000 results, with maximum absolute
difference 4.44e-16 on this random fixture, reflecting the explicit new numerical
policy rather than an approximate score API.

Cached inference changes batch membership. A fresh model can produce slightly
different float32 vectors for the same text in different batches. Retaining the
first vector improves within-computer repeatability, but does not promise
bitwise parity with fresh baseline inference. Corpus output changes below make
this distinction visible.


| Persisted semantic channels compared | Changed rows / compared rows | Largest absolute float32 coordinate difference |
| --- | ---: | ---: |
| smoke | 72 / 5,263 | 1.34e-07 |
| standard | 154 / 34,607 | 1.62e-07 |
| large | 0 / 20,302 | 0 |

Rows here are `(session date, note path)` pairs, so a reused vector can appear
in several sessions. Every row count agrees. Calendar channels are excluded
from this comparison. Standard and large raw prompts remain identical despite
the standard profile's small vector differences. Smoke changes only the two
prompt lists identified above. This is a measured numerical effect, not a claim
that changed batch membership can never affect a threshold or ranking.

## Corpus replays

Each revision completed 896 executor calls across the full smoke and standard
replays successfully,
including both lexical history modes. Stable control vectors never changed
across snapshots in either revision. The standard corpus returned identical
prompts in all 32 snapshots. The smoke corpus changed only the
`method_scrambler` prompt lists at snapshots 12 and 13; cached real-model
vectors can resolve nearly tied journal pairs differently from fresh inference.

| Geist (sum across 32 snapshots), seconds | Smoke before → after | Standard before → after |
| --- | ---: | ---: |
| `word_burst` | 0.397 → 0.437 | 1.393 → 1.371 |
| `concept_drift` | 2.338 → 3.711 | 9.638 → 11.646 |
| `attention_shift` | 0.446 → 0.974 | 5.309 → 12.898 |
| `temporal_drift` | 3.133 → 3.511 | 18.996 → 17.292 |
| `recent_focus` | 0.355 → 0.167 | 1.545 → 0.654 |
| `seasonal_patterns` | 0.100 → 0.094 | 0.186 → 0.189 |
| `temporal_clustering` | 0.074 → 0.046 | 1.127 → 0.403 |
| `this_time_last_year` | 0.005 → 0.005 | 0.009 → 0.008 |
| `density_inversion` | 0.122 → 0.013 | 0.172 → 0.020 |
| `concept_cluster` | 0.105 → 0.071 | 0.260 → 0.196 |
| `bridge_builder` | 0.277 → 0.234 | 0.489 → 0.364 |
| `method_scrambler` | 1.088 → 1.235 | 2.873 → 2.778 |
| `surprisal` | 0.213 → 0.527 | 2.948 → 4.305 |

These are raw `GeistExecutor` suggestions, before journal writing and the
whole-session filtering pipeline. Filtering has its own real-model measurement
above; prompt parity here does not assert byte-identical generated journals.
These totals include each geist's executor overhead. The `word_burst` row
shows dated-cohort execution; observed-addition execution is also measured
and retained in the raw reports and the call total. In these replays, prior
history calculations in `attention_shift` do not always have the same
population as later current surprisal work. Sharing current prepared state
does not remove the cost of canonical historical neighbourhoods. The unchanged
prompts do not turn those observed time regressions into speedups.

| Whole replay measure | Smoke before → after | Standard before → after |
| --- | ---: | ---: |
| Session embedding seconds | 31.445 → 31.879 | 224.390 → 215.959 |
| Context construction seconds | 0.099 → 0.206 | 0.906 → 0.899 |
| Sync seconds | 3.818 → 5.217 | 29.637 → 27.843 |
| Unchanged sync seconds | 1.239 → 1.394 | 12.502 → 9.106 |
| Unchanged session embedding seconds | 0.366 → 0.367 | 2.712 → 1.940 |
| Process peak RSS, MiB | 984.676 → 1014.082 | 1067.770 → 1076.242 |
| Encoded texts | 733 → 708 | 5,254 → 5,229 |
| Model calls | 32 → 32 | 32 → 32 |
| Peak accounted text cache, MiB | 0 → 1.799 | 0 → 8.000 |

On the standard replay the cache avoids only 25 of 5,254 encoded texts (0.48%).
The repeated-request microbenchmarks intentionally contain more reuse. Model
inference remains the dominant elapsed component; a 19× neighbour-query
microbenchmark improvement does not imply a 19× application speedup.

Every unchanged sync processes zero notes and performs zero lexical extractions
or dictionary changes. Every repeated `Session.compute_embeddings` call encodes
zero texts. It still writes session rows: 11,184 SQLite changes across smoke
and 74,048 across standard in both revisions. This change preserves that
existing persistence behavior; it does not claim a write-free session early exit.
The repeat-call times above include those writes.

### 10,000-note temporal scale probe

Both revisions completed 28 successful executor calls over the first two
snapshots. Every raw suggestion list matches; stable controls remain unchanged.
This probe does not exercise the later 180-day churn window at this scale.

| Geist, sum across two snapshots | Before, seconds | After, seconds |
| --- | ---: | ---: |
| `word_burst` | 0.505 | 0.157 |
| `concept_drift` | 0.365 | 0.919 |
| `attention_shift` | 0.001 | 0.000 |
| `temporal_drift` | 10.586 | 11.712 |
| `recent_focus` | 1.476 | 0.188 |
| `seasonal_patterns` | 0.016 | 0.037 |
| `temporal_clustering` | 0.712 | 0.242 |
| `this_time_last_year` | 0.002 | 0.002 |
| `density_inversion` | 0.012 | 0.002 |
| `concept_cluster` | 0.070 | 0.025 |
| `bridge_builder` | 0.158 | 0.175 |
| `method_scrambler` | 1.124 | 0.187 |
| `surprisal` | 5.205 | 23.527 |

Peak lifetime RSS is 1,506.83 → 1,284.16 MiB. Both revisions encode 11,203
texts in two model calls, so this scale probe does not show an inference-work
reduction. Surprisal is substantially slower: its 23.53 seconds above is the
sum of two executions, each below the existing 30-second limit. The reduction
in retained/index and centroid temporaries has a visible memory benefit at
this population; the stronger neighbourhood arithmetic has a visible time cost.

Unchanged sync and repeated session inference retain the same early-exit
semantics as the smaller profiles. The final summary records those times,
write counts, context cost and cache retention separately.

### Original corpus and small public control

The original benchmark directory contains the 10,000 stress notes plus its
91-byte `README.md`: both runs measure **10,001 Markdown files and 46,635,898
bytes**, with the same unchanged source manifest. With the original `10000 markdown files/` subdirectory as the relative-path
root, its 10,000 notes retain the previous 46,635,807-byte inventory and match
the previous `d361aa39…` manifest. These control timings therefore compare the same
inputs before/after here, but should not be treated as exact input matches to
the earlier README-excluded historical run. Raw undated analysis abstains;
the stress analysis uses an explicitly synthetic chronology, not recovered
historical prose. It returns the same finding digest and raw executor prompts
under both revisions. These are lexical controls without embedding inference.

| Original directory, including README | Before | After |
| --- | ---: | ---: |
| Cold sync, seconds | 94.951 | 102.613 |
| Unchanged sync, seconds | 3.162 | 3.471 |
| Fresh analysis, seconds | 25.534 | 24.786 |
| Cached analysis, seconds | 0.266 | 0.228 |
| Cached execution, seconds | 0.737 | 0.701 |
| Cache-cleared execution, seconds | 22.602 | 24.775 |
| 100-note edit sync, seconds | 6.373 | 4.682 |
| Peak process RSS, MiB | 1484.7 | 1485.9 |
| Managed database, MiB | 224.0 | 224.0 |

Both runs perform zero lexical extractions/changes on unchanged sync and
exactly 100 on the edit. Both fresh executor runs succeed within 30 seconds.
The lexical algorithm is unchanged here; timing variation in this control
is not attributed to semantic primitive optimization. Findings include rising
and declining words and phrases, with the same category counts in both runs.

The ten-note public Kepano control abstains for insufficient documents in
both runs. It retains identical source hashes and finding digests; all executor
calls succeed. Complete timings, memory and small-control edit counts are in
the archived raw reports. Its small population is a negative control rather
than evidence of detection quality at scale.

| Ten-note Kepano control | Before | After |
| --- | ---: | ---: |
| Cold sync, ms | 65.540 | 46.418 |
| Unchanged sync, ms | 4.079 | 3.829 |
| Fresh analysis, ms | 0.713 | 0.561 |
| Cached analysis, ms | 0.083 | 0.067 |
| Process peak RSS, MiB | 815.3 | 812.2 |

## Reproduce

Use the locked environment with the `vector-search` extra and materialized LFS
model files in both checkouts. Pin the historical after source and its harness
to `6555d6c`; the current harness now includes three additional follow-up cases.
Both baseline and after runs invoke that pinned harness while selecting the
package source with `--source` or `PYTHONPATH`. Current performance is reported
in the [refinement follow-up](SIMILARITY_REFINEMENT_BENCHMARK.md).
The source commit recorded for the uncommitted after run is its parent; the
per-file runtime manifest identifies the actual measured source bytes.

```bash
git worktree add --detach ../geist-primitives-before 32f9d0dba57dff1ebe983de4d894a7bffe443f92
git worktree add --detach ../geist-primitives-after-original 6555d6c547327d6c0abad55a7ab9312670c2d4d9
.venv/bin/python ../geist-primitives-after-original/scripts/benchmark_similarity_primitives.py \
  --source ../geist-primitives-before --phase before --trials 5 --output /tmp/before.json
.venv/bin/python ../geist-primitives-after-original/scripts/benchmark_similarity_primitives.py \
  --source ../geist-primitives-after-original --phase after --trials 5 --output /tmp/after.json
PYTHONPATH=../geist-primitives-before/src GEISTFABRIK_OFFLINE=1 \
  .venv/bin/python scripts/benchmark_temporal_geists.py \
  /path/to/temporal-corpus/standard /tmp/before-standard-vault \
  --real-embeddings --similarity-suite --output /tmp/before-standard.json
PYTHONPATH=../geist-primitives-after-original/src GEISTFABRIK_OFFLINE=1 \
  .venv/bin/python scripts/benchmark_temporal_geists.py \
  /path/to/temporal-corpus/standard /tmp/after-standard-vault \
  --real-embeddings --similarity-suite --output /tmp/after-standard.json
```

Repeat temporal runs with `smoke`; use `large --snapshot-limit 2` for the scale
probe. A replay destination must be a fresh owned directory. The original
corpus control uses `scripts/benchmark_word_burst.py CORPUS --trials 1
--ngram-max 2 --output REPORT` under each source selection. Run all measurements
sequentially, with no competing test or benchmark workloads. Do not mistake the
static lexical corpus control for a model-inference benchmark.

All six final temporal reports record the same harness SHA-256,
`a4b4035f6ae10ce8aaf187ad469eacc7cf0d39078948343ed7919033f48c2515`.
Both full-profile comparisons record `snapshot_limit: null`; the large reports
record `2`. All use the same 13-geist suite and both word-burst modes.

## Verification and evidence

The [shared-primitives guide](SIMILARITY_PRIMITIVES.md) specifies the score
contract and derives the error enclosure. The
[Hegel/Openclaw test audit](SIMILARITY_PRIMITIVES_TEST_AUDIT.md) records primary
owners, independent oracles, baseline red proofs, consolidation and local test
costs. Python properties use the existing Hypothesis dependency. Production-only
adversarial reviews drove numerical, lifecycle and resource-bound repairs before
benchmarking; the external canonical review status is reported separately.

Final evidence is under `benchmarks/results/`:

- [Archive receipt](../benchmarks/results/similarity_primitives_receipt.json):
  source commit, exact runtime manifest, raw/archive hashes and lossless checks.
- [Machine-readable summary](../benchmarks/results/similarity_primitives_summary.json):
  all profile totals, raw prompt differences and source identities.
- [Before microbenchmarks](../benchmarks/results/similarity_primitives_before.json.xz)
  and [after microbenchmarks](../benchmarks/results/similarity_primitives_after.json.xz):
  all five samples, allocations, RSS, owned state, work counters and output hashes.
- [Semantic-channel comparison](../benchmarks/results/similarity_primitives_vector_comparison.json):
  persisted-row counts and raw float32 differences across sessions.
- [Owner costs](../benchmarks/results/similarity_primitives_owner_costs.json)
  and [validation status](../benchmarks/results/similarity_primitives_validation.json).

The receipt indexes the losslessly compressed smoke, standard, large, original
and Kepano raw reports, baseline failures and complete validation log. Use
`xz -dc FILE.json.xz` to inspect an archived JSON report. Compressed files preserve
full evidence without checking multi-megabyte repeated passages into plain Git
blobs. No corpus source notes are modified by these measurements.

`./scripts/validate.sh` passed in 435.69 seconds locally: 1,877 unit tests passed
(one existing skip), 81 integration tests passed, all 155 automated acceptance
criteria passed, all 45 bundled geists fired, and branch coverage reached 82.33%.
Strict mypy (98 source files), whole-project ty, lint, database/security/workflow
checks and installed-wheel real offline inference also passed. The initial
lexical deadline flake and its narrow repair are recorded in the test audit and
initial validation log. GitHub's separate platform/Python jobs are not claimed
as local validation results.

Canonical Openclaw autoreview targeted source commit `6555d6c` after all 65
before/after input blobs and committed context files matched unauthenticated
public copies. The reviewer failed authentication and produced no report:
[`reviewer_unavailable`](../benchmarks/results/similarity_primitives_review.json),
not a clean verdict. Its status and suppressed-auth
execution log are archived in the receipt. The PR remains in draft; this service
failure is separate from the completed independent reviews and green validation.
