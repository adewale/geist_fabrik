"""Tests for Phase 2 Optimisation: OP-8 Optimised hubs() SQL query.

Tests the JOIN-based hubs() implementation that resolves targets in SQL
rather than Python, combined with batch loading.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.embeddings import Session
from geistfabrik.models import Note
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


@pytest.fixture
def vault_with_hub_structure(tmp_path: Path) -> Vault:
    """Create a vault with a clear hub structure for testing."""
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()

    # Create a hub note that many others link to
    (vault_dir / "hub.md").write_text("# Hub\n\nThis is a central hub note.")

    # Create notes that link to the hub
    for i in range(10):
        content = f"# Note {i}\n\nThis note links to [[hub]].\n"
        (vault_dir / f"note_{i}.md").write_text(content)

    # Create a less-connected note
    (vault_dir / "isolated.md").write_text("# Isolated\n\n[[note_0]]\n")

    # Create notes with different connection patterns
    (vault_dir / "secondary_hub.md").write_text("# Secondary Hub\n\nLinked by fewer notes.\n")
    for i in [0, 1, 2]:
        content = (vault_dir / f"note_{i}.md").read_text()
        content += "\n[[secondary_hub]]\n"
        (vault_dir / f"note_{i}.md").write_text(content)

    vault = Vault(str(vault_dir))
    vault.sync()
    return vault


@pytest.fixture
def context_with_hubs(vault_with_hub_structure: Vault) -> VaultContext:
    """Create VaultContext with hub structure."""
    session = Session(datetime.today(), vault_with_hub_structure.db)
    notes = vault_with_hub_structure.all_notes()
    session.compute_embeddings(notes)
    return VaultContext(vault_with_hub_structure, session)


class TestHubsOptimization:
    """Test OP-8: Optimised hubs() SQL query with JOIN."""

    def test_hubs_returns_most_linked_notes(self, context_with_hubs: VaultContext):
        """Test that hubs() returns notes with most incoming links."""
        hubs = context_with_hubs.hubs(k=3)

        assert isinstance(hubs, list)
        assert len(hubs) <= 3
        assert all(isinstance(n, Note) for n in hubs)

        # Hub note should be #1 (10 incoming links)
        if len(hubs) > 0:
            assert hubs[0].title == "Hub"

        # Secondary hub should be #2 (3 incoming links)
        if len(hubs) > 1:
            assert hubs[1].title == "Secondary Hub"

    def test_hubs_respects_k_parameter(self, context_with_hubs: VaultContext):
        """Test that hubs() respects the k parameter."""
        hubs_k1 = context_with_hubs.hubs(k=1)
        hubs_k3 = context_with_hubs.hubs(k=3)
        hubs_k10 = context_with_hubs.hubs(k=10)

        assert len(hubs_k1) <= 1
        assert len(hubs_k3) <= 3
        assert len(hubs_k10) <= 10

        # Larger k should include all of smaller k
        if len(hubs_k1) > 0 and len(hubs_k3) > 0:
            assert hubs_k1[0].path == hubs_k3[0].path

    def test_hubs_handles_link_target_variations(self, context_with_hubs: VaultContext):
        """Test that hubs() correctly resolves different link target formats."""
        # Links can be: "hub", "hub.md", or match by title
        # The JOIN should handle all these cases

        hubs = context_with_hubs.hubs(k=5)

        # Find the hub note
        hub_note = next((h for h in hubs if h.title == "Hub"), None)
        assert hub_note is not None, "Hub note should be found despite link format variations"

    def test_hubs_sorted_by_link_count(self, context_with_hubs: VaultContext):
        """Test that hubs are sorted by link count descending."""
        hubs = context_with_hubs.hubs(k=10)

        # Verify ordering by checking backlinks
        for i in range(len(hubs) - 1):
            current_backlinks = len(context_with_hubs.backlinks(hubs[i]))
            next_backlinks = len(context_with_hubs.backlinks(hubs[i + 1]))

            assert current_backlinks >= next_backlinks, (
                f"Hubs should be sorted by link count: "
                f"{hubs[i].title} ({current_backlinks}) vs "
                f"{hubs[i + 1].title} ({next_backlinks})"
            )

    def test_hubs_uses_batch_loading(self, context_with_hubs: VaultContext):
        """Test that hubs() uses batch loading (OP-6) internally."""
        # This is implicit in the implementation, but we can verify
        # that it returns valid Note objects efficiently
        hubs = context_with_hubs.hubs(k=3)

        # All returned notes should be fully loaded with links and tags
        for hub in hubs:
            assert isinstance(hub, Note)
            assert hub.title is not None
            assert hub.content is not None
            assert isinstance(hub.links, list)
            assert isinstance(hub.tags, list)


class TestHubsCorrectness:
    """Test that OP-8 produces same results as unoptimized version."""

    def test_hubs_returns_correct_notes(self, context_with_hubs: VaultContext):
        """Test that hubs() returns exactly the notes we expect."""
        hubs = context_with_hubs.hubs(k=5)

        # Manually verify by checking backlinks
        all_notes = context_with_hubs.vault.all_notes()
        link_counts = {}
        for note in all_notes:
            link_counts[note.path] = len(context_with_hubs.backlinks(note))

        # Sort by link count
        sorted_by_links = sorted(link_counts.items(), key=lambda x: x[1], reverse=True)
        expected_top_k = [path for path, count in sorted_by_links[:5] if count > 0]

        # Hubs should match this ordering
        actual_paths = [h.path for h in hubs]

        assert len(actual_paths) == len(expected_top_k)
        assert actual_paths == expected_top_k

    def test_hubs_handles_empty_vault(self, tmp_path: Path):
        """Test that hubs() handles vault with no links gracefully."""
        vault_dir = tmp_path / "empty_vault"
        vault_dir.mkdir()

        # Create notes with no links
        (vault_dir / "note1.md").write_text("# Note 1\n\nNo links here.")
        (vault_dir / "note2.md").write_text("# Note 2\n\nNo links here either.")

        vault = Vault(str(vault_dir))
        vault.sync()

        session = Session(datetime.today(), vault.db)
        notes = vault.all_notes()
        session.compute_embeddings(notes)
        context = VaultContext(vault, session)

        hubs = context.hubs(k=5)

        # Should return empty list (no notes have incoming links)
        assert hubs == []

    def test_hubs_handles_self_links(self, tmp_path: Path):
        """Test that hubs() handles notes that link to themselves."""
        vault_dir = tmp_path / "self_link_vault"
        vault_dir.mkdir()

        # Create a note that links to itself
        (vault_dir / "self_linker.md").write_text("# Self Linker\n\nI link to [[self_linker]].")

        # Create notes that link to self_linker
        for i in range(3):
            (vault_dir / f"note_{i}.md").write_text(f"# Note {i}\n\n[[self_linker]]\n")

        vault = Vault(str(vault_dir))
        vault.sync()

        session = Session(datetime.today(), vault.db)
        notes = vault.all_notes()
        session.compute_embeddings(notes)
        context = VaultContext(vault, session)

        hubs = context.hubs(k=5)

        # self_linker should be the top hub (3 incoming links)
        assert len(hubs) > 0
        assert hubs[0].title == "Self Linker"


class TestHubsEdgeCases:
    """Test edge cases for hubs() optimisation."""

    def test_hubs_with_duplicate_links(self, tmp_path: Path):
        """Test that hubs() counts unique source notes, not total link count."""
        vault_dir = tmp_path / "duplicate_vault"
        vault_dir.mkdir()

        (vault_dir / "target.md").write_text("# Target\n\nTarget note.")

        # Note with multiple links to same target
        (vault_dir / "source.md").write_text("# Source\n\n[[target]] and [[target]] and [[target]]")

        vault = Vault(str(vault_dir))
        vault.sync()

        session = Session(datetime.today(), vault.db)
        notes = vault.all_notes()
        session.compute_embeddings(notes)
        context = VaultContext(vault, session)

        hubs = context.hubs(k=5)

        # Target should have link count of 1 (unique source), not 3
        target_hub = next((h for h in hubs if h.title == "Target"), None)
        if target_hub:
            backlinks = context.backlinks(target_hub)
            # Should only count source.md once
            assert len(backlinks) == 1

    def test_hubs_with_k_larger_than_notes(self, tmp_path: Path):
        """Test that hubs() handles k larger than number of notes."""
        vault_dir = tmp_path / "small_vault"
        vault_dir.mkdir()

        (vault_dir / "hub.md").write_text("# Hub\n\nHub note.")
        (vault_dir / "note.md").write_text("# Note\n\n[[hub]]")

        vault = Vault(str(vault_dir))
        vault.sync()

        session = Session(datetime.today(), vault.db)
        notes = vault.all_notes()
        session.compute_embeddings(notes)
        context = VaultContext(vault, session)

        # Request more hubs than exist
        hubs = context.hubs(k=100)

        # Should return only available hubs
        assert len(hubs) <= 2


@pytest.mark.benchmark
class TestHubsPerformanceBenchmark:
    """Benchmark tests for hubs() optimisation (OP-8).

    Run with: pytest -m benchmark -v -s
    """

    def test_hubs_performance(self, context_with_hubs: VaultContext):
        """Benchmark hubs() with JOIN-based SQL query."""
        import time

        trials = 50
        times = []

        for _ in range(trials):
            start = time.perf_counter()
            _ = context_with_hubs.hubs(k=5)
            times.append(time.perf_counter() - start)

        avg_time = sum(times) / trials
        min_time = min(times)
        max_time = max(times)

        print("\n" + "=" * 70)
        print("Hubs Optimisation Benchmark (OP-8)")
        print("=" * 70)
        print(f"Vault notes: {len(context_with_hubs.vault.all_notes())}")
        print("K hubs requested: 5")
        print(f"Average time: {avg_time * 1000:.3f}ms")
        print(f"Min time:     {min_time * 1000:.3f}ms")
        print(f"Max time:     {max_time * 1000:.3f}ms")
        print("\nOptimization: JOIN-based target resolution + batch loading")
        print("=" * 70)

        # Should complete quickly (under 10ms for this small vault)
        assert avg_time < 0.010, f"Hubs should be fast (got {avg_time * 1000:.1f}ms)"
