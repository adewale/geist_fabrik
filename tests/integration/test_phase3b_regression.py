"""Regression tests for the Phase 3B pattern_finder sampling rollback.

Phase 3B made pattern_finder examine a 500-note sample, so on large vaults
most patterns went unseen. These tests guard full-corpus coverage and keep a
slow-lane bound on its runtime.

The other Phase 3B rollback (scale_shifter's switch to batch_similarity) no
longer has a test here: since commit 8ce5c8c both similarity() and
batch_similarity() are cache-aware, so the choice between them is not a
correctness contract. Cache consistency is owned by the batch_similarity
cache tests in tests/unit/test_vault_context.py.
"""

from datetime import datetime
from pathlib import Path
from typing import TypeVar, cast

import pytest

from geistfabrik.embeddings import Session
from geistfabrik.models import Note, Suggestion
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext

_T = TypeVar("_T")


class _RecordingPatternContext:
    """Minimal deterministic context for the full-corpus regression oracle."""

    def __init__(self, notes: list[Note]) -> None:
        self._notes = notes
        self.read_paths: list[str] = []

    def notes(self) -> list[Note]:
        return self._notes

    def outgoing_links(self, note: Note) -> list[Note]:
        return []

    def read(self, note: Note) -> str:
        self.read_paths.append(note.path)
        return note.content

    @staticmethod
    def sample(items: list[_T], count: int) -> list[_T]:
        return items[:count]

    @staticmethod
    def batch_similarity(notes_a: list[Note], notes_b: list[Note]) -> list[list[float]]:
        return [[1.0 for _ in notes_b] for _ in notes_a]


class TestPatternFinderCoverage:
    """Tests ensuring pattern_finder examines all notes, not a sample."""

    def test_pattern_finder_processes_all_notes_not_sample(self) -> None:
        """Regression: pattern_finder must examine ALL notes, not a sample.

        Phase 3B Issue (commit c74a12a):
        - Added: sampled_notes = vault.sample(notes, count=min(500, len(notes)))
        - Impact: On 10k vaults, only 5% of notes examined
        - Result: 95% of patterns missed, causing suggestion quality loss

        This test places a detectable pattern after the historical 500-note
        sampling boundary and records every note read by the geist.
        """
        from geistfabrik.default_geists.code import pattern_finder

        unique_phrase = "recursive improvement cycle"
        now = datetime(2025, 1, 15)
        notes = [
            Note(
                path=f"note_{i:04d}.md",
                title=f"Note {i}",
                content=unique_phrase if i >= 500 else f"ordinary material {i}",
                links=[],
                tags=[],
                created=now,
                modified=now,
            )
            for i in range(503)
        ]
        recording_context = _RecordingPatternContext(notes)
        context = cast(VaultContext, recording_context)

        suggestions: list[Suggestion] = pattern_finder.suggest(context)

        assert recording_context.read_paths == [note.path for note in notes]
        assert any(unique_phrase in suggestion.text for suggestion in suggestions)


@pytest.mark.benchmark
@pytest.mark.slow
class TestPatternFinderPerformance:
    """Tests ensuring pattern_finder completes on large vaults within timeout."""

    def test_pattern_finder_completes_on_large_vault(self, tmp_path: Path) -> None:
        """Regression: pattern_finder must complete on 10k vault within reasonable time.

        Phase 3B Issue:
        - Sampling was introduced as a "performance optimisation"
        - Reality: Phrase extraction isn't the bottleneck (link checking is)
        - Full processing completes in acceptable time (~76s on 10k vault)

        This test verifies that processing all notes doesn't cause timeout.
        """
        from geistfabrik.default_geists.code import pattern_finder

        vault_dir = tmp_path / "large_vault"
        vault_dir.mkdir()

        # Create 1000 notes (reduced from 10k for test speed)
        # In CI, this takes ~8-10s; 10k would take ~80s
        for i in range(1000):
            note_path = vault_dir / f"note_{i:04d}.md"
            content = (
                f"# Note {i}\n\n"
                f"Content about topic {i % 10}. "
                f"This note discusses various aspects of the subject. "
                f"Additional paragraph with more details.\n"
            )
            note_path.write_text(content)

        vault = Vault(str(vault_dir))
        vault.sync()
        notes = vault.all_notes()
        assert len(notes) == 1000

        session = Session(datetime(2025, 1, 15), vault.db)
        session.compute_embeddings(notes)
        context = VaultContext(vault, session)

        # Allow shared-runner headroom while still catching runaway/O(N²) behavior.
        import time

        start = time.perf_counter()
        suggestions = pattern_finder.suggest(context)
        elapsed = time.perf_counter() - start

        # Assertions
        assert elapsed < 120.0, (
            f"pattern_finder took {elapsed:.2f}s on 1000 notes. "
            f"This suggests O(N²) behaviour or performance regression. "
            f"Expected: <120s for 1000 notes on a shared runner, <10 minutes for 10k notes."
        )

        # Should complete successfully (may return 0 suggestions, that's ok)
        assert isinstance(suggestions, list), "Should return list of suggestions"
        assert all(hasattr(s, "text") for s in suggestions), "Valid suggestion objects"
