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
from typing import List, Set

from .embeddings import EmbeddingComputer, cosine_similarity
from .models import Suggestion


class SuggestionFilter:
    """Filters suggestions through boundary, novelty, diversity, and quality checks."""

    def __init__(
        self,
        db: sqlite3.Connection,
        embedding_computer: EmbeddingComputer,
        config: dict | None = None,
    ):
        """Initialize filter with database and configuration.

        Args:
            db: SQLite database connection
            embedding_computer: For computing suggestion embeddings
            config: Filtering configuration dict
        """
        self.db = db
        self.embedding_computer = embedding_computer
        self.config = config or self._default_config()

    def _default_config(self) -> dict:
        """Return default filtering configuration."""
        return {
            "strategies": ["boundary", "novelty", "diversity", "quality"],
            "boundary": {"enabled": True},
            "novelty": {
                "enabled": True,
                "method": "embedding_similarity",
                "threshold": 0.85,
                "window_days": 60,
            },
            "diversity": {
                "enabled": True,
                "method": "embedding_similarity",
                "threshold": 0.85,
            },
            "quality": {
                "enabled": True,
                "min_length": 10,
                "max_length": 2000,
                "check_repetition": True,
            },
        }

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

        # Get recent suggestions from history
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

        if method == "text_match":
            # Simple exact text matching
            return [s for s in suggestions if s.text not in recent_texts]
        else:
            # Embedding similarity matching
            if not recent_texts:
                return suggestions  # No history to compare against

            # Compute embeddings for recent suggestions
            recent_embeddings = [
                self.embedding_computer.compute_semantic(text) for text in recent_texts
            ]

            # Filter suggestions
            filtered = []
            for suggestion in suggestions:
                suggestion_embedding = self.embedding_computer.compute_semantic(suggestion.text)

                # Check if too similar to any recent suggestion
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
