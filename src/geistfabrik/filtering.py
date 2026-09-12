"""Suggestion filtering pipeline for GeistFabrik.

This module implements the four-stage filtering pipeline:
1. Boundary: Ensure referenced notes exist and aren't excluded
2. Quality: Enforce cheap structure and length standards
3. Novelty: Avoid suggestions similar to recent history
4. Diversity: Remove near-duplicate suggestions from current batch

Each filter can be enabled/disabled via configuration.
"""

import sqlite3
from collections.abc import Iterator
from datetime import datetime, timedelta
from itertools import chain
from typing import Any

import numpy as np
from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
    cosine_similarity as sklearn_cosine,
)

from .config import (
    SIMILARITY_HISTORY_CHUNK,
    SIMILARITY_SUGGESTION_CHUNK,
    get_default_filter_config,
)
from .embeddings import EmbeddingComputer
from .models import NoteLinkIndex, Suggestion, _normalise_vault_path


class SuggestionFilter:
    """Filter suggestions through cheap boundary/quality then embedding checks."""

    def __init__(
        self,
        db: sqlite3.Connection,
        embedding_computer: EmbeddingComputer,
        config: dict[str, Any] | None = None,
    ):
        """Initialise filter with database and configuration.

        Args:
            db: SQLite database connection
            embedding_computer: For computing suggestion embeddings
            config: Filtering configuration dict
        """
        self.db = db
        self.embedding_computer = embedding_computer
        self.config = config or self._default_config()

    def _default_config(self) -> dict[str, Any]:
        """Return default filtering configuration."""
        return get_default_filter_config()

    def _iter_recent_embedding_chunks(
        self, session_date: datetime, window_days: int
    ) -> Iterator[np.ndarray]:
        """Stream bounded embedding chunks from sessions before the replay date."""
        cutoff_date = session_date - timedelta(days=window_days)
        cursor = self.db.execute(
            """
            SELECT suggestion_text
            FROM session_suggestions
            WHERE session_date >= ? AND session_date < ?
            ORDER BY session_date DESC, block_id
            """,
            (cutoff_date.strftime("%Y-%m-%d"), session_date.strftime("%Y-%m-%d")),
        )
        while rows := cursor.fetchmany(SIMILARITY_SUGGESTION_CHUNK):
            texts = [str(row[0]) for row in rows]
            yield np.asarray(
                self.embedding_computer.compute_batch_semantic(texts),
                dtype=np.float32,
            )

    def filter_all(self, suggestions: list[Suggestion], session_date: datetime) -> list[Suggestion]:
        """Apply all enabled filters in sequence.

        Args:
            suggestions: Raw suggestions from geists
            session_date: Date of current session

        Returns:
            Filtered list of suggestions
        """
        filtered = suggestions
        configured = self.config.get("strategies", [])
        # Shape/length checks and DB-only boundaries must run before any
        # embedding allocation, regardless of legacy strategy ordering.
        strategies = [s for s in ("boundary", "quality") if s in configured]
        strategies.extend(s for s in configured if s not in {"boundary", "quality"})

        for strategy in strategies:
            if strategy == "boundary":
                filtered = self.filter_boundary(filtered)
            elif strategy == "novelty":
                filtered = self.filter_novelty(filtered, session_date)
            elif strategy == "diversity":
                filtered = self.filter_diversity(filtered)
            elif strategy == "quality":
                filtered = self.filter_quality(filtered)

        return filtered

    def filter_boundary(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        """Remove suggestions referencing non-existent or excluded notes.

        Args:
            suggestions: Suggestions to filter

        Returns:
            Suggestions with valid note references only
        """
        if not self.config.get("boundary", {}).get("enabled", True):
            return suggestions

        # Folder prefixes whose notes must never surface in suggestions
        # (e.g. "Private/", "People/"). Spec: filtering.boundary.exclude_paths.
        exclude_paths = tuple(
            _normalise_vault_path(path)
            for path in (self.config.get("boundary", {}).get("exclude_paths", []) or [])
        )

        index = NoteLinkIndex(
            self.db.execute("SELECT path, title, is_virtual, source_file, entry_date FROM notes")
        )

        filtered = []
        for suggestion in suggestions:
            # Check every identity behind an unscoped reference. Graph-style
            # path precedence is unsafe here: a private note title can collide
            # with a public filename alias. Boundaries therefore fail closed if
            # any matching identity is excluded.
            matches = [index.matching_paths(note_ref) for note_ref in suggestion.notes]
            if all(
                paths
                and not any(index.sources[path].startswith(exclude_paths) for path in paths)
                for paths in matches
            ):
                filtered.append(suggestion)

        return filtered

    def filter_novelty(
        self, suggestions: list[Suggestion], session_date: datetime
    ) -> list[Suggestion]:
        """Remove suggestions similar to recent history.

        Uses lazy caching and batch embedding computation for optimal performance.

        Args:
            suggestions: Suggestions to filter
            session_date: Current session date

        Returns:
            Novel suggestions only
        """
        novelty_config = self.config.get("novelty", {})
        if not novelty_config.get("enabled", True):
            return suggestions

        window_days = novelty_config.get("window_days", 60)
        threshold = novelty_config.get("threshold", 0.85)
        method = novelty_config.get("method", "embedding_similarity")

        if method == "text_match":
            # Simple exact text matching
            cutoff_date = session_date - timedelta(days=window_days)
            bounds = (
                cutoff_date.strftime("%Y-%m-%d"),
                session_date.strftime("%Y-%m-%d"),
            )
            return [
                suggestion
                for suggestion in suggestions
                if self.db.execute(
                    """
                    SELECT 1 FROM session_suggestions
                    WHERE session_date >= ? AND session_date < ?
                      AND suggestion_text = ?
                    LIMIT 1
                    """,
                    (*bounds, suggestion.text),
                ).fetchone()
                is None
            ]
        else:
            # Embedding similarity matching with lazy cache + batching
            if not suggestions:
                return suggestions

            recent_chunks = self._iter_recent_embedding_chunks(session_date, window_days)
            first_chunk = next(recent_chunks, None)
            if first_chunk is None:
                return suggestions

            # Batch compute embeddings for the bounded current suggestion set.
            suggestion_texts = [s.text for s in suggestions]
            suggestion_embeddings = self.embedding_computer.compute_batch_semantic(suggestion_texts)

            # Stream history once and compare bounded blocks in both dimensions.
            suggestion_matrix = np.asarray(suggestion_embeddings, dtype=np.float32)
            too_similar = np.zeros(len(suggestions), dtype=np.bool_)
            for recent_chunk in chain((first_chunk,), recent_chunks):
                for history_start in range(0, len(recent_chunk), SIMILARITY_HISTORY_CHUNK):
                    history_end = history_start + SIMILARITY_HISTORY_CHUNK
                    history_block = recent_chunk[history_start:history_end]
                    for suggestion_start in range(0, len(suggestions), SIMILARITY_SUGGESTION_CHUNK):
                        suggestion_end = min(
                            suggestion_start + SIMILARITY_SUGGESTION_CHUNK,
                            len(suggestions),
                        )
                        if too_similar[suggestion_start:suggestion_end].all():
                            continue
                        similarities = sklearn_cosine(
                            suggestion_matrix[suggestion_start:suggestion_end],
                            history_block,
                        )
                        too_similar[suggestion_start:suggestion_end] |= (
                            similarities >= threshold
                        ).any(axis=1)
                if too_similar.all():
                    break
            return [s for i, s in enumerate(suggestions) if not too_similar[i]]

    def filter_diversity(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        """Remove near-duplicate suggestions from current batch.

        Uses embeddings to detect semantic similarity. Keeps first occurrence
        of similar suggestions.

        Args:
            suggestions: Suggestions to filter

        Returns:
            Diverse suggestions only
        """
        diversity_config = self.config.get("diversity", {})
        if not diversity_config.get("enabled", True):
            return suggestions

        threshold = diversity_config.get("threshold", 0.85)

        if not suggestions:
            return suggestions

        # Batch compute embeddings for all suggestions at once
        suggestion_texts = [s.text for s in suggestions]
        embeddings = self.embedding_computer.compute_batch_semantic(suggestion_texts)

        # One S x S similarity matrix, then the same greedy keep-first loop
        # reading matrix cells (previously S^2/2 per-pair cosine calls - the
        # dominant filter cost in --full mode at 50-200+ suggestions).
        sim_matrix = sklearn_cosine(np.asarray(embeddings, dtype=np.float32))

        keep = [True] * len(suggestions)
        for i in range(len(suggestions)):
            if not keep[i]:
                continue

            for j in range(i + 1, len(suggestions)):
                if keep[j] and float(sim_matrix[i, j]) >= threshold:
                    # Mark later suggestion as duplicate
                    keep[j] = False

        return [s for i, s in enumerate(suggestions) if keep[i]]

    def filter_quality(self, suggestions: list[Suggestion]) -> list[Suggestion]:
        """Apply basic quality checks.

        Checks:
        - Text length within bounds
        - No exact text repetition
        - Valid structure (has geist_id and notes)

        Args:
            suggestions: Suggestions to filter

        Returns:
            Quality suggestions only
        """
        quality_config = self.config.get("quality", {})
        if not quality_config.get("enabled", True):
            return suggestions

        min_length = quality_config.get("min_length", 10)
        max_length = quality_config.get("max_length", 2000)
        check_repetition = quality_config.get("check_repetition", True)

        filtered = []
        seen_texts: set[str] = set()

        for suggestion in suggestions:
            text = suggestion.text.strip()

            # Length checks
            if len(text) < min_length:
                continue
            if len(text) > max_length:
                continue

            # Repetition check
            if check_repetition:
                if text in seen_texts:
                    continue
                seen_texts.add(text)

            # Structure validation
            if not suggestion.geist_id:
                continue
            if not suggestion.notes:
                continue

            filtered.append(suggestion)

        return filtered


def select_suggestions(
    filtered: list[Suggestion], mode: str, count: int, seed: int
) -> list[Suggestion]:
    """Select final suggestions based on invocation mode.

    Args:
        filtered: Filtered suggestions
        mode: Invocation mode ('default', 'full', 'single', 'geist')
        count: Number of suggestions to select (for default mode)
        seed: Random seed for deterministic sampling

    Returns:
        Final suggestions to write to journal
    """
    import random

    if mode == "full":
        # Return all filtered suggestions
        return filtered

    # For default mode, sample deterministically
    if len(filtered) <= count:
        return filtered

    # Use seed for deterministic sampling
    rng = random.Random(seed)
    return rng.sample(filtered, count)
