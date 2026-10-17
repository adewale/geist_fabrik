# Evaluating word-burst questions on a real vault

Synthetic corpora establish whether planted changes are detected. They cannot
establish whether a question tells the vault's owner something useful.

Start with the default detector settings and actual declared dates. A current
text cohort measures vocabulary in today's note bodies grouped by those dates;
it does not reconstruct old versions. Captured additions require real sync
history. A fresh database establishes baselines rather than inventing additions.

For a reproducible dated-text benchmark, the existing harness can now retain
source chronology instead of assigning synthetic weeks:

```bash
uv run python scripts/benchmark_word_burst.py /path/to/vault \
  --real-dates --end-day 2026-10-17 --trials 1 \
  --output /tmp/word-burst-real-dates.json
```

The harness uses an isolated copy, a fresh database and the default detector
configuration; `--ngram-max` controls extraction. It records declared-date
coverage, abstention reasons, unfiltered questions, timings and a source-content
digest. Its incremental-edit phase changes only the copy. This measures the
lexical geist without embedding inference or the complete novelty/diversity
pipeline. Use the normal CLI to evaluate a configured vault's saved history and
filtered session output.

The local ten-note Kepano fixture has only four dated notes, between September 12
and September 30, 2023. With `--end-day 2023-09-30`, the default detector abstains
because it needs at least 50 observations and eight populated weeks. Assigning
dates or lowering thresholds until it fires would not prove usefulness.

For a vault with sufficient evidence, have its owner assess questions from
several session dates. Keep the source, configuration, cutoff and previously saved
questions fixed for each comparison. Record one of these judgments with a short
reason for each question:

- Useful: the linked comparison suggests a worthwhile connection or next step.
- Already known: the change is accurate but adds no useful perspective.
- Noise: boilerplate, a temporary project label or wording dominates the result.
- Incorrect: the evidence, dates, population or claimed change is wrong.

Inspect rising and declining words and phrases separately. Check the cited
passages; a decline does not establish a forgotten belief. Count repeated
questions after normal saved-history suppression, rather than treating a new
wording of the same evidence as new value. Report useful questions as a fraction
of reviewed questions, alongside the number of distinct episodes and abstaining
sessions. Keep factual errors separate from accurate but unhelpful prompts.

No owner-rated real-vault evaluation has been completed. The available fixture
supports an abstention check; the large and temporal synthetic corpora support
correctness and capacity checks. Reader usefulness remains an explicit evaluation
gap until a suitable vault and its owner's judgments are available.
