"""Unit tests for hermeneutic_instability geist."""

import os
from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import hermeneutic_instability
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
def vault_with_multiple_sessions(tmp_path):
    """Create a vault with multiple sessions and varying embeddings."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes
    for i in range(20):
        path = vault_path / f"note_{i}.md"
        path.write_text(f"# Note {i}\n\nStable content {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create multiple sessions with embeddings
    now = datetime.now()
    for i in range(5):
        session_date = now - timedelta(days=i * 10)
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    # Touch some files to make them old
    old_date = now - timedelta(days=90)
    for i in range(10):
        path = vault_path / f"note_{i}.md"
        old_time = old_date.timestamp()
        os.utime(path, (old_time, old_time))

    # Re-sync to update modification times
    vault.sync()

    # Create one more session with current date
    current_session = Session(now, vault.db)
    current_session.compute_embeddings(vault.all_notes())

    return vault, current_session


@pytest.fixture
def vault_with_insufficient_sessions(tmp_path):
    """Create a vault with only 2 sessions (below minimum of 3)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes
    for i in range(10):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create only 2 sessions
    now = datetime.now()
    for i in range(2):
        session_date = now - timedelta(days=i * 10)
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    current_session = Session(now, vault.db)
    current_session.compute_embeddings(vault.all_notes())

    return vault, current_session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_hermeneutic_instability_returns_suggestions(vault_with_multiple_sessions):
    """Test that hermeneutic_instability returns suggestions.

    Setup:
        Vault with notes changing interpretation.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_multiple_sessions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hermeneutic_instability.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_hermeneutic_instability_suggestion_structure(vault_with_multiple_sessions):
    """Test that suggestions have correct structure.

    Setup:
        Vault with unstable interpretations.

    Verifies:
        - Has required fields
        - References notes with interpretation shifts"""
    vault, session = vault_with_multiple_sessions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hermeneutic_instability.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "hermeneutic_instability"

        # Should reference 1 note (the unstable note)
        assert len(suggestion.notes) == 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_hermeneutic_instability_uses_obsidian_link(vault_with_multiple_sessions):
    """Test that hermeneutic_instability uses obsidian_link for note references.

    Setup:
        Vault with interpretation changes.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_multiple_sessions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hermeneutic_instability.suggest(context)

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


def test_hermeneutic_instability_empty_vault(tmp_path):
    """Test that hermeneutic_instability handles empty vault gracefully.

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

    suggestions = hermeneutic_instability.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_hermeneutic_instability_insufficient_sessions(vault_with_insufficient_sessions):
    """Test that hermeneutic_instability handles insufficient sessions gracefully."""
    vault, session = vault_with_insufficient_sessions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hermeneutic_instability.suggest(context)

    # Should return empty list when < 3 sessions
    assert len(suggestions) == 0


def test_hermeneutic_instability_no_old_notes(tmp_path):
    """Test that hermeneutic_instability handles vault with only recent notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes
    for i in range(20):
        (vault_path / f"recent_{i}.md").write_text(f"# Recent {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create multiple sessions
    now = datetime.now()
    for i in range(5):
        session_date = now - timedelta(days=i * 10)
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    current_session = Session(now, vault.db)
    current_session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=current_session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hermeneutic_instability.suggest(context)

    # May return empty if no notes meet the criteria (old + unstable)
    assert isinstance(suggestions, list)


def test_hermeneutic_instability_max_suggestions(vault_with_multiple_sessions):
    """Test that hermeneutic_instability never returns more than 2 suggestions.

    Setup:
        Vault with multiple unstable notes.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_multiple_sessions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hermeneutic_instability.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_hermeneutic_instability_deterministic_with_seed(vault_with_multiple_sessions):
    """Test that hermeneutic_instability returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_multiple_sessions

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

    suggestions1 = hermeneutic_instability.suggest(context1)
    suggestions2 = hermeneutic_instability.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_hermeneutic_instability_checks_interpretive_variance(vault_with_multiple_sessions):
    """Test that hermeneutic_instability identifies notes with unstable interpretation."""
    vault, session = vault_with_multiple_sessions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hermeneutic_instability.suggest(context)

    for suggestion in suggestions:
        # Text should mention interpretation across sessions
        assert "interpreted differently" in suggestion.text or "sessions" in suggestion.text
        assert "not being edited" in suggestion.text or "days" in suggestion.text


def test_hermeneutic_instability_handles_missing_embeddings(tmp_path):
    """Test that hermeneutic_instability handles notes with missing embeddings."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes
    for i in range(10):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create sessions but only embed some notes
    now = datetime.now()
    for i in range(5):
        session_date = now - timedelta(days=i * 10)
        session = Session(session_date, vault.db)
        # Only compute embeddings for first 5 notes
        notes_to_embed = list(vault.all_notes())[:5]
        session.compute_embeddings(notes_to_embed)

    current_session = Session(now, vault.db)
    current_session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=current_session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hermeneutic_instability.suggest(context)

    # Should not crash with missing embeddings
    assert isinstance(suggestions, list)


def test_hermeneutic_instability_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with sessions
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        journal_note = journal_dir / f"2024-03-{15 + i:02d}.md"
        journal_note.write_text(
            f"# Session {i}\n\n"
            "## Suggestions\n\n"
            "[[note_5]] has been interpreted differently across sessions "
            "despite not being edited.\n\n"
            "The hermeneutic instability suggests evolving understanding."
        )

    # Create regular notes
    for i in range(20):
        path = vault_path / f"note_{i}.md"
        path.write_text(f"# Note {i}\n\nStable content {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create multiple sessions with embeddings
    now = datetime.now()
    for i in range(5):
        session_date = now - timedelta(days=i * 10)
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    # Touch some files to make them old
    old_date = now - timedelta(days=90)
    for i in range(10):
        path = vault_path / f"note_{i}.md"
        old_time = old_date.timestamp()
        os.utime(path, (old_time, old_time))

    # Re-sync to update modification times
    vault.sync()

    # Create current session
    current_session = Session(now, vault.db)
    current_session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=current_session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = hermeneutic_instability.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "2024-03-" not in note_ref.lower()  # Journal note naming pattern
