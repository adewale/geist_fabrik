"""Unit tests for blind_spot_detector geist."""

from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import blind_spot_detector
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
def vault_with_contrarian_notes(tmp_path):
    """Create a vault with recent notes and their semantic opposites."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()
    old_date = now - timedelta(days=200)

    # Create recent notes (within last 30 days)
    recent_topics = ["Optimism", "Innovation", "Collaboration", "Simplicity"]
    for i, topic in enumerate(recent_topics):
        path = vault_path / f"recent_{topic}.md"
        path.write_text(f"# {topic}\n\nContent about {topic.lower()}.")
        path.touch()
        recent_time = (now - timedelta(days=i * 5)).timestamp()
        import os

        os.utime(path, (recent_time, recent_time))

    # Create old contrarian notes (>180 days old)
    contrarian_topics = ["Pessimism", "Tradition", "Solitude", "Complexity"]
    for i, topic in enumerate(contrarian_topics):
        path = vault_path / f"old_{topic}.md"
        path.write_text(f"# {topic}\n\nContent about {topic.lower()}.")
        path.touch()
        old_time = (old_date - timedelta(days=i * 10)).timestamp()
        import os

        os.utime(path, (old_time, old_time))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_recent_notes(tmp_path):
    """Create a vault with only one recent note."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()
    path = vault_path / "recent_note.md"
    path.write_text("# Recent Note\n\nContent.")
    path.touch()

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_blind_spot_detector_returns_suggestions(vault_with_contrarian_notes):
    """Test that blind_spot_detector returns suggestions.

    Setup:
        Vault with unlinked similar notes.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_contrarian_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = blind_spot_detector.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_blind_spot_detector_suggestion_structure(vault_with_contrarian_notes):
    """Test that suggestions have correct structure.

    Setup:
        Vault with unlinked similar notes.

    Verifies:
        - Has required fields
        - References 2 similar unlinked notes"""
    vault, session = vault_with_contrarian_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = blind_spot_detector.suggest(context)

    # BEHAVIORAL: Verify geist follows output constraints
    # (This is a basic check - deeper assertions added to high-priority geists in Session 2)
    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "blind_spot_detector"

        # Should reference 2 notes (recent and contrarian)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_blind_spot_detector_uses_obsidian_link(vault_with_contrarian_notes):
    """Test that blind_spot_detector uses obsidian_link for note references.

    Setup:
        Vault with unlinked similar notes.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_contrarian_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = blind_spot_detector.suggest(context)

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


def test_blind_spot_detector_empty_vault(tmp_path):
    """Test that blind_spot_detector handles empty vault gracefully.

    Setup:
        Empty vault.

    Verifies:
        - Returns empty list"""
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

    suggestions = blind_spot_detector.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_blind_spot_detector_insufficient_recent_notes(vault_insufficient_recent_notes):
    """Test that blind_spot_detector handles insufficient recent notes gracefully."""
    vault, session = vault_insufficient_recent_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = blind_spot_detector.suggest(context)

    # Should return empty list when < 2 recent notes
    assert len(suggestions) == 0


def test_blind_spot_detector_no_contrarian_notes(tmp_path):
    """Test that blind_spot_detector handles vault with no contrarian matches."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()
    # Create recent notes only
    for i in range(5):
        path = vault_path / f"recent_{i}.md"
        path.write_text(f"# Recent Note {i}\n\nVery similar content {i}.")
        path.touch()

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = blind_spot_detector.suggest(context)

    # May return empty if no contrarian notes found
    assert isinstance(suggestions, list)


def test_blind_spot_detector_max_suggestions(vault_with_contrarian_notes):
    """Test that blind_spot_detector never returns more than 2 suggestions.

    Setup:
        Vault with many unlinked pairs.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_contrarian_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = blind_spot_detector.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_blind_spot_detector_deterministic_with_seed(vault_with_contrarian_notes):
    """Test that blind_spot_detector returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_contrarian_notes

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

    suggestions1 = blind_spot_detector.suggest(context1)
    suggestions2 = blind_spot_detector.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_blind_spot_detector_checks_old_contrarians(vault_with_contrarian_notes):
    """Test that blind_spot_detector specifically identifies old contrarian notes."""
    vault, session = vault_with_contrarian_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = blind_spot_detector.suggest(context)

    for suggestion in suggestions:
        # Text should mention days since modified
        assert "days since you touched it" in suggestion.text


def test_blind_spot_detector_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with contrarian content
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\n"
            "Content about pessimism, despair, and negativity. "
            "Contrarian views on optimism and hope."
        )

    now = datetime.now()
    old_date = now - timedelta(days=200)

    # Create recent notes that should trigger suggestions
    recent_topics = ["Optimism", "Innovation", "Collaboration", "Simplicity"]
    for i, topic in enumerate(recent_topics):
        path = vault_path / f"recent_{topic}.md"
        path.write_text(f"# {topic}\n\nContent about {topic.lower()}.")
        path.touch()
        recent_time = (now - timedelta(days=i * 5)).timestamp()
        import os

        os.utime(path, (recent_time, recent_time))

    # Create old contrarian notes (>180 days old)
    contrarian_topics = ["Pessimism", "Tradition", "Solitude", "Complexity"]
    for i, topic in enumerate(contrarian_topics):
        path = vault_path / f"old_{topic}.md"
        path.write_text(f"# {topic}\n\nContent about {topic.lower()}.")
        path.touch()
        old_time = (old_date - timedelta(days=i * 10)).timestamp()
        import os

        os.utime(path, (old_time, old_time))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = blind_spot_detector.suggest(context)

    # Verify no suggestions reference geist journal notes
    # Build title-to-path mapping to check note paths
    cursor = vault.db.execute("SELECT title, path FROM notes")
    title_to_path = {row[0]: row[1] for row in cursor.fetchall()}

    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            # Look up path by title or use note_ref as path
            note_path = title_to_path.get(note_ref, note_ref)
            assert "geist journal" not in note_path.lower(), (
                f"Geist journal note '{note_path}' was included in suggestions"
            )
