"""Cluster labeling utilities for GeistFabrik.

Provides stateless functions for generating human-readable labels for
semantic clusters using c-TF-IDF and KeyBERT approaches with MMR filtering.

This module is extracted from stats.py to be shared between ClusterAnalyser
and stats.py, avoiding circular dependencies while maintaining single source
of truth for labeling logic.
"""

import sqlite3
from typing import Dict, List

import numpy as np
from sklearn.feature_extraction.text import (  # type: ignore[import-untyped]
    TfidfVectorizer,
)
from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
    cosine_similarity as sklearn_cosine,
)


def apply_mmr(
    terms: List[str],
    scores: np.ndarray,
    lambda_param: float = 0.5,
    k: int = 4,
) -> List[str]:
    """Apply Maximal Marginal Relevance to select diverse terms.

    MMR balances relevance (TF-IDF/KeyBERT score) with diversity
    (dissimilarity to already-selected terms) to prevent redundant keywords.

    Args:
        terms: Candidate terms
        scores: Relevance scores for each term
        lambda_param: Balance parameter (0.5 = equal weight)
        k: Number of terms to select

    Returns:
        List of k diverse terms
    """
    if len(terms) <= k:
        return terms

    # Simplified MMR using string overlap as diversity metric
    # This avoids needing to recompute embeddings for terms
    try:
        # Use dict for O(1) term index lookup instead of O(N) list.index()
        term_to_idx = {t: i for i, t in enumerate(terms)}

        # Use set for O(1) membership checks instead of O(N) list membership
        selected_set: set[str] = set()
        selected: List[str] = []

        while len(selected) < k and len(selected) < len(terms):
            remaining = [t for t in terms if t not in selected_set]
            if not remaining:
                break

            mmr_scores = []
            for term in remaining:
                # Relevance: TF-IDF/KeyBERT score (O(1) dict lookup)
                term_idx = term_to_idx[term]
                relevance = scores[term_idx]

                # Diversity: string overlap with selected terms
                if selected:
                    # Calculate word overlap with all selected terms
                    term_words = set(term.lower().split())
                    max_overlap = 0.0
                    for sel_term in selected:
                        sel_words = set(sel_term.lower().split())
                        if term_words and sel_words:
                            overlap = len(term_words & sel_words) / len(
                                term_words | sel_words
                            )
                            max_overlap = max(max_overlap, overlap)
                    diversity_penalty = max_overlap
                else:
                    diversity_penalty = 0.0

                # MMR formula: λ * relevance - (1-λ) * similarity
                mmr = lambda_param * relevance - (1 - lambda_param) * diversity_penalty
                mmr_scores.append(mmr)

            # Select term with highest MMR
            best_idx = int(np.argmax(mmr_scores))
            best_term = remaining[best_idx]
            selected.append(best_term)
            selected_set.add(best_term)

        return selected

    except Exception:
        # If MMR fails, fall back to top-k by score
        indices = np.argsort(scores)[-k:][::-1]
        return [terms[int(i)] for i in indices]


def label_tfidf(
    paths: List[str],
    labels: np.ndarray,
    db: sqlite3.Connection,
    n_terms: int = 4,
) -> Dict[int, str]:
    """Generate cluster labels using c-TF-IDF with MMR filtering.

    Applies class-based TF-IDF to extract keywords, then uses Maximal
    Marginal Relevance to select diverse, non-redundant terms.

    Args:
        paths: Note paths
        labels: Cluster labels from clustering algorithm
        db: Database connection to read note content
        n_terms: Number of terms to use in final label (after MMR)

    Returns:
        Dictionary mapping cluster_id to label string (comma-separated keywords)
    """
    cluster_labels: Dict[int, str] = {}

    # Load note titles/content for each cluster
    clusters: Dict[int, List[str]] = {}
    for i, label in enumerate(labels):
        if label == -1:
            continue
        if label not in clusters:
            clusters[label] = []

        # Get note title from path
        path = paths[i]
        cursor = db.execute("SELECT title, content FROM notes WHERE path = ?", (path,))
        row = cursor.fetchone()
        if row:
            title, content = row
            # Use title + first 200 chars of content
            text = f"{title} {content[:200]}"
            clusters[label].append(text)

    if not clusters:
        return {}

    # Concatenate all text per cluster
    cluster_texts = {cid: " ".join(texts) for cid, texts in clusters.items()}

    # Compute TF-IDF
    vectorizer = TfidfVectorizer(
        max_features=100, stop_words="english", ngram_range=(1, 2)
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(cluster_texts.values())
        feature_names = vectorizer.get_feature_names_out()

        # Extract top terms per cluster with MMR filtering
        for i, cluster_id in enumerate(cluster_texts.keys()):
            cluster_vector = tfidf_matrix[i].toarray()[0]

            # Extract top 8 candidates before MMR filtering
            n_candidates = min(8, len(feature_names))
            top_indices = cluster_vector.argsort()[-n_candidates:][::-1]
            candidate_terms = [feature_names[int(idx)] for idx in top_indices]
            candidate_scores = cluster_vector[top_indices]

            # Apply MMR to select diverse subset
            diverse_terms = apply_mmr(
                candidate_terms, candidate_scores, lambda_param=0.5, k=n_terms
            )

            cluster_labels[cluster_id] = ", ".join(diverse_terms)
    except Exception:
        # If TF-IDF fails, use simple fallback
        for cluster_id in clusters.keys():
            cluster_labels[cluster_id] = f"Cluster {cluster_id}"

    return cluster_labels


def label_keybert(
    paths: List[str],
    labels: np.ndarray,
    db: sqlite3.Connection,
    n_terms: int = 4,
) -> Dict[int, str]:
    """Generate cluster labels using KeyBERT approach with semantic embeddings.

    Uses semantic similarity between candidate phrases and cluster centroids
    to select more semantically coherent labels than frequency-based c-TF-IDF.

    Requires sentence-transformers model access (lazy-loads if needed).

    Args:
        paths: Note paths
        labels: Cluster labels from clustering algorithm
        db: Database connection to read note content
        n_terms: Number of terms to use in final label (after MMR)

    Returns:
        Dictionary mapping cluster_id to label string (comma-separated keywords)
    """
    from geistfabrik.embeddings import EmbeddingComputer

    cluster_labels: Dict[int, str] = {}

    # Load note titles/content for each cluster
    clusters: Dict[int, List[str]] = {}
    for i, label in enumerate(labels):
        if label == -1:
            continue
        if label not in clusters:
            clusters[label] = []

        # Get note title and content
        path = paths[i]
        cursor = db.execute("SELECT title, content FROM notes WHERE path = ?", (path,))
        row = cursor.fetchone()
        if row:
            title, content = row
            # Use title + first 200 chars of content
            text = f"{title} {content[:200]}"
            clusters[label].append(text)

    if not clusters:
        return {}

    # Get embedding computer (lazy-load model)
    try:
        computer = EmbeddingComputer()
    except Exception:
        # If model loading fails, fall back to simple labels for all clusters
        return {cid: f"Cluster {cid}" for cid in clusters.keys()}

    # Get cluster embeddings to compute centroids
    cluster_embeddings: Dict[int, List[np.ndarray]] = {}
    for cluster_id, texts in clusters.items():
        try:
            # Embed all texts in this cluster
            embeddings = computer.compute_batch_semantic(texts)
            cluster_embeddings[cluster_id] = list(embeddings)
        except Exception:
            # If embedding fails for this cluster, skip to simple label
            cluster_labels[cluster_id] = f"Cluster {cluster_id}"

    # Process each cluster
    for cluster_id, texts in clusters.items():
        # Skip if embedding failed earlier
        if cluster_id in cluster_labels:
            continue

        # Concatenate all text for n-gram extraction
        cluster_text = " ".join(texts)

        # Compute cluster centroid
        centroid = np.mean(cluster_embeddings[cluster_id], axis=0)

        # Extract candidate phrases using TF-IDF to get good candidates
        vectorizer = TfidfVectorizer(
            max_features=100, stop_words="english", ngram_range=(1, 3)
        )
        try:
            # Fit on this cluster's text only
            tfidf_matrix = vectorizer.fit_transform([cluster_text])
            feature_names = vectorizer.get_feature_names_out()
            cluster_vector = tfidf_matrix[0].toarray()[0]

            # Get top 16 candidates by TF-IDF (more than final to allow semantic filtering)
            n_candidates = min(16, len(feature_names))
            top_indices = cluster_vector.argsort()[-n_candidates:][::-1]
            candidate_terms = [feature_names[int(idx)] for idx in top_indices]

            # Skip if no candidates
            if not candidate_terms:
                cluster_labels[cluster_id] = f"Cluster {cluster_id}"
                continue

            # Embed candidate phrases
            candidate_embeddings = computer.compute_batch_semantic(candidate_terms)

            # Compute semantic similarity to cluster centroid
            centroid_2d = centroid.reshape(1, -1)
            similarities = sklearn_cosine(centroid_2d, candidate_embeddings)[0]

            # Apply MMR with semantic scores
            diverse_terms = apply_mmr(
                candidate_terms, similarities, lambda_param=0.5, k=n_terms
            )

            cluster_labels[cluster_id] = ", ".join(diverse_terms)

        except Exception:
            # If KeyBERT approach fails, use simple fallback
            cluster_labels[cluster_id] = f"Cluster {cluster_id}"

    return cluster_labels
