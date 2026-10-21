# Word bursts

The bundled `word_burst` geist asks linked questions about words and phrases
whose document prevalence became unusually elevated or quiet. Both directions
and two-word phrases are enabled in the same geist by default; three-word phrases
are supported with `ngram_max: 3`. Invoke it with:

```bash
uv run geistfabrik invoke /path/to/vault --geist word_burst
```

Rising episodes implement Kleinberg's batched binomial model. Declining episodes
extend it with lower-rate states, `baseline / s**level`. Both use exact global
dynamic programming and traceback. Moving farther from baseline has a penalty;
returning towards it is free. Invalid probabilities are omitted rather than
clipped. A tiny rational grid preserves complementary probabilities near zero
and one. Counts remain integers and probabilities remain exact fractions.
Fast floating-point decisions carry conservative error bounds; ambiguous
decisions use adaptive Decimal bounds on integer-weighted logarithms of exact
fractions. Algebraic cancellation proves exact ties, which prefer lower states.
Only reported objective/episode scores are rounded to floats. Using Decimal
alone would still allow rounded logarithms to invent a gain at a true tie.
Decoding is O(weeks × states), with a compact two-state default path. A likelihood
gain is an episode weight, not statistical significance or evidence about a
person's mental state. Questions describe the measured population.

## History

`dated_cohorts` groups **current prose** by explicit creation dates: journal-entry
headings, frontmatter, then dated filenames. Filesystem estimates are excluded.
Editing today's text can change a reconstructed earlier cohort. This mode does
not recover the text that existed on the date assigned to it.

`observed_additions` measures positive additions captured during successful
vault syncs. The first sync establishes a baseline. Notes first discovered after
that bootstrap contribute newly observed text, never a claim about when it was
written. Edits and discoveries are observed at actual
UTC synchronization times, independently of the CLI replay date. Repeated
additions in a note/week coalesce into one observation with unioned terms,
revision evidence, and observation bounds. Removing a word later does not erase
its previously observed addition. Identical timestamps still capture changes;
regressing clocks refresh the current baseline without backdating events. A sync
that skips a changed source cannot tighten the global lower observation bound;
confirmation is tracked by source identity, including hardlinked files.
Same-path edits preserve note identity; deleting a note purges its logical
lexical history. This is not a secure physical erasure guarantee.

A coalesced row whose final addition was observed after a replay cutoff is
omitted in full. Historical quoting, exact old-text replay and Git/backup import
are deferred. Changing extraction policy archives incompatible observations and
establishes a fresh baseline. Returning to the same extraction policy restores
its retained observations; another policy never borrows their absence counts.
Pausing capture, disabling the index or geist, and reordering equivalent exclusion
prefixes preserve history. Resuming establishes a confirmed baseline before
capturing further additions. Unreadable sources retain that pending baseline
across later syncs. Deleting a note purges its active and archived observations.
Extraction version 7 uses parser-owned fence and inline-code boundaries, including
list-contained fences and separate paragraphs. It retains link/image spans,
blockquote line maps and Unicode word spans shared by counting and excerpts.
HTML tag names and attributes are excluded; visible inline formatting text is
retained. Code, preformatted text, scripts, styles, document headers and templates
cannot supply prose. HTML blockquotes follow `include_quotes`. Counting and
excerpts share these regions, including entity and escaped-text handling.
Virtual entries preserve source indentation; parser revision 7 refreshes existing
entries that an earlier splitter stripped. Declared creation
dates retain their written calendar day, independent of the host timezone;
observed instants continue to use UTC. Upgrading an earlier PR build rebuilds lexical baselines and
archives incompatible captured observations. Core notes and saved questions are
retained. A virtual entry whose corrected whitespace changes its stored text
invalidates its own cached embeddings; unchanged note bodies retain theirs.
A replay against changed, unsynchronized extraction
settings abstains until sync rebuilds the index.

Document prevalence is stored as integer mentions and observations, including
cached findings. Exact rational comparisons decide whether a decline is real;
floating values exposed by the reporting API are derived projections. Paired
percentages increase precision together until distinct rates display differently.
Analysis version 8 invalidates older cached results. Declines show the first and
last actually observed reference weeks, the count of observed weeks and any
interior gaps; missing weeks are never evidence of absence.

## Execution budget

With a supported executor deadline, analysis saves its completed candidate cursor
and exact partial episodes before returning a deferred result. Invoke again to
resume, or set a larger explicit timeout. No partial statistical finding is
presented as complete. Changed source evidence, dates, eligibility or model
settings invalidate the work. Completed findings match uninterrupted analysis.
Ordinary invocation and `--explain` report deferred work; `--quiet` suppresses the
status message. Budget exhaustion does not increment the geist failure counter.
An unrelated host alarm still propagates. Schema v15 stores this work and
inactive extraction-policy observations.

The budget is cooperative between prepared batches. Collection, presence
backfill, final evidence binding and an indivisible model operation can still
outgrow a very small budget; the hard executor deadline rolls back that attempt.
Previously committed progress survives. A larger explicit budget may still be
needed for those phases or unusually costly model settings. This mechanism
bounds an invocation; it does not guarantee less total computation.

## Configuration

```yaml
lexical_analysis:
  enabled: true
  ngram_max: 2                # 1 = words only; 2 = include pairs; 3 = include triples
  include_quotes: false
  capture_observed: true
  exclude_paths: ["Templates/"]
word_burst:
  history_mode: dated_cohorts  # or observed_additions
  window_weeks: 104
  min_documents: 50
  min_populated_bins: 8
  min_support: 3
  min_support_bins: 2
  s: 2.0
  gamma: 1.0
  max_states: 2               # includes the baseline
  max_suggestions: 3
  directions: [rising, declining]  # either direction can also be used alone
```

Words use Unicode NFKC/casefold normalization. Frontmatter, fenced/indented and
inline code, complete HTML comments, URLs, generated session output and configured
paths are excluded. Visible link labels count as prose; resolved reference-link
identifiers, definitions and destinations do not. CommonMark parsing identifies
those source spans without changing the remaining extraction policy. Caret-label
Obsidian footnotes retain the existing footnote policy. Quotes are excluded by
default. Disabling `word_burst` also skips construction and maintenance of its
unused lexical dictionary. Existing observations remain retained. Three-word
phrases remain optional. Phrases never cross sentence, semicolon, line or removed-region
boundaries. Explicit existing `ngram_max: 1` configurations stay words-only until
changed. Quotes include conservative exclusion of lazy continuation lines.
The extractor is a conservative lexical parser, not a complete
CommonMark or browser renderer. CSS and browser layout are not interpreted.

Observations with identical normalized term-count vectors in one week are
deduplicated. The same body in another week remains a separate observation.
Episode support requires at least `min_support` distinct body/evidence hashes
across the episode, and `min_support_bins` supporting weeks. This conservative
rule prevents repeated copies of one body from supplying independent support.
All supporting paths remain in analysis findings, including duplicates. The geist
checks every supporting reference against the same boundary policy as the pipeline
before capping rendered references at the runtime limit of 100. Questions display
three links. An excluded support beyond that cap still suppresses the question.

A decline must have established earlier use: `min_support` distinct prior bodies
or evidence hashes across `min_support_bins` earlier weeks. The quieter episode
also needs at least `min_support_bins` weeks with positive exposure, even when
none mention the term. An initially quiet period is not a decline. Questions give
the quieter rate, the earlier period/rate, and links to that earlier usage.
Declines do not establish forgotten interests or beliefs, and observed-addition
declines describe captured additions rather than all current note text.

The session date (today unless `--date` is supplied) sets the endpoint of the
configured weekly window. The detector finds episodes inside it. `history_mode`
is an explicit configuration choice; the geist does not switch modes itself.

Empty-exposure weeks are unobserved. Results expose interior gaps, open intervals,
left censoring and partial final weeks. Calendar dates at Python's boundaries
are supported by clamping the window and cutoff safely.

## Incremental work and safe exits

Schema v14 stores a sorted little-endian uint64 term-presence vector beside each
current and captured lexical row, sharing stable IDs in `lexical_presence_terms`.
Exact frequency/history JSON remains authoritative. Existing installations fill
missing selected vectors from stored JSON on the first cold analysis, without
reading Markdown again or resetting observations, notes, embeddings or saved
questions. It backfills only the requested history mode and weekly window.
Updates invalidate and replace projections inside the same owned transaction.
The extra index costs eight bytes per presence plus a shared term dictionary.

Cross-day reuse requires identical selected source identities and weekly exposure
under the same frame, generation, policy and settings. Future-dated notes entering
the cutoff, newly captured additions and a moving weekly window still invalidate
reuse. Stored intervals end at the model's final Sunday; returned dates and
partial-week flags are refreshed for the requested session date. A cached
abstention retains its population explanation and reports zero decoding work.

Collection streams presence vectors into compact NumPy integer weekly columns.
Source buffers stop at 256 rows or 262,144 selected occurrences, plus at most one
source's vector. Preparation stops at 1,024 terms or 131,072 sparse coordinates,
plus at most one column. Exact-series reuse retains at most 8,192 entries and
262,144 coordinates. The final sparse statistics and supported findings still
scale with actual corpus evidence; these bounds do not truncate vocabulary or
change statistical thresholds. Cache eviction can require more decoding.

Counts and dictionary document frequencies update inside `Vault.sync`'s existing
owned transaction. Failure rolls back source notes and lexical history together.
Unchanged syncs read no lexical prose and do not rebuild the dictionary. Source
fingerprint checks and filesystem scans still occur; whole-vault sync is not O(1).
Code-only changes preserve lexical generation and cached detector results.
Date-only edits invalidate chronology-dependent analysis without rewriting the
unchanged dictionary. `BurstModel` validates shared exposure once and reuses exact
probability/emission grids for equal overall prevalence. Error bounds use the
uncancelled arithmetic scale, so large counts and near-one multipliers cannot
hide uncertain decisions behind a small final score. Uncertain paths are decoded
again with the exact-log representation; uncertain pruning retains the candidate.
The layout-independent necessary-gain screen is exposed as
`BurstModel.cannot_burst_total`: a true result proves that no weekly layout with
that total can beat the baseline. Analysis applies it before allocating prepared
series. Weekly prevalence uses packed integer presences and unweighted NumPy
histograms; counts remain integers. The default two-state grid
can decode independent series in bounded NumPy batches. Identical weekly series
also share decoding; every term retains its own independent source evidence.

Detection caches empty and nonempty results by generation, extraction policy,
algorithm version, detector configuration and exact date cutoff. Eight result
variants are retained. Exposure changes invalidate all term results, including
terms absent from the changed note. Analysis uses one consistent database snapshot.

No observations, insufficient dated data, absent/ubiquitous terms, constant
prevalence, unavailable elevated probabilities and insufficient support abstain.
A conservative necessary-gain bound skips candidates that cannot pay the first
transition away from baseline. Dated cohorts also omit terms whose current document
frequency cannot meet minimum distinct-body support; captured additions never use
that current dictionary, because a historical term may have disappeared. Near-boundary cases still run the DP. Vocabulary is not sampled or
truncated to its most frequent terms. Compact integer vectors and one evidence
pass keep support collection from rescanning notes once per candidate.

Public detector counts are integers in [0, 2**53], `s` is in (1, 1,000,000],
`gamma` in [0, 1,000,000], and state count in [1, 16]. Booleans and nonfinite
parameters are rejected. Full phrase vocabularies can require substantially more
indexing time, memory and execution time. See the fresh measurements in
[WORD_BURST_PERFORMANCE.md](WORD_BURST_PERFORMANCE.md).

The [original research archive](WORD_BURST_ORIGINAL_SPEC.md) preserves the paper
review and initial proposal. This document describes the rebuilt implementation;
archive defaults, prototype measurements and deferred promises are not current
implementation guarantees.


## Fit with the vision

The geist is a retrospective muse: it notices a change in language, names the
measured population, links actual notes, and asks the reader to explore a question.
That fits the [vision](../specs/geistfabrik_vision.md)'s reflection, surprise and
divergence goals. It contributes lexical evidence alongside semantic drift;
shared vocabulary is a different signal from proximity in embedding space.

Its best use is to revisit a period of changing vocabulary and connect notes that
use the same emerging language. Current-text cohorts are explicitly reconstructed;
captured additions provide firmer observation evidence once enough sync history
accumulates. Sparse or undated vaults abstain rather than invent chronology.

Engineering choices follow the repository's practices: local SQLite ownership,
atomic sync, no vocabulary sampling, exact safe pruning, policy/versioned caching,
strict resource limits, complete-evidence boundary checks, independent property
oracles and benchmarks that use the actual executor. Words and two-word phrases are the default. Large optional vocabularies use
resumable decoding under the execution budget, as described below.

A word spike does not establish importance, intent or a change in beliefs. A
presentation gate excludes expressions made entirely of English grammatical
words, before grouping and sampling; meaningful mixed phrases remain eligible.
Extraction, dictionary counts and statistical findings remain unchanged. Other
statistical episodes can still be uninteresting. Saved episode identities
suppress overlapping repeats throughout saved history; normal novelty/diversity
filtering is still needed.
The corpus checks establish signal detection, exclusion and runtime reliability.
They do not establish reader surprise or usefulness. Real-vault qualitative
review should judge those qualities before presenting the geist as broadly proven.

Questions now show up to two bounded passages from **current** visible prose.
They never present those passages as retained historical quotations. Displayed
links are sampled and included in the bounded payload. Nested word/phrase
variants with identical episode dates and complete evidence are collapsed to the
more specific expression; remaining candidates are sampled rather than ranked
by frequency or gain. When the budget permits and both are available, the geist
samples both rising and declining candidates. Validation and saved-episode checks
happen before a question consumes a slot, so another usable episode can replace
a rejected candidate. A leading article does not displace an existing shorter
content phrase with the same complete evidence.

Saved suggestions have an optional interval evidence key (automatic additive
schema v12 migration, indexed by additive schema v13). The normal novelty filter suppresses an overlapping
episode for the same expression, mode and direction even when its percentages,
wording, chosen links or window-clipped start change. A disjoint later recurrence
remains eligible. Evidence identities survive the ordinary 60-day novelty window;
same-day and future saved runs do not affect historical replay. Previews do not
add history. Old saved suggestions without keys still use the
existing text/embedding novelty checks. Identity is observation-level, not a
model of what the reader knows; feedback controls remain deferred. Generation
uses the same indexed evidence lookup as the downstream filter and refills
from remaining candidates. `--no-filter` retains raw previews, including saved
episodes.

`invoke --explain` reports the lexical population and abstention reason from the
actual invocation, including cached empty results. A cached result retains its
original evidence counts while recording zero decoding work. Schema v13 clears
only incompatible derived result-cache rows; it preserves captured additions.

This applies lessons from Andy Matuschak's
[Notes should surprise you](https://notes.andymatuschak.org/zYaWNLqGvd3uLPDXkhRoWoq),
[fine-grained associations](https://notes.andymatuschak.org/zS27HJzP3uD366crN7PYDQU)
and [explicit associations](https://notes.andymatuschak.org/z8Ubad66AWp7ZLShUmRu3vu).
The decline direction applies the user's inversion lens to lexical evidence.
These changes support exploration; they do not prove conceptual relevance or
infer contradiction, intent or mental state from word counts or embeddings.

The positive synthetic CLI check selected a fixture marker (`specimenbb`),
showing why elevated prevalence alone is not a relevance judgment. Captured
additions are the stronger choice for observed change; dated cohorts are a
browsing lens over current text. Both need reader interpretation and ordinary
novelty/diversity filtering.
