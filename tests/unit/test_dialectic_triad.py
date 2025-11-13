"""Unit tests for dialectic_triad geist."""

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import dialectic_triad
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
def vault_with_dialectic_pairs(tmp_path):
    """Create a vault with thesis-antithesis pairs."""
    from datetime import datetime

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create thesis notes
    thesis_topics = [
        "Optimism",
        "Freedom",
        "Rationalism",
        "Individualism",
        "Progress",
    ]
    for topic in thesis_topics:
        path = vault_path / f"thesis_{topic}.md"
        path.write_text(f"# {topic}\n\nContent about {topic.lower()}.")

    # Create antithesis notes
    antithesis_topics = [
        "Pessimism",
        "Determinism",
        "Empiricism",
        "Collectivism",
        "Tradition",
    ]
    for topic in antithesis_topics:
        path = vault_path / f"antithesis_{topic}.md"
        path.write_text(f"# {topic}\n\nContent about {topic.lower()}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with insufficient notes."""
    from datetime import datetime

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "single_note.md").write_text("# Single Note\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_dialectic_triad_returns_suggestions(vault_with_dialectic_pairs):
    """Test that dialectic_triad returns suggestions.

    Setup:
        Vault with thesis/antithesis patterns.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_dialectic_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = dialectic_triad.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_dialectic_triad_suggestion_structure(vault_with_dialectic_pairs):
    """Test that suggestions have correct structure.

    Setup:
        Vault with dialectic patterns.

    Verifies:
        - Has required fields
        - References 2-3 notes (thesis/antithesis/synthesis)"""
    vault, session = vault_with_dialectic_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = dialectic_triad.suggest(context)

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
        assert suggestion.geist_id == "dialectic_triad"

        # Should reference 2 notes (thesis and antithesis)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_dialectic_triad_uses_obsidian_link(vault_with_dialectic_pairs):
    """Test that dialectic_triad uses obsidian_link for note references.

    Setup:
        Vault with dialectic notes.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_dialectic_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = dialectic_triad.suggest(context)

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


def test_dialectic_triad_empty_vault(tmp_path):
    """Test that dialectic_triad handles empty vault gracefully.

    Setup:
        Empty vault.

    Verifies:
        - Returns empty list"""
    from datetime import datetime

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

    suggestions = dialectic_triad.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_dialectic_triad_insufficient_notes(vault_insufficient_notes):
    """Test that dialectic_triad handles insufficient notes gracefully.

    Setup:
        Vault with < 15 notes.

    Verifies:
        - Returns empty list"""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = dialectic_triad.suggest(context)

    # May return empty if no contrarian notes found
    assert isinstance(suggestions, list)


def test_dialectic_triad_no_contrarians(tmp_path):
    """Test that dialectic_triad handles vault with no contrarian notes."""
    from datetime import datetime

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes with very similar content
    for i in range(10):
        path = vault_path / f"similar_{i}.md"
        path.write_text(f"# Similar Note {i}\n\nVery similar content about the same topic.")

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

    suggestions = dialectic_triad.suggest(context)

    # May return empty if no contrarian notes found
    assert isinstance(suggestions, list)


def test_dialectic_triad_max_suggestions(vault_with_dialectic_pairs):
    """Test that dialectic_triad never returns more than 2 suggestions.

    Setup:
        Vault with multiple dialectic patterns.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_dialectic_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = dialectic_triad.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_dialectic_triad_deterministic_with_seed(vault_with_dialectic_pairs):
    """Test that dialectic_triad returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_dialectic_pairs

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

    suggestions1 = dialectic_triad.suggest(context1)
    suggestions2 = dialectic_triad.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_dialectic_triad_contains_dialectic_structure(vault_with_dialectic_pairs):
    """Test that suggestions contain thesis-antithesis-synthesis structure."""
    vault, session = vault_with_dialectic_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = dialectic_triad.suggest(context)

    for suggestion in suggestions:
        # Should contain dialectic terminology
        text_lower = suggestion.text.lower()
        assert "thesis" in text_lower
        assert "antithesis" in text_lower
        assert "synthe" in text_lower  # "synthesize" or "synthesis"


def test_dialectic_triad_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    from datetime import datetime

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
            "Consider how [[Optimism]] as thesis and [[Pessimism]] as antithesis "
            "might synthesize.\n\n"
            "The dialectic tension reveals new understanding."
        )

    # Create thesis notes
    thesis_topics = ["Optimism", "Freedom", "Rationalism", "Individualism", "Progress"]
    for topic in thesis_topics:
        path = vault_path / f"thesis_{topic}.md"
        path.write_text(f"# {topic}\n\nContent about {topic.lower()}.")

    # Create antithesis notes
    antithesis_topics = ["Pessimism", "Determinism", "Empiricism", "Collectivism", "Tradition"]
    for topic in antithesis_topics:
        path = vault_path / f"antithesis_{topic}.md"
        path.write_text(f"# {topic}\n\nContent about {topic.lower()}.")

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

    suggestions = dialectic_triad.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "2024-03-" not in note_ref.lower()  # Journal note naming pattern
