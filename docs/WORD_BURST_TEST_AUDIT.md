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
