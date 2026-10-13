# Rebuilt word-burst measurements

These are fresh measurements of the rebuilt implementation on 2026-10-13.
They replace reliance on the lost implementation's raw artifacts; older numbers
remain historical records in the recovery document. Different tokenization and
machine/filesystem behavior mean those earlier figures are not a controlled
before/after comparison.

Measurements precede the final sync-order repair, which moves the existing source
validation after capture and reads the observation clock after source reads.
Stable benchmark inputs execute the same counting/decoding work; correctness of
the final ordering is proved separately by red/green ownership regressions.

## Original 10,000-note corpus

Source: [Zettelkasten-Method/10000-markdown-files](https://github.com/Zettelkasten-Method/10000-markdown-files),
commit `40c11a4bb9b96dbcf1cd3c109d32f50dbc8b61a2`: 10,000 Markdown files and
46,635,807 bytes. The benchmark copies source files and checks every source file's
SHA-256 before/after. The source stayed unchanged. Each trial has a fresh temporary
copy/database. Python 3.12.14, Linux; filesystem/model-import caches may be warm.
Embedding inference and full CLI invocation are excluded.

The original corpus has no chronology. Strict dated analysis returns no findings.
Detector timing uses an explicitly synthetic 104-week date overlay in the temporary
database. Its detected episodes have no interpretation as historical events.

| Operation | Unigrams: median of 3 trials | Up to 3-word phrases: 1 trial |
| --- | ---: | ---: |
| Cold sync/index | 34.828 s | 178.698 s |
| Unchanged sync | 3.380 s | 2.823 s |
| Edit 100 notes | 3.681 s | 5.153 s |
| Fresh detector | 4.482 s | 102.489 s |
| Cached detector | 2.249 ms | 30.955 ms |
| Raw undated abstention | 0.565 ms | 0.680 ms |
| Candidate terms | 7,422 | 1,229,147 |
| Terms decoded / pruned | 1,870 / 5,552 | 180,309 / 1,048,838 |
| Findings on artificial dates | 204 | 3,661 |
| Database after edits | 100.54 MiB | 395.80 MiB |

Unigram fresh/cache findings matched exactly in every trial, and the complete
finding digest was identical across the three independent databases. Phrase
fresh/cache findings also matched exactly. Warm sync extracted zero notes; edits
extracted exactly 100. The dictionary gains one benchmark marker after the edits.

Peak process RSS ranged from 892.9 to 894.9 MiB across unigram trials; the phrase
process reached 1,610.7 MiB. These are Linux process high-water marks, include
package/ML imports, and are cumulative within each process—not per-stage memory
deltas. Timings include normal production sync and SQL triggers. Date-overlay
preparation and source copying are outside detector timing.

The new phrase vocabulary is substantially larger than the archived implementation's
reported vocabulary. Current extraction counts every eligible within-line n-gram,
including sequences spanning punctuation; it does not impose a frequency cap or
sampling. Phrases are an expensive opt-in: their measured fresh detection exceeds
the 30-second default geist timeout. Use unigrams routinely, or configure a larger
execution budget when enabling phrases.

Raw trial records:
[unigrams](../benchmarks/results/word_burst_large_corpus.json) and
[phrases](../benchmarks/results/word_burst_large_corpus_phrases.json).
Reproduce using `scripts/benchmark_word_burst.py`; passing `--ngram-max 3` enables
the phrase case. A single phrase trial is insufficient to estimate its variability.

## Temporal replay

Generated all three 32-snapshot profiles: 128, 1,000 and 10,000 initial notes.
The 128-note profile was replayed with the real bundled MiniLM model on CPU and
eight actual bundled geists. The 10,000-note profile was replayed through both
lexical modes, with semantic work explicitly skipped. The 1,000-note profile was
generated but has not been replayed with real embeddings.

The real-model smoke replay completed without exceptions or changes to the
unchanged controls' 384-dimensional meaning bytes. Total embedding computation
over 32 sessions was 44.035 s. Seven selected geists produced suggestions:

| Geist | Snapshots with suggestions (of 32) |
| --- | ---: |
| word_burst | 31 |
| concept_drift | 28 |
| attention_shift | 27 |
| temporal_drift | 32 |
| recent_focus | 32 |
| temporal_clustering | 28 |
| this_time_last_year | 11 |
| seasonal_patterns | 0 |

Both planted lexical terms were found. In dated cohorts, aurora first appeared at
snapshot 8 and quasar at 22. In observed additions, they first appeared at 9 and 23:
the default requirement needs two supporting weekly bins. Completed historical
episodes remain available after the burst stops; appearance in later results does
not mean writing continued. The corpus does not plant seasonally coherent topics,
so seasonal silence is a limitation of this fixture, not a claimed detector failure.

In the large lexical replay, both modes first surfaced aurora at snapshot 9 and
quasar at 23. Current-prose cohorts and captured additions have different
populations; detection boundaries should not be forced to match between modes
or profiles. The complete large replay also finished without errors.

These results validate temporal signals and real-model integration, not usefulness
to a human reader. The fixture's deterministic backbone makes regressions and
policy changes measurable; real-vault qualitative evaluation remains future work.
Details and commands: [TEMPORAL_BENCHMARK_CORPUS.md](TEMPORAL_BENCHMARK_CORPUS.md).

Compact summaries retain all per-snapshot timings, work counters, planted findings
and geist suggestion counts. Lossless `.raw.json.xz` archives retain complete raw
findings/suggestions, with SHA-256 anchors in the summaries. Decode with Python's
`lzma.decompress` and verify the summary's `raw_sha256` before interpreting an archive.

- [Real-model smoke summary](../benchmarks/results/word_burst_temporal_smoke.json)
- [Large lexical replay summary](../benchmarks/results/word_burst_temporal_large.json)

## What the measurements support

Exact incremental counting and caching make routine unigram detection practical.
The unchanged corpus avoids extraction and decoding; insufficient historical
evidence exits cheaply. Whole-vault sync still scans the filesystem and checks
source fingerprints, so cached analysis does not make the whole invocation O(1).
The first cold index has material startup cost. Phrase vocabularies dominate cold
cost and require deliberate budgeting. None of these timings is a portable SLA.


## Post-review verification, 2026-10-14

The review repairs add stable near-one emissions, source-aware/native-path
exclusions, conservative lower observation bounds, and complete-evidence boundary
checks before the suggestion-reference cap. Execution benchmarks now use the
actual `GeistExecutor`; the earlier direct-call benchmarks did not exercise
runtime validation. Old measurements above remain dated evidence.

The final original-corpus trial measured cold sync 23.657 s, unchanged sync
3.672 s, editing 100 notes 3.231 s, fresh analysis 3.458 s, cached analysis
2.306 ms and cached executor rendering 72.043 ms. It decoded 1,870 candidates
and safely pruned 5,552, producing 204 findings on the explicitly synthetic
chronology. Warm sync extracted zero notes and edits extracted exactly 100.
Fresh/cache results matched, the executor succeeded, and source hashes stayed
unchanged. This is one final trial; an earlier three-trial repair run is retained
separately. Neither is a controlled cross-machine speedup comparison. The later
boundary lookup relocation preserves the detector/index code; final corpus replay
and architectural owners separately verify that rich-context delegation.

[Final original-corpus trial](../benchmarks/results/word_burst_large_corpus_verified.json)
and [initial three repair trials](../benchmarks/results/word_burst_large_corpus_post_review.json)
retain raw measurements. Phrase performance was not rebenchmarked in this repair;
the expensive opt-in limitation above remains applicable.

The ten-note Kepano fixture was copied without prior managed artifacts and tested
through real `init` and `invoke --geist word_burst --date 2023-09-30`. Both commands
succeeded; four eligible dated observations were insufficient, so the geist
returned a healthy empty result. Original Markdown hashes stayed unchanged.
[CLI evidence](../benchmarks/results/word_burst_kepano_verified.json).

The synthetic replays cover all 32 snapshots at 128, 1,000 and 10,000 initial
notes. Smoke and standard include real CPU embeddings and the eight selected
geists; large runs both lexical modes and the production executor. Final results
are recorded after the architectural repair. Corpus replays overlap validation
work and establish behavior, rather than isolated timing comparisons.


Final [corpus matrix](../benchmarks/results/word_burst_corpus_matrix.json): 96
snapshots and 192 word-burst executor calls, all successful. Smoke and standard
real-model replay preserved all stable meaning vectors. Dated-cohort questions
appeared in 31 snapshots per profile; observed-addition questions in 23. The
largest full episode had 3,200 supports, with at most 100 rendered references.
Aurora/quasar were detected in every profile. Standard replay also exercised all
eight selected geists, including seasonal patterns (seven nonempty snapshots).
All lossless archives were independently decompressed and SHA-256 verified.

A [positive real CLI check](../benchmarks/results/word_burst_cli_positive_verified.json)
with offline inference and all four filters retained one of three raw word-burst
questions. Its term was the synthetic marker `specimenbb`. This demonstrates the
runtime/pipeline path and also a relevance limitation: statistically elevated
fixture scaffolding can be less interesting than a conceptual term. The corpus
is not hand-filtered to hide that outcome; reader usefulness remains unproven.
