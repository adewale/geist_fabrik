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

The [human review packet](TOPIC_QUALITY_REVIEW.md) contains every current real
source and both prediction sets. Its response record is explicitly pending. The
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

## Reproduction and full validation

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
