# Reusing exact word-burst analysis

This change applies three improvements to `word_burst`: reuse unchanged selected
observations across days, persist compact term presence, and bound preparation
memory. It preserves extraction, thresholds, evidence populations, complete
ordered findings and deterministic questions for the same input and date. It
adds no dependency and does not sample or truncate the vocabulary.

## Reuse follows evidence

Analysis version 7 keys statistical results by policy, settings, generation,
weekly frame and an exact selected-source signature. A same-day key avoids even
the metadata scan. A new day with the same selected observations in the same
weekly frame reuses the result after checking metadata. Stored intervals have
canonical week-end dates; reporting clips dates and updates provisional flags
for each request. An open interval before trailing unobserved weeks retains its
actual endpoint.

Future-dated notes becoming eligible, captured observations entering the cutoff,
source changes and a moving weekly frame still require fresh analysis. An
unchanged corpus therefore does not imply a permanent cache hit. Cached
abstentions preserve population explanations and report zero decoding work.
Filesystem checks, metadata scanning, cached JSON decoding and question rendering
still cost time.

## Compact presence and bounded preparation

Schema 14 adds stable term IDs and sorted little-endian uint64 presence vectors
for current text and captured additions. Exact JSON frequencies/history remain
intact. Cold analysis backfills only its selected history mode and window, using
stored JSON rather than old Markdown. Unrelated undated notes, future rows and
captured history do not add upgrade work to that request. Saved questions,
embeddings and captured history survive. The projection and its source update
atomically; direct JSON changes invalidate stale projections. A changed-note
writer looks up only touched IDs in bounded indexed queries. An unchanged sync
loads no dictionary.

NumPy integer arrays hold sparse weekly counts. Duplicate bodies contribute once
per week; all paths remain available as evidence. Stable IDs are mapped to dense
positions, so an ID near the signed-64-bit limit cannot cause a huge allocation.
A second streamed pass collects evidence only for detected terms. Source buffers
stop at 256 rows or 262,144 selected occurrences; preparation stops at 1,024 terms
or 131,072 coordinates. Each permits one intrinsic source/column beyond the
coordinate limit. Exact-series reuse retains at most 8,192 entries and 262,144
coordinates. Final statistics and actual findings still scale with corpus
contents. Eviction may require repeated decoding but cannot change a result.

Persistence trades disk and indexing work for cheaper subsequent collection and
lower transient memory. Each presence takes eight bytes plus the shared term
ID dictionary; IDs retained for captured history are not reclaimed on current
term disappearance. The one-time upgrade backfill must be counted separately
from steady analysis.

## Measurement protocol

The frozen baseline is commit `6660bfa93b2a10f42d8228e9cea2d26924326785`.
Capacity runs copy the previously used 10,000 Markdown files, existing lexical
JSON and chronology overlay into independent databases. They retain 46,637,507
source bytes and inventory hash
`69d9e6ca2fd46c130d79c4fba84fa27b9a20dba66485cf2bd8c3f219092b22ac`.
Dates are explicitly synthetic. There is no embedding inference in these
capacity or sync measurements.

Fresh analysis, exact-day hits, unchanged next-day queries and a shifted weekly
window are separate measurements. Full `Vault.sync` costs cover initial indexing,
no change, one changed note and 100 changed notes. Database pages, actual presence
bytes, whole-process high-water RSS and exact finding/question digests are
retained. A copied database's first filesystem-fingerprint reconciliation is
recorded separately from an unchanged sync. It is not a no-change timing.

Trials run sequentially on one Linux/Python 3.12 environment. Imports and the OS
filesystem cache may be warm. Two capacity trials do not establish latency
percentiles or performance on another vault. Intermediate revisions and failed
harness attempts are retained and excluded from final-revision comparisons.
The implementation changes are measured together; phase timings are not an
ablation assigning a causal speedup to each line of code.

For the separate question of whether optional three-word phrases add useful
material, see [phrase research and matched evaluation](word_burst_phrases.md).

## Measured costs

These are medians of two final-source capacity trials per phase. Baseline trials
are numbered 1–2 and final trials 3–4; the retained intermediate revisions are
excluded. Every complete ordered finding digest and all sampled questions match.

| Measurement | Words/pairs, before → after | Through triples, before → after |
| --- | ---: | ---: |
| Fresh analysis, excluding upgrade | 14.27 → 12.21 s | 46.02 → 33.06 s |
| Exact-day analysis hit | 0.533 → 0.484 s | 0.222 → 0.287 s |
| Unchanged next day, same weekly frame | 14.58 → 0.370 s | 42.59 → 0.403 s |
| Next week, requiring fresh analysis | 13.70 → 11.53 s | 39.65 → 32.10 s |
| Whole-process peak RSS through first analysis | 1,241 → 902 MiB | 2,059 → 1,196 MiB |
| Peak RSS over the complete sequence, including later sync | 1,296 → 989 MiB | 2,116 → 1,382 MiB |

Fresh trigram trials range from 44.9–47.1 seconds before to 30.6–35.5 seconds
after. They still exceed the default 30-second executor budget on this stress
fixture. Reuse removes the repeated model work, but it does not make first use
or changed-population analysis instantaneous.

The projection-only upgrade costs a further 6.85 seconds for pairs and 20.94
seconds through triples in the final trials. Used pages grow by 84.17 and 167.59
MiB respectively on these copied legacy databases. This explicit whole-index
projection benchmark includes both stored history tables; production cold
analysis now backfills only its selected mode and window.

Real production executor checks starting from the legacy databases succeed in
19.40 seconds with pairs under the default 30-second budget, and 53.62 seconds
with triples under an explicit 120-second budget. These include first-use
selected backfill and question rendering. Cached executor calls take 0.703 and
0.778 seconds. Exact finding digests match the previously frozen 4,257 pair and
6,767 through-trigram findings.

### Initial indexing and edits

One independent full `Vault.sync` trial per phase, without embedding inference:

| Measurement | Words/pairs, before → after | Through triples, before → after |
| --- | ---: | ---: |
| Initial indexing | 104.95 → 117.55 s | 217.03 → 239.20 s |
| Unchanged sync | 3.49 → 3.87 s | 4.19 → 3.53 s |
| One-note edit | 3.85 → 3.65 s | 3.80 → 3.35 s |
| 100-note edit | 4.93 → 5.43 s | 7.46 → 6.87 s |
| Initial-index process peak RSS | 748 → 754 MiB | 748 → 856 MiB |
| Fresh database used pages after initial indexing | 188.5 → 267.8 MiB | 353.6 → 515.7 MiB |

Initial indexing is about 10–12% slower because it creates term IDs and writes
presence vectors as well as exact JSON. The fresh database is about 42–46%
larger. Trigram indexing peak RSS increases about 14% because the transaction
touches a large term dictionary. One-note and 100-note syncs remain incremental;
their small timing differences do not establish a speedup or regression from a
single trial. Unchanged sync extracts zero lexical sources. A separate SQLite
VM-budget regression catches reintroducing a full vocabulary scan on tiny edits.

The two sync revisions have identical `PresenceWriter` ASTs and unchanged
`lexical_index.py` and schema bytes. The later selected-backfill helper and
empty-episode exit are not invoked during sync; source receipts retain this
distinction rather than treating the earlier sync revision as a final-byte run.

### What got worse

Disk use and initial indexing increase deliberately. Trigram exact-day decoding
also rises by about 66 ms in these trials, even though next-day reuse becomes
about 106 times faster. The retained trials do not isolate the cause of the
small exact-day difference. Cached JSON and date presentation still cost work;
the cache also stores cutoff aliases under its fixed eight-entry limit.
The fixed memory bounds can require repeated decoding when reuse entries are
evicted. Tests verify identical results under forced eviction, not identical
work counters.

The fixed-width format makes byte order and exact IDs explicit. A future
versioned compressed format could reduce disk use, but would need migration and
decode-cost evidence. Quietly narrowing IDs to uint32 would lose the current
signed-63-bit safety guarantee.

## Verification and retained evidence

The full local validation gate passes 2,091 unit tests, 81 integration tests,
158 automated acceptance criteria and 83.71% branch coverage, plus all 45 geist
firing contracts, strict typing, lint/security/workflow checks and installed-wheel
offline real-model inference. The first run caught a stale schema label in
`STATUS.md`; it was corrected before a complete clean rerun.

Independent review without reading tests passes 480 complete ordered old/new
finding comparisons and 1,920 cached/fresh cutoff comparisons, including forced
tiny buffers and eviction. High-ID, rollback, calendar and count-conservation
probes pass. Openclaw test-audit and Hegel guidance add public-boundary Hypothesis
oracles, intended old-source cache failures and a separately labelled synthetic
full-scan resource mutation. No test-only production seam is added.

Both real-model narrative modes complete 48 sessions, 2,160 calls across all 45
geists and 240 saved questions without errors. Raw, filtered, selected and saved
output, exact model findings and populations match the previous repair receipts.
Concurrent replay timings are not performance evidence.

[Summary and receipt manifest](../benchmarks/results/word_burst_reuse/summary.json)
and [restoration instructions](../benchmarks/results/word_burst_reuse/README.md)
retain all trials, exact source hashes, audit/research receipts and the complete
replays. The official canonical reviewer again failed authentication and produced
no report. Independent reviews do not replace that missing verdict; the PR remains
draft.
