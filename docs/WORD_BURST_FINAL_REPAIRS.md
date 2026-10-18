# HTML evidence and canonical score repairs

The final adversarial audit of PR #97 at `36e5e59795b636a29406cf014b617b68c493eb6a`
found two correctness defects. Both have focused regressions that failed before
the repairs. Trigrams remain optional; the default is `ngram_max: 2`.

## Visible lexical evidence

A 72-note, 12-week fixture placed `<span class="orchard">Visible weather
notes.</span>` in the final 24 notes. The former extractor reported `orchard`
at 24/24 observations against a 24/72 window baseline. The bundled renderer
asked a question through `orchard visible` and quoted HTML attributes as prose.
The repaired public analysis produces no hidden-term finding and its current
passages contain `Visible weather notes`.

MarkdownIt still owns Markdown code, links, entities, escapes and quote maps.
Python's HTMLParser owns HTML attributes, raw script/style content and entity
decoding. Only complete CommonMark HTML tokens enter it as markup. Literal
escaped text and already-decoded labels enter as data, preventing both active
tag reconstruction and double entity decoding.

An excluded opening cannot activate HTML state. An eligible opening owns its
multiline attributes and hidden closing syntax; preserving that syntax does not
admit excluded trailing data. Parser-owned Markdown code is masked before HTML
token discovery, so a literal closing tag in a fence cannot end a real element.
Inline formatting preserves visible adjacency. Blocks and removed non-prose
interrupt phrases. HTML blockquotes follow the existing quote option. CSS and
browser layout are outside this conservative extraction policy.

Extraction policy 7 rebuilds incompatible lexical baselines on sync and clears
captured additions from earlier PR builds. It preserves notes, embeddings and
saved questions, and never reconstructs historical prose. A real upgrade probe
captured one event under policy 6, upgraded, and retained the current baseline
with zero events. Subsequent unchanged sync remains stable.

## Population-independent arithmetic

With seed 932 and two `(3, 8193)` normal matrices, the former Cartesian canonical
score was `0.012348492992272647`. Sparse refinement returned
`0.012348492992272649`, so strict comparison against the canonical score returned
true instead of false. NumPy's `optimize=False` did not prescribe one reduction
order across iterator-buffer and batch shapes. Normalization also depended on
shape for some wide inputs.

Normalization, corresponding pairs, Cartesian scores and ambiguous refinement
now share an explicit adjacent-pair binary64 tree. Materialized products prevent
multiply/add fusion; each separate elementwise addition combines the same
components regardless of population shape. Odd components carry unchanged.
Zero and identical-direction corrections remain explicit. The existing
conservative BLAS error bound also encloses this tree; unambiguous decisions
still use optimized estimates.

Products and alternating scratch buffers are chunked by dimension. Both buffers
are released before the next chunk; otherwise a new allocation could temporarily
overlap the preceding chunk. The allowance covers explicit working payloads,
with an intrinsic one-vector exception; inputs, requested outputs, metadata and
native iterator scratch remain additional costs.

Some canonical score bits change from the earlier PR build, including at 384
dimensions. A seeded 32-row comparison found a maximum difference of
`1.53e-16`. This is an intentional arithmetic-policy correction, not a claim
that all old threshold ties remain unchanged. Stored embeddings are unchanged.

## Measured costs

Warm microbenchmarks compare the audited head with the repaired source. Each
workload/mode ran in a separate subprocess with one BLAS thread, one warmup and
five timed calls. Memory is a separate traced call, including requested outputs
but excluding prepared input arrays. Process RSS, raw trials and source hashes
are retained separately. These are not end-to-end invocation predictions.

| Workload | Before | After | Traced peak before / after |
| --- | ---: | ---: | ---: |
| Prepare 10,000 × 384 directions | 93.35 ms | 93.78 ms | 62.50 / 62.50 MiB |
| All canonical scores, 20 queries × 10,000 peers | 48.52 ms | 268.32 ms | 1.53 / 2.54 MiB |
| 10,000 corresponding pairs | 31.39 ms | 34.79 ms | 0.08 / 1.01 MiB |
| Certified threshold decisions, 20 × 10,000 | 16.56 ms | 21.82 ms | 0.42 / 0.42 MiB |
| Exact top-10, 20 queries × 10,000 peers | 11.96 ms | 14.10 ms | 4.13 / 4.24 MiB |
| Extraction, first 100 stress-corpus notes / 455,960 bytes | 615.20 ms | 573.46 ms | 7.20 / 7.20 MiB |

The complete canonical matrix is 5.53 times slower, adding about 220 ms for this
shape. The temporary product/tree buffers add about 1 MiB. Certified decisions
and top-k have smaller observed increases, although they are not free of
refinement costs. The extraction difference is too small and noisy to claim a
speedup. The first exploratory run overlapped development/probes and used 1,000
notes; it is excluded from this final comparison.

## Verification

The original seven focused cases failed on the audited source for the expected
reasons. The repaired focused owner suite passes 289 cases. An additional
synthetic mutation removing buffer release fails the new public paired-scoring
memory regression; this mutation is not presented as historical baseline proof.

Separate reviewers derived probes without reading repository tests. Numerical
checks cover empty/odd dimensions, 8193 and 131073 components, extreme finite
values, zero/identical rows, independent preparation, threshold boundaries,
stable top-k, streams, means and working-buffer lifetimes. HTML checks cover
120 attribute combinations, 18 provenance comparisons, closing/exclusion
controls, parser-owned fences, the real 72-note analysis and policy upgrade.
The Openclaw test audit retained independent value oracles and updated obsolete
numeric-kernel instrumentation instead of adding test-only production seams.

The complete `./scripts/validate.sh` gate passed in 564.64 seconds: 2,142 unit
tests, 81 integration tests, 158/158 automated acceptance checks and 83.67%
branch coverage, plus lint/security/type/workflow checks, package builds and
installed-wheel real-model offline inference. Source/test hashes remained
unchanged throughout validation. Exact bindings are retained in the follow-up
benchmark receipts. Earlier PR benchmark receipts remain evidence for their
recorded source hashes; this repair does not relabel them as measurements of
the new arithmetic or extraction policy.
