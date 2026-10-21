# Narrative quality repair receipts

Runtime and observer checkpoint: `5cff8faf1977dd30d2b0add962d325f1e1ec0265`.
The before result is the unchanged [original narrative evaluation](../narrative_vault_v1/summary.json).
The [report](../../../docs/NARRATIVE_QUALITY_FIXES.md) describes fixes, outcomes,
costs and limits. The story, persona and ledger remain frozen.

[summary.json](summary.json) includes every geist's before/after counts, exact
model/dictionary conservation checks, repeat-run parity, real-model temporal
checks, matched capacity measurements and validation status. The main archive
is `receipts.json.xz`: XZ-decompress it, parse the resulting JSON object, and
encode each value as UTF-8 to recover the named file's original bytes.
Hashes and byte-recovery verification are in the summary. The separate
`test-audit-receipts.json.xz` preserves isolated pre-fix/fixed regression proof.
The final validation log is compressed separately as `validation.log.xz`.

Receipts retain raw candidates, filtered/selected output, all CLI logs, actual
executor profiles, cache diagnostics, source/model hashes and measurement
scripts. They also retain superseded benchmark entry-point/preflight errors
and the supplemental capacity root run, explicitly excluded from the matched
comparison. Temporary databases and model weights are not duplicated.

The full narrative replay covers all 45 bundled geists, both history modes,
real offline inference and saved production sessions. The temporal smoke run
covers 13 distinct temporal/similarity geists over 32 snapshots with real
embeddings. Capacity runs use frozen copied 10,000-note dictionaries, labelled
synthetic dates and actual fresh/cached executors; they exclude inference.
The repeat observed replay keeps the latency outlier investigation inspectable.

This evidence proves specified behaviors and reports local costs. It does not
supply an owner-rated usefulness result or a canonical autoreview report.
