# Cluster Naming Research: Academic Literature Review

**Date**: 2025-11-08
**Context**: Improving cluster names in the `cluster_mirror` geist
**Current Method**: c-TF-IDF with MMR diversity filtering

## Executive Summary

Research into academic literature (2018-2025) reveals several promising techniques for improving automatic cluster naming beyond basic c-TF-IDF. The **recommended approach** is a hybrid system combining:
1. **BM25-weighted c-TF-IDF** for candidate term extraction
2. **KeyBERT** for semantic ranking using existing embeddings
3. **MMR filtering** for diversity (already implemented)

This approach leverages GeistFabrik's existing embedding infrastructure while maintaining the local-first, deterministic philosophy.

## Current Implementation

**Location**: `src/geistfabrik/stats.py:1014-1084` (`_label_clusters_tfidf`)

**Current pipeline**:
1. Concatenate cluster texts: `title + content[:200]`
2. TF-IDF vectorization with bigrams: `ngram_range=(1, 2)`
3. Extract top 8 candidates per cluster
4. Apply MMR with string overlap for diversity
5. Select top 4 diverse terms
6. Format as: "Notes about X, Y, and Z"

**Strengths**:
- Fast and deterministic
- No external dependencies beyond sklearn
- Produces readable labels
- MMR diversity prevents redundancy

**Limitations**:
- Frequency-based (not semantic)
- Doesn't leverage computed embeddings
- String overlap is crude diversity metric
- May miss semantically central terms

## Research Findings: 5 Promising Techniques

### 1. KeyBERT (Embedding-Based Keyphrase Extraction) ⭐

**Description**: Ranks candidate phrases by semantic similarity to cluster centroid using embeddings.

**How it works**:
```
1. Compute cluster centroid (mean of document embeddings)
2. Extract candidate N-grams from cluster texts
3. Embed each candidate phrase using sentence transformer
4. Rank phrases by cosine similarity to centroid
5. Apply MMR for diversity
```

**Academic Foundation**:
- Grootendorst, M. (2020). "KeyBERT: Minimal keyword extraction with BERT"
- GitHub: https://github.com/MaartenGr/KeyBERT

**Pros**:
- ✅ Uses semantic similarity (not just frequency)
- ✅ Leverages embeddings already computed for clustering
- ✅ Works with transformer-based models (like all-MiniLM-L6-v2)
- ✅ Natural multi-word phrase extraction
- ✅ Integrates with existing MMR filtering
- ✅ Local-first (uses existing embedding model)

**Cons**:
- Requires embedding candidate phrases (computational cost)
- May select semantically similar but less specific terms
- Needs post-processing for phrase quality

**Implementation Difficulty**: Easy
**Dependencies**: `keybert` library or implement core logic
**Local-first**: ✅ Yes - uses existing embedding model

**Fit for GeistFabrik**: ⭐⭐⭐⭐⭐ Excellent - leverages existing infrastructure

---

### 2. BM25-Weighted c-TF-IDF

**Description**: Enhances TF-IDF with BM25 term saturation to handle document length variation.

**How it works**:
```
Replace raw TF with BM25 saturation:
BM25(tf) = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_doc_len)))

Parameters:
- k1 = 1.5 (term saturation)
- b = 0.75 (length normalisation)
```

**Academic Foundation**:
- Robertson, S., Zaragoza, H. (2009). "The Probabilistic Relevance Framework: BM25 and Beyond"
- Kocadağlı, O. (2011). "Improving document clustering using Okapi BM25"

**Pros**:
- ✅ Probabilistic foundation
- ✅ Handles document length variation
- ✅ Prevents over-weighting common terms
- ✅ Drop-in replacement for TF-IDF
- ✅ No new dependencies

**Cons**:
- Still frequency-based (not semantic)
- Requires parameter tuning (k1, b)
- Marginal improvements over c-TF-IDF in some cases

**Implementation Difficulty**: Easy
**Dependencies**: None (sklearn or BERTopic)
**Local-first**: ✅ Yes

**Fit for GeistFabrik**: ⭐⭐⭐⭐ Good - easy upgrade with moderate gains

---

### 3. Centroid-Based Labelling (Top2Vec Approach)

**Description**: Find nearest vocabulary words to cluster centroid in embedding space.

**How it works**:
```
1. Compute cluster centroid: mean(all_doc_embeddings)
2. Pre-compute word embeddings for vocabulary
3. Find k-nearest words using cosine similarity
4. Return top words as cluster label
```

**Academic Foundation**:
- Angelov, D. (2020). "Top2Vec: Distributed Representations of Topics"
- GitHub: https://github.com/ddangelov/Top2Vec

**Pros**:
- ✅ Direct use of embedding space geometry
- ✅ Semantically coherent with cluster structure
- ✅ Very fast once embeddings computed
- ✅ Natural fit with HDBSCAN clusters
- ✅ Can identify synonyms/related concepts

**Cons**:
- Limited to single words (unless phrase embeddings pre-computed)
- May select abstract/general terms near centroid
- Requires vocabulary of candidate words

**Implementation Difficulty**: Medium
**Dependencies**: None beyond existing embedding model
**Local-first**: ✅ Yes

**Fit for GeistFabrik**: ⭐⭐⭐⭐ Good - fast and semantically grounded

---

### 4. YAKE (Yet Another Keyword Extractor)

**Description**: Unsupervised statistical method using multiple local features for keyphrase extraction.

**How it works**:
```
Combines 5 statistical features per term:
1. Casing (uppercase/title case preference)
2. Word position (earlier = more important)
3. Word frequency
4. Context (relation to neighbours)
5. Term dispersion across documents

→ Produces composite score for multi-word phrases
```

**Academic Foundation**:
- Campos, R. et al. (2020). "YAKE! Keyword Extraction from Single Documents using Multiple Local Features." Information Sciences, Vol 509, pp 257-289

**Pros**:
- ✅ No training required
- ✅ Language and domain independent
- ✅ Excellent multi-word phrase extraction
- ✅ Fast execution
- ✅ Works on any cluster size

**Cons**:
- Doesn't leverage semantic embeddings
- May over-weight positional features
- Less effective on very short texts

**Implementation Difficulty**: Easy
**Dependencies**: `yake` library (lightweight)
**Local-first**: ✅ Yes

**Fit for GeistFabrik**: ⭐⭐⭐ Moderate - good for phrase extraction

---

### 5. LLM-Based Cluster Naming (Local Small Models)

**Description**: Use local language models to generate human-readable cluster names from representative documents.

**How it works**:
```
1. Extract representative docs/keywords from cluster
2. Prompt local LLM with few-shot examples:
   "Given these documents, generate a descriptive label (2-5 words)"
3. Use in-context learning capabilities
4. Generate creative, human-readable names
```

**Academic Foundation**:
- Vicinanza, P. et al. (2024). "Large Language Models Enable Few-Shot Clustering." TACL
- Zhang, Y. et al. (2024). "Text Clustering as Classification with LLMs." arXiv:2410.00927
- Wei, X. et al. (2024). "Evaluation of Text Cluster Naming with Generative LLMs." Journal of Data Science

**Pros**:
- ✅ Most human-readable labels
- ✅ Creative, descriptive names
- ✅ Leverages semantic understanding
- ✅ Recent models (Ministral 3B/8B, Llama 3.2) run locally

**Cons**:
- Requires additional inference (slower)
- Non-deterministic without fixed seeds
- Model size (3-8GB for small models)
- Complex integration
- May hallucinate labels not grounded in cluster

**Implementation Difficulty**: Hard
**Dependencies**: `llama-cpp-python`, `transformers`, or `ollama`
**Local-first**: ⚠️ Partial - requires model download (3-8GB), then fully local

**Fit for GeistFabrik**: ⭐⭐ Low - breaks deterministic philosophy, high complexity

---

## Comparative Analysis

| Technique | Difficulty | Dependencies | Speed | Quality | Multi-word | Semantic | Local |
|-----------|-----------|--------------|-------|---------|------------|----------|-------|
| **c-TF-IDF (current)** | Easy | sklearn | ⚡⚡⚡ | ★★★ | ✓ | ✗ | ✅ |
| **BM25 c-TF-IDF** | Easy | sklearn | ⚡⚡⚡ | ★★★½ | ✓ | ✗ | ✅ |
| **KeyBERT** | Easy | keybert | ⚡⚡ | ★★★★ | ✓✓ | ✅ | ✅ |
| **Centroid-based** | Medium | None | ⚡⚡⚡ | ★★★ | ✗ | ✅ | ✅ |
| **YAKE** | Easy | yake | ⚡⚡⚡ | ★★★½ | ✓✓ | ✗ | ✅ |
| **LLM-based** | Hard | LLM runtime | ⚡ | ★★★★★ | ✓✓✓ | ✅ | ⚠️ |

---

## Quality Evaluation Metrics

To measure cluster label quality, academic literature recommends:

### 1. UMass Coherence (Recommended)
Measures how often top label words co-occur in cluster documents.

```
Formula: Σ log((D(wi, wj) + 1) / D(wj))
where D(wi, wj) = # documents containing both wi and wj

Higher score = better coherence
```

### 2. NPMI (Normalised Pointwise Mutual Information)
Measures word association strength, less affected by rare words.

```
Range: [-1, 1]
Higher = better association
```

### 3. Human Evaluation
Gold standard but not scalable - use for validation only.

**Recommendation**: Implement UMass coherence for automated A/B testing.

---

## Recommended Implementation Strategy

### Phase 1: Hybrid Approach (Immediate)

**Combine multiple techniques for best results**:

```python
# Pipeline:
1. Use BM25-weighted c-TF-IDF to identify candidate terms (fast, broad coverage)
2. Use KeyBERT to rank candidates by semantic similarity to centroid (quality filter)
3. Use MMR for diversity (already implemented)
4. Compute UMass coherence to validate label quality
```

**Why this works**:
- BM25 c-TF-IDF: Better term weighting than vanilla TF-IDF
- KeyBERT: Semantic coherence with cluster structure
- MMR: Prevents redundant keywords
- UMass: Automated quality measurement

**Implementation priority**:
1. ✅ **KeyBERT integration** (highest quality gain, leverages existing embeddings)
2. ✅ **BM25 c-TF-IDF** (easy upgrade, zero new dependencies)
3. ✅ **UMass coherence** (quality validation)

### Phase 2: Future Enhancements

- **Centroid-based labelling** as alternative representation
- **YAKE** for improved multi-word phrase extraction
- **Evaluate local LLM approach** (research spike)

---

## Implementation Details: KeyBERT Integration

### Current Architecture Opportunity

GeistFabrik already:
- ✅ Computes cluster centroids (`vault_context.py:639`)
- ✅ Has embeddings loaded in memory
- ✅ Uses `all-MiniLM-L6-v2` sentence transformer
- ✅ Implements MMR diversity filtering

### Proposed Enhancement

**Location**: `src/geistfabrik/stats.py:_label_clusters_tfidf()`

**New pipeline**:
```python
def _label_clusters_keybert(
    self,
    cluster_id: int,
    cluster_texts: List[str],
    centroid: np.ndarray,
    n_terms: int = 4
) -> str:
    """Generate cluster label using KeyBERT approach.

    1. Extract candidate n-grams from cluster texts
    2. Embed candidates using sentence transformer
    3. Rank by cosine similarity to cluster centroid
    4. Apply MMR for diversity
    5. Return top n_terms as label
    """
    # Extract candidate phrases (1-3 grams)
    candidates = self._extract_candidate_phrases(cluster_texts)

    # Embed candidates
    candidate_embeddings = self._embed_phrases(candidates)

    # Compute similarity to centroid
    similarities = cosine_similarity([centroid], candidate_embeddings)[0]

    # Apply MMR for diversity
    diverse_terms = self._apply_mmr_filtering(
        candidates, similarities, lambda_param=0.5, k=n_terms
    )

    return ", ".join(diverse_terms)
```

**Key changes**:
- Use centroid (already computed) as semantic anchor
- Embed candidate phrases using existing model
- Rank by semantic similarity (not just frequency)
- Keep existing MMR diversity filtering

**Dependencies**:
- Option 1: Install `keybert` library (recommended)
- Option 2: Implement core logic using existing `sentence-transformers`

---

## References

### Key Papers

1. **KeyBERT**:
   - Grootendorst, M. (2020). KeyBERT: Minimal keyword extraction with BERT
   - GitHub: https://github.com/MaartenGr/KeyBERT

2. **BM25 & c-TF-IDF**:
   - Robertson, S., Zaragoza, H. (2009). "The Probabilistic Relevance Framework: BM25 and Beyond"
   - Grootendorst, M. (2022). "BERTopic: Neural topic modelling with a class-based TF-IDF procedure." arXiv:2203.05794

3. **YAKE**:
   - Campos, R. et al. (2020). "YAKE! Keyword Extraction from Single Documents using Multiple Local Features." Information Sciences, Vol 509, pp 257-289

4. **Top2Vec**:
   - Angelov, D. (2020). "Top2Vec: Distributed Representations of Topics." arXiv:2008.09470

5. **LLM Cluster Labelling**:
   - Vicinanza, P. et al. (2024). "Large Language Models Enable Few-Shot Clustering." TACL
   - Zhang, Y. et al. (2024). "Text Clustering as Classification with LLMs." arXiv:2410.00927
   - Wei, X. et al. (2024). "Evaluation of Text Cluster Naming with Generative LLMs." Journal of Data Science

6. **Coherence Metrics**:
   - Röder, M. et al. (2015). "Exploring the Space of Topic Coherence Measures"
   - Aletras, N., Stevenson, M. (2013). "Evaluating Topic Coherence Using Distributional Semantics"

---

## Conclusion

**Recommended next steps**:
1. Implement KeyBERT-based labelling (highest ROI)
2. Add UMass coherence metrics for evaluation
3. Run A/B comparison on test vault
4. Consider BM25 c-TF-IDF as fallback/complement

**Expected outcomes**:
- More semantically coherent cluster labels
- Better alignment with cluster structure
- Maintained local-first, deterministic philosophy
- Leveraged existing embedding infrastructure

**Success metrics**:
- Higher UMass coherence scores
- More meaningful labels in user testing
- Maintained performance (< 2x slowdown)
- Zero new external API dependencies
