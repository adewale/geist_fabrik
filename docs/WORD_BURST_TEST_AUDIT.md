# Word-burst test audit

This rebuild applies the user-requested
[Openclaw test-audit skill](https://github.com/openclaw/openclaw/blob/main/.agents/skills/test-audit/SKILL.md),
its authoring gate, boundary/cost guide and audit references, plus
[Hegel guidance](https://github.com/hegeldev/hegel-skill/blob/main/skills/hegel/SKILL.md)
and the [Hegel review checklist](https://github.com/hegeldev/hegel-skill/blob/main/skills/hegel-review/SKILL.md).
Python uses the existing Hypothesis dependency; no Hegel language migration is needed.
No existing test was deleted to increase apparent coverage or lower runtime.

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
- **Test:** initial fixtures assumed Vault was a context manager. Vault has
  `close`; fixtures now use `contextlib.closing`. No production wrapper was added.
- **Harness:** temporal replay created its DB before applying snapshot zero,
  correctly triggering the dedicated-vault guard. The harness now applies the
  first verified snapshot before opening the production Vault.
- **Checks:** ty found optional-note/dictionary inference and cache reconstruction
  issues; explicit narrowing/types/field reconstruction repaired them. Formatter
  and line-length failures were corrected without weakening checks.

The initial five adversarial regressions were observed red together (0.27 s).
The equal-clock regression was separately observed red (0.22 s), then green
(0.15 s). Logs live under `/workspace/verification-tools/`; durable contracts
are the committed tests. Older lost-implementation mutant counts in the recovery
record are not claimed as mutation evidence for this rebuilt code.

Recent focused runs: detector/corpus property modules 26 passed in 10.92 s;
expanded sync/analysis module 26 passed in 8.21 s. The exhaustive objective and
filesystem lifecycle properties justify their cost; full-model work stays in the
separate benchmark/package lanes. Exact counts from canonical validation and the
canonical shared autoreview outcome will be recorded after the final run.
