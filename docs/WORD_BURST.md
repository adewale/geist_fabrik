# Word bursts

The bundled `word_burst` geist asks linked questions about words whose document
prevalence became unusually elevated. Invoke it with:

```bash
uv run geistfabrik invoke /path/to/vault --geist word_burst
```

The detector implements Kleinberg's batched binomial model, with exact global
dynamic programming and traceback. Upward state transitions have a penalty;
downward transitions are free. Invalid probabilities are omitted rather than
clipped. Prefix/suffix minima make decoding O(weeks × states). A likelihood
gain is an episode weight, not statistical significance or evidence about a
person's mental state. Questions describe the measured population.

## History

`dated_cohorts` groups **current prose** by explicit creation dates: journal-entry
headings, frontmatter, then dated filenames. Filesystem estimates are excluded.
Editing today's text can change a reconstructed earlier cohort. This mode does
not recover the text that existed on the date assigned to it.

`observed_additions` measures positive additions captured during successful
vault syncs. First discovery establishes a baseline. Edits are observed at actual
UTC synchronization times, independently of the CLI replay date. Repeated
additions in a note/week coalesce into one observation with unioned terms,
revision evidence, and observation bounds. Removing a word later does not erase
its previously observed addition. Identical timestamps still capture changes;
regressing clocks refresh the current baseline without backdating events.
Same-path edits preserve note identity; deleting a note purges its logical
lexical history. This is not a secure physical erasure guarantee.

A coalesced row whose final addition was observed after a replay cutoff is
omitted in full. Historical quoting, exact old-text replay and Git/backup import
are deferred. Changing extraction policy clears incompatible observations and
establishes a fresh baseline. A replay against changed, unsynchronized extraction
settings abstains until sync rebuilds the index.

## Configuration

```yaml
lexical_analysis:
  enabled: true
  ngram_max: 1
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
```

Words use Unicode NFKC/casefold normalization. Frontmatter, fenced/indented and
inline code, complete HTML comments, URLs, generated session output and configured
paths are excluded. Visible link labels count as prose. Quotes are excluded by
default. Phrases are opt-in up to length three and never cross line boundaries or
removed regions. The extractor is a conservative lexical parser, not a complete
CommonMark renderer.

Observations with identical normalized term-count vectors in one week are
deduplicated. The same body in another week remains a separate observation.
Episode support requires at least `min_support` distinct body/evidence hashes
across the episode, and `min_support_bins` supporting weeks. This conservative
rule prevents repeated copies of one body from supplying independent support.
All supporting note paths are retained, including duplicates, so boundary
filtering checks every referenced note even when the question displays three.

Empty-exposure weeks are unobserved. Results expose interior gaps, open intervals,
left censoring and partial final weeks. Calendar dates at Python's boundaries
are supported by clamping the window and cutoff safely.

## Incremental work and safe exits

Counts and dictionary document frequencies update inside `Vault.sync`'s existing
owned transaction. Failure rolls back source notes and lexical history together.
Unchanged syncs read no lexical prose and do not rebuild the dictionary. Source
fingerprint checks and filesystem scans still occur; whole-vault sync is not O(1).
Code-only changes preserve lexical generation and cached detector results.

Detection caches empty and nonempty results by generation, extraction policy,
algorithm version, detector configuration and exact date cutoff. Eight result
variants are retained. Exposure changes invalidate all term results, including
terms absent from the changed note. Analysis uses one consistent database snapshot.

No observations, insufficient dated data, absent/ubiquitous terms, constant
prevalence, unavailable elevated probabilities and insufficient support abstain.
An exact necessary-gain bound skips candidates that cannot pay the first upward
transition. Near-boundary cases still run the DP. Vocabulary is not sampled or
truncated to its most frequent terms. Compact integer vectors and one evidence
pass keep support collection from rescanning notes once per candidate.

Public detector counts are integers in [0, 2**53], `s` is in (1, 1,000,000],
`gamma` in [0, 1,000,000], and state count in [1, 16]. Booleans and nonfinite
parameters are rejected. Unigrams are the default because phrase vocabularies
can require a larger execution-time budget. See the fresh measurements in
[WORD_BURST_PERFORMANCE.md](WORD_BURST_PERFORMANCE.md).

The [original research archive](WORD_BURST_ORIGINAL_SPEC.md) preserves the paper
review and initial proposal. This document describes the rebuilt implementation;
archive defaults, prototype measurements and deferred promises are not current
implementation guarantees.
