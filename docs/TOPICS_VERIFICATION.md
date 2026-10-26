# Topic verification

The current design, boilerplate policy and evaluation method are in
[Automatic topics](TOPICS.md). This file records measured status, not approval.

| Checkpoint | Status |
| --- | --- |
| Published e314804 before policy refactor | Canonical, 179 focused, 2,346 unit, 86 integration, 84.12% branch coverage, 158 automatic acceptance criteria, all platform/offline package lanes passed. |
| Earlier full corpus runtime 427afee5 | All six corpora, all 120 replay snapshots, exact evidence, unchanged source bytes, zero warm extractions and four final-state rebuild comparisons passed. |
| Local sentence grammar and selection explanations | Real focused tests passed306 +21subtests; final validation running. |
| 128-policy calibration and selected-policy receipt | All 128 policies and the separate role arm measured; only local-full qualifies. |
| Sixteen-note independent model holdout | Annotations withheld from quality-output inspection; receipt frozen before evaluation. |
| Empty forms and human usefulness | Existing false topic remains visible; no human relevance approval recorded. |

The repository-wide 83 manual criteria are prose verification cells, not 83
outstanding topic-specific reviews. Automatic correctness is separate from label
usefulness. Historical source hashes and CI job IDs remain in the
[readable corpus receipt](../benchmarks/results/topics/corpora/receipt.json)
and [archived raw evidence](../benchmarks/archives/topics/README.md).

Required operation checks are unchanged:

```sh
./scripts/validate.sh
uv run --frozen pytest tests/unit/test_topic*.py tests/unit/test_dependency_validation.py tests/integration/test_topics.py --no-cov -q
```

The corpus workflow replays every requested corpus/snapshot; the package lanes
exercise real extraction with an empty NLTK resource path and real offline model
inference. The cloud workspace cannot install locked dependencies through its
unavailable proxy; standalone archive/experiment helper tests and syntax checks
are supplementary. Actual runtime claims require the linked CI execution.
