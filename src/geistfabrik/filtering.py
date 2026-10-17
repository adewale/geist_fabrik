"""Suggestion filtering pipeline for GeistFabrik.

This module implements the four-stage filtering pipeline:
1. Boundary: Ensure referenced notes exist and aren't excluded
2. Quality: Enforce cheap structure and length standards
3. Novelty: Avoid suggestions similar to recent history
4. Diversity: Remove near-duplicate suggestions from current batch

Each filter can be enabled/disabled in the SuggestionFilter config dict
(config.yaml exposes only ``filtering.boundary.enabled``; ``--no-filter``
skips the whole pipeline). The quality stage drops any suggestion that names
no note.
"""

import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import chain
from typing import Any

import numpy as np

from .config import (
    SIMILARITY_HISTORY_CHUNK,
    SIMILARITY_SUGGESTION_CHUNK,
    get_default_filter_config,
)
from .embeddings import EmbeddingComputer
from .evidence_identity import evidence_interval
from .models import NoteLinkIndex, Suggestion, _normalise_vault_path
from .vector_math import UnitRows


@dataclass(frozen=True)
class FilterStageReport:
    """Count-only account of one filtering stage."""

    name: str
    input_count: int
    output_count: int

    @property
    def rejected_count(self) -> int:
        """Number removed by this stage."""
        return self.input_count - self.output_count


@dataclass(frozen=True)
class FilteringReport:
    """Privacy-preserving account of a filtering pipeline run."""

    input_count: int
    stages: tuple[FilterStageReport, ...]

    @property
    def output_count(self) -> int:
        """Number left after the final stage."""
        return self.stages[-1].output_count if self.stages else self.input_count


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
        self._pipeline_vectors: tuple[dict[str, int], UnitRows] | None = None
        self._in_pipeline = False

    def _candidate_vectors(self, texts: list[str]) -> UnitRows:
        """Share prepared candidate rows between novelty and diversity in one run."""
        if self._pipeline_vectors is not None:
            indices, prepared = self._pipeline_vectors
            if all(text in indices for text in texts):
                return prepared.take([indices[text] for text in texts])
        prepared = UnitRows(np.asarray(self.embedding_computer.compute_batch_semantic(texts)))
        if self._in_pipeline:
            self._pipeline_vectors = ({text: i for i, text in enumerate(texts)}, prepared)
        return prepared

    def _default_config(self) -> dict[str, Any]:
        """Return default filtering configuration."""
        return get_default_filter_config()

    def _iter_recent_text_chunks(
        self, session_date: datetime, window_days: int
    ) -> Iterator[list[str]]:
        """Stream bounded text chunks; exact matches can stop before encoding."""
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
            yield [str(row[0]) for row in rows]

    def filter_all(self, suggestions: list[Suggestion], session_date: datetime) -> list[Suggestion]:
        """Apply all enabled filters in sequence.

        Args:
            suggestions: Raw suggestions from geists
            session_date: Date of current session

        Returns:
            Filtered list of suggestions
        """
        filtered, _report = self.filter_all_with_report(suggestions, session_date)
        return filtered

    def filter_all_with_report(
        self, suggestions: list[Suggestion], session_date: datetime
    ) -> tuple[list[Suggestion], FilteringReport]:
        """Apply filters and return aggregate stage counts alongside survivors.

        The report deliberately contains no suggestion text or note references,
        so diagnostics can explain pipeline behaviour without exposing vault
        content.
        """
        filtered = suggestions
        stage_reports: list[FilterStageReport] = []
        configured = self.config.get("strategies", [])
        # Shape/length checks and DB-only boundaries must run before any
        # embedding allocation, regardless of legacy strategy ordering.
        strategies = [s for s in ("boundary", "quality") if s in configured]
        strategies.extend(s for s in configured if s not in {"boundary", "quality"})

        self._in_pipeline = True
        try:
            for strategy in strategies:
                input_count = len(filtered)
                if strategy == "boundary":
                    filtered = self.filter_boundary(filtered)
                elif strategy == "novelty":
                    filtered = self.filter_novelty(filtered, session_date)
                elif strategy == "diversity":
                    filtered = self.filter_diversity(filtered)
                elif strategy == "quality":
                    filtered = self.filter_quality(filtered)

                stage_reports.append(
                    FilterStageReport(
                        name=strategy,
                        input_count=input_count,
                        output_count=len(filtered),
                    )
                )
        finally:
            self._in_pipeline = False
            self._pipeline_vectors = None

        return filtered, FilteringReport(
            input_count=len(suggestions),
            stages=tuple(stage_reports),
        )

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
            if index.references_allowed(suggestion.notes, exclude_paths):
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

        # An episode remains the same observation when a template, percentage
        # or its selected links change. Persist identity only on journal writes;
        # previews keep the existing read-only, deterministic behavior.
        if any(s.evidence_key is not None for s in suggestions):
            cutoff = session_date - timedelta(days=window_days)
            seen = {
                (geist_id, key)
                for geist_id, key in self.db.execute(
                    "SELECT geist_id, evidence_key FROM session_suggestions "
                    "WHERE session_date >= ? AND session_date < ? AND evidence_key IS NOT NULL",
                    (cutoff.strftime("%Y-%m-%d"), session_date.strftime("%Y-%m-%d")),
                )
            }
            intervals: dict[tuple[str, str], list[tuple[date, date]]] = {}
            for geist_id, key in seen:
                interval = evidence_interval(key)
                if interval is not None:
                    identity, first, last = interval
                    intervals.setdefault((geist_id, identity), []).append((first, last))
            fresh = []
            for suggestion in suggestions:
                if (suggestion.geist_id, suggestion.evidence_key) in seen:
                    continue
                interval = (
                    evidence_interval(suggestion.evidence_key)
                    if suggestion.evidence_key is not None
                    else None
                )
                if interval is not None:
                    identity, first, last = interval
                    if any(
                        first <= old_last and old_first <= last
                        for old_first, old_last in intervals.get(
                            (suggestion.geist_id, identity), []
                        )
                    ):
                        continue
                fresh.append(suggestion)
            suggestions = fresh
            if not suggestions:
                return []

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

            recent_chunks = self._iter_recent_text_chunks(session_date, window_days)
            first_chunk = next(recent_chunks, None)
            if first_chunk is None:
                return suggestions

            suggestion_texts = [s.text for s in suggestions]
            suggestion_vectors = None
            too_similar = np.zeros(len(suggestions), dtype=np.bool_)
            for recent_texts in chain((first_chunk,), recent_chunks):
                exact_texts = set(recent_texts)
                too_similar |= np.array([text in exact_texts for text in suggestion_texts])
                if too_similar.all():
                    break
                if suggestion_vectors is None:
                    suggestion_vectors = self._candidate_vectors(suggestion_texts)
                history_vectors = UnitRows(
                    np.asarray(self.embedding_computer.compute_batch_semantic(recent_texts))
                )
                for history_start in range(0, len(history_vectors), SIMILARITY_HISTORY_CHUNK):
                    history_end = history_start + SIMILARITY_HISTORY_CHUNK
                    history_block = history_vectors._view(
                        history_start, min(history_end, len(history_vectors))
                    )
                    for suggestion_start in range(0, len(suggestions), SIMILARITY_SUGGESTION_CHUNK):
                        suggestion_end = min(
                            suggestion_start + SIMILARITY_SUGGESTION_CHUNK,
                            len(suggestions),
                        )
                        if too_similar[suggestion_start:suggestion_end].all():
                            continue
                        too_similar[suggestion_start:suggestion_end] |= suggestion_vectors._view(
                            suggestion_start, suggestion_end
                        ).any_matches(history_block, threshold)
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

        suggestion_texts = [s.text for s in suggestions]
        vectors = self._candidate_vectors(suggestion_texts)
        keep = [True] * len(suggestions)
        for i in range(len(suggestions)):
            if not keep[i]:
                continue

            matches = vectors._view(i, i + 1).compare(
                vectors._view(i + 1, len(vectors)), threshold
            )[0]
            for j in range(i + 1, len(suggestions)):
                if keep[j] and (
                    suggestions[i].text == suggestions[j].text or bool(matches[j - i - 1])
                ):
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
