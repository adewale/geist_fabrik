# Archived original word-burst specification

> Recovery archive, 2026-10-10. The text below is the original proposal saved on
> 2026-10-07, recovered from the [saved specification Page](https://chatgpt.com/space/page_9a26e3a8b81c819185db4b04d606fa9e).
> It is preserved verbatim after this notice. It is not the final implementation
> specification: some proposed defaults, APIs, storage and roadmap items changed
> or were deferred. In particular, the implemented default reported in the session
> uses unigrams, and Git/backup imports and retained historical prose remain deferred.
> Consult [the recovery record](WORD_BURST_RECOVERY.md) for reported implementation
> decisions, benchmark results, completed checks and pending verification. Prototype
> figures and workspace links in the original text are historical evidence and may
> be unavailable; they are not substitutes for the later production benchmark.

**Status:** Proposed implementation specification. **Date:** 7 October 2026.

**Repository reviewed:** [adewale/geist_fabrik](https://github.com/adewale/geist_fabrik), commit [`37c0fce`](https://github.com/adewale/geist_fabrik/commit/37c0fce23b8df0a02924361f456d0c67ac2e3479).

Implement `word_burst` as a lexical evidence provider and a small question-generating geist. Maintain exact term counts incrementally during vault sync, detect unusually prevalent terms with Kleinberg's batched binomial model, and supply linked examples. Historical accuracy requires an explicit distinction between current text assigned to document dates and changes actually observed over time. Ship reconstructed dated cohorts first, capture lexical revisions from installation onward, and add optional Git or backup backfill without treating commit dates as authorship dates.

The proposed thresholds below are starting settings for evaluation on personal vaults. Research on conference papers or social media does not establish the right thresholds for Obsidian.

## Purpose and output

The geist asks which language became unusually prevalent in a particular period, which previous episode it resembles, and what connects its supporting notes. It complements creation volume in [`creation_burst`](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/default_geists/code/creation_burst.py), undated phrase recurrence in [`pattern_finder`](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/default_geists/code/pattern_finder.py), and semantic outliers in [`surprisal`](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/default_geists/code/surprisal.py).

Illustrative output, with invented counts:

> “Constraint” appears in 8 of 12 entries dated 1–14 September, compared with 4 of 46 outside that interval, including [[Journal#2026-09-02]] and [[API Design]]. What connects the limits they describe?

> Another burst of “maintenance” appears in your dated notes after an earlier episode in March. [[Garden Planning]] and [[Software Stewardship]] are among the supporting notes. What is different about the work it names this time?

> During September, “feedback loop” was observed in additions to [[Workshop Design]], [[Team Rituals]], and [[Learning Log]]. What connects these additions?

Render one or two sentences and two or three representative note links. Keep full counts, exclusions, dates, revision references, and model settings in internal evidence. Describe literal lexical observations; meaning, importance, causes, and changes in the user's thinking remain open questions. An isolated high fold increase is insufficient.

The first output follows the project's [guide to writing geists](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/docs/WRITING_GOOD_GEISTS.md). Each `Suggestion` must carry the contributing notes' `link_text`; all contributing notes, not just displayed examples, should be available to the boundary filter.

## Historical evidence

| Evidence source | What it establishes | Main limitation | Proposed use |
| --- | --- | --- | --- |
| Current text and explicit entry or document date | Current wording occurs in a document assigned to that date | Later edits can move present wording into an earlier cohort | Immediate retrospective mode, explicitly labelled reconstructed |
| File timestamps | Filesystem metadata observed on this machine | Copies, imports, sync and checkouts can reset dates | Exclude from the strict default; allow an explicit estimated-date option |
| Lexical revisions captured during sync | Exact lexical states observed at particular sync times | Changes between observations remain unseen | Prospective mode, with observation intervals |
| Selected Git history | Text states and changes along a chosen commit lineage | Commit time is recording time; history may be shallow, squashed or rewritten | Optional backfill, with Git provenance |
| Dated backup snapshots or exported version history | Text states present in those snapshots | Sparse sampling and incomplete exports | Optional importer using the same revision contract |
| Existing session embeddings | Stored semantic vectors | Words and past text cannot be recovered from them | Contextual evidence only; no lexical backfill |

The current [`notes` table](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/schema.py) stores current text. Historical `session_embeddings` rows store vectors and cluster labels. [`Vault._update_note_from_object`](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/vault.py#L465) overwrites same-path text while preserving its embedding history. No existing table supports reconstruction of when individual words were added.

### Reconstructed dated cohorts

Start with virtual journal entries and notes with explicit dates. [`date_collection.py`](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/date_collection.py#L230) already creates separate notes with `entry_date` and `source_file`. Ordinary note dates can come from frontmatter or dated filenames. Add date provenance such as `entry_heading`, `frontmatter`, `filename`, or `filesystem_estimate`; a bare `Note.created` cannot currently distinguish these reliably.

For each bin, count distinct eligible notes and term presence in their current prose. A change to an old note updates its original cohort. A corrected declared date moves the note's denominator and term contributions between bins. Say “entries dated …” or “in the current text of notes dated …”, rather than “you began writing this word on …”. Declared dates establish the document's assigned date, not the original wording.

Strict mode excludes estimated dates, future-dated notes after the session cutoff, generated session journals, and explicit import/template exclusions. Extend the existing bulk-import guard as one signal, but do not use it to dismiss a large set of explicitly dated entries from many different dates. Import detection and date reliability are separate questions.

### Changes observed during sync

Record revisions using actual `observed_at` timestamps, independent of the requested session date. A `--date` invocation must never backdate a newly observed edit. Store observation time in UTC and use a versioned bin-calendar policy consistent with the application's session calendar.

The first scan establishes a baseline. It does not count the entire existing vault as a burst of newly written material. A first observation of a note discovered later is a discovery event; its earlier authorship is unknown. Keep discovery events separate from changes to previously observed notes, rather than combining imported documents with measured additions.

For a changed note, compare current and preceding term-frequency vectors. For term `w`, define `added(w) = max(tf_new(w) - tf_old(w), 0)`. Count the note once for `w` in an observation bin if any observed revision pair has a positive difference. The bin denominator counts coalesced note/bin events with at least one eligible added term. Deduplicate repeated observations by note and bin, taking the union of added terms; many edits to one note must not dominate the model. Persist event membership so these unions remain correct.

This union records any observed positive addition during the bin, not net growth over the entire bin. Adding a word and subsequently removing it still supplies evidence of an observed addition. A bin-start versus bin-end net-growth series would be a different optional mode, with its own denominator and cache identity.

This mode measures net additions between observations. It misses wording changes with identical term counts and edits that were made and reversed between syncs. An increase from 2 to 3 occurrences is evidence of one net addition; it is not evidence that exactly one occurrence was typed. Where possible, include both bounding observation dates in the evidence.

An optional `first_seen_documents` series can cover newly discovered notes after bootstrap, with term presence among those newly indexed documents. Its claim is “first observed in the indexed vault”, with imports identified separately. Do not merge that series with edits to established notes or call it a record of when notes were written.

A virtual entry's own content hash determines whether it changed. Editing one journal section must not create events for every section because their shared source file has a new modification time. The current virtual-note `modified` field inherits the source file's value; it is unsuitable as the lexical event timestamp.

### Backfill from Git or backups

Offer a separate local import operation, for example `geistfabrik history import-git VAULT --ref REF`. Read a selected lineage, defaulting to the first-parent history of a selected branch. Record the ref, commit IDs and coverage boundaries. Use changed-file discovery and batched object reads rather than one process and full checkout per revision. Git's [log](https://git-scm.com/docs/git-log) and [cat-file batch interface](https://git-scm.com/docs/git-cat-file) support this workflow.

Apply revisions in ancestry order, then assign their recording dates with provenance. Preserve author and committer timestamps separately; neither proves the precise time prose was written. Flag nonmonotonic timestamps rather than applying text changes in timestamp order. Strict temporal mode excludes revision pairs with invalid observation bounds; an optional monotone-date repair policy must retain the original timestamps and record the adjustment. Parse historical journal text with a recorded parser version. Distinguish renames from new-note discovery where identity is sufficiently clear; otherwise report the uncertainty.

Do not mutate the working tree, create commits, or fetch remotely as part of this local backfill. Default importer scope is currently eligible documents; purged document history must not be restored silently by a later import. Keep a non-content purge marker and require an explicit importer scope setting to re-admit that history. Deduplicate by provenance and content hashes. Merge historical and prospective evidence only where predecessor states and document identities are established, and avoid counting overlapping observations twice. Sparse backup imports follow the same rules, with snapshot dates and gaps retained.

This recovers history actually available in the selected sources. Squashed commits, missing backups and unrecorded edits remain gaps. Obsidian or cloud version history can be imported if the user supplies an accessible export; availability of a supported history API is not assumed.

## Lexical extraction and eligibility

Store both token frequency and document presence. Token frequency supports revision comparisons; document presence is the detector's default input.

Build lexical cleaning from the shared Markdown helpers and existing [`voice_analysis`](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/voice_analysis.py) and [`pattern_finder`](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/default_geists/code/pattern_finder.py) conventions. Exclude frontmatter, code, URLs, engine output, and configured templates or imported material; these rules extend the helpers rather than relying on a single existing prose-extraction API. Keep quoted prose as an explicit policy because some vaults deliberately contain reading excerpts. Preserve boundaries between removed regions, sentences and table cells: concatenating prose across removed code can invent a phrase.

Start with Unicode-normalized, case-folded words, bigrams and trigrams. Preserve readable examples of the original spelling. Filter phrases beginning or ending with a configured stopword, allow internal stopwords such as “theory of mind”, and reject numeric/markup artefacts. Keep language and normalization policies explicit. Existing heuristic tokenization does not provide reliable segmentation for every language; unsupported segmentation should be identified in diagnostics.

Treat a virtual journal entry as a document. Require multiple distinct supporting notes or dated entries; repeated wording inside one entry contributes only once to document frequency. For dated cohorts, suppress identical normalized bodies within a bin consistently in both numerator and denominator. For observed additions, duplicate evidence is an identical normalized revision-pair history, not merely an identical added-term set: different changes may legitimately add the same words.

Require at least three distinct eligible evidence groups across the emitted interval as well as multiple supporting notes. Copies spread over several weeks must not satisfy independence just because their paths and dates differ. Record the duplicate/evidence-group policy in the population identity. Do not collapse an entire journal to one physical source file, which would remove its temporal structure.

Extract supported phrases during ingestion and retain their counts even before they reach the detector's support threshold. Otherwise a phrase first admitted to the dictionary later loses its earlier history. Enabling a new phrase length or tokenizer version requires a versioned rebuild from retained text. Arbitrary synonyms remain separate; consolidate obvious phrase/subphrase redundancy after detection rather than assuming equivalent meaning.

When extraction changes, old and new revisions must be reprocessed under the same version before computing their differences. If retained text is insufficient, establish a new observation baseline and record lost comparability. Newly extracted words or phrases must never become synthetic writing events.

## Detection model

Use the discrete batch model in Section 4 of [Kleinberg's original paper](https://www.cs.cornell.edu/home/kleinber/bhs.pdf). That section already handles groups of documents arriving together; it does not require inventing inter-arrival gaps for notes sharing a date.

For term `w` in each populated bin `t`:

```text
d[t] = eligible document or addition-event count
r[t] = documents whose prose contains w, in dated cohort mode
     = coalesced events whose added-term set contains w, in observed mode
p[0] = sum(r) / sum(d)
p[i] = p[0] * s**i, for valid states with p[i] <= 1
emission(t, i) = -r[t]*log(p[i]) - (d[t]-r[t])*log(1-p[i])
transition(i, j) = gamma * log(B) * max(0, j-i)
```

Here `B` is the number of populated bins in the selected analysis series. Initial state is baseline. Use a proper cumulative dynamic program and traceback. Omit the binomial coefficient because it is identical across states for a given bin. Handle probabilities 0 and 1 by their mathematical limits; do not manufacture duplicate states by clipping invalid probabilities.

Initialize `DP[-1,0]=0` and `DP[-1,i>0]=infinity`, so a burst in the first populated bin still pays its entry cost. Start with a maximum of two states, `s=2` and `gamma=1`; allow a small additional state count for optional nested intensity levels. Requested state count is a maximum: if `p[0]>0.5` and `s=2`, no elevated state is valid and the detector abstains for that term. Require integer counts, `0 <= r[t] <= d[t]`, and deterministic ties favoring lower states and stable term identities. An entirely absent term is not a candidate. A term present everywhere cannot show increased document prevalence.

Compute the likelihood gain of each elevated interval over its baseline state as its ranking weight. Keep that separate from transition cost, observed rate, absolute support and reference rate. Weight is not a p-value, a probability that the user's interests changed, or a confidence percentage.

### Calendar gaps and unfinished intervals

Use weekly bins by default. Daily bins are available for dense histories; monthly bins are an explicit alternative for sparse vaults. Evaluate populated bins while preserving their calendar mapping. A week with no eligible documents has no evidence about word prevalence: it is not a week with an observed term rate of zero.

Mark gaps in evidence and avoid claiming uninterrupted attention across them. A long unobserved gap can split analysis segments under a recorded policy; the resulting boundaries are censored, not observed cooling periods. Mark the first interval left-censored if earlier coverage is missing, and the latest interval open/provisional when no subsequent populated baseline bin closes it. Partial current weeks remain explicitly partial.

A returning burst requires separate elevated intervals with intervening observed baseline evidence. Silence alone does not establish that a preoccupation went away. Compare recurring episodes within the same evidence mode and population definition.

### Baselines and sparse histories

Default to the original full-window mean so the implementation has a clear reference model. Display the actual burst-period rate and the rate outside that interval, with separate denominators; this descriptive comparison is distinct from the model's baseline.

Long bursts can raise their own reference mean and become harder to identify. [Tatti's parameter study](https://arxiv.org/html/1902.01727) establishes this issue for exponential/geometric delay models. Include planted long bursts in evaluation and compare a preceding-history baseline as an explicitly different experimental model. Its parameter-optimization guarantees must not be claimed for this binomial implementation.

Suggested initial eligibility: at least 50 eligible documents/events, eight populated bins, three distinct supporting documents, and support in at least two populated burst bins. Return `[]` when evidence is insufficient. Make thresholds configurable and validate them on sparse journal vaults; a newly installed vault may have reconstructed results immediately but insufficient prospective history.

## Evidence and API

Expose the detector through `VaultContext`; geists perform no SQL, filesystem history scans or per-note embedding loops.

```python
def word_bursts(
    self,
    *,
    mode: str = "dated_cohorts",
    window_weeks: int = 104,
    bin_size: str = "week",
    min_support: int = 3,
    min_support_bins: int = 2,
    states: int = 2,
    s: float = 2.0,
    gamma: float = 1.0,
) -> list[WordBurst]: ...
```

Proposed evidence fields:

| Field group | Contents |
| --- | --- |
| Identity | Normalized term, display form, unigram/phrase length, stable episode ID |
| Population | Evidence mode, date provenance, corpus generation, exclusions and denominator definition |
| Timing | Calendar interval, observation bounds, coverage start, gaps, partial/open/censored flags |
| Counts | Per-bin `r` and `d`, interval totals, outside-interval totals, distinct supporting-note and evidence-group counts |
| Model | Baseline probability, state level, likelihood gain, tokenizer/model/config versions |
| Sources | Stable note identities, current `link_text`, supporting revision IDs and optional captured excerpt |
| Relationship | Earlier comparable episodes and overlapping phrase candidates |

The context supplies its session cutoff and pins an index generation. The geist filters valid, linkable evidence, groups redundant candidates, and uses the existing seeded `vault.sample` to choose at most one suggestion from a bounded high-quality pool. Full evidence remains available for an explicit developer inspection operation; ordinary `--explain` retains its existing protection against printing rejected content.

For dated cohorts, a historical invocation means current eligible text grouped by dates no later than the session cutoff. For observed additions, select observations actually available by the cutoff; a later scan cannot appear in an earlier replay. Exact replay also pins the corpus generation, parser/config versions and observation cutoff. Date alone cannot freeze historical results after evidence is imported or corrected.

## Persistent data

Use a dedicated lexical layer rather than adding large dictionaries to inferred metadata JSON. Logical tables can be implemented with compact blobs where appropriate:

| Table | Required role |
| --- | --- |
| `lexical_terms` | Stable integer term IDs, normalized forms and extraction version |
| `lexical_documents` | Stable logical identity, current path/source entry, declared-date provenance, current revision |
| `lexical_content` | Content hash and tokenizer version, compact term-frequency vector; optionally compressed cleaned prose |
| `lexical_revisions` | Document/content reference, real observation time, preceding revision, source type/ID and discovery/deletion status |
| `lexical_events` | Coalesced document/bin contributions for observed positive additions, linked to contributing revisions |
| `lexical_bucket_totals` | Mode, population/config identity, bin, eligible document count |
| `lexical_bucket_terms` | Sparse mode/bin/term document frequencies |
| `lexical_index_state` | Generation, coverage boundaries, extraction version, completion and invalidation state |
| `lexical_burst_cache` | Complete detector key, compact intervals and evidence references |

Store sparse vectors, not a dense vocabulary array for every note. A content-addressed vector can be shared by repeated identical revisions; timestamp-only sync changes should not re-tokenize prose. Keep raw content identity and normalized lexical identity distinct so changes to frontmatter or irrelevant markup can be recorded without pretending new language appeared.

Term vectors suffice for measured net additions and document-presence history. They do not retain phrase context or permit arbitrary future tokenization. Offer a retention policy for compressed cleaned-prose revisions when historical quotations and future reprocessing matter. Default evidence can name current supporting notes and state the observation interval without quoting missing historical text. A quotation must come from the cited stored revision, not today's note.

Define retention before implementation: preserve the predecessor needed for the first retained observation; record coverage lost through pruning; invalidate dependent caches. Never silently substitute current text for missing historical revisions. Deletion should purge retained prose and note-linked lexical history by default, updating derived counts and recorded coverage. Drop dependent historical result caches and excerpts too. Outputs then describe surviving evidence, and exact replay of a purged generation becomes unavailable: a generation ID detects the mismatch but cannot recreate missing data.

An explicit history-retention option can preserve tombstones/counts, but deleted notes cannot be the sole evidence of a normal linked suggestion. Avoid accidental cascading loss or retention through reuse of the existing `notes` foreign key.

## Sync and cache lifecycle

[`Vault.sync`](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/vault.py#L97) already reconciles a validated source snapshot transactionally. Its [`source_fingerprint`](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/vault.py#L190) skips unchanged sources, and semantic cache identity already uses a [content hash](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/config.py#L23).

1. Reuse accepted `Note` objects during sync. Capture the previous lexical revision before replacing it, including virtual entries and deletions.

2. Hash and extract changed eligible prose once. Reuse the vector when content/extraction identity matches.

3. For reconstructed cohorts, subtract the old document contribution and add the new one; move both term counts and the denominator when dates or eligibility change.

4. For prospective history, append the observed revision and update its coalesced additions event. Renames with preserved identity are not automatically new writing.

5. Persist counts, revision references and generation changes atomically with the accepted source reconciliation. A sync retry must roll back and must not double-count an observation.

6. Detect lazily from committed counts, once per complete cache key. An unchanged lexical population and configuration can reuse cached results.

Initially, perform lexical maintenance in the sync transaction for simplicity and correctness. If profiling shows unacceptable lock duration, capture immutable revision records and an outbox in that transaction, then process bounded jobs after commit. The index remains explicitly pending until its generation is complete; the geist abstains rather than mixing old counts with a new denominator. Bootstrap can use the same resumable pipeline for large vaults.

Changing `d[t]` alters the emissions for every term, including terms absent from the changed document. Admission, deletion, date correction, deduplication and eligibility changes therefore invalidate the full candidate population. If denominators are unchanged, selectively recompute terms whose `r[t]` changed. Sliding the window, changing bin count, configuration or baseline policy can also require complete detection.

Incremental counts do not make exact burst boundaries append-only. Updated full-window baselines and `gamma*log(B)` change old costs, and new evidence can change the optimal earlier path even with fixed parameters. Recompute the bounded series from cached counts; preserve prior result versions when exact replay is requested and its underlying evidence remains retained.

## Configuration and integration

The following is a proposed configuration extension, not syntax accepted by the current release:

```yaml
default_geists:
  word_burst: true

lexical_analysis:
  enabled: true
  ngram_max: 3
  date_policy: declared_only
  capture_history: true
  retain_history_text: false
  history_retention_days: 730
  deleted_note_history: purge

word_burst:
  mode: dated_cohorts
  bin_size: week
  window_weeks: 104
  min_eligible_documents: 50
  min_populated_bins: 8
  min_support: 3
  min_support_bins: 2
  max_states: 2
  s: 2.0
  gamma: 1.0
```

Add typed configuration models, allowed-root keys, validation, serialization and initialized-vault examples in [`config_loader.py`](https://github.com/adewale/geist_fabrik/blob/37c0fce23b8df0a02924361f456d0c67ac2e3479/src/geistfabrik/config_loader.py); unknown keys are currently rejected. Validate `s>1`, `gamma>0`, bounded state counts, supported modes/bin sizes and positive support/retention values. Extraction-version identity is assigned by the implementation and includes lexical settings.

Keep history retention independent of embedding-session retention. A 104-week window requires that much retained coverage plus its predecessor state for faithful observed-change replay; shorter available coverage must be reported. `capture_history` begins at a real initial observation even when reconstructed cohort mode remains selected.

Add a migration after the reviewed schema version 10, with legacy rows assigned unknown date provenance until reprocessed. The ordinary sync/parser-version mechanism should refresh provenance safely. Place lexical extraction and persistence in a shared module, the decoder in a separately testable module, and suggestion prose in `default_geists/code/word_burst.py`. The context helper is the only entry point used by the geist.

## Performance and optimization

Let `L` be eligible tokens, `P` distinct document-term pairs, `Delta L` tokens in changed documents, `V` support-qualified candidate terms, `B` populated bins and `K` states.

| Operation | Expected work | Practical implication |
| --- | --- | --- |
| Cold lexical extraction | `O(L)` plus phrase extraction and persistence | Needed on installation or extraction-version changes |
| Incremental extraction | `O(Delta L)` | Reuse sync's changed-source detection; avoid full-vault tokenization per invocation |
| Contribution updates | Work proportional to changed term vectors/contributions | Keep old vectors so deletions and bin moves can be reversed |
| Current vector storage | `O(P)` plus sparse bin counts | Vocabulary alone is small; document-term associations dominate |
| Standard detector | `O(V*B*K*K)` | Small `K` makes this feasible, but structured transitions are cheaper |
| Optimized detector | `O(V*B*K)` | Run from cached counts, in bounded candidate batches |
| Traceback memory | `O(B*K)` for one term | Decode candidates sequentially rather than keeping every term's matrix |
| Historical storage | Proportional to distinct retained revisions and their vectors/text | Sync frequency and edit volume determine cost, not session count alone |

Use streaming token iteration and per-note `Counter` objects; avoid a global list of all tokens. Share extraction results across lexical geists. Store integer term IDs, compact frequency vectors and sparse nonzero bucket rows. Use batched SQLite writes and prepared statements rather than one transaction per word. Phrase lengths 1–3 create roughly three extraction streams and many more distinct associations; benchmark phrases separately before enabling them in large vaults.

Apply safe support filters before decoding. Process all qualifying terms by default; limiting analysis to the most frequent words loses emerging vocabulary. If a resource cap forces an approximate shortlist, report truncation and preserve enough state to resume. Fetch prose and optional semantic neighbours only for the final few candidates. Consolidate phrase/subphrase episodes with nearly identical intervals and supporting notes to avoid three versions of the same prompt.

### Measured synthetic prototype

The accompanying `benchmark.py` and `results.json` use Python 3.12.14 and SQLite 3.53.1 on this Linux execution environment. Corpus generation is excluded: 500 synthetic alphabetic tokens per note, a 20,000-term Zipf-like vocabulary, 104 bins, and one added word in each changed note. Each note has about 308 distinct terms. These are single local measurements, not production latency guarantees.

| Measurement | 1,000 notes | 10,000 notes |
| --- | --- | --- |
| Tokens | 500,000 | 5,000,000 |
| Cold tokenization and document-frequency aggregation | 196 ms | 3.207 s |
| Incremental in-memory count update after changing 1% of notes | 1.17 ms for 10 notes | 11.1 ms for 100 notes |
| Separate full content-hash scan | 2.73 ms | 27.7 ms |
| SQLite cold persistence | Not measured | 2.266 s |
| Changed-note tokenization, SQLite cache reads, updates and commit | Not measured | 55.5 ms |
| Lexical cache database size | Not measured | 30.7 MiB |

The 10,000-note prototype has approximately 3.08 million note-term associations and 956,512 nonzero term-bin rows. Its database uses per-note term-ID JSON and sparse aggregates. It excludes multi-version lexical history, full prose retention and phrases. No resident-memory measurement was made.

For 104 bins and five states, the optimized cost-only decoder took 113 ms for 500 candidate terms and 1.128 s for 5,000. Full traceback, Markdown cleaning, filesystem discovery, evidence lookup, revision capture and the rest of `invoke` are excluded. The decoder agreed with exhaustive state-path enumeration in 160 seeded small cases; this validates the prototype recurrence, not the proposed full feature.

The measurements indicate that incremental counting can be inexpensive while full candidate decoding may become the larger recurring cost. Use cached detector results when the lexical generation is unchanged. Existing filesystem discovery/stat work still occurs even when lexical work is skipped.

### Linear transition evaluation

With `c = gamma*log(B)`, the recurrence for target state `j` is:

```text
DP[t,j] = emission(t,j) + min(
    min(DP[t-1,i] for i >= j),
    c*j + min(DP[t-1,i] - c*i for i < j)
)
```

Suffix and prefix minima evaluate all target states in two scans. Store the corresponding predecessor index for exact traceback. This gives `O(B*K)` time per term and `O(K)` score working memory. The optimization follows from the transition structure and applies to binomial emissions; [Tatti's appendix](https://arxiv.org/html/1902.01727#A1) supplies the analogous optimized Viterbi construction.

### Full text indexes and approximate dictionaries

[SQLite FTS5](https://www.sqlite.org/fts5.html#the_fts5vocab_virtual_table_module) already offers document counts, occurrence counts and document/term instances. It is an alternative if GeistFabrik also needs text search. It does not supply historical bins or revisions automatically, and tokenization must match the lexical policy. Phrase positions add storage; external-content tables require correct synchronization. Prefer a small exact lexical cache for the first release, and benchmark FTS5 before adding a second index.

Count-Min sketches, heavy-hitter lists and reservoir sampling are useful at stream scale but introduce approximation, deletion complications or loss of rare candidates. They do not provide the exact evidence and historical replay needed here. Optimize changed-note extraction and detector caching first.

## Kleinberg after the original paper

The 2003 journal article is the journal version of the [2002 original](https://link.springer.com/article/10.1023/A:1024940629314), rather than a new sequel. The later works below extend the surrounding programme of temporal text analysis and probability-change detection.

| Work | Relevant contribution | Application to this geist |
| --- | --- | --- |
| Felzenszwalb, Huttenlocher and Kleinberg, [Fast Algorithms for Large State Space HMMs](https://papers.nips.cc/paper_files/paper/2003/hash/9407c826d8e3c07ad37cb2d13d1cb641-Abstract.html), 2003 | Structured transition costs permit faster inference than generic all-pairs HMM transitions | Use the model's transition structure; a generic HMM dependency is unnecessary |
| Aizen, Huttenlocher, Kleinberg and Novak, [Traffic Based Feedback on the Web](https://www.cs.cornell.edu/home/kleinber/pnas04-usage.pdf), 2004 | Models changing acquisition fractions, rather than raw traffic | Normalize by eligible notes/events; a future probability-change geist could also detect decreases |
| Kleinberg, [Temporal Dynamics of On-Line Information Streams](https://www.cs.cornell.edu/home/kleinber/stream-survey04.pdf), written 2004 and [published 2016](https://link.springer.com/chapter/10.1007/978-3-540-28608-0_11) | Discusses temporal models, misleading raw-change/ratio rankings, recurrence and streaming | Rank with likelihood and support; distinguish retrospective episodes from provisional current results |
| Backstrom, Huttenlocher, Kleinberg and Lan, [Group Formation in Large Social Networks](https://www.cs.cornell.edu/home/kleinber/kdd06-comm.pdf), 2006 | Word bursts use title-presence fractions within conferences, with elevated rate twice the mean | Count once per note; later consider folder/project-specific baselines when each population has enough evidence |
| Leskovec, Backstrom and Kleinberg, [Meme-tracking and the Dynamics of the News Cycle](https://www.cs.cornell.edu/home/kleinber/kdd09-quotes.pdf), 2009 | Tracks distinctive phrases and clusters textual variants | Include phrases and consolidate redundant variants; it is adjacent work, not a replacement automaton |
| Chierichetti, Kleinberg, Kumar, Mahdian and Pandey, [Event Detection via Communication Pattern Analysis](https://www.cs.cornell.edu/home/kleinber/icwsm14-event.pdf), 2014 | Uses relationships between primary and secondary communication as event signals | A later provenance-aware model could separate new prose from copied material; this application is an inference |

The [chronological publication list](https://www.cs.cornell.edu/home/kleinber/chrono.html) and targeted search did not identify a later standalone replacement for the word-burst algorithm. The practical additions come from related work and other researchers' implementations. This is a bounded literature review, rather than a claim to cover every citing paper.

## Later research and implementations

| Work | What researchers wrote or built | Insight to adopt |
| --- | --- | --- |
| Mane and Börner, [Mapping topics and topic bursts in PNAS](https://pmc.ncbi.nlm.nih.gov/articles/PMC387309/), 2004 | Applied Kleinberg to terms/phrases and combined bursts with co-occurrence maps | Keep recurrent episodes and group terms through shared supporting documents |
| Fung and colleagues, [Parameter Free Bursty Events Detection in Text Streams](https://www.vldb.org/conf/2005/papers/p181-fung.pdf), 2005 | Detects bursty features first and groups them into supported events | Use a lexical detection stage followed by grouping and evidence extraction |
| Chen's [CiteSpace burst detection tools](https://citespace.podia.com/glossary-burstness) | A deployed application of keyword, phrase and citation bursts, with interval displays and duration controls | Borrow understandable episode intervals and support/duration controls; keep the original model's parameter definitions |
| Mathioudakis and Koudas, [TwitterMonitor](https://snap.stanford.edu/class/cs224w-readings/mathioudakis10twitter.pdf), 2010 | Real-time keyword detection, accidental/spam-burst controls and co-occurrence grouping | Separate detection, grouping and contextual evidence; adapt spam controls to templates and copied imports |
| Lijffijt, Säily and Nevalainen, [CEECing the baseline](https://varieng.helsinki.fi/series/volumes/10/lijffijt_saily_nevalainen/), 2012 | Examined lexical-change tests and dependence among words within texts | Prefer document support; any future significance calibration must account for dependence and searching many terms |
| Karkali and colleagues, [Using temporal IDF for efficient novelty detection](https://arxiv.org/abs/1401.1456), 2014 | Historical document-frequency summaries support efficient novelty scoring | Reuse lexical summaries for a cheap comparison baseline; decayed summaries do not reproduce exact historical intervals |
| Tatti, [Discovering bursts revisited](https://arxiv.org/html/1902.01727), SDM 2017 with public arXiv version 2019 | Optimizes delay-model parameters, exposes mean-baseline contamination, and provides faster DP | Adopt the transition optimization and baseline stress tests; do not transfer guarantees to binomial emissions |
| Tattershall, Nenadic and Stevens, [Detecting bursty terms in computer science research](https://link.springer.com/article/10.1007/s11192-019-03307-5), online 2019 and volume 2020 | Uses word/phrase frequencies, support filters, MACD momentum and co-occurrence consolidation | Evaluate a cheap momentum baseline; remove boilerplate and merge overlapping phrase prompts |
| Štimec and colleagues, [Identifying and evaluating emerging scientific trends](https://link.springer.com/article/10.1007/s11192-026-05744-5), 30 September 2026 | Cached temporal n-gram processing, Kleinberg and MACD scoring, and human evaluations | Cache/batch work and test actual perceived usefulness; their intensity scores did not align closely with human graded judgments |

Some later descriptions say Kleinberg only supports continuous event arrivals. Section 4 of the original already supports discrete batches. Use that primary model rather than inheriting the mistaken restriction. Large-corpus support thresholds and quarterly settings also do not transfer directly to personal notes.

Implementation choice matters. The inspected [`nmarinsek/burst_detection` source](https://github.com/nmarinsek/burst_detection/blob/master/burst_detection/__init__.py) chooses each time step from the previously selected state; it does not retain alternative cumulative path costs and backtrack. It also computes binomial probabilities directly and uses `np.float`. Borrowing its count-array interface is reasonable; using that loop as the correct Viterbi oracle is not. Implement a small log-space decoder and check it against exhaustive short sequences.

[R bursts](https://search.r-project.org/CRAN/refmans/bursts/html/kleinberg.html) and [pybursts](https://github.com/romain-fontugne/pybursts) implement the inter-arrival model. They are useful references, but require different input from this batched document-presence specification. Wavelet methods such as [Zhu and Shasha's elastic-window detector](https://cs.nyu.edu/cs/faculty/shasha/papers/burst.d/burst.pdf) become relevant at much larger event volumes and add little to a few hundred weekly bins.

Adopt exact batch counts, structured DP, phrase consolidation, provenance and empirical usefulness evaluation now. Defer automated baseline optimization, semantic synonym clustering, seasonal correction, sketches and stream-scale window machinery until measured failures justify them.

## Acceptance criteria

Test behaviors rather than reproducing code details:

1. A planted relative-prevalence increase is found; a proportional increase in total writing alone does not produce equivalent burst evidence.

2. A long burst, returning burst and brief intense episode are distinguishable at supported resolution. Mean-baseline sensitivity is measured rather than hidden.

3. One verbose note or many duplicate notes cannot satisfy the independent-support criterion.

4. Zero-document weeks remain unobserved, partial weeks are identified, and missing coverage cannot fabricate a burst end or a returning episode.

5. The optimized DP agrees with exhaustive state paths on small integer batches; invalid and boundary probabilities are handled deterministically.

6. An old-note edit changes the reconstructed cohort but generates an observation at its real sync time. A historical session invocation cannot backdate it.

7. Editing one virtual journal entry leaves the other entries' lexical event histories unchanged.

8. Date corrections, deletion, renames, reimports and eligibility changes update both numerators and denominators. Denominator changes invalidate all affected candidates.

9. Same-content syncs and retried transactions do not add lexical events, duplicate history or rerun extraction.

10. Generated journals and configured excluded notes cannot supply a selected suggestion's hidden supporting evidence. All suggestions have resolvable current links.

11. Historical excerpts come from the cited revision; pruned or missing evidence does not fall back to current text.

12. Git/backup imports are idempotent, record their coverage, and preserve gaps and uncertain timestamp provenance.

13. An unchanged index/config reuses detection results; performance is measured separately for cold build, small edits, all-note edits, phrases, history capture and evidence rendering.

14. A word added and removed within a bin remains an observed-addition event, while its final cohort frequency reflects the removal; the two series cannot be confused in output.

Evaluate usefulness with a small real-vault review: inspect about 20 candidate episodes and rate accurate evidence, interesting connection, redundancy and annoyance separately. Compare the proposed questions with a simple recent-versus-reference document-frequency signal and an EMA/MACD baseline. Detector weights alone cannot establish whether a muse is useful.

## Implementation sequence

**First increment:** Add a versioned lexical cache, declared-date provenance, the correct binomial detector, evidence objects and the `VaultContext` helper. Implement the `word_burst` geist over reconstructed dated cohorts. Include rollback, denominator and virtual-entry contracts from the start. Update the default registry, validated config model, examples, catalog and count-consistency checks; geists remain thin.

**Second increment:** Capture compact immutable lexical revisions at sync and provide observed-addition mode. Bootstrap is a baseline, discovery stays separate, and observation cutoffs are independent of session dates. Define retention and replay keys before collecting history.

**Third increment:** Add optional Git and backup importers through the same revision contract, with explicit lineage/coverage reporting. Add retained cleaned prose only where historical quoting or re-tokenization requires it.

**Subsequent improvements:** Use real results to decide whether folder baselines, phrase variants, baseline sensitivity, momentum or seasonal models improve suggestions. Keep each improvement independently evaluable. Full-vault dictionary rebuilds on every invocation are unnecessary; reliable provenance, exact delta maintenance and cached detection are the implementation priorities.

