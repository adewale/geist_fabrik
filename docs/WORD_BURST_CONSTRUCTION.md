# Correctness by construction: audit repairs, 2026-10-17

This closes the findings recorded in the
[2026-10-16 audit](WORD_BURST_NUMERIC_AUDIT_2026-10-16.md). That report remains
an historical record of the audited head, rather than being rewritten to look clean.
The runtime checkpoint is `abfdec672edaaf0b3ad5a647ed80552f6616aca9`.

## Representations and invariants

| Finding | Construction that prevents recurrence | Primary proof |
| --- | --- | --- |
| Tabs broke normalized-to-source link matching | Markdown block line maps establish coordinates; inline parser spans remove metadata without inferred character offsets | Existing extraction owner extended with tab/list forms |
| Parentheses, titles and multiline destinations leaked | One parser path handles ordinary links, references and images | Visible-prose syntax table and generated reference windows |
| Unicode casefold created words with no excerpts | Words retain combining marks and source spans; counting and excerpts consume the same tokens | Independent Unicode sliding-window oracle and excerpt agreement |
| Host timezone changed declared cohorts | A dedicated calendar-day API reads the declared date before any timezone conversion | Real sync under UTC, Helsinki and Los Angeles |
| Float division hid tiny declines | `DocumentRate` contains validated integer counts; decisions compare exact fractions | Arbitrary-integer properties and the audited cross-product-minus-one example |
| Rounded percentages hid actual changes | Both exact rates are formatted together, increasing precision until distinct | Independent Decimal oracle and renderer transport in both directions |
| Repetition invented centroid dispersion | Float64 offsets are centered relative to one input vector; identical inputs subtract to exact zero | Generated identical populations through the actual geist, retained positive control |
| Scalar/batch/cache order changed thresholds | One scale-safe kernel uses fixed per-pair reduction independent of batch shape | Existing independent math oracle strengthened with exact scalar/matrix equality; separate cache transport owner |
| Threshold one retained repeats | Equal nonzero directions have exact similarity one; exact text identity also handles zero vectors | Actual novelty/diversity filter decisions at one, with positive and zero vectors |
| Tiny/huge cosine norms underflowed/overflowed | Scale each row before float64 normalization | Non-identical directions across the full positive finite float64 range, including subnormals |
| Bare-CR frontmatter entered prose | Normalize physical EOLs before lexical frontmatter parsing | Existing prose owner with bare-CR metadata |

Independent production-only review also found and closed comment masking that
erased code indentation and blockquotes nested in lists. Comment masking now
preserves indentation and physical line count without creating fences. Parser
blockquote maps cover nested containers. Shared direction objects store immutable
bytes and dimensions; disposable read-only NumPy views cannot corrupt their
identity keys by changing data or array metadata.

## Numeric policy and compatibility

Counts remain Python integers through decisions and cache serialization.
Fractions are used for rate comparisons, not for dense embedding arithmetic.
Derived float rate properties remain available for existing report consumers.
The paired percentage formatter rounds exact rationals and also supports counts
beyond Python's decimal-string conversion limit.

Embedding storage remains float32. Semantic computations promote to float64;
centroid offsets prevent a population-dependent artificial signal. A scale-safe
norm covers finite directions far outside stored-model magnitudes. The detector's
existing adaptive high-precision likelihood path is unchanged: the independent
audit found no demonstrated detector defect.

The in-memory backend caches immutable normalized rows at its existing
load/rebuild/close boundaries. Optional sqlite-vec neighbour search still returns
native float32 scores; its pair-similarity API uses the canonical kernel.
Neither the legacy general Note timestamp API nor general HTML attribute handling
is redefined by the lexical extraction repairs.

Extraction policy 5 rebuilds incompatible lexical baselines and clears captured
observations; existing notes, embeddings and saved questions remain intact.
Prospective history starts again at the new baseline. Analysis version 5 rejects
older cached findings. This reset is necessary: incompatible tokens and dates
must not silently coexist in one historical series.

## Verification ownership

Applied [Hegel guidance](https://github.com/hegeldev/hegel-skill/blob/main/skills/hegel/SKILL.md)
and [Openclaw test-audit](https://github.com/openclaw/openclaw/blob/main/.agents/skills/test-audit/SKILL.md).
Three separate reviewers derived production-only probes without reading tests or
recorded results; a fourth audited test ownership and generator quality.
The final prose review passed 576 structural probes. Numeric review included
30,059 initial independent rate checks and 3,029 follow-up magnitude/rounding
checks, including 4,500-digit displays. Vector review used a Decimal100 oracle,
scalar/batch/symmetry probes and actual backend cache lifecycle checks.

Initial new regressions failed against the audited implementation: 24 failures,
127 passes. The first repair run exposed an upstream rule imported as a module;
concrete function imports fixed the implementation rather than weakening tests.
The expanded focused run passed 344 tests, with one optional-backend skip.
Subsequent cache/direction owners passed 109 and 86 tests respectively (one skip
in each); final integer/range properties passed 36 tests and both renderer
transport cases passed. These overlapping runs are not summed as unique tests.

The audit removed the obsolete `fast_path` toggle alongside its test dimension;
nonfinite-input rejection remains covered. Existing independent detector,
storage, positive-trigger, and bounded-memory owners remain. No tolerance was
widened. An irrational cosine oracle has a documented 3e-16 absolute allowance;
identity, cache agreement and percentage ordering use exact assertions.

The [performance report](WORD_BURST_PERFORMANCE.md) records the completed original
10,000-note run, real-model smoke/standard temporal replays, Kepano abstention,
and persisted novelty endpoint probe. All 576 temporal executor calls succeeded
with unchanged stable meaning vectors. The large fresh executor took 25.914 s
within the normal 30-second budget, while unchanged sync extracted zero notes.
Fixed-order arithmetic has a real throughput cost relative to BLAS: a bounded
1,000-by-1,000 kernel probe took 0.144 s versus 0.00753 s. Caching normalized
directions reduced 20 canonical neighbour queries from 2.064 s to 0.273 s.

## Final validation and review receipts

Full `scripts/validate.sh` passed at `dff03bfec0c3b0174171687f843cf69862967564`:
1,816 unit tests (one skipped, eight deselected), 81 integration tests (eight
deselected), 155/155 automated acceptance criteria, 82.16% branch coverage,
all 45 bundled geists firing, strict type/lint/security/workflow checks and
installed-wheel real offline model inference. The 83 manual acceptance criteria
remain unverified. Runtime, tests, scripts and lock match checkpoint `abfdec6`.
The [validation receipt](../benchmarks/results/word_burst_construction_validation.json)
anchors the lossless complete log with raw and archive SHA-256 hashes.

The unmodified canonical Openclaw autoreview helper targeted source commit
`abfdec6`, with four frozen caller/contract files.
All 43 before/after and context blobs first matched unauthenticated public
GitHub copies byte-for-byte. The helper attempted one Codex review, failed
authentication, and returned `reviewer_unavailable`, `report_produced: false`.
The [review receipt](../benchmarks/results/word_burst_construction_review.json)
records this outcome and links the public-input proof. This is not a clean
canonical verdict. PR #97 remains draft awaiting authenticated canonical review;
the independent reviews above do not substitute for that report.

This final receipt update changes only documentation/evidence. Local full
validation is separate from the GitHub Actions platform matrix, which was
in progress on `dff03bf` when these receipts were recorded.
