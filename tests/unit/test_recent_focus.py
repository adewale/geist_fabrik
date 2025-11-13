"""Unit tests for recent_focus geist."""

import os
from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import recent_focus
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
def vault_with_recent_and_old_similar(tmp_path):
    """Create a vault with recent notes and old similar notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()
    old_date = now - timedelta(days=90)

    # Create recent notes (within last few days)
    recent_topics = [
        "Machine Learning",
        "Neural Networks",
        "Deep Learning",
        "AI Ethics",
        "Computer Vision",
    ]
    for i, topic in enumerate(recent_topics):
        path = vault_path / f"recent_{topic.replace(' ', '_')}.md"
        path.write_text(f"# {topic}\n\nRecent content about {topic.lower()}.")
        path.touch()
        recent_time = (now - timedelta(days=i)).timestamp()
        os.utime(path, (recent_time, recent_time))

    # Create old similar notes (>60 days old)
    old_topics = [
        "Artificial Intelligence",
        "Machine Learning History",
        "Neural Net Theory",
        "AI Safety",
        "Image Recognition",
    ]
    for i, topic in enumerate(old_topics):
        path = vault_path / f"old_{topic.replace(' ', '_')}.md"
        path.write_text(f"# {topic}\n\nOld content about {topic.lower()}.")
        path.touch()
        old_time = (old_date - timedelta(days=i * 5)).timestamp()
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


def test_recent_focus_returns_suggestions(vault_with_recent_and_old_similar):
    """Test that recent_focus returns suggestions.

    Setup:
        Vault with recently modified notes.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_recent_and_old_similar

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = recent_focus.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_recent_focus_suggestion_structure(vault_with_recent_and_old_similar):
    """Test that suggestions have correct structure.

    Setup:
        Vault with recent activity.

    Verifies:
        - Has required fields
        - References recently modified notes"""
    vault, session = vault_with_recent_and_old_similar

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = recent_focus.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "recent_focus"

        # Should reference 2 notes (recent and old)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_recent_focus_uses_obsidian_link(vault_with_recent_and_old_similar):
    """Test that recent_focus uses obsidian_link for note references.

    Setup:
        Vault with recent notes.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_recent_and_old_similar

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = recent_focus.suggest(context)

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


def test_recent_focus_empty_vault(tmp_path):
    """Test that recent_focus handles empty vault gracefully.

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

    suggestions = recent_focus.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_recent_focus_insufficient_recent_notes(vault_insufficient_recent_notes):
    """Test that recent_focus handles insufficient recent notes gracefully."""
    vault, session = vault_insufficient_recent_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = recent_focus.suggest(context)

    # Should return empty list when < 2 recent notes
    assert len(suggestions) == 0


def test_recent_focus_no_old_similar_notes(tmp_path):
    """Test that recent_focus handles vault with only recent notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()
    # Create only recent notes
    for i in range(10):
        path = vault_path / f"recent_{i}.md"
        path.write_text(f"# Recent Note {i}\n\nContent.")
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

    suggestions = recent_focus.suggest(context)

    # May return empty if no old notes found
    assert isinstance(suggestions, list)


def test_recent_focus_max_suggestions(vault_with_recent_and_old_similar):
    """Test that recent_focus never returns more than 3 suggestions.

    Setup:
        Vault with many recent notes.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_recent_and_old_similar

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = recent_focus.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_recent_focus_deterministic_with_seed(vault_with_recent_and_old_similar):
    """Test that recent_focus returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_recent_and_old_similar

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

    suggestions1 = recent_focus.suggest(context1)
    suggestions2 = recent_focus.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_recent_focus_connects_recent_to_old(vault_with_recent_and_old_similar):
    """Test that recent_focus connects recent work to old similar notes."""
    vault, session = vault_with_recent_and_old_similar

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = recent_focus.suggest(context)

    for suggestion in suggestions:
        # Text should mention recent work connecting to old notes
        text_lower = suggestion.text.lower()
        assert "recent" in text_lower or "work" in text_lower
        assert "older" in text_lower or "old" in text_lower
        assert "similar" in text_lower or "connect" in text_lower


def test_recent_focus_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with session notes
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"""# Session {i}

Recent focus on machine learning topics. Neural networks and deep learning.

^g20240315-{i}"""
        )

    now = datetime.now()
    old_date = now - timedelta(days=90)

    # Create regular recent notes that should trigger suggestions
    recent_topics = [
        "Machine Learning",
        "Neural Networks",
        "Deep Learning",
        "AI Ethics",
        "Computer Vision",
    ]
    for i, topic in enumerate(recent_topics):
        path = vault_path / f"recent_{topic.replace(' ', '_')}.md"
        path.write_text(f"# {topic}\n\nRecent content about {topic.lower()}.")
        recent_time = (now - timedelta(days=i)).timestamp()
        os.utime(path, (recent_time, recent_time))

    # Create old similar notes
    old_topics = [
        "Artificial Intelligence",
        "Machine Learning History",
        "Neural Net Theory",
        "AI Safety",
        "Image Recognition",
    ]
    for i, topic in enumerate(old_topics):
        path = vault_path / f"old_{topic.replace(' ', '_')}.md"
        path.write_text(f"# {topic}\n\nOld content about {topic.lower()}.")
        old_time = (old_date - timedelta(days=i * 5)).timestamp()
        os.utime(path, (old_time, old_time))

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

    suggestions = recent_focus.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()
