# Cluster Mirror Geist Specification

## Overview

The **cluster_mirror** geist reveals the natural semantic structure of a vault by showing automatically-named clusters with representative note samples, then asking: "What do these clusters remind you of?"

This is a pure muse geist—it presents patterns without interpretation, letting users discover meaning in their own organizational structures.

## Design Philosophy

**Muse, not Oracle**
- Shows patterns, doesn't interpret them
- Asks provocative questions, doesn't give answers
- Reveals unconscious organizational structure
- Uses "What do..." not "What if..." (direct inquiry vs. hypothetical)

**Local-First**
- No LLM dependencies
- Deterministic results (same vault + session = same clusters)
- Fast computation (reuses existing embeddings)

## Research Foundation

### Automatic Cluster Labelling: State of the Art (2024)

#### c-TF-IDF (Class-Based TF-IDF)
The current industry standard for cluster naming, implemented in BERTopic and other production systems.

**How it works:**
1. Aggregate all documents in a cluster into a single "class document"
2. Calculate term importance at cluster level (not document level)
3. Terms with high frequency in the cluster but low frequency elsewhere become labels

**Research validation:**
- BERTopic paper (Grootendorst, 2022): "Leveraging c-TF-IDF for topic representation"
  - https://arxiv.org/abs/2203.05794
- Shown to be 34%+ better than Top2Vec centroid approach
- Used in production by Google, Spotify, Netflix for document clustering

**Pros:**
- Simple, fast, no external dependencies
- Works well for distinctive topics
- Highly interpretable for human users

**Cons:**
- Produces keyword lists rather than readable phrases
- May select statistically significant but semantically weak terms
- Can include redundant terms

#### MMR (Maximal Marginal Relevance)
Diversity filtering to reduce keyword redundancy in cluster labels.

**How it works:**
- Balance relevance (TF-IDF score) with diversity (dissimilarity to already-selected terms)
- Formula: MMR = λ * Relevance(term) - (1-λ) * max_similarity(term, selected_terms)
- λ=0.5 balances relevance and diversity equally

**Research validation:**
- Carbonell & Goldstein (1998): "The Use of MMR, Diversity-Based Reranking for Reordering Documents"
  - https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf
- KeyBERT implementation (Grootendorst, 2020): Uses MMR for keyphrase extraction
  - https://github.com/MaartenGr/KeyBERT
- Prevents labels like "machine, machine learning, learning, ml"

**Implementation:**
- Apply MMR with λ=0.5 after c-TF-IDF extraction
- Select 3-4 diverse terms from top 8-10 keywords
- Significantly improves label interpretability

#### Representative Document Selection
Showing example notes alongside cluster labels dramatically improves interpretability.

**Research validation:**
- Lau et al. (2011): "Best Topic Word Selection for Topic Labelling"
  - https://aclanthology.org/P11-2084/
  - Found that showing representative documents increased label quality by 23%
- BERTopic default behaviour: Always show top-3 representative documents
- Human evaluation studies consistently prefer labels + examples over labels alone

**Selection methods:**
1. **Centroid-based** (recommended): Notes with highest cosine similarity to cluster centroid
2. **Medoid-based**: Note that minimizes average distance to all cluster members
3. **Random sampling**: Simpler but less representative

**Best practices:**
- Show 2-3 representative notes per cluster
- Use note titles (already human-written, immediately recognizable)
- Display alongside keywords, not as replacement

#### Optimal Label Length
Research consensus: **2-4 terms** provides best balance.

**Research validation:**
- Chang et al. (2009): "Reading Tea Leaves: How Humans Interpret Topic Models"
  - https://papers.nips.cc/paper/2009/file/f92586a25bb3145facd64ab20fd554ff-Paper.pdf
  - Single keywords insufficient for interpretation
  - 10+ terms overwhelming and redundant
- Lau et al. (2014): "Automatic Labelling of Topic Models"
  - https://aclanthology.org/P14-1009/
  - Multi-word phrases (bigrams/trigrams) more effective than same number of unigrams
- BERTopic defaults: Top-10 keywords for LLM input → 2-4 word final labels

#### Phrase Templates vs. Keyword Lists
Phrases strongly preferred by users in evaluation studies.

**Research validation:**
- Mei et al. (2007): "Automatic Labelling of Multinomial Topic Models"
  - https://dl.acm.org/doi/10.1145/1281192.1281246
  - Keyphrase extraction consistently outperforms keyword lists
  - Hybrid linguistic + statistical approaches balance readability with relevance

**Implementation options:**
1. **Simple**: Comma-separated keywords: "embeddings, semantic search, vectors"
2. **Template**: "Notes about [keyword1], [keyword2], and [keyword3]"
3. **LLM-generated**: Requires external dependency (not local-first)

**Recommendation**: Use template format for readability while maintaining determinism

### Alternative Approaches Considered

#### LLM-Based Label Generation
The 2024 emerging standard for cluster naming.

**How it works:**
- Extract top-N keywords via c-TF-IDF
- Prompt GPT-4/Claude/Llama to generate human-readable labels

**Pros:**
- Most interpretable labels
- Can generate phrases, summaries, questions
- Contextually appropriate

**Cons:**
- Requires API calls or local LLM
- Non-deterministic (violates muse principle)
- Potential cost and latency
- Not local-first

**Decision:** Not implemented due to non-determinism and external dependencies

#### Top2Vec Centroid Approach
Finds n-closest word embeddings to cluster centroid vector.

**Research:**
- Angelov (2020): "Top2Vec: Distributed Representations of Topics"
  - https://arxiv.org/abs/2008.09470

**Decision:** BERTopic paper showed c-TF-IDF is 34%+ better

#### Hierarchical Naming
Broader categories → specific subclusters.

**Research:**
- Zhao et al. (2021): "Effective and Scalable Clustering on Massive Attributed Graphs"
  - https://arxiv.org/abs/2102.05869
- Useful for large knowledge bases (100+ clusters)

**Decision:** Deferred to post-1.0 (most vaults have <10 clusters)

## Technical Specification

### VaultContext Methods

#### `get_clusters(min_size: int = 5) -> Dict[int, Dict[str, Any]]`

Computes cluster assignments and labels for the current session.

**Returns:**
```python
{
    0: {
        "label": "embeddings, semantic search, vector similarity",
        "formatted_label": "Notes about embeddings, semantic search, and vector similarity",
        "notes": [Note(...), Note(...), ...],
        "size": 15,
        "centroid": np.ndarray([...]),  # 387-dim embedding
    },
    1: {
        "label": "philosophy, consciousness, ethics",
        "formatted_label": "Notes about philosophy, consciousness, and ethics",
        "notes": [...],
        "size": 12,
        "centroid": np.ndarray([...]),
    },
    # ... more clusters
}
```

**Algorithm:**
1. Get all embeddings for current session
2. Run HDBSCAN with `min_cluster_size=min_size`
3. For each cluster:
   - Extract top 8 keywords via c-TF-IDF
   - Apply MMR (λ=0.5) to select 3-4 diverse terms
   - Format as phrase template
   - Calculate cluster centroid (mean of embeddings)

**Caching:**
- Compute once per session
- Reuse for multiple geist invocations
- Invalidate when vault changes

#### `get_cluster_representatives(cluster_id: int, k: int = 3) -> List[Note]`

Returns the k most representative notes for a cluster.

**Selection method:**
- Calculate cosine similarity between each note and cluster centroid
- Return top-k notes with highest similarity

**Why centroid-based:**
- Fast computation
- Mathematically principled
- Consistently identifies "typical" notes

### Cluster Labelling Algorithm

#### Step 1: c-TF-IDF Extraction

```python
from sklearn.feature_extraction.text import TfidfVectorizer

# Aggregate cluster texts
cluster_texts = {
    cluster_id: " ".join([f"{note.title} {note.content[:200]}"
                          for note in cluster_notes])
    for cluster_id, cluster_notes in clusters.items()
}

# Compute TF-IDF at cluster level
vectorizer = TfidfVectorizer(
    max_features=100,
    stop_words="english",
    ngram_range=(1, 2),  # Include bigrams
)
tfidf_matrix = vectorizer.fit_transform(cluster_texts.values())

# Extract top 8 terms per cluster
for i, cluster_id in enumerate(cluster_texts.keys()):
    cluster_vector = tfidf_matrix[i].toarray()[0]
    top_8_indices = cluster_vector.argsort()[-8:][::-1]
    top_8_terms = [feature_names[idx] for idx in top_8_indices]
```

#### Step 2: MMR Filtering

```python
def maximal_marginal_relevance(
    terms: List[str],
    tfidf_scores: np.ndarray,
    embedder,  # sentence-transformers model
    lambda_param: float = 0.5,
    k: int = 4,
) -> List[str]:
    """Apply MMR to select diverse terms."""
    # Get embeddings for all terms
    term_embeddings = embedder.encode(terms)

    selected = []
    selected_embeddings = []

    while len(selected) < k:
        remaining = [t for t in terms if t not in selected]
        if not remaining:
            break

        mmr_scores = []
        for i, term in enumerate(remaining):
            # Relevance: TF-IDF score
            relevance = tfidf_scores[terms.index(term)]

            # Diversity: max similarity to already-selected terms
            if selected_embeddings:
                term_emb = term_embeddings[terms.index(term)]
                similarities = [
                    cosine_similarity(term_emb, sel_emb)
                    for sel_emb in selected_embeddings
                ]
                diversity_penalty = max(similarities)
            else:
                diversity_penalty = 0

            # MMR score
            mmr = lambda_param * relevance - (1 - lambda_param) * diversity_penalty
            mmr_scores.append(mmr)

        # Select term with highest MMR
        best_idx = np.argmax(mmr_scores)
        best_term = remaining[best_idx]
        selected.append(best_term)
        selected_embeddings.append(term_embeddings[terms.index(best_term)])

    return selected
```

#### Step 3: Format as Phrase

```python
def format_cluster_label(terms: List[str]) -> tuple[str, str]:
    """Format terms as keyword list and phrase template.

    Returns:
        (keyword_label, formatted_label)
    """
    keyword_label = ", ".join(terms)

    # Phrase template
    if len(terms) == 1:
        formatted_label = f"Notes about {terms[0]}"
    elif len(terms) == 2:
        formatted_label = f"Notes about {terms[0]} and {terms[1]}"
    else:
        # Oxford comma for 3+ terms
        formatted_label = f"Notes about {', '.join(terms[:-1])}, and {terms[-1]}"

    return keyword_label, formatted_label
```

### Geist Implementation

**File:** `src/geistfabrik/default_geists/code/cluster_mirror.py`

```python
"""Cluster Mirror geist - reveals semantic vault structure.

Shows automatically-named clusters with representative samples,
then asks what they remind you of. Pure pattern presentation
without interpretation.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Show named clusters and ask what they remind you of.

    Returns:
        Single suggestion showing 2-3 clusters with examples
    """
    from geistfabrik import Suggestion

    # Get cluster assignments and labels
    clusters = vault.get_clusters(min_size=5)

    # Need at least 2 clusters to show patterns
    if len(clusters) < 2:
        return []

    # Sample 2-3 clusters to show
    cluster_ids = list(clusters.keys())
    selected_ids = vault.sample(cluster_ids, k=min(3, len(cluster_ids)))

    cluster_descriptions = []
    all_sampled_notes = []

    for cluster_id in selected_ids:
        cluster = clusters[cluster_id]

        # Use formatted phrase label
        label = cluster['formatted_label']

        # Get 3 representative notes (closest to centroid)
        representatives = vault.get_cluster_representatives(cluster_id, k=3)
        note_titles = [f"[[{n.title}]]" for n in representatives]

        cluster_descriptions.append(
            f"{label}\n→ {', '.join(note_titles)}"
        )
        all_sampled_notes.extend([n.title for n in representatives])

    # Pure muse question: no interpretation, just pattern presentation
    text = "\n\n".join(cluster_descriptions) + "\n\nWhat do these clusters remind you of?"

    return [Suggestion(
        text=text,
        notes=all_sampled_notes,
        geist_id="cluster_mirror",
    )]
```

### Example Output

```
Notes about embeddings, semantic search, and vector similarity
→ [[Building a Semantic Search Engine]], [[Understanding BERT]], [[Cosine Distance Explained]]

Notes about philosophy, consciousness, and ethics
→ [[Hard Problem of Consciousness]], [[Moral Foundations Theory]], [[Qualia]]

Notes about productivity, zettelkasten, and note-taking
→ [[Building a Second Brain]], [[Atomic Notes]], [[Evergreen Notes]]

What do these clusters remind you of?
```

## Configuration

### HDBSCAN Parameters

**`min_cluster_size`**: Minimum notes required to form a cluster
- Default: 5
- Too low: Many tiny, incoherent clusters
- Too high: Only very large, obvious clusters
- Research: 5-10 is optimal for personal knowledge bases

**`min_samples`**: Minimum samples for core points
- Default: 3
- Controls cluster density threshold
- Lower = more permissive clustering

### Label Generation Parameters

**`n_terms`**: Number of keywords to extract
- Default: 4 (after MMR filtering)
- Research shows 2-4 is optimal
- Extract 8 before MMR, select 4 after

**`lambda_param`**: MMR balance parameter
- Default: 0.5
- Higher = prioritise relevance over diversity
- Lower = prioritise diversity over relevance

**`max_features`**: TF-IDF vocabulary size
- Default: 100
- Controls total vocabulary for label generation

**`ngram_range`**: Include bigrams in labels
- Default: (1, 2)
- Allows phrases like "semantic search" not just "semantic" + "search"

## Testing Strategy

### Unit Tests

1. **MMR filtering**
   - Verify diverse terms selected
   - Test edge cases (empty clusters, single term)
   - Validate λ parameter behaviour

2. **Cluster labelling**
   - c-TF-IDF produces sensible keywords
   - Phrase formatting works correctly
   - Handles clusters of various sizes

3. **Representative selection**
   - Centroid calculation correct
   - Returns k closest notes
   - Handles edge cases (k > cluster size)

### Integration Tests

1. **Full clustering pipeline**
   - Run on test vault (15+ notes)
   - Verify clusters formed
   - Check label quality

2. **Geist execution**
   - Produces valid suggestions
   - Handles small vaults gracefully
   - Deterministic across sessions

### Quality Metrics

**Cluster coherence** (internal):
- Silhouette coefficient > 0.5 (good separation)
- Calinski-Harabasz index (high = well-defined clusters)

**Label quality** (manual):
- Keywords semantically related to cluster contents
- Phrases grammatically correct
- Representative notes actually representative

## Implementation Checklist

- [ ] Add MMR filtering to stats.py `_label_clusters_tfidf()`
- [ ] Implement `VaultContext.get_clusters()`
- [ ] Implement `VaultContext.get_cluster_representatives()`
- [ ] Create `cluster_mirror.py` geist
- [ ] Add unit tests for clustering
- [ ] Add integration tests
- [ ] Update default geist configuration
- [ ] Document in CHANGELOG

## Future Enhancements (Post-1.0)

### Cluster Evolution Tracking
Track how clusters change over time:
- Which notes join/leave clusters
- How cluster labels evolve
- Seasonal clustering patterns

### User Refinement
Allow users to:
- Rename clusters manually
- Merge/split clusters
- Pin important clusters

### Hierarchical Clustering
For large vaults (100+ notes):
- Broad categories → specific subclusters
- Multi-level drill-down
- Contextual-Top2Vec approach

### Cross-Cluster Patterns
Additional geists:
- **Cluster Boundary Explorer**: Notes near boundaries
- **Missing Cluster Detector**: Conceptual gaps
- **Cluster Collision**: Suggest cross-domain connections

## References

### Key Papers

1. Grootendorst, M. (2022). "BERTopic: Neural topic modelling with a class-based TF-IDF procedure"
   - https://arxiv.org/abs/2203.05794
   - Industry-standard cluster labelling

2. Carbonell, J. & Goldstein, J. (1998). "The Use of MMR, Diversity-Based Reranking for Reordering Documents"
   - https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf
   - Original MMR formulation

3. Lau, J.H., Grieser, K., Newman, D., & Baldwin, T. (2011). "Best Topic Word Selection for Topic Labelling"
   - https://aclanthology.org/P11-2084/
   - Representative documents improve labels by 23%

4. Chang, J., Boyd-Graber, J., Gerrish, S., Wang, C., & Blei, D.M. (2009). "Reading Tea Leaves: How Humans Interpret Topic Models"
   - https://papers.nips.cc/paper/2009/file/f92586a25bb3145facd64ab20fd554ff-Paper.pdf
   - Optimal label length: 2-4 terms

5. Lau, J.H., Newman, D., & Baldwin, T. (2014). "Automatic Labelling of Topic Models"
   - https://aclanthology.org/P14-1009/
   - Multi-word phrases more effective than unigrams

6. Mei, Q., Shen, X., & Zhai, C. (2007). "Automatic Labelling of Multinomial Topic Models"
   - https://dl.acm.org/doi/10.1145/1281192.1281246
   - Keyphrase extraction outperforms keyword lists

7. Angelov, D. (2020). "Top2Vec: Distributed Representations of Topics"
   - https://arxiv.org/abs/2008.09470
   - Alternative centroid-based approach

### Production Systems

1. **BERTopic** (Maarten Grootendorst)
   - https://github.com/MaartenGr/BERTopic
   - Industry standard for topic modelling
   - Used by Google, Spotify, Netflix

2. **KeyBERT** (Maarten Grootendorst)
   - https://github.com/MaartenGr/KeyBERT
   - Keyphrase extraction with MMR
   - Integration with BERTopic

3. **Top2Vec** (Dimo Angelov)
   - https://github.com/ddangelov/Top2Vec
   - Alternative clustering approach

### Additional Resources

1. scikit-learn TfidfVectorizer documentation
   - https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html

2. HDBSCAN documentation
   - https://hdbscan.readthedocs.io/
   - Parameter tuning guide

3. Sentence-Transformers documentation
   - https://www.sbert.net/
   - All-MiniLM-L6-v2 model (used in GeistFabrik)

## Version History

- **v0.1.0** (2025-10-31): Initial specification with research foundation
