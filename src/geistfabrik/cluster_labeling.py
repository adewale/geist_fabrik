"""Cluster labeling utilities for GeistFabrik.

Provides stateless functions for generating human-readable labels for
semantic clusters using c-TF-IDF and KeyBERT approaches with MMR filtering.

This module is extracted from stats.py to be shared between ClusterAnalyser
and stats.py, avoiding circular dependencies while maintaining single source
of truth for labeling logic.
"""

import hashlib
import logging
import re
import sqlite3
import weakref
from datetime import date
from typing import Protocol

import numpy as np
from sklearn.feature_extraction.text import (  # type: ignore[import-untyped]
    TfidfVectorizer,
)
from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
    cosine_similarity as sklearn_cosine,
)

from geistfabrik.markdown_parser import (
    INLINE_CODE_PATTERN,
    markdown_prose_lines,
    parse_frontmatter,
)

logger = logging.getLogger(__name__)

# Label candidates are words of two or more letters: no numbers (dates such
# as "2023 09"), no underscores or code identifiers.
_WORD_TOKEN_PATTERN = r"(?u)\b[^\W\d_]{2,}\b"

#: Characters of note body (after code removal) that a label text keeps.
_LABEL_BODY_CHARS = 200

# --- Frontmatter strip without YAML parsing -------------------------------
#
# parse_frontmatter() runs a full, bounded YAML parse only to decide whether
# the leading "---" block is metadata (stripped) or ordinary Markdown (kept:
# invalid YAML, a non-mapping, or non-string keys). That parse was most of
# the cost of labelling a cluster. _strip_frontmatter() decides the common
# shapes of real frontmatter -- "key: value" lines, "- item" lists under a
# key, inline [a, b] lists, quoted strings, integers and dates -- with a
# conservative recogniser that only accepts blocks PyYAML is certain to load
# as a string-keyed mapping, and hands anything else to parse_frontmatter()
# itself. The body is therefore always the one parse_frontmatter() returns.

# Every character PyYAML's reader accepts, minus tab and the YAML 1.1 line
# breaks NEL (\x85), LS and PS, and BOM (\ufeff), which complicate scanning.
_YAML_SAFE_CHARS = (
    "\x20-\x7e\xa0-\u2027\u202a-\ud7ff\ue000-\ufefe\uff00-\ufffd\U00010000-\U0010ffff"
)
_SAFE_LINE = re.compile(f"[{_YAML_SAFE_CHARS}]*")
_FM_KEY_LINE = re.compile(r"([A-Za-z_][A-Za-z0-9_-]{0,63}):(?: +(.*?))? *")
_FM_ITEM_LINE = re.compile(r"( *)-(?: +(.*?))? *")
_FM_COMMENT_LINE = re.compile(r" *(?:#.*)?")
# Keys PyYAML would load as booleans or None (no longer string keys).
_FM_NON_STRING_KEYS = frozenset({"yes", "no", "true", "false", "on", "off", "null", "y", "n"})
_FM_INT = re.compile(r"[0-9]{1,30}")
_FM_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_FM_DOUBLE_QUOTED = re.compile(r'"[^"\\]*"')
_FM_SINGLE_QUOTED = re.compile(r"'[^']*'")
_FM_FLOW_ITEM = re.compile(r'(?:[A-Za-z_][A-Za-z0-9_ ./-]*|"[^"\\]*"|\'[^\']*\')')
_FM_MAX_CHARS = 100_000  # far below the loader's 1 MiB bound
_FM_MAX_NODES = 10_000  # half the loader's node bound
_FM_MAX_FLOW_ITEMS = 200
# Every character an int, float or timestamp scalar can contain.
_FM_NUMERIC_CHARS = frozenset("0123456789abcdefABCDEFxXoObB_.:+-eEtTzZ ")


def _plain_text_value(value: str) -> bool:
    """A plain scalar that always loads as a string and never fails to parse.

    It starts with a letter or "_" (never a YAML indicator), or with a digit
    but contains a character no number or timestamp can (as in "0🌲").
    """
    # ": " (or a trailing ":") would start a nested mapping, an error here;
    # " #" starts a comment, so any "#" is left to the full parser.
    if "#" in value or ": " in value or value.endswith(":"):
        return False
    first = value[0]
    if first.isalpha() or first == "_":
        return True
    if "0" <= first <= "9":
        return any(character not in _FM_NUMERIC_CHARS for character in value)
    return False


def _value_nodes(value: str | None) -> int | None:
    """YAML nodes for one value if it is certainly loadable, else None."""
    if value is None or value == "":
        return 1  # null
    if _plain_text_value(value) or _FM_INT.fullmatch(value):
        return 1
    if _FM_DOUBLE_QUOTED.fullmatch(value) or _FM_SINGLE_QUOTED.fullmatch(value):
        return 1
    date_match = _FM_DATE.fullmatch(value)
    if date_match:
        try:
            date(*(int(part) for part in date_match.groups()))
        except ValueError:
            return None  # loader raises on an impossible date; let it
        return 1
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return 1
        items = [item.strip() for item in inner.split(",")]
        if len(items) > _FM_MAX_FLOW_ITEMS:
            return None
        if all(_FM_FLOW_ITEM.fullmatch(item) for item in items):
            return 1 + len(items)
    return None


def _is_simple_mapping(lines: list[str]) -> bool:
    """True only if PyYAML certainly loads these lines as a str-keyed mapping
    (or as nothing at all: blank and comment lines only)."""
    if sum(len(line) + 1 for line in lines) > _FM_MAX_CHARS:
        return False
    nodes = 1
    # None: no key yet; "value": last key had a value; "open": last key had
    # none, so "- item" lines may follow; an int: indent of the current items
    items_state: str | int | None = None
    for raw in lines:
        line = raw[:-1] if raw.endswith("\r") else raw
        if not _SAFE_LINE.fullmatch(line):
            return False
        if _FM_COMMENT_LINE.fullmatch(line):
            continue
        key_match = _FM_KEY_LINE.fullmatch(line)
        if key_match:
            if key_match[1].lower() in _FM_NON_STRING_KEYS:
                return False
            value_nodes = _value_nodes(key_match[2])
            if value_nodes is None:
                return False
            nodes += 1 + value_nodes
            items_state = "value" if key_match[2] else "open"
            continue
        item_match = _FM_ITEM_LINE.fullmatch(line)
        if item_match and items_state is not None and items_state != "value":
            indent = len(item_match[1])
            if items_state == "open":
                items_state = indent
                nodes += 1  # the sequence
            elif items_state != indent:
                return False
            value_nodes = _value_nodes(item_match[2])
            if value_nodes is None:
                return False
            nodes += value_nodes
            continue
        return False
    return nodes <= _FM_MAX_NODES


def _strip_frontmatter(content: str) -> str:
    """parse_frontmatter(content)[1], usually without parsing any YAML."""
    if not content.startswith("---"):
        return content
    lines = content.split("\n")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return content
    if _is_simple_mapping(lines[1:end_idx]):
        return "\n".join(lines[end_idx + 1 :])
    return parse_frontmatter(content)[1]


def _label_text(title: str, content: str) -> str:
    """Title plus the opening of the note body, for cluster labelling.

    Frontmatter and code are not what a note is about; labelled from raw
    content, clusters were named after YAML keys and dates.

    Only the first 200 characters of code-free prose are kept, so prose
    lines are read only until that many are collected. (Inline code never
    spans a line, so removing it line by line equals removing it from the
    joined text.)
    """
    body = _strip_frontmatter(content)
    kept: list[str] = []
    length = -1  # joined length: one "\n" between consecutive lines
    for _, line in markdown_prose_lines(body):
        cleaned = INLINE_CODE_PATTERN.sub(" ", line)
        kept.append(cleaned)
        length += len(cleaned) + 1
        if length >= _LABEL_BODY_CHARS:
            break
    return f"{title} {chr(10).join(kept)[:_LABEL_BODY_CHARS]}"


def apply_mmr(
    terms: list[str],
    scores: np.ndarray,
    lambda_param: float = 0.5,
    k: int = 4,
) -> list[str]:
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
        selected: list[str] = []

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
                            overlap = len(term_words & sel_words) / len(term_words | sel_words)
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
        logger.debug(
            "MMR filtering failed, falling back to top-k by score",
            exc_info=True,
        )
        indices = np.argsort(scores)[-k:][::-1]
        return [terms[int(i)] for i in indices]


def label_tfidf(
    paths: list[str],
    labels: np.ndarray,
    db: sqlite3.Connection,
    n_terms: int = 4,
) -> dict[int, str]:
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
    cluster_labels: dict[int, str] = {}

    # Load note titles/content for each cluster
    clusters: dict[int, list[str]] = {}
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
            text = _label_text(title, content)
            clusters[label].append(text)

    if not clusters:
        return {}

    # Concatenate all text per cluster
    cluster_texts = {cid: " ".join(texts) for cid, texts in clusters.items()}

    # Compute TF-IDF
    vectorizer = TfidfVectorizer(
        max_features=100,
        stop_words="english",
        ngram_range=(1, 2),
        token_pattern=_WORD_TOKEN_PATTERN,
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
        logger.debug(
            "TF-IDF labeling failed, using simple fallback",
            exc_info=True,
        )
        for cluster_id in clusters.keys():
            cluster_labels[cluster_id] = f"Cluster {cluster_id}"

    return cluster_labels


class TextEncoder(Protocol):
    """What KeyBERT labelling needs of an embedding computer."""

    def compute_batch_semantic(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Embed each text (one row per text)."""
        ...


# Label-text embeddings, keyed by the SHA-256 of the text, held per encoder
# (so per model) and dropped with it. Each labelling run keeps exactly the
# texts it used, so an encoder reused across sessions re-encodes only notes
# whose label text changed.
_LABEL_TEXT_EMBEDDINGS: "weakref.WeakKeyDictionary[TextEncoder, dict[str, np.ndarray]]" = (
    weakref.WeakKeyDictionary()
)


def _text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _embed_label_texts(
    computer: TextEncoder, texts: list[str], cache: dict[str, np.ndarray]
) -> list[np.ndarray]:
    """Embeddings for texts, encoding only those not already in cache.

    When nothing is cached the encode call is exactly the uncached one
    (same texts, same order), so cold results are unchanged.
    """
    keys = [_text_key(text) for text in texts]
    missing = [text for text, key in zip(texts, keys) if key not in cache]
    if missing:
        encoded = computer.compute_batch_semantic(missing)
        for text, embedding in zip(missing, encoded):
            cache[_text_key(text)] = embedding
    return [cache[key] for key in keys]


def label_keybert(
    paths: list[str],
    labels: np.ndarray,
    db: sqlite3.Connection,
    n_terms: int = 4,
    computer: TextEncoder | None = None,
) -> dict[int, str]:
    """Generate cluster labels using KeyBERT approach with semantic embeddings.

    Uses semantic similarity between candidate phrases and cluster centroids
    to select more semantically coherent labels than frequency-based c-TF-IDF.

    Requires sentence-transformers model access (lazy-loads if needed).

    Args:
        paths: Note paths
        labels: Cluster labels from clustering algorithm
        db: Database connection to read note content
        n_terms: Number of terms to use in final label (after MMR)
        computer: Embedding computer to reuse (the session's, whose model is
            usually loaded already). None creates one, loading the model.
            Label-text embeddings are cached per computer by content hash.

    Returns:
        Dictionary mapping cluster_id to label string (comma-separated keywords)
    """
    from geistfabrik.embeddings import EmbeddingComputer

    cluster_labels: dict[int, str] = {}

    # Load note titles/content for each cluster
    clusters: dict[int, list[str]] = {}
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
            text = _label_text(title, content)
            clusters[label].append(text)

    if not clusters:
        return {}

    # Get embedding computer (lazy-load model)
    if computer is None:
        try:
            computer = EmbeddingComputer()
        except Exception:
            # If model loading fails, fall back to simple labels for all clusters
            logger.debug(
                "Model loading failed for KeyBERT labeling",
                exc_info=True,
            )
            return {cid: f"Cluster {cid}" for cid in clusters.keys()}

    try:
        text_cache = dict(_LABEL_TEXT_EMBEDDINGS.get(computer, {}))
        cacheable = True
    except TypeError:  # an encoder that cannot be weakly referenced
        text_cache, cacheable = {}, False

    # Get cluster embeddings to compute centroids
    cluster_embeddings: dict[int, list[np.ndarray]] = {}
    for cluster_id, texts in clusters.items():
        try:
            # Embed all texts in this cluster (cached ones are not re-encoded)
            cluster_embeddings[cluster_id] = _embed_label_texts(computer, texts, text_cache)
        except Exception:
            # If embedding fails for this cluster, skip to simple label
            logger.debug(
                "Embedding failed for cluster %d",
                cluster_id,
                exc_info=True,
            )
            cluster_labels[cluster_id] = f"Cluster {cluster_id}"

    # Keep only this run's texts: bounded by the vault, and a later run
    # re-encodes exactly the label texts that changed.
    if cacheable:
        used = {_text_key(text) for texts in clusters.values() for text in texts}
        _LABEL_TEXT_EMBEDDINGS[computer] = {
            key: value for key, value in text_cache.items() if key in used
        }

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
            max_features=100,
            stop_words="english",
            ngram_range=(1, 3),
            token_pattern=_WORD_TOKEN_PATTERN,
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
            diverse_terms = apply_mmr(candidate_terms, similarities, lambda_param=0.5, k=n_terms)

            cluster_labels[cluster_id] = ", ".join(diverse_terms)

        except Exception:
            # If KeyBERT approach fails, use simple fallback
            logger.debug(
                "KeyBERT labeling failed for cluster %d",
                cluster_id,
                exc_info=True,
            )
            cluster_labels[cluster_id] = f"Cluster {cluster_id}"

    return cluster_labels
