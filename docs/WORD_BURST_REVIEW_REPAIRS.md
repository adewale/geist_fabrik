# PR 97 audit repairs and phrase capacity

Historical implementation and measurements: current history retention, execution
budgets and compatibility rules are in [Word bursts](WORD_BURST.md).

Lexical repair and benchmark source: `88a1bd3062178950321eb8c816b718c0191e3a8e`.
Repair baseline: `b036e47754ac699f40816317623ef6744970fb44`.
Evidence checkpoint `d432f84924fca94b1ac4e8dcbfb6fe8bfb6b57f7` strengthens one
migration fixture without changing runtime code. The alarm follow-up below
subsequently corrects host-callback scheduling in `execution_timeout.py`; the
measured detector and aggregation modules remain unchanged. [Machine-readable receipts](../benchmarks/results/word_burst_review_repairs/summary.json)
retain raw timings, source hashes, executor statuses, tests and lossless archives.

## Four confirmed findings

1. Native sqlite-vec Session test parameters lacked the existing macOS capability
   policy. The shared test helper now probes extension loading. Unsupported
   native parameters skip, while in-memory parameters always run and Linux CI
   requires native loading. CI no longer cancels sibling matrix jobs on failure.
2. List-contained fenced code polluted the dictionary and hid subsequent prose.
   Lexical extraction now uses MarkdownIt block maps to exclude code blocks.
3. A global backtick substitution deleted prose between separate paragraphs,
   headings and lists. Inline-code exclusion now follows actual inline blocks.
4. A policy rebuild stamped stale stored text from unreadable sources as newly
   observed. Both rebuild and missing-baseline paths now require a confirmed
   physical source, including the source of virtual entries. Recovery establishes
   a fresh baseline rather than manufacturing an additions interval.

Independent production-code review also found two related boundary errors.
Wiki-link shielding inside Markdown link-label lookahead exposed destinations;
its silent parser callback now preserves normal link parsing. Virtual-entry
splitting stripped code indentation and hard-break spaces; it now removes only
outer newlines. Parser fingerprint 7 refreshes previously split entries.
Extraction policy 6 rebuilds lexical baselines and resets incompatible captured
history. Unchanged note bodies retain their embeddings; corrected virtual bodies
invalidate their own caches. Saved questions remain intact.

Regression tests belong to the existing parser/history/Session owners. The
migration fixture keeps real stat/settings fingerprint fields, so removing only
the parser-version bump makes it fail. The restored code passes. Hegel-guided
independent rational/Decimal oracles and Hypothesis properties check the new
pruning bound against the existing exact model. Openclaw test-audit guidance
informed owner placement, shared capability support and regression verification;
this does not mean canonical autoreview succeeded.

## Phrase analysis

Packed per-week integer IDs and shared duplicate-body spans reduce Python object
work. Unweighted NumPy counting preserves exact integer frequencies. A
conservative total-prevalence bound rejects impossible candidates before sparse
materialization, and sparse batch filling avoids repeated dense lookups. The
default two-state path does less layout screening, decoding more candidates but
spending less total time. Other state grids retain their original pruning.
No terms are sampled or truncated, and the detector's decision policy is unchanged.

The input is the existing 10,000-note benchmark copy, including its earlier
100-note marker edit: 46,637,507 bytes. Both vocabulary runs and their runtime
copies have the same verified source-content manifest. No chronology is claimed
for the synthetic date overlay.

The controlled comparison freezes the same file-backed version-5 dictionary and
changes only the detector and analysis modules. Each phase has two independent
process trials in before/after/after/before order on one Linux/Python 3.12 host.
All ordered findings agree within each vocabulary, including the separately
measured current-policy executor results. These are local observations, not
latency percentiles or whole-application speedups.

| 10,000-note vocabulary | Median analysis before → after | Median process peak RSS before → after |
| --- | ---: | ---: |
| Words and pairs, 42,990 terms | 17.818 → 11.084 s (37.8% less) | 1,243.3 → 1,241.9 MiB |
| Through triples, 821,665 terms | 50.684 → 29.815 s (41.2% less) | 2,266.4 → 2,058.6 MiB |

The packed-ID optimization provides little measured pair-memory improvement;
triple peak RSS falls about 208 MiB (9.2%). These are process high-water marks
including imports, not isolated allocation sizes. Cached analysis code did not
change; observed cache timing differences do not establish a cache speedup.
The comparison excludes extraction-policy migration costs.

Separate fresh policy-6 indexing took 103.7 s for pairs and 182.3 s through
triples. Unchanged sync took 3.07/2.67 s with zero lexical extractions and changes.
These indexing observations have no matched before measurement.

The real executor, with analysis cache cleared, completed default words/pairs in
11.58 s under its 30 s budget. Its cached call took 0.513 s. Optional triples
**timed out** under 30 s; an explicit 120 s budget completed in 30.46 s, followed
by a 0.437 s cached call. Both successful fresh calls returned three questions.
The triple executor process peaked at about 2,059 MiB. For a large optional
trigram vocabulary, use an explicit budget, for example:

```bash
geistfabrik invoke /path/to/vault --geist word_burst --timeout 120
```

This is capacity guidance, not a guarantee that every corpus fits 120 s. The
default timeout stays 30 s. Measurements use a labelled synthetic date overlay
on the existing large corpus and exclude embedding inference, CLI startup and
the full filtering pipeline. They cannot establish historical accuracy or reader
usefulness.

## Validation and remaining gates

Fresh 32-snapshot replays completed the smoke (128 initial notes), standard
(1,000) and large (10,000) temporal profiles with `ngram_max=3`. All 192
word-burst executor calls succeeded across both history modes. Each profile/mode
produced rising and declining words and phrases. These replays skip semantic
geists and real embedding inference; analysis primes the lexical cache before
the executor call. They verify temporal behavior, not uncached executor capacity
or owner usefulness. Earlier real-model multi-geist runs remain documented in
[the historical performance report](WORD_BURST_PERFORMANCE.md).

The four directly affected test owners separately passed 314 tests with one
existing skip. Their JUnit receipts preserve per-test timings.

The complete local `scripts/validate.sh` gate passed after the stronger migration
fixture: 1,927 unit tests, 81 integration tests, 155/155 automated acceptance
criteria, 45 bundled geist firing contracts and 82.71% branch coverage. Lint,
strict typing, security, workflow checks and installed-package real-model offline
inference passed. The earlier source-only gate passed separately.

[Source CI run 39080482479](https://github.com/adewale/geist_fabrik/actions/runs/39080482479)
passed macOS/Python 3.11, Ubuntu/Python 3.11 and 3.12, and both package-smoke
jobs. This replaces the earlier red/cancelled matrix; final evidence-commit CI
must also pass before merge.

Canonical Openclaw autoreview was attempted against the committed repair range
using the official helper, after all 33 input/context public Git blobs were
verified. It failed with HTTP 401: “Could not parse your authentication token.
Please try signing in again.” Status is `reviewer_unavailable`, with
`report_produced: false`. No canonical review verdict exists. A working Codex CLI
login or an already configured authenticated provider is needed to complete it;
independent reviews do not substitute for that report.

The real-date Kepano run used the default detector on an isolated copy, preserved
source hashes, and correctly abstained for insufficient documents. It has only
four dated notes across September 12–30, 2023. No owner-rated real-vault evaluation
has been completed. [The evaluation guide](WORD_BURST_EVALUATION.md) gives the
chronology, normal-CLI and reader-judgment procedure. A suitable vault and its
owner's judgments remain necessary to assess useful versus already-known prompts.

## Follow-up: macOS host-alarm failure

The evidence checkpoint's [run 39081882510](https://github.com/adewale/geist_fabrik/actions/runs/39081882510)
passed both Ubuntu jobs and both package-smoke jobs, but macOS failed one existing
host-alarm test. The complete authenticated run-level ZIP was recovered after
workflow completion; the redirected job log was inaccessible. The macOS unit log
records 1 failed, 1,883 passed and 44 skipped. The lexical/native regressions pass.

The failing test expected at least two periodic SIGALRM deliveries during a fixed
200 ms sleep, then inspected a counter with the timer still active. POSIX periodic
signals can coalesce while a runner is descheduled. Its failure renders as
`assert 2 >= 2`, consistent with another delivery between the comparison and
assertion formatting. This is concrete evidence of an asynchronous test oracle,
rather than a reason to rerun CI until it passes.

The primary test now models only the public signal/timer API and a monotonic
clock. It delivers through the handler installed by `signal.signal`, checks known
host deadlines and verifies remaining delay, period and original handler on exit.
Only the timeout module's bindings are replaced; real process timers, including
pytest-timeout, remain untouched. The adjacent OS integration test keeps real
host delivery and a real plugin timeout, disarms before asserting, and accepts
coalesced deliveries. Repetition and phase belong to the deterministic oracle.

Independent production-only review also exposed runtime errors: late delivery
shifted a periodic timer's phase; a raising callback left an expired host deadline
for cleanup; catching that exception inside a plugin could leave its own earlier
deadline unarmed. The dispatcher now schedules the next original-phase tick,
coalesces missed ticks, reconciles the host's timer in `finally`, and re-arms the
multiplexed deadline before propagating a host exception. Cancellation and
replacement timers survive exceptions. The callback's exception is preserved.

Before these production corrections, four deterministic cases fail and the
on-time control passes. Afterwards, all nine focused alarm tests pass. A separate
mutation that chooses the later deadline is rejected. Independent standalone
probes pass early delivery, cancellation/replacement followed by raising, and
cancellation/replacement with a caught exception. The raw failure, red/green runs,
mutation and independent probes are retained in `alarm_followup.json` and its
lossless receipt archive beside the original summaries.

The complete follow-up `scripts/validate.sh` gate passed: 1,931 unit tests,
81 integration tests, 155/155 automated criteria, 45 bundled firing contracts and
82.69% branch coverage, plus strict typing, lint, security, workflows and
installed-package real-model offline inference. Final-head platform status is
recorded in the PR checks. The receipt also retains an interrupted run and a
network-denied dependency-fetch run; neither is counted as a successful gate.

The analysis timing/memory measurements above remain tied to source `88a1bd3`.
This follow-up changes the host-callback branch of the deadline dispatcher, not
the measured word-burst kernels. Its validation and platform CI are separate
from the historical green source run and the failed evidence checkpoint.

## Receipt format

The frozen-dictionary timing inputs are identified by their compressed database
hashes but are not committed. Reproduction requires rebuilding the policy-5
dictionaries from the named benchmark copy, or retaining those local inputs;
the current-policy executor harness builds fresh dictionaries. Archived harnesses
record the workspace paths and commands actually used.

`summary.json` links lossless XZ archives. For a multipart archive, concatenate
its listed `parts` in order, verify `xz_sha256`, decompress, then verify
`raw_sha256`. Each part is smaller than the repository's large-file hook limit.
The receipts bundle maps original filenames to complete text, including harnesses
and validation logs; temporal archives retain the complete snapshot reports.
Working databases and model environments are deliberately excluded.
