# Local Utility Evaluation Readiness

**Last verified:** 2026-09-13

The repository does **not** currently contain enough evidence to measure user
utility locally.

## What exists

- One checked-in sample vault, `testdata/kepano-obsidian-main`, containing 10
  Markdown notes (26 files and about 104 KiB including Obsidian configuration,
  examples, and licensing).
- Synthetic unit and integration fixtures designed to trigger individual code
  paths and verify deterministic, bounded, and safe behaviour.
- Performance benchmarks for query counts, runtime, clustering, and vector
  backends.

This is enough to measure mechanical properties such as correctness, output
shape, empty-result rates, determinism, latency, and regressions. It is not
enough to estimate whether suggestions are relevant, surprising, specific,
actionable, repetitive over time, or preferable to the current alternatives.
The fixtures encode expected program behaviour, not independent judgements of
suggestion quality.

## Evidence needed

A useful local evaluation set should be opt-in and kept outside the repository
when it contains personal notes. At minimum it needs:

1. Several representative vaults with different sizes, link densities,
   writing styles, and dated histories—not multiple synthetic variants of one
   shape.
2. Frozen input snapshots and exact configuration/model provenance so runs are
   reproducible.
3. Blinded per-suggestion judgements from the vault owner for relevance,
   surprise, specificity, and whether the suggestion led to a useful action or
   edit. Empty sessions and rejected suggestions must remain in the denominator.
4. Repeated sessions across dates to measure fatigue and repetition, not only
   one-shot appeal.
5. A comparison baseline (for example the previous release or a simple random
   note-pair prompt) so a score has an interpretable reference point.

Until that corpus and judgement protocol exist, local numbers should be called
correctness or performance measurements—not utility measurements.
