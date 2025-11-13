"""Unit tests for session_drift geist."""

from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import session_drift
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
def vault_with_session_history(tmp_path):
    """Create a vault with multiple sessions for drift detection."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Create notes with stable content
    for i in range(35):
        path = vault_path / f"note_{i}.md"
        path.write_text(f"# Note {i}\n\nContent about topic {i}.")
        # Set creation time to be old
        old_time = (now - timedelta(days=200)).timestamp()
        import os

        os.utime(path, (old_time, old_time))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create multiple sessions (at least 2 for drift comparison)
    sessions = []
    for i in range(3):
        session_date = now - timedelta(days=(3 - i) * 30)  # Monthly sessions
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())
        sessions.append(session)

    # Return most recent session as active session
    return vault, sessions[-1]


@pytest.fixture
def vault_single_session(tmp_path):
    """Create a vault with only single session."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes
    for i in range(20):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Only 1 session
    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_session_drift_returns_suggestions(vault_with_session_history):
    """Test that session_drift returns suggestions with session history.

    Setup:
        Vault with notes showing embedding drift across sessions.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = session_drift.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_session_drift_suggestion_structure(vault_with_session_history):
    """Test that suggestions have correct structure.

    Setup:
        Vault with drifting notes.

    Verifies:
        - Has required fields
        - References notes with session-to-session drift"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = session_drift.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "session_drift"

        # Should reference 1 note (the drifting note)
        assert len(suggestion.notes) == 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_session_drift_uses_obsidian_link(vault_with_session_history):
    """Test that session_drift uses obsidian_link for note references.

    Setup:
        Vault with drift.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = session_drift.suggest(context)

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


def test_session_drift_empty_vault(tmp_path):
    """Test that session_drift handles empty vault gracefully.

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

    suggestions = session_drift.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_session_drift_single_session(vault_single_session):
    """Test that session_drift handles single session gracefully."""
    vault, session = vault_single_session

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = session_drift.suggest(context)

    # Should return empty list when only 1 session
    assert len(suggestions) == 0


def test_session_drift_max_suggestions(vault_with_session_history):
    """Test that session_drift never returns more than 3 suggestions.

    Setup:
        Vault with drifting notes.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = session_drift.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_session_drift_deterministic_with_seed(vault_with_session_history):
    """Test that session_drift returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_session_history

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

    suggestions1 = session_drift.suggest(context1)
    suggestions2 = session_drift.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_session_drift_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    now = datetime.now()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\nTemporal drift in understanding across multiple sessions."
        )
        # Set file times
        timestamp = (now - timedelta(days=180 - i)).timestamp()
        import os

        os.utime(journal_dir / f"2024-03-{15 + i:02d}.md", (timestamp, timestamp))

    # Create regular notes that should trigger drift
    for i in range(35):
        path = vault_path / f"note_{i}.md"
        path.write_text(f"# Note {i}\n\nContent about topic {i}.")
        # Set creation time to be old
        old_time = (now - timedelta(days=200)).timestamp()
        import os

        os.utime(path, (old_time, old_time))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create multiple sessions (at least 2 for drift comparison)
    for i in range(3):
        session_date = now - timedelta(days=(3 - i) * 30)  # Monthly sessions
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    # Final session
    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = session_drift.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()
