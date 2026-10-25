# Topic corpus evidence

See [Automatic topics](TOPICS.md) for the single current design and evaluation
summary. The [input manifest](../benchmarks/corpora/topic_corpora.json) preserves
the complete six-corpus scope: 24 narrative snapshots, 32 each at temporal
128/1,000/10,000, the pinned 10,000-file stress vault and 272-note LYT mirror.
The mirror is distinct from the unrecovered historical 235-note snapshot.

The [last full raw report set](../benchmarks/results/topics/corpora/grammar-repair/index.json)
and [source-bound receipt](../benchmarks/results/topics/corpora/receipt.json)
remain readable. They measure runtime 427afee5, before the local-policy refactor.
Narrative is fiction and the original stress text is scrambled; scale and replay
correctness do not establish real-owner topic usefulness. Sync timing excludes
lexical capture and whole-invocation costs; separate CI trials are not causal
performance estimates.

All earlier raw runs and pending review records are in the
[durable evidence archive](../benchmarks/archives/topics/README.md). Its original
paths, hashes, failure reports and unrated judgments remain intact. Restore them
when reproducing historical comparisons; do not treat an old `final` directory
name as current validation. [Current status](TOPICS_VERIFICATION.md) distinguishes
completed measurements from pending experiments.
