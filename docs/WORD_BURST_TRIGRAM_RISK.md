# Trigram capacity and the missing narrative vault

This investigation follows runtime checkpoint
`8b1cde5afee1fffe21e995a691938e3463953b5a`. It changes no detector, extraction or
timeout behavior. [Feature receipts and source/probe provenance](../benchmarks/results/word_burst_trigram_risk/summary.json)
retain the independently measured distributions and pinned public inputs. The
latest capacity measurements remain those in
[the repair report](WORD_BURST_REVIEW_REPAIRS.md).

## What the current corpora establish

The 10,000-note capacity corpus contains scrambled Alice-in-Wonderland prose,
with the benchmark's earlier 100-note marker edit. Its dates are a labelled
synthetic overlay. The temporal corpus repeats eight stock topic sentences,
identity labels and planted changes. Both fixtures have useful independent
controls, but neither represents a person developing a coherent body of ideas.

Read-only inspection of their existing through-trigram dictionaries shows:

| Feature | Capacity fixture | Temporal large, last snapshot |
| --- | ---: | ---: |
| Indexed observations | 10,000 | 12,232 |
| Visible word tokens | 7,099,810 | 482,801 |
| Median visible tokens per observation | 705 | 24 |
| Distinct trigrams | 778,675 | 12,337 |
| Trigrams present in at least three documents | 379,457 | 137 |
| Expressions of all sizes present in at least three documents | 407,696 | 398 |

These are global document-frequency eligibility upper bounds, not confirmed episodes or independent
body support inside an episode. The model applies additional support, chronology
and likelihood requirements. The temporal fixture has more observations yet about
one thousand times fewer frequency candidates. Note count alone is a poor capacity
predictor.

The capacity fixture has only 7,422 unigram types, but repeatedly recombines that
small vocabulary into hundreds of thousands of recurrent trigrams. Scrambling
natural-language text changes the workload. Coherent prose also produces many
one-off phrases, which cost extraction/collection but can be pruned before
likelihood decoding. We cannot assume all real writing is either cheaper or more
expensive without inspecting its recurrence and length distribution.

## Authored public prose comparison

The sub-agent also measured [Blue Book](https://github.com/lyz-code/blue-book/tree/e494de6c0d30b338b3117025819be35bdf1e5af6),
a personal knowledge wiki under CC0-1.0. It processed 1,123 Markdown files
(10,907,925 bytes), using the current production extractor with through-trigram
settings. All Markdown and the license were fetched at that fixed commit and
verified against their Git blob identities. No dates, embeddings or burst
analyses were assigned to the public source.

| Global document support of at least three | Authored wiki | Scrambled capacity corpus |
| --- | ---: | ---: |
| Eligible words and pairs | 28,079 | 28,239 |
| Eligible words, pairs and trigrams | 42,661 | 407,696 |
| Increase when adding trigrams | 51.9% | 1,343.7% |
| Distinct trigrams passing this screen | 6.38% | 48.73% |

These are upper bounds across current prose, before date-window selection and
within-week deduplication. They are not actual decoder counts. The authored wiki
has 448,213 visible tokens, median 113 per note; its 99th-percentile note has
4,020 visible tokens. Its short-note majority and long tail differ substantially
from the stress fixture. The samples also differ in size and subject matter;
this is not a controlled experiment isolating the effect of scrambled prose.

The similar eligible word/pair counts and very different trigram increase show
that the stress corpus is a poor proxy for this authored collection's phrase
recurrence. One technical wiki does not establish a distribution of everyday
Obsidian vaults. No probability of timeout, linear runtime extrapolation or
historical usefulness is established. Long-article collections can still exceed
the stress workload on relevant dimensions.

The complete Kepano public example was also inspected: 103 Markdown files,
52 of them excluded templates. The remaining 51 notes have only 4,233 visible
tokens and one trigram present in at least three notes. Expanding the local
excerpt to the full example does not supply a representative large working vault.

## Measured cost and practical exposure

The controlled two-trial median through-trigram analysis improved from 50.68 to
29.82 seconds. A fresh actual executor still exceeded its default 30-second
budget; an explicit 120-second invocation completed in 30.46 seconds. Cached
execution completed in 0.44 seconds. Default words/pairs completed in 11.58 seconds.
No vocabulary was sampled or truncated.

One matched after-trial attributed 15.36 seconds to collection, 11.91 to decoding
and 2.39 to evidence assembly. These phase times are one observation, not medians
or an additive model of arbitrary vaults. Collection is substantial even when
most terms can eventually be pruned.

Risk rises with total eligible prose, recurrent candidate phrases, populated
history bins and extra model states. Long imported articles, technical reference
collections, repeated meeting templates and large captured-addition histories
need particular attention. Source exclusions and phrase settings matter. Smaller
short-note collections offer less work, but no sampled population of real vaults
has established a timeout probability or a safe note-count cutoff.

Trigrams are optional; words/pairs remain the default. Repeated unchanged analysis
benefits from its cache, while a fresh corpus generation or analysis window can
require the expensive path again. A longer invocation budget is a measured
operational mitigation, not a universal latency guarantee.

## Exact optimization opportunities

Collection accounts for roughly half the measured triple runtime. Reusing exact
collected/prepared inputs is a higher-priority investigation than focusing only
on the NumPy decoder. The current result cache includes the exact cutoff day;
unchanged files can therefore require fresh work on a later day.

A reusable input cache would need to prove identical selected observations,
weekly exposure, policy and model configuration. Presentation dates and partial
week flags must remain current. Rounding the cutoff to a week without checking
membership would mishandle future notes, moving windows and partial weeks.

Two other candidates are bounded decoding that releases prepared Python objects
sooner, and transactional per-week presence aggregates using the existing lexical
store. The latter needs duplicate-body reference counts and correct handling of
date moves, deletions, virtual entries, source recovery, additions history and
policy resets. It trades index size and write amplification for less JSON parsing
and aggregation. No speedup is measured for either proposal.

Default two-state dated-cohort timings do not establish performance for larger
state grids or long observed-additions histories. Historical additions can exceed
the number of current notes; present-day document frequency cannot safely prune
that history. An old out-of-window archive can also inflate the global candidate
setup even when only a small slice is selected. These cases belong in future
capacity profiles.

## Why there is no realistic fictional vault yet

We built the temporal fixture to trigger geists, validate planted changes and
preserve stable controls. We used the large corpus to expose scaling costs.
We did not add the intermediate fixture needed to assess the meaning of the
questions. This is an evaluation-design gap, rather than a prerequisite that
requires access to private notes.

A fictional vault can verify plausible evidence-linked questions and expose
obvious observations, misleading declines, boilerplate and repetition. Its
judgments must be tied to a fictional author's independently written brief.
It cannot by itself establish what real readers already know or find useful.

## Proposed narrative fixture contract

Start with a modest curated vault, approximately 150–300 notes over 18–24 months,
then add independently authored personas rather than multiplying one template.
Use a person with overlapping work, study and personal projects. Include varying
note lengths, ordinary titles, cross-links, unfinished notes, journals, quotes,
clippings, code and real-looking revisions. Keep the synthetic nature explicit.

Write an author brief and an event/evaluation ledger **outside the ingested
vault**, before running the geist. The first scenario set should include:

- An obvious project launch whose vocabulary growth the author already knows.
- A quieter repeated concern spanning different projects, with passages that
  support a worthwhile comparison the author has not explicitly made.
- A completed project whose vocabulary declines; asking about a forgotten belief
  would misrepresent the known reason.
- A terminology replacement, where falling use of an old phrase does not imply
  falling interest in the underlying topic.
- Stable interests, repeated templates and an imported batch as controls.
- A previously saved question, followed by overlapping and genuinely disjoint
  later evidence, to assess repetition and renewed value.

Use authored source revisions with actual replay times for the fictional story.
Reuse the existing content-addressed manifest and safe sequential replay format.
Dated cohorts and captured additions should retain their separate meanings.
Do not assign dates to real public notes and present them as historical evidence.

Review the full normal invocation path, including filters and saved-history
suppression, across several session dates. Record useful, already-known, noisy,
incorrect and abstaining outcomes. Prefer factual constraints and acceptable
questions over one exact expected sentence. Compare against a simple frequency
change prompt or random linked-note baseline, retaining all sessions in the
results. The independently written ledger must remain fixed when outputs are
unhelpful.

This narrative fixture has not yet been implemented. Its purpose is to fill a
specific evaluation gap while retaining the existing mechanical and stress
fixtures. Owner-rated real-vault evaluation remains a separate later check;
[the existing protocol](WORD_BURST_EVALUATION.md) describes that process.
