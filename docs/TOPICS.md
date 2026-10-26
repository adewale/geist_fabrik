# Automatic topics

GeistFabrik derives a local topic index during normal vault sync. Up to five
English labels per eligible note or dated entry connect observed subjects to
source notes. Existing geists and Tracery can consume the index through
VaultContext. This work adds shared metadata and inspection, with no new geist.

## Contracts

- Markdown, frontmatter and authored tags remain unchanged; derived memberships
  and exact evidence live in the existing SQLite database.
- Shared exclusions apply to logical, physical and dated-entry identities before
  extraction or counts. Hidden syntax, metadata and non-prose remain outside the
  candidate text. Pending/error/excluded states are distinct from complete-empty.
- Topic keys normalize Unicode, case and whitespace only. Singleton subjects
  remain eligible; there is no public-topic promotion floor or semantic merging.
- Normal operation requires no network, LLM, background service or dashboard.
  Inspection loads neither an embedding model nor user plugins.
- Edits, deletions, code/data/settings changes invalidate derived results. A clean
  rebuild must match incremental state; extraction errors never certify absence.
- Topics describe observed text, without claims about stance or intent. Suggestion
  sampling, boundaries, preview and explicit `--write` retain their existing flow.

## Pipeline and decisions

Source eligibility and the offset-preserving Markdown projection are hard
boundaries. YAKE proposes labels from the admitted prose. The separate selection
module grounds occurrences, applies the current relevance policy, and returns
bounded labels. The transactional index stores them; geists never repeat this
processing or query its tables directly.

Relevance is fallible. Seven rules are measured independently and in combination:
heading priors, link priors, predicate hints, relative score-gap abstention,
containment suppression, repeated-word filtering and grammatical eligibility.
Grammar uses only the occurrence's mapped sentence within a visible block.
Generic named section headings are a separate, earlier source-role heuristic,
with their own preprocessor ablation. Explanations label that judgment as
relevance, rather than claiming the text was code or metadata.
Unrelated sentences cannot change that decision. Uncertain alignment preserves
candidates; unavailable packaged grammar produces an extraction error.
Immediately colon-followed candidates use the ordinary noun/clause checks rather
than the isolated-subject or nominal-context shortcuts. This can reject real
adjectival or postposition-ending subject fields; the contrast panel reports that
cost. It does not classify an entire form as empty.

```sh
geistfabrik topics /path/to/vault --note '[[My note]]' --json --explain
geistfabrik topics /path/to/vault --topic 'paper folding'
geistfabrik topics /path/to/vault --rebuild
```

An explanation separates structural mask spans from grounding, relevance and
selection decisions. It lists every proposal, inspected occurrence, local grammar
reason, score adjustment and final selection/rejection reason. Masked source text
is not exposed. Excluded or incomplete notes are not re-extracted for explanation.
The current single-span evidence format admits only a contiguous visible source
span. A proposal crossing masked markup/content must find a later safe occurrence;
composite evidence would require a separate representation change.
Scores are ordering values, not probabilities. Exit codes: 0 complete, 1 error,
2 incomplete; unavailable memberships/counts are null rather than false zeroes.

## Boilerplate policy

| Source role | Policy |
| --- | --- |
| Excluded source or structurally empty visible prose | Hard boundary; zero assigned topics. |
| Substantive outline or filled part of a form | Empty siblings/children alone cannot suppress observed subject evidence. |
| Unused form with nominal prompt wording | Syntax, repetition and grammar alone cannot distinguish every prompt from an authored category; retain uncertainty and report noise. |

This tradeoff is frozen in the [experiment plan](../benchmarks/corpora/topic_policy_experiment.json)
before new measurements. The old LYT empty-form zero-false-topic gate remains
unchanged and failed until actually satisfied. Its failure is not hidden by
excluding Calendar, reading excluded templates, adding journal word lists or
changing the oracle. [Constructed contrasts](../benchmarks/corpora/topic_boilerplate_controls.json)
cover empty forms, meaningful outlines and partially completed forms.

## Evaluation and current results

The controlled experiment compares all 128 rule combinations with identical
cached real YAKE proposals on the four unchanged calibration fixtures. Selection
requires their numeric floors, no increased empty-case noise and unchanged
known-answer regressions; eligible policies are ranked by simplicity before
quality tie-breaks. A selection receipt must be committed before fresh evaluation.

Sixteen previously unselected LYT sources were frozen by a length-stratified path
hash. Two independent source-only model annotators and a third adjudicator labelled
them before extraction. The chosen policy is evaluated once alongside clean YAKE
and the frozen legacy comparator. Underspecified sources remain visible separately.
These are model annotations from one public PKM vault, not human judgments or a
claim about arbitrary personal vaults. No tuning follows that held-out evaluation.
Earlier full-vault operational runs indexed all LYT sources. These sixteen notes
are held out from quality annotation, output inspection and policy tuning, not
claimed to have never been processed by the index. Calibration does not inspect
their note-specific predictions.

The first local-grammar experiment was rejected because it increased unused-form
noise; its raw failure is retained. The final calibration uses the local colon
correction and safe evidence grounding. Exactly one of 128 policies qualifies:
all seven rules. There is **no selector complexity reduction**. Generic heading
role curation also earns retention under its fixed contracts and empty-case
measurements; disabling it produces additional false topics on stub cases.

| Calibration proxy | Clean-text YAKE precision / recall | Selected policy |
| --- | --- | --- |
| synthetic | 0.419 / 0.667 | 0.629 / 0.881 |
| public-starter | 0.314 / 0.667 | 0.529 / 0.857 |
| narrative | 0.238 / 0.500 | 0.562 / 0.857 |
| lyt | 0.427 / 0.675 | 0.535 / 0.625 |

Repeated-word filtering is retained by an existing validity regression, without
a measured calibration gain. The historical 32x predicate penalty and 8x gap
are not claimed to be optimal or calibrated confidence values. Every removal
and contract/quality consequence is recorded in the
[current results](../benchmarks/results/topics/current.json); the full raw
[selection archive](../benchmarks/archives/topics/calibration-selected.archive.json)
is committed before held-out evaluation. The selected policy and measured input
hashes must match that receipt before fresh predictions are inspected.

The held-out evaluation and final runtime validation are pending. The original
LYT unused-form failure and genuine human relevance review remain open. No
annotation, threshold or failing case is removed to obtain approval. See
[verification](TOPICS_VERIFICATION.md).

Raw historical evidence is preserved byte-for-byte in a [durable Git archive](../benchmarks/archives/topics/README.md),
with checksums and standard-library verification/restoration commands. The
[specification](../specs/TOPIC_EVIDENCE_SPEC.md) remains the delivery contract.
