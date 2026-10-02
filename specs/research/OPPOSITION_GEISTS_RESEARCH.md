# Can the "Opposition" Geists Work? Literature, Prototype and Cost

**Date**: 2026-10-02
**Status**: Research / proposal (not implemented)
**Geists concerned**: dialectic_triad, antithesis_generator, contradictor,
blind_spot_detector, columbo, assumption_challenger

## Verdict

Partly, and offline, but not with today's infrastructure.

- **Sentence embeddings cannot detect opposition.** On 28 hand-made pairs the
  bundled all-MiniLM-L6-v2 gave contradictions a *higher* mean cosine (0.879)
  than paraphrases (0.848); every contradiction scored above every compatible
  same-topic pair. "Least similar note = opposite" (`contrarian_to`) therefore
  looks in exactly the wrong place: contradictions are on-topic and high-cosine.
- **Retrieve-then-classify works.** Retrieve high-cosine sentence pairs from
  different notes with the bundled MiniLM, then label each pair with a small
  NLI cross-encoder (DeBERTa-v3, 70-185M parameters, Apache-2.0/MIT, CPU).
  No new Python dependencies (sentence-transformers already provides
  `CrossEncoder` and torch).
- **Quality is muse-grade, not oracle-grade.** On the 77-note documentation
  vault plus 7 planted contradictions, the best model put 5 of 7 planted pairs
  in its top 11 of 1,105 candidates; 45% (up to ~55% with a deictic filter) of
  the non-planted top-25 pairs were genuinely useful (one real doc
  inconsistency, many design tensions), against 8% for random candidate pairs.
  Suggestions must quote both sentences and ask, never accuse.
- **Cost** (xsmall model, 1 thread): ~45 ms per pair direction; a first full
  index takes 8-23 min for 1k notes and 1.3-3.9 h for 10k notes, then seconds
  per changed note. It must be an incremental, cached, budgeted index built
  before geists run, never inside a geist's 30 s timeout.
- **Packaging**: the model cannot be bundled. The wheel is 83.8 MB against a
  95 MB artifact gate and PyPI's 100 MB default; the smallest usable 3-class
  NLI model is 83-87 MB even as int8 ONNX (283 MB fp32). It has to be an
  opt-in pinned download (or a companion package); without it the geists stay
  silent.
- **Small local LLMs are not a substitute.** Qwen2.5-0.5B/1.5B-Instruct as
  yes/no judges did worse than chance under three prompt wordings (they behave
  as similarity detectors) and were 12-60x slower, matching the literature.

## Why embeddings fail (literature)

- Antonyms share contexts, so distributional vectors place them together
  (Mohammad, Dorr, Hirst & Turney 2013, *Computational Linguistics* 39(3));
  separating them needed thesaurus signals (Ono, Miwa & Sasaki 2015, NAACL;
  Nguyen, Schulte im Walde & Vu 2016, ACL).
- Pretrained encoders largely ignore negation: Ettinger 2020 (TACL), Kassner &
  Schütze 2020 (ACL), García-Ferrero et al. 2023 (EMNLP), Truong et al. 2023
  (*SEM). For sentence-embedding models specifically: Opitz & Frank 2022
  (S³BERT, AACL); Truong, Verspoor, Cohn & Baldwin 2025 (arXiv:2507.12782);
  Frias 2026 (arXiv:2608.10216: cosine gates caught 0 of 56 meaning reversals).
- A bi-encoder (Reimers & Gurevych 2019, SBERT) encodes sentences separately;
  a cross-encoder reads both together and is the standard tool for labelling a
  pair (sentence-transformers "Retrieve & Re-Rank").

Measured on the bundled model:

| Pair class | Mean cosine | Range |
|---|---|---|
| Contradiction | 0.879 | 0.78-0.96 |
| Paraphrase | 0.848 | 0.63-0.91 |
| Compatible, same topic | 0.440 | 0.26-0.65 |
| Tension | 0.329 | 0.08-0.66 |

Consequence: embeddings are good for *finding candidates* (contradictions are
high-cosine) and useless for *labelling* them. Tensions phrased in different
vocabulary have low cosine and will not be retrieved: a recall limit.

## NLI and contradiction detection

- Datasets: SNLI (Bowman et al. 2015), MultiNLI (Williams et al. 2018), ANLI
  (Nie et al. 2020), FEVER-NLI.
- Caveats that matter for notes: SNLI's "same event" assumption makes models
  over-call contradiction for related but non-coreferent sentences (the main
  false-positive mode in the prototype: "This document outlines X" vs "... Y");
  annotation artefacts (Gururangan et al. 2018; Hossain et al. 2020).
- de Marneffe, Rafferty & Manning 2008, "Finding Contradictions in Text" (ACL):
  contradiction requires event coreference; filter to same-topic pairs first,
  then classify. This is still the right pipeline. SummaC (Laban et al. 2022)
  shows NLI works at document level when split into sentence pairs.
  ContraDoc (Li et al. 2024) and WikiContradict (Hou et al. 2024): even GPT-4
  is unreliable on implicit conflicts.
- Stance detection is defined against a topic or motion (SemEval-2016 Task 6;
  IBM Project Debater: Levy et al. 2014, Bar-Haim et al. 2017); a personal
  vault has no motion, so pairwise NLI is the target-free substitute.
  Detection can only surface oppositions the user has already written;
  generating an antithesis is a different product (a prompt).

Candidate models (sizes from the Hugging Face API):

| Model | Params | Licence | fp32 | int8 ONNX |
|---|---|---|---|---|
| cross-encoder/nli-deberta-v3-xsmall | 70.8M | Apache-2.0 | 283 MB | 87 MB |
| cross-encoder/nli-MiniLM2-L6-H768 | 82.1M | Apache-2.0 | 329 MB | 83 MB |
| cross-encoder/nli-deberta-v3-small | 142M | Apache-2.0 | 568 MB | 173 MB |
| cross-encoder/nli-deberta-v3-base | 184M | Apache-2.0 | 738 MB | 244 MB |
| MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli | 184M | MIT | 369 MB (fp16) | - |

## Prototype (4 vCPU Xeon, CPU only)

Hand-made pairs, fraction flagged contradiction (min over both directions, p >= 0.5):

| Model | Contradiction | Tension | Compatible | Paraphrase | ms/pair (1 / 2 threads) | Peak RAM |
|---|---|---|---|---|---|---|
| xsmall fp32 | 0.9 | 0.6 | 0 | 0 | 45 / 26 | 1.35 GB |
| MiniLM2-L6-H768 | 0.9 | 0.2 | 0 | 0.2 | 51 / 22-28 | 1.21 GB |
| deberta-v3-small | 0.8 | 0.8 | 0 | 0.2 | 91 / 39-50 | 1.78 GB |
| base-ANLI | 0.8 | 1.0 | 0 | 0 | 174 / 83-97 | 2.10 GB |
| xsmall int8 ONNX | 0.9 | 0.6 | 0 | 0 | 38 / 23 | 0.65 GB |

CPU inference was bitwise repeatable. All models missed a world-knowledge case.

Real vault: 1,249 claim sentences, top-10 cross-note neighbours at cosine >= 0.6
gave 1,105 pairs; NLI in both directions took 100 s (xsmall, 1 thread).
Top-25 precision (single annotator; P planted, C contradiction, T tension, F false):

| Ranker | P/C/T/F | Useful among non-planted |
|---|---|---|
| Random candidates | 0/0/2/23 | 8% |
| xsmall | 4/0/6/15 | 29% |
| MiniLM2 | 4/1/6/14 | 33% |
| base-ANLI | 5/1/8/11 | 45% |
| xsmall -> base cascade | 4/1/9/11 | 43% |
| base + deictic filter | 5/1/10/7 | ~55% |

Genuine finds included a real inconsistency ("Most geists completed within the
5-second timeout" vs "The per-geist timeout is 30s") and design tensions
("No caching initially - premature optimisation" vs "75% speedup from session
caching"). One planted pair was missed at retrieval (cosine 0.47): short
sentences that lean on context should be indexed with their note title or the
previous sentence.

## Tension, not contradiction, is the better target for a muse

Strict contradictions in a real vault are mostly stale-documentation errors
(linter territory); the interesting finds were tensions (8-10 per top 25 vs 1
contradiction). Usable signals: NLI score bands (strict: p >= 0.95 both ways;
tension: 0.5 <= p_min < 0.95 or one direction >= 0.8); temporal reversal (the
same pair from notes created far apart: "Earlier you wrote..., later...");
certainty vs hedge on the same subject; and *absence* of tension (a dense topic
of mutual entailments, an "echo chamber"), the only honest form of "blind spot".

## Proposed infrastructure

1. **Claim selection** (`content_extraction.py`): `strip_code` +
   `prose_sentences` + a `ClaimCandidateFilter` (declarative, 5-40 words, no
   URL/code/citation, not a question; drop or contextualise deictic openers);
   at most 8 sentences per note, chosen deterministically.
2. **Sentence embeddings**: the bundled MiniLM; table
   `claim_sentences(note_path, idx, sent_hash, text, emb float16, content_key)`,
   recomputed only when a note's `semantic_cache_key` changes.
3. **Candidates**: top k = 5 cross-note sentences at cosine >= 0.6 on the 384
   semantic dimensions (NumPy chunks or sqlite-vec).
4. **NLI scoring**: nli-deberta-v3-xsmall at a pinned revision via
   `CrossEncoder`; score A->B first and B->A only if A->B >= 0.5 (~1.3
   inferences per pair); optional base-ANLI re-score of pairs >= 0.5 (~10%).
5. **Cache**: `nli_pair_scores(model_id, hash_a, hash_b, p_contra_ab,
   p_contra_ba, p_entail_ab, p_entail_ba, cos)`, keyed by sentence hash so edits
   elsewhere in a note never invalidate scores; additive migration.
6. **Scheduling**: a session phase after `compute_embeddings`, budgeted by
   inference count (deterministic), changed/recent notes first; plus an
   optional `geistfabrik index-tensions` command for a full build.
7. **VaultContext API** (geists never touch SQL): `tension_pairs(...)`,
   `topic_agreement(note)`, `tension_index_status()`.
8. **Packaging**: `geistfabrik models fetch nli` downloads a pinned, sha256-
   checked revision (283 MB fp32 / 142 MB fp16), then runs offline; or a
   companion package with the 87 MB int8 ONNX (+ onnxruntime ~62 MB). Missing
   model: geists return `[]` with one hint; `GEISTFABRIK_OFFLINE` respected.
9. **Determinism**: scores are written once and reused; which pairs have been
   scored depends on budgeted history, so ordering must be documented.

## Cost

| | 1k notes | 10k notes |
|---|---|---|
| Claim sentences | ~8k | ~80k |
| Candidate pairs | 8k-24k | 80k-240k |
| NLI inferences (x1.3 lazy reverse) | 10k-31k | 104k-312k |
| First build, xsmall, 1 thread | 8-23 min | 1.3-3.9 h |
| First build, 2 threads / int8 ONNX | 4-13.5 min | 40 min-2.3 h |
| Sessions to full coverage at 4,000 inferences/session | 3-8 | 26-78 |
| Incremental, per changed note | ~2.5-4.5 s | same |
| Disk (sentences + score cache) | ~9 MB | ~90 MB |
| Model on disk | 283 MB fp32 / 142 MB fp16 / 87 MB int8 | same |
| Extra RAM while scoring | +0.5-0.9 GB (torch); 0.65 GB total (ONNX) | same |
| Extra wheel size | 0 if downloaded | same |
| Geist runtime (reads the cache) | milliseconds | milliseconds |

## Per-geist plan

- **columbo**: rebuild on `tension_pairs(min_contra=0.95, both_directions)`;
  quote both sentences; drop "I think you're lying" (~50% precision cannot
  support an accusation).
- **dialectic_triad**: rebuild on the tension band, preferring notes created
  90+ days apart; stop using `contrarian_to`.
- **antithesis_generator**: keep as a generation prompt that quotes one claim;
  optionally add "your vault may already argue the other side: [[B]]".
- **contradictor**: retire into antithesis_generator (same prompt, no quote).
- **blind_spot_detector**: retire as written (pairwise detection cannot see
  what is absent); optional echo-chamber replacement via `topic_agreement()`.
- **assumption_challenger**: keep; optionally pair with an NLI-scored neighbour.
- **`contrarian_to`**: re-document or rename (`most_distant`, keeping an alias)
  so no geist reads it as "opposite".
- Until the model ships, rebuilt geists return `[]` rather than falling back
  to embeddings or keywords; the current honest wording stays.

## Risks

Thin precision evidence (one annotator, a documentation-heavy vault: evaluate
on 2-3 real personal vaults first); recall gaps (context-dependent sentences,
different-vocabulary tensions, world knowledge); English only (mDeBERTa-xnli
is 279M parameters); long technical notes need the per-note claim cap.

Prototype scripts and data are not checked in; the session that produced this
report kept them in its scratchpad (`round3/opposition/`).
