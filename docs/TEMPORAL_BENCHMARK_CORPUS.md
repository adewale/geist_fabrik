# Temporal benchmark corpus

`scripts/generate_temporal_corpus.py` creates deterministic, entirely synthetic
Obsidian snapshots. The smoke, standard and large profiles begin with 128, 1,000
and 10,000 notes. Each has 32 weekly observations from 2026-01-05 to 2026-08-10,
with declared creation history extending back 540 days. New notes increase the
population; deletion removes a cohort at week 24.

Sixty percent of initial notes are byte-stable controls. Other cohorts undergo
semantic rewrites every four weeks, an abrupt rewrite at week 16, or accumulating
weekly writing. `aurora` appears in weeks 8–11 and `quasar` in weeks 22–25 in
both new dated notes and additions to existing notes. Body identities are
alphabetic so lexical normalization does not collapse independent numeric IDs.
Declared modification dates and two backlinks per initial note support age and
recent-focus geists. A changing dated-entry journal exercises virtual identities.

Generation stores content-addressed SHA-256 objects and manifests/deltas rather
than duplicating unchanged notes. Replay validates object hashes and contained
paths before applying a snapshot. It refuses occupied unmarked vaults, changed
corpus identity and out-of-order snapshots. Replay directories must be outside
the corpus. Use only a dedicated benchmark destination; replay is sequential,
not a crash-atomic replacement of the filesystem.

```bash
python scripts/generate_temporal_corpus.py /tmp/temporal-smoke --profile smoke
GEISTFABRIK_OFFLINE=1 uv run python scripts/benchmark_temporal_geists.py \
  /tmp/temporal-smoke /tmp/temporal-replay \
  --real-embeddings --output /tmp/temporal-results.json
```

Omitting `--real-embeddings` runs both lexical modes and explicitly skips semantic
work. With it, replay uses the real bundled model on CPU, real sessions and eight
bundled geists. The benchmark harness simulates observation clocks; the production
feature has no backdating flag. Exceptions are recorded and fail the runner.
Raw suggestions, findings, timings and unchanged-control meaning-vector checks
are retained. Identical text must have identical 384-dimensional meaning bytes;
calendar features are excluded from that comparison. A stable note can correctly
have changing neighbours when other notes change.

Episode detection can retain a completed historical burst after its planted
writing stops. Expected windows describe the corpus's writing schedule, not
guaranteed exact boundaries of the model's optimum. Two supporting weeks are
needed before the default observed-addition policy can surface a new term.
The fixture establishes reproducibility and useful temporal signals, not human
judgments of suggestion quality. Seasonal similarity may remain silent because
the corpus does not deliberately make creation-month topics coherent.

Fresh results and limitations are in [WORD_BURST_PERFORMANCE.md](WORD_BURST_PERFORMANCE.md).
