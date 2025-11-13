"""Unit tests for pattern_finder geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import pattern_finder
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def vault_with_repeated_phrases(tmp_path):
    """Create a vault with repeated phrases across unlinked notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes with repeated phrase "emergent behaviour patterns"
    for i in range(5):
        (vault_path / f"emergent_{i}.md").write_text(
            f"# Emergent Note {i}\n\n"
            f"This discusses emergent behaviour patterns in complex systems. "
            f"Various phenomena exhibit these characteristics."
        )

    # Create notes with repeated phrase "distributed consensus algorithms"
    for i in range(5):
        (vault_path / f"consensus_{i}.md").write_text(
            f"# Consensus Note {i}\n\n"
            f"Exploring distributed consensus algorithms for fault tolerance. "
            f"These protocols ensure agreement."
        )

    # Create filler notes to reach minimum count
    for i in range(10):
        (vault_path / f"filler_{i}.md").write_text(
            f"# Filler Note {i}\n\nUnrelated content about topic {i}."
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with too few notes for pattern detection."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 10 notes (need at least 15)
    for i in range(10):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_pattern_finder_returns_suggestions(vault_with_repeated_phrases):
    """Test that pattern_finder returns suggestions with repeated patterns."""
    vault, session = vault_with_repeated_phrases

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_pattern_finder_suggestion_structure(vault_with_repeated_phrases):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_repeated_phrases

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "pattern_finder"

        # Should mention patterns or themes
        assert any(
            keyword in suggestion.text.lower()
            for keyword in ["phrase", "pattern", "theme", "cluster", "similar"]
        )

        # Should reference at least 3 notes
        assert len(suggestion.notes) >= 3

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_pattern_finder_uses_obsidian_link(vault_with_repeated_phrases):
    """Test that pattern_finder uses obsidian_link for note references."""
    vault, session = vault_with_repeated_phrases

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_pattern_finder_empty_vault(tmp_path):
    """Test that pattern_finder handles empty vault gracefully."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_pattern_finder_insufficient_notes(vault_insufficient_notes):
    """Test that pattern_finder handles insufficient notes gracefully."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    # Should return empty list when < 15 notes
    assert len(suggestions) == 0


def test_pattern_finder_max_suggestions(vault_with_repeated_phrases):
    """Test that pattern_finder never returns more than 2 suggestions."""
    vault, session = vault_with_repeated_phrases

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_pattern_finder_deterministic_with_seed(vault_with_repeated_phrases):
    """Test that pattern_finder returns same results with same seed."""
    vault, session = vault_with_repeated_phrases

    # Reuse same FunctionRegistry to avoid duplicate registration
    registry = FunctionRegistry()

    context1 = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=registry,
    )

    context2 = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=registry,
    )

    suggestions1 = pattern_finder.suggest(context1)
    suggestions2 = pattern_finder.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_pattern_finder_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with repeated phrases
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\n"
            f"This discusses emergent behaviour patterns in complex systems. "
            f"Various phenomena exhibit these characteristics."
        )

    # Create regular notes with repeated phrases
    # Create notes with repeated phrase "emergent behaviour patterns"
    for i in range(5):
        (vault_path / f"emergent_{i}.md").write_text(
            f"# Emergent Note {i}\n\n"
            f"This discusses emergent behaviour patterns in complex systems. "
            f"Various phenomena exhibit these characteristics."
        )

    # Create notes with repeated phrase "distributed consensus algorithms"
    for i in range(5):
        (vault_path / f"consensus_{i}.md").write_text(
            f"# Consensus Note {i}\n\n"
            f"Exploring distributed consensus algorithms for fault tolerance. "
            f"These protocols ensure agreement."
        )

    # Create filler notes to reach minimum count
    for i in range(10):
        (vault_path / f"filler_{i}.md").write_text(
            f"# Filler Note {i}\n\nUnrelated content about topic {i}."
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    # Get all journal note titles to check against
    journal_notes = [n for n in vault.all_notes() if "geist journal" in n.path.lower()]
    journal_titles = {n.title for n in journal_notes}

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert note_ref not in journal_titles, (
                f"Geist journal note '{note_ref}' was included in suggestions. "
                f"Expected only non-journal notes."
            )
