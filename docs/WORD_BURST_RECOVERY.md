# Word-burst and temporal-corpus recovery record

Recorded 2026-10-10 from the retained session record while the execution
environment was offline. This document preserves project context; it is not
a substitute for the implementation, raw benchmark artifacts, or test logs.
The results below were reported from earlier executions and have not been
rechecked during this recovery step.

## Review follow-up, 2026-10-14

PR #97 now includes the five independent review repairs and the follow-up hardlink
case. Full episode evidence remains available; rich-context boundary checks precede
bounded suggestion references. Source/native-path exclusions and near-one numeric
costs are repaired. Skipped sources cannot tighten observation bounds. The
executor-based corpus matrix covers all three changing profiles, alongside real
CLI checks on the small fixture and the original large corpus. New raw archives,
failed-harness evidence and the vision assessment are preserved on this branch.
See the current performance and test-audit documents for exact scope and outcomes.

## Rebuilt implementation, 2026-10-13

The feature was rebuilt from the preserved specification, not recovered byte for
byte. [Draft PR #97](https://github.com/adewale/geist_fabrik/pull/97) tracks the
implementation on `codex/word-burst-context`. Source, schema-v11 migration,
property/integration tests, deterministic temporal generator and benchmark runners
are committed. The original corpus was fetched at its pinned revision and the
bundled model hydrated. New measurements and lossless raw replay archives live
in `benchmarks/results/`; see [WORD_BURST_PERFORMANCE.md](WORD_BURST_PERFORMANCE.md).
These measurements supersede the unverified historical timings below.

Repository-wide validation passed after rebuilding. The Openclaw canonical
shared autoreview could not authenticate and produced no report; the PR remains
draft pending that review. See [WORD_BURST_TEST_AUDIT.md](WORD_BURST_TEST_AUDIT.md)
for current verification evidence and failure classification. Earlier inspection
statements below describe their dated checkpoints, not the current branch.

## Salvage inspection, 2026-10-13

The execution environment connected successfully. Inspection found no previous
checkout at /workspace/geist_fabrik and none of the recorded specification,
verification-tools, benchmark-corpora or temporal-corpus directories.
The accessible shared/downloads, scratch and library-files directories contained
no files. This establishes absence from the current workspace, not destruction
of every possible external backup.

Cloned codex/word-burst-context into /workspace/geist_fabrik and checked it out
with LFS smudging disabled. The working tree was clean. Its 395 tracked paths
are the 393-file source baseline plus the two recovery documents. Its last
implementation ancestor remains main commit
37c0fce23b8df0a02924361f456d0c67ac2e3479; the three subsequent commits before
this update contain only recovery documentation. The tree contains no new
word_burst source, word-burst tests, temporal generator or replay runner.

Recoverable exactly:
- Original repository source baseline and existing tests from Git.
- Original research/specification archive and recovery ledger from Git.
- Public literature, testing guidance, benchmark corpus source and pinned refs.

Recoverable as recorded knowledge, without original raw evidence:
- Reported production benchmark summary and optimization lessons.
- Historical provenance decisions, configuration defaults, module inventory,
  audit/oracle strategy and explicitly deferred scope.

Not found in the current workspace or this branch:
- Uncommitted word-burst implementation, migrations and its new tests.
- Raw benchmark JSON, profiler data, complete validation/audit logs and local
  prototype scripts.
- Synthetic temporal corpus generator, generated corpus and replay results;
  their earlier completion was never verified.

Reconstructing code is new implementation, not recovery of the exact lost
source. Rerun measurements and tests rather than treating retained summaries
as verification of a rebuilt implementation. The old large corpus is
re-downloadable at its pinned commit. Synthetic corpora can be regenerated
once a deterministic generator is rebuilt.

No new implementation or performance result is claimed by this inspection.
The local checkout currently has model LFS pointers, not hydrated model weights,
and its execution dependencies have not been restored.

## Recovery progress, 2026-10-10

The full original 44,948-character research/specification was recovered from
the saved Page and committed as
[WORD_BURST_ORIGINAL_SPEC.md](WORD_BURST_ORIGINAL_SPEC.md), commit
185d9392b49540ae19ec3449317c9070d9525c42. A read-back confirmed exact equality
with the uploaded archive (including its clearly separated recovery notice).
This preserves the original proposal and literature, not the later local
implementation specification.

Execution remains disconnected. No implementation source, raw production
benchmark JSON, test logs or synthetic corpus have been recovered remotely
during this step. Their survival on the workspace has not been inspected.
Do not reconstruct those artifacts from prose and call them recovered files.

## User-authorized work

- Research and specify a Kleinberg word-burst geist for GeistFabrik: historical
  accuracy, word-frequency indexing cost, exact optimizations, later Kleinberg
  work and subsequent literature.
- Implement it and benchmark against the previously used large corpus.
- Investigate safe early exits, especially an unchanged corpus.
- Apply property-based testing, Hegel.dev guidance, and the Openclaw test-audit
  skill, using existing branches and linked guidance as context.
- Create a synthetic corpus with substantial change over time so both new and
  existing temporal geists can be benchmarked.
- Explain what the findings enable and continue through verification.

Repeated requests for status or to continue did not cancel this scope.

## Git and recovery state

The implementation was prepared in /workspace/geist_fabrik on local branch
codex/word-burst. It remained uncommitted and was not pushed. That was a
checkpointing failure: a branch name alone does not preserve working-tree
changes, and workspace files do not provide a remote recovery checkpoint.

Source main used for implementation:
37c0fce23b8df0a02924361f456d0c67ac2e3479 (0.11.0 beta).
The checkout was initially materialized with exact Git blob verification, then
initialized with local baseline commit
358a1a360bda0599ce487ba83072fed8178ab427 before origin/main was fetched.
The materialized baseline has different ancestry from origin/main. Inspect
history before preparing a PR; preserve the working tree and do not blindly
reset it.

This remote branch preserves context only. No implementation files or raw
results have been uploaded by this recovery step. When the workspace returns,
inspect all files and logs before claiming they survived, then make durable
commits of the implementation, research, results, and remaining-work ledger.
Keep large generated corpora outside Git; commit deterministic generators,
manifests/hashes, commands, and compact results instead.

## Implemented work reported before disconnection

The following files were reported as created or changed locally:

- src/geistfabrik/word_burst.py: exact binomial Kleinberg section 4 dynamic
  programming with O(bins × states) prefix/suffix transitions and traceback.
  Validates count and parameter domains; does not clip invalid probabilities.
  Missing exposure remains unobserved. Results distinguish gaps, left censoring,
  and open intervals. Likelihood gain is not a significance claim.
- src/geistfabrik/lexical_index.py: incremental normalized Unicode word/phrase
  extraction, shared Markdown prose classification, per-note vectors and
  hashes, bounded dictionary cache, and changed-term indexed lookups.
  Owned transactions cover updates. Initial discovery establishes a baseline,
  rather than inventing writing events.
- src/geistfabrik/schema.py: additive automatic schema v11 migrations for
  lexical metadata, dictionary, note vectors, observed additions and result
  cache; reference counts and generation invalidation.
- src/geistfabrik/vault.py: lexical capture integrated with the existing atomic
  sync transaction and source revalidation.
- src/geistfabrik/config_loader.py: strict lexical and word-burst configuration.
- src/geistfabrik/word_burst_analysis.py: shared service, exposure-aware support
  and exact gain pruning, compact term IDs, bounded persistent cache, diagnostic
  counters and explicit historical modes.
- src/geistfabrik/vault_context.py: public word_bursts API.
- src/geistfabrik/default_geists/code/word_burst.py: linked questions based on
  findings, including historical limitations and all supporting note references.
- Tests, configuration examples, acceptance criteria, README/counts, changelog,
  spec reconciliation and explanatory documentation.

Defaults: unigram extraction, s=2, gamma=1, two states, 104-week window,
50 documents, eight populated bins, support in three documents and two bins,
at most three suggestions. Two/three-word phrases are opt-in because measured
full-corpus latency exceeds the default 30-second geist timeout.

Exact early exits include no observations, absent/ubiquitous terms, insufficient
dated support, constant prevalence, and conservative gain bounds. Persistent
cache keys include data generation, algorithm version, configuration and exact
cutoff. Changes to exposure invalidate all term results. Warm lexical work
avoids rebuilding the dictionary; filesystem synchronization still scans notes.

## Historical accuracy decisions

Dated cohorts associate current note prose with explicit dates from journal
entries, frontmatter or dated filenames. They reconstruct cohorts; they do not
recover earlier versions of prose. Filesystem date estimates are excluded from
strict dated analysis.

Observed additions capture positive lexical additions after actual UTC
observations begin. Initial discovery is a baseline. A replay date does not
backdate a real edit. Events are coalesced per note/week, with revision evidence
and observation bounds. Changed extraction policy resets the baseline/history
explicitly. Deletions purge logical note history.

Observed coalesced rows whose latest observation exceeds a requested cutoff
are conservatively omitted in full. The implementation does not retain old
prose for exact historical replay. Logical deletion is not secure physical
erasure.

Deferred: Git/backup history import, retained historical prose/quotes, exact
old-text replay, alternative rolling baselines and selective term cache
invalidation.

## Original large-corpus benchmark

Corpus: https://github.com/Zettelkasten-Method/10000-markdown-files
Commit: 40c11a4bb9b96dbcf1cd3c109d32f50dbc8b61a2
10,000 Markdown files, 46,635,807 bytes; reported complete Git blob verification.

The original corpus has no usable chronology. Strict dated analysis therefore
abstains. Detector timing used an explicitly artificial 104-week date overlay
in a temporary database. These timings do not establish historical accuracy or
human usefulness.

Reported medians, generally three trials:

| Operation | Unigrams | Words and phrases up to length 3 |
| --- | ---: | ---: |
| Cold sync/index | 20.225 s | 86.526 s |
| Unchanged sync | 1.771 s | 1.890 s |
| Edit 100 notes | 2.293 s | 2.597 s |
| Fresh detector | 3.284 s | 48.496 s |
| Cached detector | 2.085 ms | 11.270 ms |
| Dictionary terms | 7,374 | 493,107 |
| Database size | 91.27 MiB | 168.88 MiB |

Unigram decoder: 1,850 candidate terms decoded, 5,485 pruned, 207 findings.
Phrase decoder: 79,744 decoded, 415,403 pruned, 1,289 findings.
Before optimization, phrase decoding median was 103.332 s across two original
trials; do not label that baseline as three trials.

Exact pruning approximately halved phrase CPU time. Compact term IDs reduced
additional RSS from approximately 687.75 to 302.85 MiB. Total process peaks
include ML imports: approximately 888.4 MiB for unigrams and 1,120.9 MiB for
phrases. Raw undated analysis exited in approximately 0.441 ms; cached empty
result approximately 0.092 ms.

Cached lexical analysis is effectively constant work, but an unchanged whole
Vault sync still took approximately 1.8 seconds and retained filesystem scans
and per-note SQL activity. Do not claim the whole invocation is O(1).
The benchmark excludes embedding inference and full CLI invocation.
Original corpus hashes were reported unchanged before/after.

Expected local evidence:
- scripts/benchmark_word_burst.py
- benchmarks/results/word_burst_large_corpus.json
- docs/WORD_BURST_PERFORMANCE.md
- /workspace/benchmark-corpora/10000-markdown-files/MANIFEST.json
- /workspace/benchmark-corpora/10000-markdown-files/VERIFICATION.json

## Research and applicable insights

Original model: https://www.cs.cornell.edu/home/kleinber/bhs.pdf
Later structured-HMM work supports exact prefix/suffix DP acceleration.
Kleinberg-related usage streams, conference topics and meme tracking motivate
exposure normalization, phrase variants and clustering of related findings.
The research search did not find a standalone replacement burst model written
by Kleinberg; that is a bounded-search finding, not proof of absence.

Tatti's parameter optimization work:
https://arxiv.org/html/1902.01727
Its exponential/geometric guarantees do not automatically transfer to this
binomial model. Appending observations can revise previous optimal states.

CiteSpace and other applications show practical use for topic discovery.
Twitter stream systems motivate incremental counting and spam/duplicate
handling. Lexical dependence and multiple comparisons argue against presenting
burst scores as statistical significance. Recent large n-gram work reinforces
dictionary caching and the need to evaluate whether parameter choices match
human expectations.

The inspected nmarinsek/burst_detection implementation used greedy local
state selection rather than the complete cumulative DP/traceback, so it was not
used as an independent oracle. Full research/spec text was saved locally in
specs/WORD_BURST_GEIST_SPEC.md and /workspace/geist-word-burst-spec/.

## Test audit and verification reported before disconnection

Guidance:
- https://github.com/openclaw/openclaw/blob/main/.agents/skills/test-audit/SKILL.md
- https://github.com/hegeldev/hegel-skill/blob/main/skills/hegel/SKILL.md
- https://github.com/hegeldev/hegel-skill/blob/main/skills/hegel-review/SKILL.md
- https://github.com/adewale/testing-best-practices/blob/main/testing-best-practices/SKILL.md

Native Python Hypothesis was used. Tests include exhaustive small DP objectives,
known answers, missing-bin invariance, conservative-pruning oracles, stateful
lexical/reference-count contracts, aggregate analysis properties, atomic
migration/rollback, invalidation and nonempty genuine geist firing.
Reported 139 new feature tests passed in 10.18 seconds.

Fault planting: 12 isolated detector mutants and four configuration mutants
were killed against final sources. Nine analysis fault plants were killed
before the last sparse-pruning edits; the complete analysis test module was
rerun afterward. Preserve this distinction.
A genuine completed-Sunday provisional-status bug was observed red then fixed.
Test corrections and oracle assumptions were recorded in
docs/WORD_BURST_TEST_AUDIT.md.

Last canonical scripts/validate.sh run was NOT wholly green:
- Ruff, strict mypy, ty, Bandit and table checks passed.
- 1,743 unit tests passed; one skipped and nine deselected.
- 45/45 bundled geists passed the firing gate.
- 80 integration tests passed; seven deselected.
- Measured branch coverage: 81.30%, above the 70% gate.
- 152/152 AUTO acceptance criteria passed; 83 MANUAL remained non-gating.
- Wheel/sdist/build-from-sdist and real offline bundled-model inference passed.
- Workflow lint failed because /usr/bin/go was a different program, not Golang.

Do not claim validation passed overall. Resolve the tool failure and run the
required canonical checks after further edits. CLAUDE.md requires validation
before pushing code. This recovery branch changes only this prose record.

Canonical independent autoreview was NOT completed. A prior launch failed
network connections; absent output is not a clean verdict. Helper was installed
unchanged from agent-skills upstream
7e733069bc6d4e4e77adddb4fb4fcaca5a15e021 at:
 /workspace/verification-tools/installed-skills/autoreview/scripts/autoreview
Read its SKILL.md and diagnostics instructions, then run canonical local review
against source main with explicit datasets and outputs outside the repository.
Do not substitute a normal agent review for the mandated helper.

Other expected local logs:
- /workspace/verification-tools/validate-final.log
- /workspace/verification-tools/burst-review-initial-run.log
- docs/WORD_BURST.md
- docs/WORD_BURST_TEST_AUDIT.md

## Synthetic temporal corpus: planned, completion unverified

Inspect these expected paths when execution resumes; their existence and
completion were not verified before disconnection:
- scripts/generate_temporal_corpus.py
- scripts/benchmark_temporal_geists.py
- tests/unit/test_temporal_corpus.py
- tests/unit/test_temporal_benchmark.py
- docs/TEMPORAL_BENCHMARK_CORPUS.md
- /workspace/temporal-benchmark-corpus/

Design: deterministic standard-library generator, content-addressed Markdown
objects and ordered manifests/deltas. APIs under discussion were
generate_corpus(output, config) and apply_snapshot(corpus, vault, snapshot_index).
Profiles: 128-note smoke, 1,000-note standard, 10,000-note large, 32 weekly
observations with declared prior creation history for seasonal/year-ago geists.

Scenarios: approximately 60% unchanged controls; independent planted lexical
bursts in weeks 8–11 and 22–25; gradual/abrupt semantic rewrites; new dated notes;
recurrent topics and phrases; balanced writing-volume controls; duplicate
bodies; links/aliases; journal-entry edits; deletions and initial discovery.
Do not rely on numeric note IDs alone for independent prose: normalization can
collapse their lexical bodies.

Replay should exercise actual Vault sync, sessions, real bundled model and
selected temporal geists, including word_burst, concept_drift, temporal_drift,
attention_shift, recent_focus, seasonal_patterns, temporal_clustering and
this_time_last_year where their real contracts permit.
Simulated observation clocks belong to the benchmark harness, clearly labeled
synthetic, without production backdating switches.
Unchanged text must retain identical meaning vectors across sessions.

Run real embeddings on the small profile and, if practical, standard profile.
Run large lexical replay with semantic work explicitly skipped if appropriate.
Record timings, exceptions, raw suggestions, links, firing dates and control
behavior. Geists returning empty output or executor errors must be visible.
Test deterministic generation, hashes, replay transitions, stable controls and
planted event integrity with independent properties.
Expected qualitative scenarios do not imply exact burst-boundary ground truth.

## Next concrete actions

1. Restore execution; inspect working tree, history, artifacts and unfinished
   processes. Preserve existing files before making changes.
2. Commit the existing implementation and evidence locally with accurate
   completion status. Reconcile ancestry safely for a reviewable branch.
3. Finish and verify deterministic temporal corpus generation and actual
   replay; record measured behavior of target scenarios and controls.
4. Resolve workflow-lint tooling, run canonical validation after final edits,
   and complete the canonical independent review with its required follow-up.
5. Update specs/audit/performance ledger to match actual finished results.
6. Publish the validated implementation branch with durable context and
   compact artifacts. Do not imply this recovery document contains the code.

Usefulness so far: indexed word bursts are practical at this scale and can
produce linked questions with honest evidence. Synthetic replay and real-vault
qualitative evaluation remain necessary to establish which temporal geists
produce useful suggestions, rather than merely firing.

## Bidirectional phrase extension, 2026-10-15

The next request was to keep inversion in the same geist and include phrases.
The implementation on `codex/word-burst-context` extends `word_burst`, with rising
and declining directions, words plus pairs by default, and optional triples.
A decline requires established prior use and later populated observations; it
cannot infer abandonment from missing data. Historical modes remain explicit.
The lower-probability state grid is our extension of the Kleinberg model.

Matuschak's notebook discussion led to current passage excerpts, questions that
invite connecting notes, nested-expression deduplication, and saved episode
identity that survives wording/window changes. Munger's inversion lens led to
questions about vocabulary that has become quieter. Neither establishes that a
reader has forgotten an idea or that a change is conceptually important. Feedback,
semantic terminology replacement and contradiction detection remain deferred.

Extraction version 3 changes sentence/quote boundaries. The next sync rebuilds
that derived index and starts a new observed-additions baseline; old captured
observations cannot safely be compared across extraction policies. Schema v12
adds nullable evidence identity while preserving source notes, saved questions,
and history for unchanged policies. Existing explicit words-only settings stay
words-only. See [current behavior](WORD_BURST.md),
[measurements](WORD_BURST_PERFORMANCE.md), and
[test audit](WORD_BURST_TEST_AUDIT.md) for verification and limitations.
