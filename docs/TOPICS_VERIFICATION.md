# Topic verification

PR [#96](https://github.com/adewale/geist_fabrik/pull/96) is rebased onto main
`657f85675bc05d3f353ed88940f36efe604b0367`. The implementation preserves the
session's narrowed goal: automatic local topic extraction, derived tags and
inspection APIs. It adds no new geist, source rewrite, dashboard, background
monitor, public-topic threshold, aggressive merging or editorial ranking.

## Root causes and regression coverage

The [historical adversarial audit](TOPICS_ADVERSARIAL_AUDIT.md) describes the
pre-repair source at `16d0adba380c306b3ff19f455ae3f4787aa78e68`.
The following repairs address its causes rather than suppressing symptoms.

| Cause | Repair | Verification |
| --- | --- | --- |
| Logical names were trusted without their physical source identity. | Persist resolved identities; require both identities to pass the shared policy on sync and cached reads. Missing provenance is pending. | Protected aliases, virtual dated entries, database reopen and missing-provenance regressions. |
| Topics duplicated and weakened the shared boundary policy. | Reuse SourceEligibility, retain logical and physical checks, always exclude managed state and journals. | Templates, configured prefixes, disabled suggestion filters and alias tests. |
| Discovery failures and skipped files disappeared before completeness checks. | Maintain failed-source and observed-source manifests independently of parsed rows; validate all observed identities/stat signatures before committing. Directory traversal errors abort sync atomically, preserving the previous database. | Permission/stat failures, unreadable directories at discovery and final validation, late oversized files and oversized alias retargeting tests. |
| Regex cleaning confused hidden syntax with visible prose. | Markdown-owned block/inline spans and bounded HTML/comment ownership preserve offsets while masking metadata and hidden bodies. | Nested link titles, reference definitions, list fences, multiline code, HTML self-closing/raw-text syntax and comment ownership tests. |
| A stale lock was silently repaired by validation commands. | Commit the actual resolved YAKE dependency graph; locked sync, frozen execution and lock checksum enforcement. | Dependency graph coverage, lock-mutation rejection and offline installed-wheel extraction. |
| Quality fixtures existed without executable release checks. | Evaluate every assigned label at the shipped maximum, check source hashes and fixed thresholds, wire both reports into tests/CI. | Noise injection, label-cap drift, checksum and empty-case regressions. |

The quality run also exposed forced padding with weak standalone words. A relative
score-gap abstention rule now treats five labels as a maximum; authored labels,
phrases and an isolated subject remain eligible. The frozen oracle and thresholds
were unchanged. Related topic/body/metadata reads use one SQLite snapshot.
Schema v15-to-v16 migration tests preserve authored data and lexical history.

Two independent post-fix reviewers rechecked parser and source completeness.
Their additional findings prompted the raw-text and traversal regressions above.
The source reviewer executed real permission failures with Vault/SQLite and empty
notes, verified full-database rollback at both scan stages, and confirmed recovery.
The parser reviewer executed the actual HTML helper on the adversarial input.
Those isolated checks do not replace full YAKE/MarkdownIt execution below.

## Measured focused validation

Source `32db958961e4a5ddbc9b61b44fd0cdc961df52fb` passed
[the focused CI job](https://github.com/adewale/geist_fabrik/actions/runs/40087616669/job/120853648723):
117 tests, repository hooks, locked dependencies, both quality gates and the
positive-query benchmark. Hooks left no uncommitted repairs. This used real YAKE
and MarkdownIt on Python 3.12.15. Reports and their source/run receipt are checked
in under `benchmarks/results/topics/`.

| Fixed sample | YAKE precision / recall | Frequency baseline precision / recall | Required precision / recall |
| --- | --- | --- | --- |
| Synthetic: 8 cases, 7 with required subjects | 0.600 / 0.833 | 0.029 / 0.071 | 0.45 / 0.60 |
| Bundled real notes: 10 cases, 7 with required subjects | 0.500 / 0.857 | 0.229 / 0.381 | 0.50 / 0.60 |

Both sets had no empty-case violations. Metrics average per substantive note and
score every assigned label, up to five; real-source SHA256 checks bind the oracle
to the source. An independent model annotated sources before seeing extraction
code/output. These are small calibration/regression samples, not human annotations,
a representative study, or an untouched holdout after tuning. The specification's
representative human-reviewed quality gate remains open; these results do not
justify a production accuracy claim or removing draft status.

The historical [human review packet](TOPIC_QUALITY_REVIEW.md) contains all ten
starter sources and the earlier prediction sets. Its response record is explicitly
pending. Current grammar outputs are retained in the repair reports below. The
exact-label model score can reject supported phrase variants; it is not a human
judgment that half the assigned labels are useless. Neither the frozen oracle nor
its thresholds has been changed to address that measurement limitation.

Single-run benchmark on repeated synthetic 141-character notes:

| Notes | Cold sync | Warm sync | Catalog | Positive membership query |
| --- | --- | --- | --- | --- |
| 100 | 0.301 s | 0.034 s | 1.44 ms | 1.03 ms |
| 1,000 | 3.029 s | 0.331 s | 13.13 ms | 9.88 ms |

Membership queries returned all 100/1,000 expected sources. These costs are useful
regression evidence, not representative real-vault latency measurements.

## Existing large-corpus follow-up

Merged PRs already supplied a narrative vault, temporal profiles at 128/1,000/10,000
notes and the original 10,000-file stress corpus. A public LYT Kit mirror extends
authored-note coverage. The [corpus evaluation](TOPIC_CORPUS_EVALUATION.md) records
the recovered provenance, frozen source-first sample and executable checks.
These inputs have now been exercised before and during targeted property-
metadata and grammar repairs. The latest grammar meets both broader proxies'
numeric thresholds, while an unfilled-form violation remains. Their source-first
annotations, measured reports and audit follow-ups are retained in the corpus
evaluation. Merge readiness remains blocked on that violation and the
representative human-review gate.

## Reproduction and full validation

The audited runtime `e0c4ecbfaab773c8ebe69390b5d347441be39cc9` passed
[focused and canonical validation](https://github.com/adewale/geist_fabrik/actions/runs/40108166879):
151 focused tests, 2,318 unit tests, 86 integration tests, 84.07% branch coverage,
all 158 automatic acceptance criteria, hooks, lint, both type checkers, security
and workflow checks, and offline package smoke with the real model and YAKE.
The 83 manual acceptance criteria are not certified by this automatic run.
The [platform matrix](https://github.com/adewale/geist_fabrik/actions/runs/40108166883)
passed Linux/Python 3.11 and 3.12, macOS/Python 3.11, and offline package smoke
on both Python versions. The strengthened corpus verifier also passed all six
corpora; its final source-bound reports and failed broader relevance scores are
linked in the corpus evaluation above. Functional validation is complete for
this runtime; quality remains insufficient for a merge recommendation.

Revision `45aff5021c184229e6861ef1b47142f8be5226eb` expands the temporal large
profile from two to all 32 snapshots. [Full corpus validation](https://github.com/adewale/geist_fabrik/actions/runs/40110002076)
passed all six corpora: 120 replay snapshots plus both full static populations.
[Focused/canonical validation](https://github.com/adewale/geist_fabrik/actions/runs/40110002074)
and the [platform/package matrix](https://github.com/adewale/geist_fabrik/actions/runs/40110002075)
also passed on this revision, with the same test counts and coverage above.
The extraction source and annotations remain unchanged. The final large-profile
inventory matches a separate generation, and every requested snapshot index is
present in the [retained reports](../benchmarks/results/topics/corpora/all-snapshots/index.json).
Broader relevance proxies still fail; complete corpus execution does not close
that quality gate.

The contextual grammar repair in
`427afee5a4c7ae5df044441f4f105c288a75c671` passed
[focused/canonical validation](https://github.com/adewale/geist_fabrik/actions/runs/40123416947):
178 focused tests, 2,345 unit tests, 86 integration tests, 84.12% branch coverage,
all 158 automatic acceptance criteria, hooks, lint, both type checkers,
security/workflow checks and offline installed-package/model inference. The
[platform/package matrix](https://github.com/adewale/geist_fabrik/actions/runs/40123416927)
passed all three platform lanes and both Python package lanes. Empty NLTK
resource paths do not prevent packaged grammar extraction.

The [completed corpus run](https://github.com/adewale/geist_fabrik/actions/runs/40123416962)
passed every requested observation across all six corpora and 120 replay
snapshots. [Source-bound reports](../benchmarks/results/topics/corpora/grammar-repair/index.json)
and the [receipt](../benchmarks/results/topics/corpora/receipt.json) retain exact
inputs, source-file hashes and comparison checks. Stored sampled memberships
match the quality scorer's predictions exactly. Frozen precision/recall is now
0.629/0.881 synthetic, 0.529/0.857 starter, 0.571/0.857 narrative and 0.520/0.625 LYT.
All numeric thresholds pass; LYT still fails its empty-form case on
`important action items`. [Repair decisions and counterexamples](TOPIC_QUALITY_REPAIR.md)
explain why no corpus-specific deletion was added. Human review remains open.

```sh
uv sync --locked --extra vector-search
uv run --frozen pytest tests/unit/test_topic*.py tests/unit/test_dependency_validation.py tests/integration/test_topics.py --no-cov -q
uv run --frozen python scripts/evaluate_topics.py
uv run --frozen python scripts/benchmark_topics.py
./scripts/validate.sh
```

The dedicated workflow runs the exact canonical script after focused gates; the
normal Test workflow supplies platform/Python lanes and offline installed-wheel
smokes. The final PR description links their completed results. Local downloads
are blocked in the execution sandbox, so local compilation and standalone SQLite
probes are supplementary evidence, not a substitute for these real CI runs.
