# Topic verification

[Automatic local topics](TOPICS.md) is the current design/results entry point.
[Structured current results](../benchmarks/results/topics/current.json) bind the
measurements to code, inputs, CI jobs and exact-byte evidence archives.

Validated runtime: `507f98e1731871f40f6d37e7c6736e75e460d541`.
The selection freeze and later workflow/docs commits preserve its source bytes.

| Check | Measured result |
| --- | --- |
| Focused regressions | 306 passed; 21 subtests passed. |
| Canonical unit/integration | 2,471 unit passed, 1 skip; 88 integration passed. |
| Branch coverage | 3,953/4,704 = 84.03%, above the unchanged 70% floor. |
| Acceptance runner | 158/158 automatic criteria passed; no parse/evidence errors. |
| Platforms and offline packages | All Linux/macOS lanes and both Python package lanes passed; real model inference and extraction without NLTK resource downloads. |
| Complete corpus scope | Six corpora, all 120 ordered replay snapshots and both static populations passed. Every input inventory matches the earlier full run. |
| Corpus invariants | Exact spans/positive queries, unchanged source bytes, zero warm extractions, four full fresh-rebuild comparisons and stable-source checks passed. |
| Selection evidence | 128 combinations plus separate role ablation; only local-full qualifies; no rule-count reduction. |
| Independent quality | Queued for a runner; annotations/selection frozen before output inspection. |
| Delivery | Draft: existing unused-form failure and human relevance/representativeness remain open. |

[Canonical/focused CI](https://github.com/adewale/geist_fabrik/actions/runs/40206794180),
[platform/packages](https://github.com/adewale/geist_fabrik/actions/runs/40206794158)
and [full corpus replay](https://github.com/adewale/geist_fabrik/actions/runs/40206794210)
are completed. The 83 manual criteria are repository-wide prose checks, not 83
outstanding topic reviews. Passing mechanics does not certify topic usefulness.
Historical raw outputs and unrated review records remain in the
[durable archive](../benchmarks/archives/topics/README.md).

Required operation checks remain `./scripts/validate.sh` and the focused topic
workflow. Local dependency downloads were unavailable; standalone helper/parser
replays supplement the actual locked-dependency CI evidence above.

The [independent evaluation](https://github.com/adewale/geist_fabrik/actions/runs/40252867577)
is queued with the frozen selection archive. It has produced no inspected result.
A completed negative result must be retained without policy or annotation tuning.
