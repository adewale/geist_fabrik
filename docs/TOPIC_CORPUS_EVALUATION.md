# Topic evaluation on the existing large test vaults

The earlier conclusion that the project had only ten usable starter notes was
incomplete: merged PRs already establish larger corpora. This work reuses their
inputs and generators. No runtime extraction policy, calibration labels or
thresholds are changed merely to improve a score.

| Corpus | Provenance | Use in this evaluation |
| --- | --- | --- |
| Mara narrative vault | Merged PR #97; checked-in authored fiction | All 24 snapshots; diverse prose, dated entries, edits, deletion and stable controls. |
| Temporal smoke and standard | Merged PR #97; deterministic synthetic generator | All 32 snapshots at 128 and 1,000 initial notes. |
| Temporal large | Merged PR #97; same generator | First two snapshots at 10,000 initial notes, matching the prior large-probe scope. |
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

## Final measured result

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
