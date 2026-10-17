# Semantic primitives: verification and test audit

This change applies the Hegel adversarial-property workflow and Openclaw test
audit guidance. Separate reviewers inspected production code and its contracts
before seeing tests or benchmark results. Their findings drove changes to the
implementation and to the properties below. Review is evidence of examined
contracts, not a formal proof that arbitrary BLAS implementations conform.

The Python properties use the project's existing Hypothesis library. Hegel's
guidance supplies the surface, generator, oracle and adversarial-review checks;
this does not claim to run an unsupported Python Hegel library.

## Primary owners

| Contract | Primary proof | Credible failure |
| --- | --- | --- |
| Certified strict/inclusive thresholds equal canonical scores | `test_vector_primitives.py` generated populations and adjacent representable thresholds | An interval misses a boundary or uses the wrong inequality |
| Score enclosure includes an independently computed dot product | Decimal arithmetic at 2,300 digits over prepared binary64 components | Cancellation, underflow or extreme finite inputs invalidate the bound |
| Paired results equal the canonical Cartesian diagonal | Generated paired populations | A new reduction order changes returned scores |
| Exact stable top-k, including across query and peer tiles | Generated dense canonical oracle; boundary table at 129 queries and reduced budgets | A tile drops a possible winner, or ties reorder |
| Streamed pair enumeration and scored pairs preserve ordering and thresholds | Generated dense canonical oracle | Duplicated, omitted, reordered or incorrectly rescored pairs |
| Means and mean decisions agree with canonical `fsum` | Generated independent triangle/cross-population oracle | Diagonal inclusion, empty population or ambiguous threshold errors |
| Score tiles and refinement copies remain bounded | Real kernel operand sizes for wide means, tied top-k and dense ambiguity | A wide peer population or tied frontier creates an unbounded temporary |
| Identity correction verifies equality even on hash collision | Forced collision with unequal directions | A hash becomes a false equality oracle |
| Prepared selections reject invalid indices | Shared malformed-input table | Boolean, fractional, negative or overflowing indices silently select rows |
| Cache values/order survive eviction and caller mutation | `test_text_embeddings.py`, independent encoder output | Stale payload, aliased memory, partial failed-batch publication |
| Overlapping batches encode unique misses and obey LRU/quota | Encoder input ledger and budget-reduction properties | An apparently correct cache encodes everything again or exceeds a lowered quota |
| Backend mutations invalidate prepared state | `test_vector_search_backends.py`, same-length replacement through the public mapping | Length-only invalidation returns an old neighbour |
| Raw and prepared payloads are immutable; views have disposable metadata | Backend owner tests | A caller mutates a vector or changes another caller's shape |
| Native backend CPU reductions respect dimensions and close | Real sqlite-vec backend with width three | Hardcoded 384-wide sentinel or prepared access after close |
| Neighbour cache prefixes retain missing-note rank slots | `test_phase2_return_scores.py`, real backend search ledger and result parity | A large cached request changes the answer to a smaller request |
| SQLite batches respect lowered bind limits | `test_phase2_batch_loading.py`, real connection with lowered limit | A batched neighbour request exceeds SQLite's parameter limit |
| Historical/current neighbourhoods normalize consistently | `test_surprisal_churn.py`, near-tied float32 epochs | Double normalization creates churn with unchanged input |
| Surprisal follows canonical stable ordering | Dense canonical stable-sort and scalar centroid oracle | BLAS/argpartition tie policy leaks into the new explicit contract |
| Filtering reuses candidate inference across novelty/diversity | `test_filtering.py`, real pipeline and encoder input ledger | Each filter re-encodes the same candidate texts |
| Session closure releases the shared cache | Existing `test_embeddings.py` lifecycle owner, now populated before close | Closed sessions retain text/vector state |
| Unlinked-pair top-k preserves full stable ordering | Existing `test_vault_context.py` owner, independent scalar pair oracle | Heap selection changes stable equal-score ordering |

The numerical generators cover empty and singleton populations, zero dimensions,
zeros, duplicates, subnormals, large finite exponents, cancellation and exact or
adjacent threshold boundaries. Collection sizes are bounded where arrays are
materialized; the finite float64 value space remains broad. Larger boundary
fixtures exercise the tiling paths independently of small generated cases.

## Findings acted on

Production review found wide-peer means and tied top-k could exceed temporary
bounds, double normalization could create false historical churn, a native
backend sentinel assumed dimension 384, cache budgets could be lowered without
eviction, and SQL note loading did not honor lowered variable limits. Each was
fixed at its owner. Prepared-state retention and contiguous selections were also
improved; no test-only runtime injection hooks were added.

The test audit found a dense-ambiguity fixture that did not enter its claimed
branch, generators that did not cross query batch boundaries, cache tests that
would pass despite recomputing every vector, and isolated filter tests that
missed reuse across the pipeline. Those owners now exercise the actual resource
or input ledger. An old minimal fake backend was replaced by the real in-memory
backend in the large Cartesian-output owner, preserving its cache and numerical
assertions while exercising the production lifecycle.

## Consolidation and retained contracts

Tests of the previous private normalization/mean helpers moved to public owner
operations when those helpers were removed. Private cache-key shape assertions
became search-count and output-prefix contracts. The existing large matrix test
still protects the absence of millions of per-pair cache entries. The greedy
filter owner spies on actual `any_matches` work rather than supplying mocked
cosine decisions.

Surprisal's old BLAS/argpartition oracle was replaced deliberately: the new
contract requires canonical scores and stable ties. The replacement oracle
materializes the dense canonical matrix and sorts it independently of the
blocked implementation. This changes the numerical policy being tested; it is
not a claim of bitwise compatibility with the old policy. The historical/current
near-tie regression protects against introducing artificial churn under that
policy. Removing an ignored private block-size argument removes an obsolete
seam rather than reducing coverage.

## Baseline proof and cost

The pre-change source at `32f9d0dba57dff1ebe983de4d894a7bffe443f92` fails the
same-length replacement and immutable vector-view regressions, and fails the
lowered SQLite variable-limit regression with `too many SQL variables`.
New primitive APIs do not exist on that baseline: an import or missing-method
failure would not establish their numerical correctness, so those properties
are described as new-contract proof rather than baseline red/green proof.

Timing and complete validation receipts accompany the
[measurement report](SIMILARITY_PRIMITIVES_BENCHMARK.md). The new tests retain
observable contracts rather than source spelling. The main sizeable existing
surprisal oracle now uses a stable NumPy sort instead of a Python per-row sort;
its measured cost fell from roughly 22 seconds to roughly 6 seconds on this
machine without weakening its dense reference calculation. Benchmarks use real
model inference separately from the stubbed fast unit lane.

## Measured owner costs

| Changed owner | Selected cases | Pytest suite seconds | Fresh-process wall seconds |
| --- | ---: | ---: | ---: |
| `test_density_inversion.py` | 13 | 1.325 | 8.546 |
| `test_embeddings.py` | 32 | 0.174 | 7.494 |
| `test_filtering.py` | 10 | 0.081 | 7.586 |
| `test_phase2_batch_loading.py` | 12 | 0.324 | 7.920 |
| `test_phase2_return_scores.py` | 8 | 0.170 | 7.952 |
| `test_surprisal_churn.py` | 31 | 8.253 | 15.616 |
| `test_text_embeddings.py` | 12 | 0.540 | 7.946 |
| `test_vault_context.py` | 45 | 1.770 | 9.423 |
| `test_vector_primitives.py` | 42 | 4.924 | 11.909 |
| `test_vector_search_backends.py` | 69 | 0.542 | 7.328 |
| `test_word_burst_integration.py` | 128 | 10.493 | 17.720 |

All 401 selected cases passed; one pre-existing case skipped.
Fresh-process wall time includes the Python/ML test environment's startup and
teardown, which the normal single-process CI suite amortizes across files.
The larger surprisal owner exercises real default-size neighbour tiles and
historical/current population reuse against its dense independent oracle.
Shrinking it to a tiny fixture would remove that resource/lifecycle contract.
The lexical owner combines 1,000 independent extraction examples with real
SQLite edit/delete and captured-history compositions; its 10.493 seconds
protects storage and parser boundaries rather than a mocked implementation.
CI timing is not yet available; these figures are local measurements.

The production patch adds 989 lines and removes 557; test changes add 639 and
remove 99. This includes the new cache and numerical properties, plus existing
owner upgrades. Benchmark harness changes are counted separately (586 added,
eight removed). These are diff line counts, not a quality metric or a reason
to remove independent proof.

The first validation attempt exposed an existing lexical property's default
200 ms Hypothesis deadline: an initial 343.33 ms execution failed, while the same
input reran in 0.52 ms with the semantic assertion passing. The property checks
sliding-window extraction, not latency. Its 1,000-example target, generated
inputs and independent oracle remain unchanged; only the incidental deadline
is disabled. The outer pytest timeout remains. The initial attempt stopped
after its unit failure, successful integration suite and coverage gate; its log
is retained separately. The final gate reruns the original full suite with
coverage rather than treating an isolated retry as sufficient proof.

## Refinement and unchanged-session follow-up

The follow-up uses baseline `201acf98162ee03272783143249106425cf19836`.
Two fresh production-only reviewers examined numerical selection and SQLite
persistence independently, without tests or measurements. The persistence
review found that sqlite-vec projection loading invalidated the new local
change token, and that external-change rejection could retain a stale backend.
Both were fixed at Session's owner. The reviewer also identified inconsistent
float64/f32 cache composition and caller-owned population-list mutation;
composition now uses the persisted float32 representation and computation
captures a separate list of frozen Notes. A subsequent production-only review
found no remaining defect in those corrections. A separate numerical review
also checked the distinct-direction overlap shortcut, including forced hash
collisions and repeated/reordered selections.

| Observable contract | Primary owner and independent evidence |
| --- | --- |
| Both top-k output formats retain exact stable order | Existing generated canonical dense-sort oracle, now exercising indices and scored APIs, negative/large counts and three tile budgets; 129-query boundary case covers both formats |
| Invalid top-k counts reject even with no query rows | Shared malformed-input table across both public APIs |
| Exact zero/identity work avoids numeric kernels | Existing public decisions/top-k owner with actual NumPy kernels forbidden after preparing its oracle; diagnostic counters also remain zero |
| A repeated compute/search cycle writes no rows and retains its backend | Real SQLite and both real backends; empty, singleton and multi-note populations; reordered input |
| A reopened Session preserves unchanged BLOBs and labels | Real conditional UPSERT path and complete before/after rows, not a mocked writer |
| Local input deletion/change or corrupt persisted vectors forces repair | Real writes, global label invalidation, repaired vector bytes and closed prior projection |
| External rejection invalidates the cached projection | Two database connections and both real search backends |
| An eligible shortcut cannot commit a caller's transaction | Pending real SQLite write remains in its original transaction after rejection |
| Fresh float64 and persistent float32 cache paths agree | A representable rounding boundary exposed through injected model output, followed by full cache-backed recomputation |
| Callback mutation cannot replace the population being validated | Public computer injection mutates the original list and commits deleted notes; captured population is rejected |
| Closing a Session releases cached input text | Weak-reference lifetime check with persistent semantic cache already seeded; the injected computer never sees the tracked text |
| Replacing the embedding computer invalidates accepted state | Cached Session result agrees exactly with a fresh Session using a replacement computer with different temporal features; deterministic recycled-ID fault exercises actual identity admission |
| Mutating a returned search projection cannot poison unchanged computation | Row replacement, whole-map replacement, and explicit reloads through real backends; next search restores persisted vectors without persistent rewrites |
| Accepted state cannot retain a replaced model | Weak-reference lifetime check on a replaced embedding computer |
| Changed retention cannot be hidden by unchanged inputs | Three real sessions, a changed retention setting and a query of the removed oldest rows |

The unchanged-session, reopened-label, cache-representation and caller-population
regressions produce **nine intended failures** on the baseline and pass after
repair. Existing atomic-write rollback, stale/incomplete input, retention and
model-failure owners remain. New APIs unavailable on the baseline are treated
as new-contract proof, not missing-method red/green evidence.

Openclaw's authoring gate kept storage/lifecycle proof in `test_embeddings.py`
and numerical/resource proof in `test_vector_primitives.py`. The old tied
refinement fixture used exact duplicate directions: it now uses distinct but
equal-scoring directions so it still exercises real refinement; exact duplicate
short-circuiting has its own work contract. No runtime hook, exported testing
API or mock implementing the asserted storage behavior was introduced.

Hegel's surface/generator review uses Hypothesis, the project's Python PBT
library. Finite scalar domains still include subnormals and extreme exponents;
only materialized shape/work is bounded. Top-k count generation now includes
negative integers. Existing canonical normalization/threshold/mean properties
remain the owners for unchanged score semantics. No tolerance was widened.
Model identity inside the text cache remains covered by its existing owner
tests; arbitrary mutation of a Session's dated identity
is not a newly supported API. The measurement report records owner cost,
production/test LOC and full validation separately from review results.

The final memory pass also found that the input manifest outlived Session.close.
A weak-reference owner regression failed before the two-field cleanup and is
retained alongside the earlier resource-release tests. Final measurements use
the corrected source; preliminary measurements are excluded from the report.

The final persistence review also found that callers could mutate a returned
search projection without changing SQLite, and that retaining only `id(computer)`
could admit a recycled object ID after replacement. Backend revision tokens now
identify projection mutations; a weak reference with an explicit `is` check
guards both accepted-state reuse and projection-write absorption. The reviewer
rechecked these production-only corrections and reported no concrete defect.
The projection regression produces three intended failures and one passing
native-backend case against the archived pre-guard source. The replacement
regression produces one intended recycled-ID failure and one passing ordinary
replacement against the archived numeric-ID source. These are separate from
the nine baseline failures and the close-lifetime failure. The receipt retains
both intermediate source files and logs so the staged proofs are reproducible.
