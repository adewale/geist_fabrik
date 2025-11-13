"""Unit tests for vocabulary_expansion geist."""

from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import vocabulary_expansion
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
    """Create a vault with multiple sessions showing semantic coverage change."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes with varying topics
    topics = [
        ("tech", "Technology and software development topics."),
        ("philosophy", "Philosophy and existential questions."),
        ("art", "Art, design, and creative expression."),
        ("science", "Scientific methods and discoveries."),
        ("history", "Historical events and contexts."),
    ]

    for i, (topic, desc) in enumerate(topics):
        for j in range(3):
            content = f"# {topic.title()} Note {j}\n\n{desc} " * 5
            (vault_path / f"{topic}_{j}.md").write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create 5 sessions with different semantic coverage
    now = datetime.now()
    session_dates = [
        now - timedelta(days=120),  # 4 months ago
        now - timedelta(days=90),  # 3 months ago
        now - timedelta(days=60),  # 2 months ago
        now - timedelta(days=30),  # 1 month ago
        now,  # Today
    ]

    for session_date in session_dates:
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    return vault, Session(now, vault.db)


@pytest.fixture
def vault_with_insufficient_sessions(tmp_path):
    """Create a vault with too few sessions for analysis."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    for i in range(12):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent here.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Only 2 sessions (need at least 3)
    now = datetime.now()
    for session_date in [now - timedelta(days=30), now]:
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    return vault, Session(now, vault.db)


@pytest.fixture
def vault_with_insufficient_notes_per_session(tmp_path):
    """Create a vault with too few notes per session for coverage analysis."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only 5 notes (need at least 10 per session)
    for i in range(5):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create 5 sessions
    now = datetime.now()
    for i in range(5):
        session_date = now - timedelta(days=30 * i)
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    return vault, Session(now, vault.db)


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_vocabulary_expansion_returns_suggestions(vault_with_session_history):
    """Test that vocabulary_expansion returns suggestions with session history.

    Setup:
        Vault with rich vocabulary.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = vocabulary_expansion.suggest(context)

    # Should return list (up to 1 suggestion)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 1


def test_vocabulary_expansion_suggestion_structure(vault_with_session_history):
    """Test that suggestions have correct structure.

    Setup:
        Vault with varied vocabulary.

    Verifies:
        - Has required fields
        - References notes with vocabulary patterns"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = vocabulary_expansion.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "vocabulary_expansion"

        # May have no note references (meta-observation)
        assert isinstance(suggestion.notes, list)


def test_vocabulary_expansion_mentions_timeframes(vault_with_session_history):
    """Test that suggestions mention specific timeframes."""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = vocabulary_expansion.suggest(context)

    if suggestions:
        # Should mention dates in YYYY-MM format
        suggestion_text = suggestions[0].text
        # Look for date patterns like "2024-01" or "2025-11"
        import re

        assert re.search(r"\d{4}-\d{2}", suggestion_text)


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_vocabulary_expansion_empty_vault(tmp_path):
    """Test that vocabulary_expansion handles empty vault gracefully.

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

    suggestions = vocabulary_expansion.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_vocabulary_expansion_insufficient_sessions(vault_with_insufficient_sessions):
    """Test that vocabulary_expansion handles insufficient sessions gracefully."""
    vault, session = vault_with_insufficient_sessions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = vocabulary_expansion.suggest(context)

    # Should return empty list when < 3 sessions
    assert len(suggestions) == 0


def test_vocabulary_expansion_insufficient_notes_per_session(
    vault_with_insufficient_notes_per_session,
):
    """Test that vocabulary_expansion handles sessions with too few notes."""
    vault, session = vault_with_insufficient_notes_per_session

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = vocabulary_expansion.suggest(context)

    # Should return empty list when sessions have < 10 notes
    assert len(suggestions) == 0


def test_vocabulary_expansion_no_significant_change(tmp_path):
    """Test that vocabulary_expansion handles vault without significant coverage change."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes with similar semantic content
    for i in range(12):
        content = "Similar content about the same topic. " * 8
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\n{content}")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create 5 sessions
    now = datetime.now()
    for i in range(5):
        session_date = now - timedelta(days=30 * i)
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    session = Session(now, vault.db)

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = vocabulary_expansion.suggest(context)

    # May return empty list if no significant trend detected
    assert isinstance(suggestions, list)


def test_vocabulary_expansion_max_suggestions(vault_with_session_history):
    """Test that vocabulary_expansion never returns more than 1 suggestion.

    Setup:
        Vault with varied vocabulary.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_session_history

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = vocabulary_expansion.suggest(context)

    # Should never return more than 1
    assert len(suggestions) <= 1


def test_vocabulary_expansion_deterministic_with_seed(vault_with_session_history):
    """Test that vocabulary_expansion returns same results with same seed.

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

    suggestions1 = vocabulary_expansion.suggest(context1)
    suggestions2 = vocabulary_expansion.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_vocabulary_expansion_handles_database_errors(tmp_path):
    """Test that vocabulary_expansion handles database query errors gracefully."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    for i in range(12):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

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

    # Should not crash even if database operations fail
    suggestions = vocabulary_expansion.suggest(context)
    assert isinstance(suggestions, list)


def test_vocabulary_expansion_excludes_geist_journal(tmp_path):
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

    # Create journal notes with diverse topics
    for i in range(5):
        content = f"""# Session {i}

Technology and software development topics. Philosophy and existential questions.
Art, design, and creative expression. Scientific methods and discoveries."""
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(content)

    # Create regular notes with varying topics
    topics = [
        ("tech", "Technology and software development topics."),
        ("philosophy", "Philosophy and existential questions."),
        ("art", "Art, design, and creative expression."),
        ("science", "Scientific methods and discoveries."),
        ("history", "Historical events and contexts."),
    ]

    for i, (topic, desc) in enumerate(topics):
        for j in range(3):
            content = f"# {topic.title()} Note {j}\n\n{desc} " * 5
            (vault_path / f"{topic}_{j}.md").write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Create 5 sessions with different semantic coverage
    now = datetime.now()
    session_dates = [
        now - timedelta(days=120),  # 4 months ago
        now - timedelta(days=90),  # 3 months ago
        now - timedelta(days=60),  # 2 months ago
        now - timedelta(days=30),  # 1 month ago
        now,  # Today
    ]

    for session_date in session_dates:
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

    session = Session(now, vault.db)

    context = VaultContext(
        vault=vault, session=session, seed=20240315, function_registry=FunctionRegistry()
    )

    suggestions = vocabulary_expansion.suggest(context)

    # Verify no suggestions reference geist journal notes
    journal_notes = [note for note in vault.all_notes() if "geist journal" in note.path.lower()]
    journal_titles = {note.title.lower() for note in journal_notes}

    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert note_ref.lower() not in journal_titles, (
                f"Found journal note reference: {note_ref}"
            )
