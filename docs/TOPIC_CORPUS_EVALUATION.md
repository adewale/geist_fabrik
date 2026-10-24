# Topic evaluation on the existing large test vaults

The earlier conclusion that the project had only ten usable starter notes was
incomplete: merged PRs already establish larger corpora. This work reuses their
inputs and generators. No runtime extraction policy, calibration labels or
thresholds are changed merely to improve a score.

| Corpus | Provenance | Use in this evaluation |
| --- | --- | --- |
| Mara narrative vault | Merged PR #97; checked-in authored fiction | All 24 snapshots; diverse prose, dated entries, edits, deletion and stable controls. |
| Temporal smoke and standard | Merged PR #97; deterministic synthetic generator | All 32 snapshots at 128 and 1,000 initial notes. |
| Temporal large | Merged PR #97; same generator | First two snapshots at 10,000 initial notes, matching the prior large-probe scope. |
| Original 10,000 files | Historical benchmark and PR #97; Zettelkasten-Method/10000-markdown-files at `40c11a4bb9b96dbcf1cd3c109d32f50dbc8b61a2` | Exact 10,000-note, 46,635,807-byte population; cold/warm sync, exact evidence, positive query and source-preservation checks. Text is scrambled, so its size is not evidence of semantic usefulness. |
| LYT Kit | Historical 235-note benchmark removed in merged PR #61; recovered public mirror thebrianbug/LYT-Kit at `e191473fcb326df78cca8a6c49b29420ab318e46` | This mirror has 272 notes; it is not claimed to be the same snapshot. Run the full index and retain a frozen 28-note, length-stratified source-first quality sample, including four excluded-template controls. |

The [input manifest](../benchmarks/corpora/topic_corpora.json) records provenance,
pinned versions, sample selection and expected inventory. The LYT sample was
selected and its source Git blob hashes checked before viewing extractor output.
It covers short notes, empty notes, navigation notes, essays, dated notes and
configured templates. No private-owner ratings are inferred from public examples.

## Executable checks

`scripts/benchmark_topic_corpora.py` uses real `Vault.sync` and `TopicIndex` with
YAKE/MarkdownIt. It loads no embedding model or user plugin and emits no geist
suggestion. Lexical capture is explicitly disabled to isolate raw sync plus topic
indexing cost; these are not whole-invocation or embedding timings.

For each snapshot, it checks complete state and every stored evidence span/line,
then verifies nonempty topic memberships against stored eligible source rows.
It hashes Markdown before/after sync, asserts zero topic extractions and unchanged
memberships on warm sync, and compares edited/replayed final state with a fresh
index. Stable-source evidence must remain unchanged throughout each replay.
The static stress corpus is indexed once and checked warm; no redundant cold
rebuild is required when its source has never changed.

The dedicated [workflow](../.github/workflows/topic-corpora.yml) checks out pinned
external corpora and runs:

```sh
uv sync --locked --extra vector-search
uv run --frozen python -m scripts.benchmark_topic_corpora \
  --work /tmp/topic-corpus-checks \
  --lyt /path/to/pinned-lyt-mirror \
  --stress '/path/to/10000 markdown files'
```

The work destination must not exist. It owns all generated/replay data. External
source corpora are read without importing their plugins, and source bytes must
remain unchanged. Reports retain provenance, snapshot counts, extraction counts,
query timings, evidence checks and unrated sample labels. Human usefulness fields
remain unset. Completed results will be recorded here after the actual run.

Corpus execution can establish correctness and cost. Fiction, planted topics,
scrambled stress prose and unrated public demonstration notes do not establish
human usefulness by themselves. The representative quality gate remains separate
from the automatic checks; existing large corpora nevertheless provide substantial
verification work that should be completed before requesting new vault data.
