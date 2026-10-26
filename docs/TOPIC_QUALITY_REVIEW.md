# Topic relevance review

The [current design and results](TOPICS.md) distinguish calibration, independent
model evaluation and genuine human review. Existing frozen regressions remain
unchanged. Sixteen additional source paths were selected deterministically outside
all previous quality samples and labelled by two source-only model annotators plus
an independent source-only adjudicator before extraction. Their
[selection](../benchmarks/corpora/topic_fresh_selection.json) and
[frozen annotations](../benchmarks/corpora/topic_fresh_gold.json) retain source
hashes, uncertainty and disagreements. They contain no human approval.

The experiment freezes its chosen policy in a committed calibration receipt before
opening fresh predictions. Only the chosen policy and two fixed comparators are
evaluated there; results cannot select another policy. Every output remains
visible, including underspecified sources, with omissions/phrase variants and
label-limit recall bounds disclosed. The same-vault sample does not establish
broad personal-vault representativeness.

Earlier human response packets were never rated and now describe historical
policies. Their exact bytes are in the [durable archive](../benchmarks/archives/topics/README.md).
They cannot approve current outputs. Any human review must read source subjects
before predictions, judge every assigned label and missed subject, and separately
assess corpus representativeness. Null judgments remain pending. See
[current verification](TOPICS_VERIFICATION.md) for the remaining delivery gates.
