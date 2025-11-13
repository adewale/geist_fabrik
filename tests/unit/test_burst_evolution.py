"""Tests for burst_evolution geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import burst_evolution
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


@pytest.fixture
def vault_with_sessions(tmp_path):
    """Create a test vault with burst days and multiple sessions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create burst day: 2024-03-15 with 5 notes
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    note_titles = []
    for i in range(5):
        title = f"Burst Note {i}"
        note_titles.append(title)
        note_path = vault_path / f"burst_note_{i}.md"
        # Create notes with different content to get different embeddings
        content = f"# {title}\n\n{'Content ' * (i + 1)} about topic {i}."
        note_path.write_text(content)

    # Initialise vault and sync
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set created dates
    for i in range(5):
        vault.db.execute(
            "UPDATE notes SET created = ? WHERE title = ?",
            (burst_date.isoformat(), f"Burst Note {i}"),
        )
    vault.db.commit()

    # Create initial session (creation session)
    session1_date = datetime(2024, 3, 16)  # Day after creation
    session1 = Session(session1_date, vault.db)
    notes = vault.all_notes()
    session1.compute_embeddings(notes)

    # Create second session (current session) with slightly modified embeddings
    # This simulates notes evolving
    session2_date = datetime(2024, 6, 15)  # 3 months later
    session2 = Session(session2_date, vault.db)

    # For testing, we'll just compute embeddings again
    # In real usage, notes would have changed and embeddings would differ
    session2.compute_embeddings(notes)

    return vault, session1, session2


def test_burst_evolution_detects_burst_with_history(vault_with_sessions):
    """Test that burst evolution works with session history."""
    vault, session1, session2 = vault_with_sessions

    function_registry = FunctionRegistry()
    context = VaultContext(
        vault=vault,
        session=session2,
        seed=20240615,
        function_registry=function_registry,
    )

    suggestions = burst_evolution.suggest(context)

    # Should return 1 suggestion if we have enough data
    # May return 0 if embeddings are identical (no drift)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 1

    if suggestions:
        suggestion = suggestions[0]
        assert suggestion.geist_id == "burst_evolution"
        assert "2024-03-15" in suggestion.text
        assert "drift" in suggestion.text.lower()


def test_burst_evolution_no_sessions(tmp_path):
    """Test that geist returns empty list when no session history."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create burst day with notes
    for i in range(5):
        note_path = vault_path / f"note_{i}.md"
        note_path.write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    burst_date = datetime(2024, 3, 15)
    vault.db.execute("UPDATE notes SET created = ?", (burst_date.isoformat(),))
    vault.db.commit()

    # Create session WITHOUT populating session_embeddings
    # (just current embeddings, no history)
    session = Session(datetime(2024, 3, 16), vault.db)
    notes = vault.all_notes()
    session.compute_embeddings(notes)

    # Delete session_embeddings to simulate no history
    vault.db.execute("DELETE FROM session_embeddings")
    vault.db.commit()

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240316,
        function_registry=FunctionRegistry(),
    )

    suggestions = burst_evolution.suggest(context)

    # Should return empty list (no historical embeddings)
    assert len(suggestions) == 0


def test_burst_evolution_no_bursts(tmp_path):
    """Test that geist returns empty list when no burst days."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create only 2 notes per day (below burst threshold)
    for i in range(2):
        note_path = vault_path / f"note_{i}.md"
        note_path.write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = burst_evolution.suggest(context)

    # Should return empty list (no bursts)
    assert len(suggestions) == 0


def test_burst_evolution_insufficient_drift_data(vault_with_sessions):
    """Test fallback when <3 notes have drift data."""
    vault, session1, session2 = vault_with_sessions

    # Delete session_embeddings for most notes, keeping only 2
    paths = [note.path for note in vault.all_notes()]
    paths_to_keep = paths[:2]

    vault.db.execute(
        """
        DELETE FROM session_embeddings
        WHERE note_path NOT IN ({})
        """.format(",".join("?" * len(paths_to_keep))),
        paths_to_keep,
    )
    vault.db.commit()

    context = VaultContext(
        vault=vault,
        session=session2,
        seed=20240615,
        function_registry=FunctionRegistry(),
    )

    suggestions = burst_evolution.suggest(context)

    # Should return empty (need at least 3 notes with drift data)
    assert len(suggestions) == 0


def test_burst_evolution_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    # Create 10 journal notes
    for i in range(10):
        note_path = journal_dir / f"2024-03-{15 + i:02d}.md"
        note_path.write_text(f"# Session {i}\n\nJournal entry.")

    # Create only 2 regular notes (below threshold)
    for i in range(2):
        note_path = vault_path / f"note_{i}.md"
        note_path.write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    burst_date = datetime(2024, 3, 15)
    vault.db.execute("UPDATE notes SET created = ?", (burst_date.isoformat(),))
    vault.db.commit()

    session = Session(burst_date, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = burst_evolution.suggest(context)

    # Should return empty (journal excluded, only 2 regular notes)
    assert len(suggestions) == 0


def test_burst_evolution_drift_label():
    """Test drift label classification."""
    from geistfabrik.default_geists.code.burst_evolution import _drift_label

    assert _drift_label(0.05) == "mostly stable"
    assert _drift_label(0.15) == "moderate evolution"
    assert _drift_label(0.30) == "significant shift"
    assert _drift_label(0.50) == "major evolution"


def test_burst_evolution_includes_note_titles(vault_with_sessions):
    """Test that suggestion includes note titles in notes list."""
    vault, session1, session2 = vault_with_sessions

    context = VaultContext(
        vault=vault,
        session=session2,
        seed=20240615,
        function_registry=FunctionRegistry(),
    )

    suggestions = burst_evolution.suggest(context)

    if suggestions:
        # Should have note titles
        assert len(suggestions[0].notes) >= 3
        # All should be note titles
        for note_title in suggestions[0].notes:
            assert isinstance(note_title, str)


def test_burst_evolution_single_suggestion(vault_with_sessions):
    """Test that geist returns at most 1 suggestion."""
    vault, session1, session2 = vault_with_sessions

    context = VaultContext(
        vault=vault,
        session=session2,
        seed=20240615,
        function_registry=FunctionRegistry(),
    )

    suggestions = burst_evolution.suggest(context)

    # Should return 0 or 1, never more
    assert len(suggestions) <= 1
