# Word-burst test audit

This rebuild applies the user-requested
[Openclaw test-audit skill](https://github.com/openclaw/openclaw/blob/main/.agents/skills/test-audit/SKILL.md),
its authoring gate, boundary/cost guide and audit references, plus
[Hegel guidance](https://github.com/hegeldev/hegel-skill/blob/main/skills/hegel/SKILL.md)
and the [Hegel review checklist](https://github.com/hegeldev/hegel-skill/blob/main/skills/hegel-review/SKILL.md).
Python uses the existing Hypothesis dependency; no Hegel language migration is needed.
A duplicate timer-only benchmark was retired after auditing its stronger
query-count and correctness owners; this was not a coverage/runtime shortcut.

## Contract owners and independent evidence

| Surface | Credible regression | Primary proof |
| --- | --- | --- |
| Dense detector | Greedy transition, wrong initial/upward cost, bad traceback | Exhaustive short-path negative-log-likelihood oracle, 1,000 generated cases; known gap episode |
| Sparse gain bound | Pruning a path with genuine benefit | Agreement with full decoding, 1,000 cases over parameters/state limits |
| Exposure and proportions | Empty weeks becoming absences, numerical fake bursts | Missing-bin metamorphism; 1,000 proportional-count cases and targeted numeric regressions |
| Extraction | Hidden code/comments counted, phrases crossing removed regions | Independent sliding-window Counter, 1,000 cases; Markdown boundary and delimiter regressions |
| Strict config | Accepting bool/nonfinite/unknown/out-of-range policy | Full existing config roundtrip generator extended to both sections; explicit rejection directions |
| Atomic sync/index | Committing partial capture, stale document frequencies | Real filesystem/Vault rollback and edit/delete sequence model, 100 cases |
| History | Discovery inventing writing, date replay backdating edits, wrong coalescing | Real sync with simulated observation clocks; bootstrap, watermark, union, cutoff, deletion and reset contracts |
| Analysis/cache | Stale exposure, duplicate inflation, wrong cutoff/provisional flag | Genuine planted-vault analysis, duplicate invariance, exposure-only edit, cached/fresh agreement and calendar endpoints |
| Geist | Tests looping over empty output or hiding fourth/private support | Genuine nonempty aurora question, measured prevalence, complete 12-note references; repository firing gate |
| Migration | v10 upgrade losing notes/embedding bytes | Upgrade with existing durable data and rebuilt lexical vectors |
| Generator/replay | Nonrepeatable fixtures, unstable controls, corrupt/escaping snapshots | Deterministic independent runs, exact hash manifests, all 32 transitions, corruption-before-mutation and dedicated-vault guards |

The decoder oracle materializes at most six bins/three states because enumeration
is exponential, while a separate 200,000-bin probe checks iterative scaling.
Broader parameter/state ranges are covered by cheap pruning/proportion properties
and configuration generators. Test files do not need real inference for lexical
contracts; the standalone temporal benchmark explicitly uses the real bundled model.
Public service/context/renderer paths are exercised together rather than mocking
the evidence they are meant to produce. Internal transaction methods have real
production callers, not test-only injection flags.

## Adversarial review and failure ledger

A separate Hegel-required reviewer inspected implementation/contracts **without
reading tests**. Its proposals led to added proportional-count, endpoint, duplicate,
dictionary-lifecycle and history-cutoff coverage. Existing objective, cache,
transaction, policy and rendering owners cover the overlapping recommendations.
Distinct-body support across weeks is intentional and documented. A valid
calendar cutoff is clamped, not silently restricted to recent years.

Observed failures were classified and fixed:

- **Product:** near-one `s` and zero gamma made constant prevalence falsely
  elevated through floating cancellation. Two numeric regressions failed before
  the exact integer-proportion abstention and passed afterward.
- **Product:** multiline HTML comments and inline spans containing shorter
  backticks leaked terms. Both regressions failed before matching complete
  regions/delimiter lengths and passed afterward; multiline spans were also checked.
- **Product:** oversized integer parameters raised `OverflowError`. A red
  regression now receives the documented `ValueError`; bounds precede conversion.
- **Product:** equal-timestamp observations discarded positive edits. The real
  sync regression failed with a missing event, then passed after capture accepted
  nonregressing equal timestamps.
- **Product:** a source edit during lexical capture escaped the earlier snapshot
  validation, and the observation clock was read before source discovery. Two
  regressions were observed red (0.28 s). Validation now follows capture before
  commit, and timestamps follow source reads; retries roll back all lexical work.
- **Test:** initial fixtures assumed Vault was a context manager. Vault has
  `close`; fixtures now use `contextlib.closing`. No production wrapper was added.
- **Harness:** temporal replay created its DB before applying snapshot zero,
  correctly triggering the dedicated-vault guard. The harness now applies the
  first verified snapshot before opening the production Vault.
- **Checks:** ty found optional-note/dictionary inference and cache reconstruction
  issues; explicit narrowing/types/field reconstruction repaired them. Formatter
  and line-length failures were corrected without weakening checks.
- **Documentation:** canonical checks found two unresolved performance links and
  stale schema-v10 status. The performance report and schema-v11 status repaired
  them; five documentation contracts passed in 0.28 s afterward.
- **Existing test:** AC-11.1 failed a 100-note, approximately 1 ms timing ratio
  (1.14x versus an arbitrary 1.3x threshold). Auditing the full owner, callers,
  performance spec and history showed the durable contract is at most three
  batch payload queries. The benchmark retains its timings, but gates real SQLite
  trace counts and independently known source contents. One duplicate ten-note
  timer comparison was removed; getter correctness and neighbour/backlink/hub
  query-budget owners remain. No production batch-loading seam was added.

The initial five adversarial regressions were observed red together (0.27 s).
The equal-clock regression was separately observed red (0.22 s), then green
(0.15 s). Logs live under `/workspace/verification-tools/`; durable contracts
are the committed tests. Older lost-implementation mutant counts in the recovery
record are not claimed as mutation evidence for this rebuilt code.

Recent focused runs: detector/corpus property modules 26 passed in 10.92 s;
expanded sync/analysis module 26 passed in 8.21 s. The exhaustive objective and
filesystem lifecycle properties justify their cost; full-model work stays in the
separate benchmark/package lanes. The completed canonical validation and separate shared autoreview outcome are
recorded below.

The final capture-order and batch owner run passed 40 tests in 5.59 s. The
objective oracle now disables pytest's default relative tolerance and retains
the original 2e-12 absolute allowance for independent floating-log evaluation.

Canonical shared autoreview was attempted against committed source candidate
`aea57856c52253bd31e8d8ed41986d891b5df1cf`, using the unchanged installation from
`openclaw/agent-skills`. The Codex CLI failed authentication (401); status was
`reviewer_unavailable`, one attempt, `report_produced: false`. This is not a clean
review, and the Hegel adversarial review is not presented as its substitute.
The PR remains draft pending authenticated canonical review. Repository-wide
validation passed before publishing the rebuilt code.


The follow-up independent review found two confirmed replay defects: redirected
state files and accepting a changed manifest at the same path. Both regressions
failed before the fix (2 failures in 0.34 s); marker validation/atomic replacement
and manifest SHA-256 binding now reject before any file changes. Changed objects
are hash-verified incrementally; unchanged corpus objects are not reread. This
scope is explicit in the corpus contract rather than claimed as full integrity
validation on every step.

A corrupt object in the second snapshot also revealed that pipeline exceptions
lost the first snapshot's completed evidence. The CLI regression failed before
the fix (6.97 s); it now writes the completed rows, failing stage/index/error,
returns failure, and closes an initialized model even after startup errors.

After the final capture-order repair, a fresh 32-snapshot lexical replay matched
all findings in both modes against the archived real-model smoke replay (64
exact comparisons). Both lossless archives independently match their recorded
SHA-256 after decompression.


Final `scripts/validate.sh` exited zero: 1,661 unit tests passed (one skipped,
eight deselected); 81 integration tests passed (eight deselected); all 152 AUTO
acceptance criteria passed (83 MANUAL criteria remain unverified); branch coverage
was 2,893/3,570 (81.04%, gate 70%). Ruff, mypy, ty, unused-table detection,
Bandit, actionlint and package checks passed. All 45 bundled geists fired in the
required lane. The installed wheel performed real offline model inference with
384-dimensional outputs and expected related/unrelated similarity ordering.

[Machine-readable validation evidence](../benchmarks/results/word_burst_validation.json)
anchors a lossless compressed log with SHA-256. The validation record identifies
the tested commit; subsequent changes only preserve this evidence and clarify
this audit. Documentation contracts are rerun after those edits. CI platform
coverage is separate from this successful local run.


## Review fixes and corpus verification, 2026-10-14

The requested four-agent review found the 100-reference executor limit, excluded
virtual source globs, Windows separator exclusions, near-one nonconstant emission
cancellation, and incorrect lower bounds after skipped reads. New regressions
were observed failing before fixes. The original Windows fixture initially failed
on foreign-key update ordering; after correcting that fixture, all three variants
failed on the actual exclusion contract. A successful executor leaves no failure
row, and virtual bodies strip trailing whitespace; those fixture expectations
were corrected after the production contracts passed.

Findings retain complete support paths; the geist checks every reference with the
same `NoteLinkIndex.references_allowed` policy used by the filter, then bounds its
returned references at 100. Tests place a private support beyond that limit and
run the real executor three times: public episodes succeed and remain enabled;
private-supported episodes abstain successfully. Extraction version 2 forces
incompatible old lexical baselines to rebuild, retaining core notes/embeddings.

The exhaustive property now independently recomputes the returned path objective
and checks interval coverage. An 80-digit Decimal oracle covers the smallest
supported `s` with zero gamma; stable log ratios restore the correct four-week
interval. Source/read failures keep the watermark conservative. The follow-up
Hegel-required reviewer read production/contracts without tests and found a
hardlink collision in the first fingerprint-only repair. Its natural probe and
an observed-red regression led to source-path confirmation tracking; recovery
now retains the correct lower bound. The reviewer rechecked and reported no
remaining P1/P2 findings in the requested repairs.

Focused owners passed: detector, history, filtering and journal identity 84 tests
in 13.08 s; generator/replay 8 tests in 6.88 s. New hardlink/observation owner checks
passed after the source-identity repair. Corpus runners now execute geists through
`GeistExecutor`; their errors include swallowed executor failures rather than
claiming success from direct calls to `suggest`.

Canonical shared autoreview was retried once against the committed repairs
through `e242dba`, with the previous PR head as its base. Preparation succeeded;
the Codex engine again failed authentication. Status is `reviewer_unavailable`,
one attempt, no report. This is still not a clean canonical autoreview. The PR
remains draft; independent review and repository validation are separate evidence.


The first executor-based real-model replay exposed a harness lifecycle mistake:
constructing `VaultContext` before embeddings held a closed backend after session
computation. The complete failed replay is preserved in
`word_burst_temporal_harness_failure.json` and its lossless archive. Embeddings now
precede context construction, and a fast two-snapshot lifecycle regression runs
real sessions/backends/executors with only inference stubbed. Corrected standalone
smoke and standard runs use the real bundled model, with no test stubs.

Full validation then caught direct SQL in the geist's new boundary preflight.
That lookup moved into `VaultContext.references_allowed`; the geist uses the rich
context API, and the shared identity policy remains in `NoteLinkIndex`. Architecture,
word history, filtering and journal identity owners passed 66 tests in 5.96 s.
All corpus profiles are replayed again against this final architectural repair.


The rich-context helper initially preceded its instance-state declaration, which
mypy rejected even though runtime checks passed. Moving the unchanged method
body below `__init__` repaired both strict type-check criteria; no gate was
weakened. Final standalone replay covers 96 snapshots and 192 word-burst executor
calls across all profiles. Complete episode evidence reaches 3,200 paths; returned
references remain within 100. Both semantic profiles preserve stable meaning
bytes. Real CLI checks verify a healthy sparse-vault abstention and a positive
question surviving the four-stage pipeline with offline inference required.


Final acceptance exposed another pre-existing millisecond ratio gate: the OP-9
neighbour-score benchmark measured 1.16x against an arbitrary 1.2x threshold
(0.507 ms versus 0.436 ms). Auditing the complete owner, OP-9 specification,
production caller and history showed the durable contract is avoiding redundant
pairwise similarity computation while preserving scores. Timings remain printed;
the gate now counts four actual pairwise backend calls in the old usage and zero
in scored retrieval, and checks scores against a scalar cosine oracle over stored
semantic vectors. The fast owner also replaces a vacuous `cache_after >= before`
assertion with nonempty results, no pairwise calls and independent score values.
The requested count is five but this fixture has only four neighbours; diagnostics
now report the actual four calls. No production optimization or test-only seam was
added. All nine owner tests passed in 0.36 s; mypy and ty passed afterward.


Final required validation passed after all repairs: 1,671 unit tests (one skipped,
eight deselected), 81 integration tests (eight deselected), 152/152 AUTO acceptance
criteria, 81.25% branch coverage, lint/security/unused-table checks, strict mypy/ty,
actionlint, and installed-wheel real offline inference. All 45 geists passed the
firing gate. The [validation record](../benchmarks/results/word_burst_review_fixes_validation.json)
identifies the tested source commit and anchors the lossless full log with SHA-256.
Only this verification evidence is added afterward. Canonical autoreview remains
unavailable because of authentication; the PR remains draft.

## Bidirectional phrases and episode identity, 2026-10-15

The same geist now handles both directions and 1–3-word phrases (pairs default,
triples configurable). This follows the Openclaw authoring gate and Hegel surface,
generator, direction and adversarial-review guidance linked above. The scalar,
sparse, prepared and bounded-batch model surfaces share independent exhaustive
objective proof; parameter generators retain their original domains. High-precision
Decimal references cover both near-one grid boundaries and coefficient cancellation
at accepted counts up to 2**53. No tolerance was widened to hide these failures.

A separate reviewer read production/contracts without tests/results. Its concrete
findings drove repairs for rounded baseline complements, valid rising states near
one, sub-ulp gains, lazy quoted continuations, Unicode source-line numbering,
thematic quote boundaries and repeat identity under rolling-window clipping.
It independently compared 17,600 scalar/batch results, including the 1,024-series
boundary, and reported exact parity before the final precision/preparation changes.
Those changes receive a follow-up review. Initial red proof is retained outside
this repo; new feature tests on the old API initially failed as expected. One
initial test run failed collection because positional Hypothesis arguments consumed
a pytest parameter; switching to named generators restored intended red proof.

Primary lifecycle owners are the real Vault sync/history plus GeistExecutor
phrase test in both modes, JournalWriter-to-novelty overlap test, v11 migration
preserving captured observations/questions, and chronology-only write-budget test.
The independent dictionary edit/delete model now spans all configured n-gram
lengths. Sentence/removal/quote boundary tables own extraction/excerpt exclusion.
Displayed references remain in the bounded payload after complete privacy checks.
No new reader-feedback controls, stance inference or historical prose store are
claimed. Old explicit words-only configurations remain valid.

Profiling found repeated sparse validation, vocabulary construction and gain-bound
work, not just recurrence time. The two-state scalar and bounded NumPy paths,
shared immutable exposure, prevalence grids, validated series and necessary-gain
bounds preserve complete eligible vocabulary. Earlier experimental timings are
not treated as final acceptance evidence. Phrases increase indexing, memory and
analysis costs; cold/cache and actual executor results are reported separately.

The final production-only follow-up found no outstanding concrete P1/P2 issues.
It independently checked copied/immutable prepared inputs, foreign-owner and
invalid-input rejection, the tiny-gain reproduction, and 1,000 raw/prepared/batch
cases across both directions. No necessary-bound false prune was observed.
The dated current-DF screen is a necessary upper bound; observed history bypasses
it. A lifecycle test removes a phrase from every current note and still recovers
its captured decline. The early episode gates check necessary support/exposure,
then final evidence still enforces distinct-body support.

Final required [validation](../benchmarks/results/word_burst_bidirectional_validation.json)
passed for source commit `ae2a868`: 1,724 unit tests (one skipped, eight deselected),
81 integration tests, 155/155 AUTO acceptance criteria, 81.61% branch coverage,
all 45 bundled geists firing, type/security/workflow checks, and installed-wheel
real offline inference. The lossless full log is SHA-256 anchored in that record.
Only benchmark/documentation evidence follows this source checkpoint.

The Openclaw [test-audit skill](https://github.com/openclaw/openclaw/blob/main/.agents/skills/test-audit/SKILL.md)
requires “then autoreview.” The initial combined local review/process-stop command
was rejected before execution over unpublished-source egress and process scope.
After pushing the authorized implementation and verifying unauthenticated public
access to its exact SHA, a separate committed-only canonical review was approved.
It prepared one pass, then failed authentication (`reviewer_unavailable`, no
report). The [review status](../benchmarks/results/word_burst_bidirectional_review.json)
records both the resolved approval concern and remaining authentication gap.
The PR stays draft; the independent production review does not substitute for a
clean canonical report.

Final default-pair original-corpus execution passed uncached at 22.131 s within
30 s, with fresh/cached suggestion equality and identical full finding digest to
the contended trial. The earlier 30-second timeout remains archived. The triple
run passed uncached at 110.912 s with an explicit 120-second budget. Six final
cache-cleared snapshot comparisons matched the earlier full triple replay. The
real default-pair CLI passed on positive synthetic and sparse real fixtures,
with unchanged source hashes. Resource/relevance limitations remain explicit.

## Reference prose and numeric decisions, 2026-10-16

The next audit confirmed hidden reference-link metadata entering vocabulary and
excerpts, plus false positive/negative large-count paths and an unsafe pruning
result. Seven initial owner regressions failed before repair. Reference handling
now changes only resolved source spans; unused definitions preserve surrounding
code, Unicode line, entity, HTML, quote and wikilink policy. Caret-label Obsidian
footnotes remain prose, including reference links/images in their bodies. The
existing extraction table/window property owns visible counts and phrase bounds;
small negative controls protect real block boundaries, line endings and NULs.
Policy version 4 rebuilds incompatible lexical capture; the existing real-Vault
policy-reset owner protects that lifecycle without duplicating the detector proof.

Numeric counts remain Python integers, probability grids remain exact fractions,
and fast float recurrence/batching carries coefficient and arithmetic bounds.
An ambiguous comparison reruns the complete recurrence with integer-weighted
logarithms, adaptive Decimal enclosures and algebraic tie reduction. Pruning only
exits when its bound is decisively below the transition cost. Exact aggregate
emissions also produce accurately rounded reported scores. No epsilon is used to
turn a small gain into a tie. Interval rescoring traverses disjoint intervals.

An independent 180-digit exhaustive oracle now covers the accepted count range,
near-one and larger multipliers, both directions, gaps, and gamma values around
transition boundaries. Generated algebraic identities cover exact ties, including
higher states and nonadjacent observations. Dense, sparse and batch paths agree;
the unsafe-prune regression remains an explicit owner. A production-only reviewer
also independently enumerated 163 nondegenerate exact rational-product cases,
without using logarithmic comparisons or reading tests/results: all paths were
optimal, with no false prune. Its final score-helper review found no correctness
issue. The separate Markdown reviewer found several concrete boundary defects
that were repaired before final validation.

Two repair iterations found additional product regressions: an unreachable-state
prefix shortcut in the guarded recurrence, and inaccurate reported tiny scores
although the selected path was correct. Existing exhaustive properties caught
the first; the new high-precision oracle caught the second. Test authoring also
initially omitted the selected direction in one property; this was corrected.
No tolerances were widened. The 1e-150 oracle floor accounts for rounding at
180 digits multiplied by the maximum short-case exposure, independently of the
implementation. The original seven red cases and intermediate failures are
recorded in the external work log; committed tests are the durable proof.
