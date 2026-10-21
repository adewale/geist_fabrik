# Word-burst lifecycle and execution repairs

These repairs address the deep review of PR 97 at `b8e0ddb`. The feature and shared
semantic changes remain in the same PR. [Current behavior](WORD_BURST.md) is the
reference for configuration and history semantics.

## What changed

| Trigger | Previous behavior | Repaired behavior |
| --- | --- | --- |
| Pause capture or indexing; disable the geist; reorder exclusions | Captured history could be erased | Operational controls preserve evidence; equivalent exclusion sets share a policy |
| Change phrase/quote/exclusion policy, then restore it | Original observations were lost | Inactive policy observations are archived and restored only to that exact policy |
| Unreadable source during resume | A later sync could capture an unconfirmed interval | Pending confirmation survives across syncs and reopened databases |
| Add a source after bootstrap | Its initial text never entered captured additions | Initial text is newly observed at sync time, regardless of its declared date |
| Private source changes | Its terms and absences could change public questions | Source eligibility applies before population, exposure and evidence collection |
| A sampled candidate is unsafe or already saved | It consumed the question budget | The sampler continues to another eligible episode |
| Decline reference has empty leading/trailing/interior weeks | Displayed period overstated coverage | Actual endpoints, observed-week count and interior gaps are reported |
| Disable `word_burst` | Its dictionary was still maintained | Lexical indexing pauses and history is retained |
| Optional phrase analysis exceeds an invocation budget | Three timeouts could disable the geist | Completed decoding is saved; later invocations resume; budget deferral is visible and does not count as failure |

Schema 15 adds archived observations, pending source baselines and resumable
analysis work. Existing source notes, embeddings, saved questions and compatible
captured observations remain intact. Archived JSON retains exact evidence without
assuming stable term IDs across extraction policies. Deletion purges both active
and archived observations. Storage can grow when many distinct extraction
policies retain different histories; this is the cost of preserving recoverable
evidence.

## Correctness and limits

A checkpoint binds the source generation, selected observations, eligibility,
weekly frame and analysis settings. It stores exact intervals for completed
candidates. Questions are produced only after all candidates are processed and
source evidence is rebound. Changed inputs invalidate the checkpoint. Exact
resumed findings are compared with uninterrupted findings, including multi-state
and near-unity parameter cases.

The controller separately limits unseen series and candidate traversal. Cheap
cache hits cannot justify an oversized batch of unseen histories. A controlled
cost regression and an independent mixed-cost native-timeout probe cover that
failure. Unrelated host alarms propagate; an executor-owned timeout defers the
optional analysis instead of poisoning persistent failure state.

Collection, projection backfill, evidence binding and an indivisible model
operation remain outside cooperative checkpoints. A sufficiently costly such
phase can require an explicit larger timeout. No promise of eventual completion
under every budget is made. Multiple invocations repeat population collection and
lose the invocation-local series cache; total elapsed work can increase.

Saved-episode checks share the filter's indexed evidence lookup. A leading-article
variant no longer displaces an existing shorter content phrase with identical
evidence. These changes prevent specific poor questions; they do not establish
reader surprise or usefulness. Owner-rated evaluation on an authentic dated vault
remains outstanding. Trigrams remain optional.

## Proof and measurements

The test audit applies Openclaw's test authoring and boundary/cost guidance, with
Hypothesis and Hegel's independent implementation-only review. Regression owners
exercise real syncs, storage, executor behavior and command output. The interrupted
analysis test requires a nonempty checkpoint before resuming. The citation test
uses an allowed support beyond the 100-reference limit whose alias is ambiguous
with an excluded source; early private-source exclusion alone cannot satisfy it.

The [repair receipts](../benchmarks/results/word_burst_lifecycle_repairs/README.md)
retain source hashes, failing baseline regressions, independent probes, validation,
full-corpus replays and the matched 10,000-note executor experiment. The corpus
runner uses real offline embeddings and the full invocation/filter/selection/write
path for all bundled geists. Stress dates are explicitly synthetic benchmark
metadata; source text and recorded frozen manifests are retained unchanged.
