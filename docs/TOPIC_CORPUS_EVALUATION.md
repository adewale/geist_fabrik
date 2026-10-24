# Topic evaluation on the existing large test vaults

The earlier conclusion that the project had only ten usable starter notes was
incomplete: merged PRs already establish larger corpora. This work reuses their
inputs and generators. No runtime extraction policy, calibration labels or
thresholds are changed merely to improve a score.

| Corpus | Provenance | Use in this evaluation |
| --- | --- | --- |
| Mara narrative vault | Merged PR #97; checked-in authored fiction | All 24 snapshots; diverse prose, dated entries, edits, deletion and stable controls. |
| Temporal smoke and standard | Merged PR #97; deterministic synthetic generator | All 32 snapshots at 128 and 1,000 initial notes. |
| Temporal large | Merged PR #97; same generator | All 32 snapshots at 10,000 initial notes. The earlier probe covered only the first two. |
| Original 10,000 files | Historical benchmark and PR #97; Zettelkasten-Method/10000-markdown-files at `40c11a4bb9b96dbcf1cd3c109d32f50dbc8b61a2` | Exact 10,000-note, 46,635,807-byte population; cold/warm sync, exact evidence, positive query and source-preservation checks. Text is scrambled, so its size is not evidence of semantic usefulness. |
| LYT Kit | Historical 235-note benchmark removed in merged PR #61; recovered public mirror thebrianbug/LYT-Kit at `e191473fcb326df78cca8a6c49b29420ab318e46` | This mirror has 272 notes; it is not claimed to be the same snapshot. Run the full index and retain a frozen 28-note, length-stratified source-first quality sample, including four excluded-template controls. |

The [input manifest](../benchmarks/corpora/topic_corpora.json) records provenance,
pinned versions, sample selection and expected inventory. The LYT sample was
selected and its source Git blob hashes checked before viewing extractor output.
It covers short notes, empty notes, navigation notes, essays, dated notes and
configured templates. No private-owner ratings are inferred from public examples.

## Source-first relevance proxy

The [new LYT proxy annotations](../benchmarks/corpora/topic_lyt_proxy_gold.json)
were frozen after reading the selected sources but before viewing their extractor
outputs. The annotator is a model already familiar with the implementation; these
are not independent human ratings or an untouched validation holdout. Twenty
substantive sources and three empty/stub controls are scored with the existing
0.50 precision / 0.60 recall thresholds. One underspecified diary entry remains
ungraded for human adjudication; four templates are checked as excluded sources.
These choices were made before predictions, not by discarding failed outputs.

The [narrative proxy annotations](../benchmarks/corpora/topic_narrative_proxy_gold.json)
freeze three final-snapshot notes from each of seven domains (21 substantive
cases) plus two excluded-template controls. Source selection, reading and model
annotations precede prediction inspection. This tests personal-note prose forms
beyond the PKM demonstration vault, while retaining its fictional provenance.

The report evaluates every assigned label and the same frequency baseline using
the existing evaluator. This proxy reports its own pass/fail result. Functional
corpus validation does not certify semantic usefulness or close the human gate;
a failing relevance proxy must remain visible even if indexing checks pass.

## Initial measured findings and targeted repair

The complete run on `52b25c556dbf731c66e25a139348dd01eacaafd3` passed
all functional corpus checks. The narrative proxy scored 0.448 precision / 0.667
recall, and the LYT proxy scored 0.377 / 0.575, below their fixed precision
thresholds. LYT also emitted labels for an unfilled daily-note form. These
results do not justify a merge recommendation.

The LYT outputs exposed property metadata entering the topic budget: `moc tags`,
`meta pkm tags`, `url` and parent-navigation link titles were treated as subjects.
The targeted repair treats property-only paragraphs as structural metadata using
Markdown spans and source-ordered HTML ownership. It retains headings and mixed
prose, does not blacklist property names, and keeps comments/code/HTML from owning
the wrong later text. Existing and new proxy annotations remain frozen. Sentence
fragments and unfilled-form noise are separate unresolved quality findings; they
are not hidden by changing the oracle or corpus population.

## Audit repairs to the proof boundaries

Follow-up reviewers reproduced two verifier defects using real Vault/SQLite
with injected faults: an incomplete empty-note rebuild could retain the same
membership digest, and a same-count replacement path could pass the population
check. The runner now requires rebuilt completeness, compares full note-state
populations and memberships, and checks every replayed path and SHA256 against
the snapshot manifest. New regressions retain a complete-empty positive control
and reject extraction failure, renamed source and same-byte content corruption.

The parser audit also exposed field-created HTML state escaping after an earlier
owner closed, or consuming its closing syntax. Property-created nesting and raw
text now have paragraph-local lifetime, while matching closes preserve earlier
real HTML owners. The real helper probes and source-level regressions cover these
cases; full committed-revision MarkdownIt tests remain required.

The [baseline reports](../benchmarks/results/topics/corpora/baseline/index.json)
and [initial property-mask probe](../benchmarks/results/topics/corpora/property-mask-probe/index.json)
retain their exact measured revisions. That initial repair raised the LYT proxy
from 0.377 / 0.575 to 0.482 / 0.625, with the empty-form violation remaining.
Narrative relevance stayed at 0.448 / 0.667. Both relevance proxies still failed
the fixed thresholds. The [receipt](../benchmarks/results/topics/corpora/receipt.json)
keeps this failure visible and distinguishes those historical runs from the final
strengthened proof. No score or annotation is presented as a human judgment.

## Earlier completed 90-snapshot run

Runtime `e0c4ecbfaab773c8ebe69390b5d347441be39cc9` passed the
[complete corpus workflow](https://github.com/adewale/geist_fabrik/actions/runs/40108166872).
The [final reports](../benchmarks/results/topics/corpora/final/index.json) bind
the measured Git commit, six source-file hashes, manifest and dependency versions.
All 90 replay snapshots and both static corpora passed source preservation,
exact evidence, nonempty positive-query and zero-extraction warm-sync checks.
All four edited/replayed corpora passed complete fresh-rebuild and stable-source
comparisons. Every snapshot inventory also matches the historical baseline.

| Frozen model proxy | Final precision / recall | Frequency baseline | Result |
| --- | --- | --- | --- |
| Narrative, 21 substantive notes | 0.448 / 0.667 | 0.238 / 0.333 | Fails precision. |
| LYT, 20 substantive notes plus three empty/stub controls | 0.482 / 0.625 | 0.240 / 0.425 | Fails precision; one empty-form violation. |

The property repair improves the LYT proxy without changing annotations or
thresholds. It does not resolve sentence fragments or unfilled-form labels.
For example, an unfilled daily form still yields `action items today` and
`today i accomplished`. No corpus-specific word blacklist, frequency floor or
semantic merging was added to suppress these failures. Quality remains a merge
blocker; the human-review gate is also open.

| Corpus | Initial cold sync | Final warm sync |
| --- | --- | --- |
| Narrative | 0.349 s | 0.085 s |
| Temporal 128 | 0.970 s | 0.093 s |
| Temporal 1,000 | 7.487 s | 0.609 s |
| Temporal 10,000 | 76.115 s | 5.016 s |
| Original 10,000 files | 740.370 s | 5.182 s |
| LYT mirror | 7.780 s | 0.150 s |

These are single CI observations with lexical capture disabled, not a causal
performance comparison. Initial and final replay populations differ. The larger
original corpus contains 46.6 MB of scrambled prose; its successful indexing
establishes robustness and measured cost, not useful topics.

## Full coverage: all corpora and all snapshots

Revision `45aff5021c184229e6861ef1b47142f8be5226eb` removes the large-profile
two-snapshot limit. The [full run](https://github.com/adewale/geist_fabrik/actions/runs/40110002076)
completed successfully. Its [retained reports](../benchmarks/results/topics/corpora/all-snapshots/index.json)
contain every requested observation, with no skipped snapshot indices:

| Corpus | Observations tested | Final indexed note/entry states |
| --- | ---: | ---: |
| Mara narrative | 24 | 189 |
| Temporal 128 | 32 | 211 |
| Temporal 1,000 | 32 | 1,252 |
| Temporal 10,000 | 32 | 12,232 |
| Original 10,000 files | Full static population | 10,000 |
| LYT mirror | Full static population | 272 |

This covers 120 replay snapshots and both complete static populations. Every
observation passed completeness, exact evidence and nonempty positive-query
checks. All six preserved Markdown and reused the warm index without extraction;
all four changing corpora matched a complete fresh final-state rebuild and
preserved stable-source evidence. The large profile includes 6,000 stable
controls, the week-16 rewrite and 1,000 deletions at week 24. Its final source
inventory (12,201 Markdown files, 5,005,176 bytes) matches a separate generator
run exactly. All snapshot inventories shared with the earlier run also match.

The large-profile syncs totalled 798.530 seconds across 32 snapshots; its final
sync took 26.829 seconds and the unchanged warm sync took 6.419 seconds with zero
extractions. The original stress corpus took 810.691 seconds cold and 5.363
seconds warm. These remain single-run raw-sync-plus-topics measurements with
lexical capture disabled; source generation and verification add further cost.

The extraction source and frozen annotation hashes are unchanged. Both broader
proxy reports are identical to the preceding run: narrative 0.448 / 0.667 and
LYT 0.482 / 0.625 precision/recall, with the unfilled-form violation still present.
Indexing every note does not make these annotated subsets an all-note relevance
assessment or a human judgment. Quality continues to block merge. The separate
focused workflow also passed both original calibration gates, including all ten
public starter notes. The [receipt](../benchmarks/results/topics/corpora/receipt.json)
binds this full coverage to its actual commit, source hashes and CI jobs.

## Completed grammar repair on the full corpus scope

The [grammar repair](TOPIC_QUALITY_REPAIR.md) rejects statistical clause fragments
using packaged local grammar, while preserving authored priors, rare subjects,
nominal outlines and uncertain alignments. An independent review exposed
possessive modifiers, numeric names and postpositive adjectives; regressions
protect their entire grammatical classes. Runtime
`427afee5a4c7ae5df044441f4f105c288a75c671` passed the
[full corpus workflow](https://github.com/adewale/geist_fabrik/actions/runs/40123416962).

The [new reports](../benchmarks/results/topics/corpora/grammar-repair/index.json)
retain all 120 ordered replay snapshots and both complete static populations.
Every source inventory is identical to the pre-grammar full run. All six preserve
Markdown, exact evidence and positive memberships and extract zero topics when
unchanged; all four changing corpora match complete fresh final-state rebuilds
and retain stable-source evidence. The large final population remains 12,201
Markdown files and 12,232 indexed note/entry states. Stored labels on every
graded sample match the quality evaluator's predictions, with unchanged source
and annotation hashes.

| Frozen model proxy | Before grammar precision / recall | After grammar | Result |
| --- | --- | --- | --- |
| Narrative | 0.448 / 0.667 | 0.571 / 0.857 | Passes both numeric thresholds. |
| LYT | 0.482 / 0.625 | 0.520 / 0.625 | Passes numeric thresholds; empty-form gate still fails. |

The original synthetic and public-starter gates also pass unchanged, at
0.629/0.881 and 0.529/0.857. Every pre-repair baseline prediction is reproduced by
the diagnostic's grammar-disabled counterfactual. These remain model calibration
results, not human ratings or an untouched holdout. The remaining LYT form emits
`important action items`; neither the form nor its assigned label was removed
from evaluation. A same-shaped rare-topic outline is preserved by regression.
No frequency floor, domain word list, semantic merging or weakened oracle was
used to close a gate. Merge readiness remains blocked.

| Measured cost | Pre-grammar full run | Grammar repair |
| --- | ---: | ---: |
| Temporal large: sum of 32 syncs | 798.530 s | 929.478 s |
| Temporal large: last changed sync | 26.829 s | 37.914 s |
| Temporal large: final warm sync | 6.419 s | 4.464 s |
| Original stress corpus: cold sync | 810.691 s | 933.437 s |
| Original stress corpus: warm sync | 5.363 s | 3.731 s |

Inputs are matched, but these are separate single CI trials with varying host
costs; the differences are not isolated causal estimates. Lexical capture stays
disabled. Generation, verification and whole invocation/embedding costs are
outside these sync timings. Warm extraction counts are zero in both revisions.

Canonical and platform/package checks also pass on this runtime: 178 focused,
2,345 unit and 86 integration tests, 84.12% branch coverage and all 158 automatic
acceptance criteria. The 83 manual criteria remain unverified. The
[receipt](../benchmarks/results/topics/corpora/receipt.json) binds these results to
the actual source, locked dependencies and CI jobs.

## Executable checks

`scripts/benchmark_topic_corpora.py` uses real `Vault.sync` and `TopicIndex` with
YAKE/MarkdownIt. It loads no embedding model or user plugin and emits no geist
suggestion. Lexical capture is explicitly disabled to isolate raw sync plus topic
indexing cost; these are not whole-invocation or embedding timings.

For each snapshot, it checks complete state and every stored evidence span/line,
then verifies nonempty topic memberships against stored eligible source rows.
It compares complete replay path/hash maps, hashes Markdown before/after sync,
asserts zero topic extractions and unchanged
memberships on warm sync, and compares edited/replayed final state with a fresh
index, including complete-empty states and note populations. Stable-source evidence must remain unchanged throughout each replay.
The static stress corpus is indexed once and checked warm; no redundant cold
rebuild is required when its source has never changed.

The dedicated [workflow](../.github/workflows/topic-corpora.yml) checks out pinned
external corpora and runs:

```sh
uv sync --locked --extra vector-search
uv run --frozen python -m scripts.benchmark_topic_corpora \
  --work /tmp/topic-corpus-checks \
  --lyt /path/to/pinned-lyt-mirror \
  --stress '/path/to/10000 markdown files'
```

The work destination must not exist. It owns all generated/replay data. External
source corpora are read without importing their plugins, and source bytes must
remain unchanged. Reports retain provenance, snapshot counts, extraction counts,
query timings, evidence checks and unrated sample labels. Human usefulness fields
remain unset. Historical and final measured results are retained above.
External repositories must match their pinned Git commit and have clean
tracked sources. Reports record the measured project commit and relevant source
file hashes in addition to the requested PR revision.

Corpus execution can establish correctness and cost. Fiction, planted topics,
scrambled stress prose and unrated public demonstration notes do not establish
human usefulness by themselves. The representative quality gate remains separate
from the automatic checks; existing large corpora nevertheless provide substantial
verification work that should be completed before requesting new vault data.
