# Before/After Benchmark — June 2026 performance work

Reproduce with `uv run python benchmarks/perf_before_after.py`. Each case runs
the shipped path and an inline reconstruction of the previous implementation on
the same synthetic data (best-of-N timings, single machine), so the ratio
isolates the change.

| Case | Before | After | Speedup |
|---|---:|---:|---:|
| `find_similar` end-to-end (N=10k, k=11, 50 queries) | 381 ms | 374 ms | 1.0× |
| └─ top-k sort only (N=10k, k=11) | 0.655 ms | 0.050 ms | **13×** |
| `orphans` (N=6k notes, M=3k links) | 1531 ms | 8.6 ms | **179×** |
| `filter_diversity` (S=200 suggestions) | 5384 ms | 4.2 ms | **1281×** |

## Reading the numbers

- **`find_similar`** — the argpartition change replaced an O(N log N) full
  stable argsort with O(N + k log k) top-k selection. In isolation that step is
  **13× faster**, but end-to-end `find_similar` is dominated by the cosine
  matmul (identical in both paths), so the user-visible win is small per call.
  It still matters on the hottest path (every `neighbours()` call) and removes
  a term that grows with vault size.
- **`orphans`** — the old LEFT-JOIN had a non-sargable `OR` on `l2.target`, so
  SQLite scanned the whole links table per note (O(N·M)). The set-difference is
  O(N+M): **~179× here**, and the gap widens with vault size (it was a genuine
  scaling cliff, not just a constant factor).
- **`filter_diversity`** — replacing the S²/2 per-pair Python `cosine_similarity`
  calls with one BLAS matrix is **~1281×** at S=200. This is the dominant filter
  cost in `--full`/firehose mode (50–200+ suggestions); `filter_novelty` got the
  same treatment.

Other changes in the same body of work are correctness/scaling rather than
micro-speed (sync `NOT IN` temp-table removes the 32k-variable hard cap;
`island_hopper`/`find_bridges`/`detect_structural_holes` batch their similarity
matrices; `session_embeddings` retention bounds DB growth) and aren't captured
by these micro-benchmarks.

## Issue #78 replica (3,175-note synthetic vault, stub model)

`benchmarks/issue78_replica.py` rebuilds the issue's conditions and runs
unchanged on both the current branch and the issue's exact commit (3b248e6).
Validation: the BEFORE side reproduces the issue's M4 Pro numbers within ~5%
(hidden_hub 29.8s vs the issue's 28.2s; method_scrambler 17.8s vs ~17s), so
the AFTER numbers translate directly.

| Geist | Before (3b248e6) | After (current) | Speedup | Issue #78 reported |
|---|---:|---:|---:|---:|
| hidden_hub | 29.77 s | 0.13 s | **227×** | 28.21 s |
| island_hopper | 313.09 s † | 2.83 s | **111×** | 28.23 s |
| method_scrambler | 17.78 s | 0.08 s | **225×** | ~17 s |
| task_archaeology | 0.006 s / **0 sugg.** | 0.030 s / **3 sugg.** | revived | — |
| blind_spot_detector | 0.025 s / **0 sugg.** | 0.013 s / **2 sugg.** | revived | — |
| Total (these geists) | 360.7 s | 3.1 s | **117×** | — |

† The synthetic vault's hubs carry ~100 backlinks each — denser clusters than
the reporter's vault — and island_hopper's old cost grew with
hubs × N × cluster_size, so BEFORE blows past the 30 s production timeout by
10× at this density. AFTER handles the same density in 2.8 s: the timeout
cliff the issue flagged at ~3.4k notes is gone.

Rows not shown: columbo early-returns on this synthetic content (its
assertion-word guard never fires) — identical on both commits but
uninformative; cluster_evolution_tracker early-returns with a single session
(its before-crash is pinned by tests/unit/test_cluster_label_persistence.py);
pattern_finder is deliberately excluded as explicitly untouched (quality >
speed rollback policy).
