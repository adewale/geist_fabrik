"""Suggestion filtering pipeline for GeistFabrik.

This module implements the four-stage filtering pipeline:
1. Boundary: Ensure referenced notes exist and aren't excluded
2. Novelty: Avoid suggestions similar to recent history
3. Diversity: Remove near-duplicate suggestions from current batch
4. Quality: Enforce basic quality standards

Each filter can be enabled/disabled via configuration.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set

from .config import (
    get_default_filter_config,
)
from .embeddings import EmbeddingComputer, cosine_similarity
from .models import Suggestion


class SuggestionFilter:
    """Filters suggestions through boundary, novelty, diversity, and quality checks."""

    def __init__(
        self,
        db: sqlite3.Connection,
        embedding_computer: EmbeddingComputer,
        config: Dict[str, Any] | None = None,
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
        # Lazy caching for novelty filter
        self._recent_embeddings_cache: Any = None  # numpy array when populated
        self._cache_metadata: Any = None  # (session_date, window_days) tuple when populated

    def _default_config(self) -> Dict[str, Any]:
        """Return default filtering configuration."""
        return get_default_filter_config()

    def _get_recent_embeddings(self, session_date: datetime, window_days: int) -> Any:
        """Get embeddings for recent suggestions with lazy caching.

        Args:
            session_date: Current session date
            window_days: Number of days to look back

        Returns:
            Numpy array of embeddings for recent suggestions
        """
        import numpy as np

        cache_key = (session_date, window_days)

        # Check if cache is valid
        if self._recent_embeddings_cache is not None and self._cache_metadata == cache_key:
            # Cache hit - return cached embeddings
            return self._recent_embeddings_cache

        # Cache miss - compute embeddings
        cutoff_date = session_date - timedelta(days=window_days)
        cursor = self.db.execute(
            """
            SELECT suggestion_text
            FROM session_suggestions
            WHERE session_date >= ?
            """,
            (cutoff_date.isoformat(),),
        )
        recent_texts = [row[0] for row in cursor.fetchall()]

        if recent_texts:
            # Batch compute all embeddings at once
            recent_embeddings = self.embedding_computer.compute_batch_semantic(recent_texts)
        else:
            recent_embeddings = np.array([])

        # Update cache
        self._recent_embeddings_cache = recent_embeddings
        self._cache_metadata = cache_key

        return recent_embeddings

    def filter_all(self, suggestions: List[Suggestion], session_date: datetime) -> List[Suggestion]:
        """Apply all enabled filters in sequence.

        Args:
            suggestions: Raw suggestions from geists
            session_date: Date of current session

        Returns:
            Filtered list of suggestions
        """
        filtered = suggestions

        for strategy in self.config.get("strategies", []):
            if strategy == "boundary":
                filtered = self.filter_boundary(filtered)
            elif strategy == "novelty":
                filtered = self.filter_novelty(filtered, session_date)
            elif strategy == "diversity":
                filtered = self.filter_diversity(filtered)
            elif strategy == "quality":
                filtered = self.filter_quality(filtered)

        return filtered

    def filter_boundary(self, suggestions: List[Suggestion]) -> List[Suggestion]:
        """Remove suggestions referencing non-existent or excluded notes.

        Args:
            suggestions: Suggestions to filter

        Returns:
            Suggestions with valid note references only
        """
        if not self.config.get("boundary", {}).get("enabled", True):
            return suggestions

        # Get all valid note paths from database
        cursor = self.db.execute("SELECT path FROM notes")
        valid_paths = {row[0] for row in cursor.fetchall()}

        # Get note titles for lookup
        cursor = self.db.execute("SELECT title, path FROM notes")
        title_to_path = {row[0]: row[1] for row in cursor.fetchall()}

        filtered = []
        for suggestion in suggestions:
            # Check if all referenced notes exist
            all_exist = True
            for note_ref in suggestion.notes:
                # Try both as title and as path
                if note_ref not in valid_paths and note_ref not in title_to_path:
                    all_exist = False
                    break

            if all_exist:
                filtered.append(suggestion)

        return filtered

    def filter_novelty(
        self, suggestions: List[Suggestion], session_date: datetime
    ) -> List[Suggestion]:
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
            cursor = self.db.execute(
                """
                SELECT suggestion_text
                FROM session_suggestions
                WHERE session_date >= ?
                """,
                (cutoff_date.isoformat(),),
            )
            recent_texts = {row[0] for row in cursor.fetchall()}
            return [s for s in suggestions if s.text not in recent_texts]
        else:
            # Embedding similarity matching with lazy cache + batching
            if not suggestions:
                return suggestions

            # Get recent embeddings (uses lazy cache)
            recent_embeddings = self._get_recent_embeddings(session_date, window_days)

            if len(recent_embeddings) == 0:
                return suggestions  # No history to compare against

            # Batch compute embeddings for all suggestions at once
            suggestion_texts = [s.text for s in suggestions]
            suggestion_embeddings = self.embedding_computer.compute_batch_semantic(suggestion_texts)

            # Filter suggestions with early stopping
            filtered = []
            for i, suggestion in enumerate(suggestions):
                suggestion_embedding = suggestion_embeddings[i]

                # Check if too similar to any recent suggestion (early stop on first match)
                is_novel = True
                for recent_embedding in recent_embeddings:
                    similarity = cosine_similarity(suggestion_embedding, recent_embedding)
                    if similarity >= threshold:
                        is_novel = False
                        break

                if is_novel:
                    filtered.append(suggestion)

            return filtered

    def filter_diversity(self, suggestions: List[Suggestion]) -> List[Suggestion]:
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

        # Compute embeddings for all suggestions
        embeddings = [self.embedding_computer.compute_semantic(s.text) for s in suggestions]

        # Keep track of which suggestions to include
        keep = [True] * len(suggestions)

        # Compare each suggestion with all previous ones
        for i in range(len(suggestions)):
            if not keep[i]:
                continue

            for j in range(i + 1, len(suggestions)):
                if not keep[j]:
                    continue

                similarity = cosine_similarity(embeddings[i], embeddings[j])
                if similarity >= threshold:
                    # Mark later suggestion as duplicate
                    keep[j] = False

        return [s for i, s in enumerate(suggestions) if keep[i]]

    def filter_quality(self, suggestions: List[Suggestion]) -> List[Suggestion]:
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
        seen_texts: Set[str] = set()

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
    filtered: List[Suggestion], mode: str, count: int, seed: int
) -> List[Suggestion]:
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
