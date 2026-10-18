# Narrative vault: Mara, version 1

An authored fictional notebook for evaluating questions in context. Read
[the persona](persona.md) and [the independent ledger](ledger.json) before
reviewing outputs. None of those files is ingested. `notes/` contains readable
initial note bodies; `entries.json` controls availability, `revisions/` contains
replacement prose, and `revisions.json` schedules edits and a deletion.
`journal.json` supplies dated entries for one date-collection source.

The story covers 24 monthly snapshots in 2024–2025. All dates are invented. Six
2022 clippings are imported together in September 2024; their declared dates
are deliberately different from their observed arrival. Quoted passages are
also invented. Engine journals accumulate independently of source snapshots.

Compile and open an ordinary Markdown vault:

```bash
uv run python -m scripts.generate_narrative_corpus /tmp/mara-corpus
uv run python -c 'from pathlib import Path; from scripts.generate_temporal_corpus import apply_snapshot; apply_snapshot(Path("/tmp/mara-corpus"), Path("/tmp/mara-vault"), 0)'
```

Apply subsequent indexes sequentially with the same command. The existing replay
tool refuses nonempty unowned vaults, changed manifests and corrupt objects.
The source corpus and evaluation outputs must stay outside the replay vault.

Run the whole production invocation path, including real offline embeddings,
every bundled Code/Tracery geist, filtering, default selection and journal writes:

```bash
GEISTFABRIK_OFFLINE=1 uv run python -m scripts.evaluate_narrative_vault \
  /tmp/mara-corpus /tmp/mara-dated --mode dated_cohorts --output /tmp/mara-dated.json
GEISTFABRIK_OFFLINE=1 uv run python -m scripts.evaluate_narrative_vault \
  /tmp/mara-corpus /tmp/mara-observed --mode observed_additions --output /tmp/mara-observed.json
```

The harness enables optional trigrams to exercise phrase support; all thresholds,
timeouts, filtering and five-question selection retain production defaults.
Only the source-capture clock is set to the fictional observation time. Inference,
geist execution and filtering are real. Reports distinguish raw output from
filtered, selected and saved output and retain errors and empty results.
This is an initial authored usefulness proxy, not evidence of real-reader utility.
