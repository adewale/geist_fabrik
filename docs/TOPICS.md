# Automatic local topics

Normal vault sync derives up to five English topic labels per eligible note or
dated entry. Labels, memberships and exact source evidence live in SQLite;
VaultContext, Tracery and the topics CLI expose them. This adds shared intelligence
for existing geists, without introducing a new geist family.

## Guiding contracts

- Preserve Markdown, frontmatter, authored tags and existing lexical history.
- Enforce logical, physical and dated-entry exclusions before extraction/counts.
  Keep complete-empty, pending, error and excluded states distinct.
- Normalize keys by Unicode, case and whitespace only. Preserve singleton topics;
  introduce no semantic merging, popularity floor or public-topic promotion.
- Run locally on user invocation, with no network/LLM requirement, monitoring
  service or dashboard. Inspection loads no embedding model or user plugins.
- Keep derived data incremental, versioned and rebuildable. Membership describes
  observed text; it establishes neither stance nor intent. Suggestion sampling,
  filtering, preview and explicit `--write` retain their existing behavior.

## Pipeline and explanations

Source eligibility and syntax-owned non-prose are hard boundaries. Generic named
heading suppression is a separate, fallible role judgment. YAKE proposes labels;
the selection layer grounds occurrences and applies relevance rules; the
transactional index stores the results.

```sh
geistfabrik topics /path/to/vault --note '[[My note]]' --json --explain
geistfabrik topics /path/to/vault --topic 'paper folding'
geistfabrik topics /path/to/vault --rebuild
```

Explanations distinguish structural exclusions, heading-role judgments, source
grounding, local grammar, score adjustments and final decisions. Masked content
cannot be reconstructed into a raw evidence span: proposals crossing it require
a later safe occurrence or future composite-evidence support. Excluded/incomplete
sources are not re-extracted for explanation.

Grammar uses the candidate's mapped sentence. Unrelated sentences cannot supply
its clause context. Alignment uncertainty preserves candidates; model failures
remain errors. A candidate immediately followed by a colon uses ordinary noun/
clause checks rather than isolated-subject shortcuts. This can miss substantive
adjectival or postposition-ending field names; the contrast panel retains those
costs. Scores are ordering values, never calibrated probabilities. Complete means
processing finished, not exhaustive subject discovery. Exit codes: 0 complete,
1 command error, 2 incomplete; unavailable memberships/counts are null.

## Boilerplate tradeoff

| Case | Policy |
| --- | --- |
| Excluded/non-prose or genuinely empty admitted text | Zero derived topics. |
| Substantive parent caption or filled response | Empty fields alone cannot suppress otherwise eligible subject evidence. |
| Nominal wording in an unused form | Blank fields, list shape and repetition do not justify suppressing an uncertain nominal subject; report any resulting prompt noise. |

For policy selection, require the frozen precision/recall floors and no additional
empty-case labels relative to the legacy comparator. This is an experimental
comparison, not delivery approval. The old LYT unused-form zero-false-topic gate
remains unchanged and failed on
`important action items`. No oracle, threshold, source exclusion or domain list is
changed to manufacture a pass.

The constructed contrast panel records these actual selected outputs; candidate
eligibility is separate from final ranking. These are diagnostics, not held-out
quality evidence.

| Contrast | Selected labels / observed cost |
| --- | --- |
| Metadata-only; generic structural stub | None in either case. |
| Unused form | `important action items` remains. |
| Substantive parent | `transitive`, `important relation properties`, `reflexive`, `wind`; noun subject survives, unrelated prompt fragment remains. |
| Rare outline | `cyanotypes`, `ferric ammonium citrate`, `potassium ferricyanide`, `exposure time`. |
| Partly filled priority form | `repair the rainwater`, `important action items`, `rainwater pump`, `big`, `medium`; response subject survives alongside prompt noise. |
| Partly filled reflection | `restored cyanotype prints`. |
| Adjectival relation fields | `relation properties`, `reflexive`, `transitive`; `Symmetric` is rejected. |
| Named subject field | `game`; injected `Game over` is rejected. |

## Measured results

The preregistered [experiment](../benchmarks/corpora/topic_policy_experiment.json)
tests 128 combinations of seven selection rules with shared YAKE proposals, plus
a separate heading-role preprocessing ablation with its own proposals. Only the
full seven-rule policy meets all numeric floors, no-extra-empty-noise criteria
and unchanged known-answer regressions. **No selector complexity reduction was
supported.** Repeated-word filtering earns retention only through its existing
validity regression; the other removals violate quality/noise floors as well as
some contracts. The 32x hint penalty and 8x gap remain historical settings.

| Calibration proxy | Projected-prose YAKE precision / recall | Selected policy |
| --- | --- | --- |
| synthetic | 0.419 / 0.667 | 0.629 / 0.881 |
| public-starter | 0.314 / 0.667 | 0.529 / 0.857 |
| narrative | 0.238 / 0.500 | 0.562 / 0.857 |
| lyt | 0.427 / 0.675 | 0.535 / 0.625 |

The baseline shares ordinary prose/heading-role curation; the separate role arm
shows the cost of removing that earlier heuristic. Raw failures and every assigned
label remain available in the [durable archive](../benchmarks/archives/topics/README.md).

Sixteen previously unselected LYT notes were independently model-annotated and
adjudicated before quality-output inspection. Prior full-vault integrity runs had
indexed all sources: these notes are held out from quality tuning/inspection,
not claimed never processed. The [selection archive](../benchmarks/archives/topics/calibration-selected.archive.json)
was committed before their evaluation. Only selected policy and fixed comparators
are scored; no policy tuning follows. This is same-vault model evidence, with
underspecified cases visible separately, not human or cross-vault approval.

Independent evaluation is pending. Runtime verification passed: 306 focused,
2,471 unit and 88 integration tests, 84.03% branch coverage, 158 automatic criteria,
all platform/offline package lanes, all six corpora and all 120 replay snapshots.
See [current results](../benchmarks/results/topics/current.json),
[verification](TOPICS_VERIFICATION.md) and the unchanged
[delivery contract](../specs/TOPIC_EVIDENCE_SPEC.md).
