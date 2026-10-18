# What optional three-word phrases add

The `word_burst` work in [PR #97](https://github.com/adewale/geist_fabrik/pull/97)
supports words, two-word phrases and optional three-word phrases in one geist.
Words and pairs remain the default (`ngram_max: 2`). Three-word expressions can
name a concept more precisely, but the research reviewed here does not establish
that enabling every trigram produces more useful questions about personal notes.

For this geist, a trigram means **three consecutive words**, such as “theory of
mind”. It preserves internal function words and the extractor's sentence, line
and excluded-region boundaries. SQLite FTS5's
[trigram tokenizer](https://www.sqlite.org/fts5.html#the_trigram_tokenizer)
instead indexes **three-character substrings**. It is not a replacement for this
word-phrase analysis.

## What the research supports

The papers distinguish temporal change, a well-formed phrase, topical
informativeness and usefulness to a reader. These are different properties.

| Primary source | Finding and implication |
| --- | --- |
| [Kleinberg, 2002: Bursty and Hierarchical Structure in Streams](https://www.cs.cornell.edu/home/kleinber/bhs.pdf) | State transitions identify unusually intense periods in a stream. The paper does not demonstrate an advantage for trigrams in personal reflection. An episode's gain is not the probability that a question matters to its author. |
| [Kleinberg: Temporal Dynamics of On-Line Information Streams](https://www.cs.cornell.edu/home/kleinber/stream-survey04.pdf), author-hosted survey labelled 2004 | Its conclusion identifies the alignment problem: relating detected events to events outside the stream helps interpretation and evaluation. Keep the frozen event ledger and distinguish a known project completion from a forgotten interest. |
| [Leskovec, Backstrom and Kleinberg, 2009: Meme-tracking and the Dynamics of the News Cycle](https://www.cs.cornell.edu/home/kleinber/kdd09-quotes.pdf) | Distinctive phrases can track changing story lines without large changes in overall vocabulary. The experiment clusters variants of quotations in news and blogs; it does not test exhaustive word trigrams or personal-note questions. |
| [Tomokiyo and Hurst, 2003: A Language Model Approach to Keyphrase Extraction](https://aclanthology.org/W03-1805/) | Phrase cohesion and informativeness relative to a background corpus are separate. A collocation such as “in spite of” need not be informative. The authors explicitly acknowledge difficulty evaluating utility quantitatively. |
| [Frantzi, Ananiadou and Mima, 2000: C-value/NC-value](https://doi.org/10.1007/s007999900023) | The verified publisher abstract describes nesting-sensitive frequency and context evidence. Repeated fragments within a longer term need special care. Only the abstract was obtained in this review; no new performance claim is made for this method. |
| [Liu et al., 2015: Mining Quality Phrases from Massive Text Corpora](https://hanj.cs.illinois.edu/pdf/sigmod15_jliu.pdf), SegPhrase | Phrase quality combines popularity, concordance, informativeness and completeness. “Vector machine” can recur inside “support vector machine” without being complete in that context. A phrase and subphrase can also both be valid. |
| [Shang et al., 2018: Automated Phrase Mining from Massive Text Corpora](https://doi.org/10.1109/TKDE.2018.2812203), AutoPhrase | Knowledge-base training and optional POS-guided segmentation improve phrase mining on large corpora. Its rectified segmentation frequencies would change our literal-count definition. The inspected full source is the [2017 preprint](https://arxiv.org/abs/1702.04457); publication metadata was checked separately. |

These findings support the existing presentation gate and conservative nesting
collapse: reject function-word-only lenses, preserve meaningful mixed phrases,
and prefer the more specific expression when episode dates and complete evidence
agree. They do not justify always choosing the longest phrase. Any future
cohesion or completeness rule belongs in a separately evaluated question-selection
policy, preserving the dictionary and statistical findings.

AutoPhrase would also add external training data and a segmentation pipeline.
Its phrase-quality results are not evidence that this dependency would improve
the project's [surprise and reflection goals](../specs/geistfabrik_vision.md).
No learned phrase miner is required for the exact performance improvements.

## Established storage and retrieval practice

The [IR textbook's phrase-index discussion](https://nlp.stanford.edu/IR-book/html/htmledition/biword-indexes-1.html)
warns that exhaustive longer phrases expand vocabulary substantially. Its
[combined approach](https://nlp.stanford.edu/IR-book/html/htmledition/combination-schemes-1.html)
uses positional postings with selected phrase acceleration. Elastic's
[index_phrases](https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/index-phrases)
similarly offers opt-in two-term indexing: faster exact phrase queries at the
cost of a larger index. Answering a supplied phrase query differs from finding
unknown temporal candidates, so those search speedups do not predict our runtime.

Exact representation reuse has academic precedent too.
[Yamamoto and Church, 2001](https://aclanthology.org/J01-1001/)
groups substrings into equivalence classes to compute their statistics without
treating every substring independently. This supports sharing identical inputs;
it does not establish that a suffix-array rewrite would help our bounded,
incrementally indexed phrases.

Existing dependencies provide suitable building blocks, with explicit limits:

- [SciPy COO](https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.coo_matrix.html)
  supports sparse construction and conversion to CSR/CSC. Duplicate coordinates
  are **summed** during conversion. Note/week unions and duplicate-body evidence
  must therefore be handled deliberately, rather than silently becoming repeated
  occurrences. Bound intermediate allocations as well as the final matrix.
- [CountVectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.CountVectorizer.html)
  demonstrates sparse count and binary-presence representations. Its default
  tokenization and n-gram boundaries differ from our Markdown policy. Reuse
  storage primitives without replacing the extractor's semantics.
- Elastic's [request-cache documentation](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/shard-request-cache)
  requires invalidation as documents or mappings change and excludes most queries
  using `now`. Our cross-day reuse likewise needs identical observation
  membership, exposure and settings. Simply deleting the cutoff date from a key
  would be unsafe; rolling windows and newly eligible future dates still matter.

There is no verified universal latency target for exhaustive two-direction
Kleinberg analysis of 10,000 personal notes. Fresh analysis, cached invocation,
sync cost, peak memory and index size are measured separately. The
[capacity investigation](WORD_BURST_TRIGRAM_RISK.md) records why note count alone
is a poor workload predictor; the [performance report](WORD_BURST_PERFORMANCE.md)
retains source-bound measurements. This literature review promises no speedup.

## How to judge the added value

The original narrative run enabled trigrams, so it cannot alone establish their
incremental benefit over words and pairs. Its
[evaluation](NARRATIVE_VAULT_EVALUATION.md) and
[quality-fix replay](NARRATIVE_QUALITY_FIXES.md) retain the limitations of
assistant-authored prose and ratings. Public current-prose counts establish
neither authentic history nor owner-rated usefulness.

A subsequent matched lexical-only replay at source
[`6660bfa`](https://github.com/adewale/geist_fabrik/commit/6660bfa93b2a10f42d8228e9cea2d26924326785)
uses all 24 frozen narrative snapshots, both history modes and independent fresh
word/pair and through-trigram vaults: 96 analyses over 48 matched contexts.
Production sync, analysis and `word_burst.suggest` run with equal dates, seeds,
thresholds and a three-question budget. Embeddings, downstream filtering, saved
question history and owner judgments are outside this experiment.

| Dated-cohort result across 24 snapshots | Words/pairs | Through trigrams |
| --- | ---: | ---: |
| Model finding appearances, including repeats across snapshots | 146 | 154 |
| Sampled geist questions | 41 | 41 |
| Snapshots producing questions | 19 | 19 |

Every word/pair finding is identical across arms. The only additional trigram
term is `the repair cafe`: eight finding appearances, covering four distinct
term/direction/interval identities. Four appearances share exact dates, direction
and complete evidence with a contained shorter finding; four have different
evidence. Five of the through-trigram questions use this lens. Twenty-nine of 41
question texts match between arms in the same context; 12 differ, including
indirect effects on grouping and deterministic sampling. Different wording is
not itself added value. Both observed-additions arms abstain in all 24 snapshots
because they lack the required document population.

The pinned [Blue Book public wiki](https://github.com/lyz-code/blue-book/tree/e494de6c0d30b338b3117025819be35bdf1e5af6)
provides a separate current-prose check: 1,123 Markdown files contain 28,079
words/pairs present in at least three documents and 14,582 additional trigrams.
A deterministic SHA-ranked sample of 32 recurrent trigrams includes fragments
such as `can use the` and descriptive expressions such as `definition of objects`.
Several sampled recurrences come from repeated changelog text. A grammatical
boundary word occurs in 9,688 of 14,582 candidates, but that structural property
is not a usefulness label: valid phrases can contain function words. No historical
dates, burst findings or reader benefit are inferred from this static comparator.

The stress corpus behaves differently: its dictionary grows from 42,990 words
and pairs to 821,665 expressions through triples, about 19 times as many. The
static public prose vocabulary grows about 1.52 times. Neither is a prediction
for another vault. Eligible vocabulary, distinct weekly presence patterns and
repeated boilerplate explain workload better than the number of Markdown files.

The matched narrative results establish a small change in available material,
not an improvement in reader usefulness. Review passages with arm metadata
masked, retaining already-known, generic, misleading and abstaining outcomes.
The question's wording reveals its phrase length, so this cannot be a fully
blind comparison. Distinguish an additional episode from a clearer phrase naming
the same evidence; both can have value, but they answer different questions.
Measure complete invocation separately, using independent saved histories and
recording pairs displaced under the fixed question budget. Owner judgment or a
second author is needed before claiming personal usefulness. Keep triples optional
unless their added value warrants their measured runtime and storage costs.

A separate reviewer, who did not author the story, assessed all 53 distinct
question packets before seeing either arm's identity or aggregate results. Its
labels were frozen before unmasking. All five selected `the repair cafe` prompts
were labelled already known, with reasons tied to explicit source lessons.
Across each arm's 41 selected questions, it marked five word/pair questions and
four through-trigram questions as potential useful connections. These small
descriptive counts are not a causal benefit estimate. The first assessor found
no useful candidates at all; disagreement about the broader questions reinforces
the need for actual owner feedback. Neither assessment supports an incremental
benefit from this fixture's added three-word lens.

## Research receipts

Supplementary downloaded papers, official documentation, resolved URLs and hashes
are retained outside the repository at
`/workspace/verification-tools/trigram-reuse/literature/`. The primary links above
remain usable independently of that workspace. `source_manifest.json` has SHA-256
`22fdd03374b91c7698013db4616f9176e648c9d8b7b52dde30bbbab4f19c19ef`.
`claim_ledger.json` retains 15 quotations checked against the downloaded text.
Failed URLs and four title-mismatched downloads are recorded as uncited discovery
attempts; they are not supporting evidence.

Matched replay receipts are in
`/workspace/verification-tools/trigram-reuse/value/summary.json` and
`baseline-value.json`. The protocol was frozen before inspecting matched output;
its SHA-256 is
`87750517c4eaaf87a9f44d7b54f8d90a54acee2f6155d70b3adf4ee705259073`.
The summary binds the runtime, evaluator, raw results, source manifest and frozen
ledger. Elapsed times from this concurrent replay are not performance claims.
`static-public-value.json` in the same directory retains the public comparator's
inventory hash, extraction settings and complete 32-expression sample.
