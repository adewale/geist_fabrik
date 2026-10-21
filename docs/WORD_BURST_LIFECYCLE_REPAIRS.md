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

### Measured results

The final runtime is committed at `c624c2e57ccbda3b02b2090405c980f481e328d6`.
Controls use `b8e0ddb217092299d821bdd4d89b7e82fb824ef4`. These are single
sequential trials with numerical library threads limited to one, not estimates
of statistical significance.

| Experiment | Before | After |
| --- | --- | --- |
| Public/private sampling fixture, empty outcomes | 18/30 seeds | 0/30 seeds |
| Observed-additions narrative, raw / filtered / saved word-burst questions | 0 / 0 / 0 | 39 / 38 / 7 |
| Dated-cohort narrative, raw / filtered / saved word-burst questions | 41 / 20 / 5 | 26 / 21 / 5 |
| 10,000-note optional-trigram analysis, default 30-second executor | Timeout; persistent failure recorded | Four invocations: 25.10, 25.08, 25.08, 22.59 seconds; no persistent failures |
| Same trigram analysis, fresh unrestricted process | 39.03 seconds; 1,182.95 MiB peak RSS | 39.27 seconds; 1,184.18 MiB peak RSS |
| Same trigram analysis, final allocated database | 561.76 MiB | 562.34 MiB |

The default-budget sequence takes **97.85 seconds total**, about 2.5 times a
single unrestricted analysis. Repeated population collection and lost local
series caches account for extra work. This is a completion and failure-state
repair, not a speedup. The resumed 6,767 findings exactly match a fresh
unrestricted run. Their core statistical fields also match the baseline;
reference coverage fields changed deliberately. The stress dictionary contains
821,664 terms over 104 weeks. Initial corpus extraction and embeddings are
excluded from these analysis timings. Archived-policy storage growth is not
measured by this single-policy experiment.

The final-source corpus checks ran **3,129 successful geist executions** with
no errors: all 45 bundled geists over 48 narrative sessions (2,160 calls),
32 snapshots each of the 128-note and 1,000-note temporal corpora (448 each),
the first two snapshots of the 10,000-note temporal corpus (28), and all 45
bundled geists on the ten-note public snapshot. The temporal runner exercises
13 geists, with both word-burst modes, rather than all 45. Every unchanged
temporal probe performed zero lexical extraction, embedding inference or
embedding writes. Stable-note meaning remained unchanged.

Narrative replay wall time increased from 91.18 to 103.02 seconds for dated
cohorts and 87.20 to 103.21 seconds for observed additions. Observed-mode peak
RSS rose from 1,040.28 to 1,098.07 MiB, while dated-mode peak fell from 1,041.32
to 1,031.85 MiB. The repaired observed mode now performs work that was previously
missing. These workload changes and single trials do not isolate a causal
performance effect. Output counts are not usefulness scores.

The public snapshot has no eligible documents in the selected 104-week window;
word-burst correctly abstains. Its bundled sample managed-plugin directory
contains five obsolete plugin examples already incompatible on main; the fresh
notes-only replay exercises current bundled geists and does not claim those
legacy plugins passed.

The [unrated comparison packet](../benchmarks/results/word_burst_lifecycle_repairs/usefulness-review/review.md)
contains 12 partially masked pairs against a linked-note baseline, with source
contexts reconstructed as of each session. Its fictional notes permit a
coherence review. Authentic owner usefulness remains unverified.
