# Full-geist evaluation on an authored fictional vault

This report preserves the original evaluation. The source, ledger and original
receipts remain frozen while the follow-up repairs are evaluated separately.

At source checkpoint `73c3393898420f115a6d4b967ffa8fe3284eb590`, the full invocation
path completed 48 historical sessions and 2,160 executor calls without a failure.
The questions expose a usefulness gap: the existing filters accept structurally
valid prompts that are obvious, generic or misleading in the author's context.

[The readable sources](../testdata/narrative_vault/README.md),
[fictional author brief](../testdata/narrative_vault/persona.md) and
[independent event ledger](../testdata/narrative_vault/ledger.json) are checked in.
[Machine-readable results and lossless receipts](../benchmarks/results/narrative_vault_v1/summary.json)
retain configuration, model/code provenance, raw candidates, selected output,
judgments and the superseded first runs. Nothing here establishes real-reader
utility or a timeout probability for a population of vaults.

## Corpus and execution

Mara's notebook follows museum research, a volunteer workshop and repair cafe,
care arrangements, gardening, cycling and pottery over 24 months in 2024–2025.
It contains 166 final physical Markdown files, indexed as 189 notes after journal
splitting. There are nine substantive replacements, one deletion, six backdated
fictional clippings imported together, quoted/code controls and templates. Fifteen
physical source files remain unchanged throughout. The final lexical population
contains 11,125 visible word tokens and 18,318 distinct word/phrase expressions.

The initial notes are readable prose, not repeated topic templates. The persona
and ledger were frozen before the first run and never ingested. Sources and
thresholds were not tuned after seeing output. The story includes a known project
completion, a known launch and a terminology replacement, so a detector cannot
earn a useful label merely by rediscovering those changes.
The regular six-note monthly writing schedule and month-end captures simplify
real behavior. They do not establish when edits occurred within a month or
represent the uneven writing cadence of a sampled working vault.

Each mode uses a separate fresh vault and persists the normal five-question
selection into its journal. The harness calls the production `InvokeCommand.run`
with the normal parser, real offline sentence-transformer inference, Code and
Tracery loading, timeout handling, filtering and selection. Observational hooks
retain stages; they do not replace scoring, inference or filters. All bundled
geists are enabled in a stable alphabetical configuration order. Optional
trigrams are enabled; thresholds, timeouts and filter settings retain defaults.

Only source-capture time is patched. The shared replay primitive also sets the
mtime of changed sources to the recorded observation time. Its previous use of
today's filesystem clock leaked future modification dates into journal metadata.
The corrected runs have no future note dates. Their raw and selected questions
match the original runs, which are retained as superseded evidence.

| Recorded outcome | Dated cohorts | Observed additions |
| --- | ---: | ---: |
| Sessions / executor calls | 24 / 1,080 | 24 / 1,080 |
| Executor errors or skips | 0 | 0 |
| Geists producing output at least once | 31 | 30 |
| Raw / filtered questions | 906 / 882 | 849 / 826 |
| Selected and saved questions | 120 | 120 |
| Changed meaning vectors on stable sources | 0 | 0 |
| Median invocation duration | 3.40 s | 2.79 s |
| Maximum invocation duration | 5.27 s | 3.96 s |
| Peak whole-process RSS | 1,071 MiB | 1,065 MiB |
| Final SQLite database | 8.58 MiB | 8.57 MiB |

Timings include embedding/context setup, execution, filtering and journal writing,
plus observer work; interpreter/package import is outside them. These are one
local replay per mode, not replicated comparative benchmarks. RSS includes Python,
Torch and real models and is not incremental word-burst memory. The corpus is
small and short-note heavy; it does not replace the large capacity benchmark.

## What the question review found

The primary population is every selected question, including every session. The
secondary diagnostic sample is the first nonempty raw output of each geist in
each mode. A simple seeded linked-note prompt supplies one reference per session,
outside the generated, filtered or saved population. Every assessment is bound
to the exact output hash and dated context.

The assistant that authored the fixture reviewed it against the ledger. These
are subjective author-side judgments, not independent human or owner ratings.
The rubric deliberately distinguishes a plausible useful question from a correct
measurement or valid reference. Playful transformations can qualify when their
particular pairing or constraint supplies a useful angle.

| Author-side label | Dated selected | Observed selected | Both |
| --- | ---: | ---: | ---: |
| Useful candidate | 20 | 21 | 41 |
| Already known | 32 | 30 | 62 |
| Generic or weak | 64 | 65 | 129 |
| Misleading in context | 4 | 4 | 8 |

Thus 41/240 selected questions were judged promising under this rubric. This is
not an estimated real-world success rate. In the 61-question secondary sample,
14 were promising, 14 already known, 31 weak and two misleading. All 48 simple
linked-note reference prompts restated an existing connection. That weak baseline
and a single unblinded author do not establish superiority over alternatives.
Unreviewed raw output is not silently assigned a useful label.

Several prompts deserve further investigation. The hypothesis harvester asks how
to test the proposal for places to wait around an appointment. The concept-drift
and evolution geists correctly identify substantive rewrites and offer bounded
comparisons of changed relationships. The stub expander explicitly permits the
care card's intentional brevity. A few creative pairings connect consent,
accessibility and the ability to refuse across different projects.

The weaker questions identify concrete opportunities:

- **Linguistic signal is not conceptual value.** Of 57 dated word-burst prompts,
  32 center on `for`, `but`, `with`, `of` or `of a`. The four selected prompts
  center on `of a`, `of`, and twice on the already-known `supported` terminology.
  Their statistics and source passages can be correct while their questions add
  little. The current core notes also have a median 122 visible words versus 62
  in other authored current notes: presence per note depends partly on length,
  not just interest. This comparison does not isolate the cause of any episode.
- **Source eligibility differs across geists.** Templates correctly contribute
  no lexical sentinel terms, but other geists select template notes in eight
  sessions per mode. The orphan, attention, recent-focus, creative-collision,
  transformation and anniversary lenses all participate. The general boundary
  filter has no default template exclusion.
- **A date concentration is not a recurring interest.** The seasonal geist asks
  about rhythmic interest in `#clippings` because six backdated notes share one
  autumn. This is a single import/year, not a repeated annual practice.
- **A shared file's edit is not an entry's edit.** Three selected recent-focus
  questions per mode call unchanged, older journal entries recent work. Virtual
  entries inherit their physical source's modification time when it is appended.
  Correcting the replay clock cannot fix that production granularity limitation.
- **History expires.** The same `supported` episode and exact evidence key are
  selected on September 30 and November 30, 61 days apart. The default novelty
  window is 60 days. Five repeated selected hedging prompts about Repair ideas
  show that the issue extends beyond word bursts.

Boundary and structural quality reject zero questions. Novelty removes 38 and
diversity removes nine across the two modes. Those stages do not assess whether
the author already knows an observation or whether a proposed interpretation
fits the source. Selecting five from the survivors cannot supply that judgment.

## What the lexical modes establish

Dated cohorts produce 57 word-burst prompts: 36 rising and 21 declining. The
diagnostic finding counts include repeated findings across dates and must not be
treated as independent discoveries. All four finally selected word-burst prompts
are rising. The decline capability works without ensuring the default sample
represents both directions.

Observed additions produces no word-burst prompt. The final history has nine
note/week edit observations in eight populated bins, below the default minimum
of 50 observations. A cache-cleared diagnostic on a database copy reports
`insufficient_documents`, decodes no candidates and abstains. New discoveries and
backdated imports establish baselines; they do not invent writing intervals.
The mode stays explicitly configured throughout; it does not silently switch.
The ordinary cached diagnostic reports only `cached`, losing the original empty
reason and counts. The uncached database-copy check was needed to recover that
explanation. Preserving abstention metadata would make this behavior easier to
understand without changing the conservative evidence requirement.

The revision schedule also demonstrates the dated mode's historical limit. The
handbook retains its 2023 creation date when a 2025 revision adds `supported
practice`. Dated cohorts assign its current prose to that older cohort; they
do not prove that the new phrase was written in 2023. The generated provenance
label is essential, and the captured-additions mode cannot reconstruct revisions
that occurred before successful observations.

A final cache-cleared dated diagnostic has 168 window observations, 1,216 frequency
candidates and six findings. With trigrams included, collection, decoding and
evidence assembly take about 0.056 seconds in that single diagnostic. It is an
explanatory check, not an isolated latency benchmark. All code, quote and template
sentinels are absent from the lexical dictionary in both modes. The small corpus
increases global frequency-eligible expressions by only 59 when adding triples
(1,165 to 1,224); this says nothing about safety on long-prose collections.

## How to use the result

Keep this version fixed as an evaluation fixture and compare later changes on
the same dated questions. The most promising shared changes are:

1. An explicit source-role/eligibility policy used by geists and filtering, so a
   template can be indexed without automatically becoming an idea to revisit.
2. A presentation-level lexical candidacy gate that rejects empty grammatical
   lenses while preserving exact dictionary counts, meaningful phrases and
   sampling among eligible ideas. Do not change statistical thresholds merely
   to make this story's named projects appear.
3. Evidence requirements appropriate to the claim: cross-year recurrence before
   suggesting a rhythm, and entry-level content history before claiming an old
   journal entry was recently rewritten.
4. A durable episode/question history with explicit rules for renewed evidence,
   so expiring a short novelty window need not rediscover the same observation.
5. Cached abstention reasons and population counts, so users can distinguish an
   unchanged empty result from insufficient captured history.

These are findings and proposed follow-ups, not runtime changes shipped by this
evaluation. The only replay correction is the source filesystem clock. Tests
cover safe chronology, actual replacements/imports/deletion, exclusion of the
evaluation ledger, stable semantic controls, saved-selection ownership and failure
retention. Hypothesis varies snapshot cutoffs against declared dates independently
of any detector output.

The fixture also exposes its limits. It has no task lists, little formatting
variety, mostly short English prose and only nine captured edits. Empty task,
structure, cycle and high-similarity geists do not establish their usefulness or
failure on other vaults. A second independently authored persona with long essays,
task-bearing notes and sustained evergreen editing should complement this one.
Actual owners must judge surprise and usefulness before making real-vault claims.

The completed `scripts/validate.sh` gate passes 1,940 unit tests, 81 integration
tests, all 155 automated acceptance criteria and 83.11% branch coverage, plus
strict typing, lint, security/workflow checks and installed-package offline
real-model inference. A deliberate removal of only the mtime correction makes
its contract test fail. The new prose also exposed a brittle existing label-text
test that banned the word `categories`; its replacement compares exact output
with the independent full-parser oracle while retaining the no-YAML-parse check.
The initial failed gate and final passing log are retained with the receipts.

## Outcome of every bundled geist

The table below is generated from the frozen reports at the stated checkpoint.
Each pair is **dated / observed**. Every geist was attempted in every session;
zero output means healthy emptiness, not an exception or a skipped test.

| Geist | Sessions with output | Raw questions | Selected questions |
| --- | ---: | ---: | ---: |
| `assumption_challenger` | 0 / 0 | 0 / 0 | 0 / 0 |
| `attention_shift` | 22 / 22 | 22 / 22 | 4 / 4 |
| `bridge_builder` | 0 / 0 | 0 / 0 | 0 / 0 |
| `bridge_hunter` | 24 / 24 | 48 / 48 | 8 / 8 |
| `claim_harvester` | 4 / 4 | 4 / 4 | 1 / 1 |
| `cluster_mirror` | 23 / 23 | 23 / 23 | 4 / 4 |
| `concept_cluster` | 8 / 8 | 10 / 10 | 3 / 3 |
| `concept_drift` | 16 / 16 | 28 / 28 | 0 / 0 |
| `contradictor` | 24 / 24 | 24 / 24 | 3 / 3 |
| `convergent_evolution` | 1 / 1 | 1 / 1 | 0 / 0 |
| `creation_burst` | 0 / 0 | 0 / 0 | 0 / 0 |
| `creative_collision` | 24 / 24 | 70 / 70 | 11 / 12 |
| `cyclical_thinking` | 0 / 0 | 0 / 0 | 0 / 0 |
| `definition_harvester` | 12 / 12 | 12 / 12 | 1 / 1 |
| `density_inversion` | 0 / 0 | 0 / 0 | 0 / 0 |
| `divergent_evolution` | 3 / 3 | 4 / 4 | 1 / 1 |
| `hidden_hub` | 0 / 0 | 0 / 0 | 0 / 0 |
| `hub_explorer` | 24 / 24 | 48 / 48 | 9 / 9 |
| `hypothesis_harvester` | 20 / 20 | 21 / 21 | 2 / 2 |
| `link_density_analyser` | 0 / 0 | 0 / 0 | 0 / 0 |
| `metadata_driven_discovery` | 0 / 0 | 0 / 0 | 0 / 0 |
| `method_scrambler` | 24 / 24 | 72 / 72 | 6 / 7 |
| `orphan_connector` | 24 / 24 | 24 / 24 | 3 / 3 |
| `pattern_finder` | 5 / 5 | 5 / 5 | 0 / 0 |
| `question_generator` | 24 / 24 | 72 / 72 | 8 / 8 |
| `question_harvester` | 24 / 24 | 24 / 24 | 2 / 2 |
| `quote_harvester` | 1 / 1 | 1 / 1 | 1 / 1 |
| `recent_focus` | 23 / 23 | 62 / 62 | 11 / 11 |
| `scale_shifter` | 0 / 0 | 0 / 0 | 0 / 0 |
| `seasonal_patterns` | 16 / 16 | 17 / 17 | 1 / 1 |
| `self_and_other` | 24 / 24 | 24 / 24 | 1 / 2 |
| `sentence_variance` | 0 / 0 | 0 / 0 | 0 / 0 |
| `structure_diversity_checker` | 0 / 0 | 0 / 0 | 0 / 0 |
| `stub_expander` | 8 / 8 | 8 / 8 | 0 / 0 |
| `surprisal` | 24 / 24 | 24 / 24 | 3 / 3 |
| `task_archaeology` | 0 / 0 | 0 / 0 | 0 / 0 |
| `temporal_clustering` | 1 / 1 | 1 / 1 | 0 / 0 |
| `temporal_drift` | 23 / 23 | 69 / 69 | 8 / 8 |
| `this_time_last_year` | 16 / 16 | 16 / 16 | 3 / 3 |
| `todo_harvester` | 0 / 0 | 0 / 0 | 0 / 0 |
| `uncertainty_mapper` | 24 / 24 | 24 / 24 | 5 / 5 |
| `vocabulary_expansion` | 0 / 0 | 0 / 0 | 0 / 0 |
| `voice_absence` | 19 / 19 | 19 / 19 | 3 / 4 |
| `what_if` | 24 / 24 | 72 / 72 | 14 / 14 |
| `word_burst` | 19 / 0 | 57 / 0 | 4 / 0 |
