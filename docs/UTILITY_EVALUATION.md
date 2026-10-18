# Local Utility Evaluation Readiness

**Last reviewed:** 2026-10-18

The repository now supports an authored fictional usefulness evaluation. It does
**not** contain enough independent owner judgments to estimate real-user utility.

## What exists

- One checked-in public sample vault, `testdata/kepano-obsidian-main`, containing 10
  Markdown notes (26 files and about 104 KiB including Obsidian configuration,
  examples, and licensing).
- Synthetic unit and integration fixtures designed to trigger individual code
  paths and verify deterministic, bounded, and safe behaviour.
- Performance benchmarks for query counts, runtime, clustering, and vector
  backends.
- A changing temporal corpus with eight stock topic sentences and planted
  scenarios, plus a separate scrambled-prose capacity corpus. Neither is a
  curated fictional author's working vault.
- A pinned authored public knowledge-wiki comparison for lexical workload
  features. It supplies no owner judgments or reconstructed writing history.
- A coherent fictional notebook, `testdata/narrative_vault`, with two years of
  notes, actual text revisions, virtual journal entries, a backdated import,
  templates and an external persona/evaluation ledger. Both lexical history
  modes run through the full production invocation path with every bundled
  geist and real offline inference. Selected questions receive an explicit
  author-side assessment against the ledger.

See [the narrative evaluation](NARRATIVE_VAULT_EVALUATION.md) and
[the preceding trigram investigation](WORD_BURST_TRIGRAM_RISK.md).

This is enough to measure mechanical properties such as correctness, output
shape, empty-result rates, determinism, latency, and regressions. It is not
enough to estimate those qualities for real readers. The narrative fixture can
expose obvious observations, misleading claims, repetition and plausible useful
comparisons in one author's fictional context. Its author-side judgments are
not independent ratings, and its simple linked-note baseline does not establish
superiority to competing approaches.

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

Until independent owner evaluation exists, distinguish correctness/performance
measurements and fictional author-side assessments from real-user utility.
