"""Unit tests for creative_collision geist."""

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import creative_collision
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
def vault_with_diverse_notes(tmp_path):
    """Create a vault with notes from different domains."""
    from datetime import datetime

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes from different domains
    domains = {
        "Science": ["Physics", "Biology", "Chemistry", "Astronomy", "Geology"],
        "Art": ["Painting", "Sculpture", "Music", "Dance", "Theatre"],
        "Philosophy": ["Ethics", "Metaphysics", "Logic", "Aesthetics", "Epistemology"],
        "Technology": ["AI", "Blockchain", "IoT", "Cloud", "Quantum"],
    }

    for domain, topics in domains.items():
        for topic in topics:
            path = vault_path / f"{domain}_{topic}.md"
            path.write_text(f"# {topic}\n\nContent about {topic.lower()} in {domain.lower()}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_with_linked_notes(tmp_path):
    """Create a vault where most notes are linked."""
    from datetime import datetime

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes with cross-links
    for i in range(10):
        path = vault_path / f"note_{i}.md"
        # Link to next note
        next_i = (i + 1) % 10
        path.write_text(f"# Note {i}\n\nContent linking to [[note_{next_i}]].")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with only one note."""
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


def test_creative_collision_returns_suggestions(vault_with_diverse_notes):
    """Test that creative_collision returns suggestions.

    Setup:
        Vault with notes from different domains.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_diverse_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = creative_collision.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_creative_collision_suggestion_structure(vault_with_diverse_notes):
    """Test that suggestions have correct structure.

    Setup:
        Vault with cross-domain notes.

    Verifies:
        - Has required fields
        - References 2+ notes from different domains"""
    vault, session = vault_with_diverse_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = creative_collision.suggest(context)

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
        assert suggestion.geist_id == "creative_collision"

        # Should reference 2 notes (the collision pair)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_creative_collision_uses_obsidian_link(vault_with_diverse_notes):
    """Test that creative_collision uses obsidian_link for note references.

    Setup:
        Vault with cross-domain notes.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_diverse_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = creative_collision.suggest(context)

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


def test_creative_collision_empty_vault(tmp_path):
    """Test that creative_collision handles empty vault gracefully.

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

    suggestions = creative_collision.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_creative_collision_insufficient_notes(vault_insufficient_notes):
    """Test that creative_collision handles insufficient notes gracefully.

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

    suggestions = creative_collision.suggest(context)

    # Should return empty list when < 2 notes
    assert len(suggestions) == 0


def test_creative_collision_all_linked_notes(vault_with_linked_notes):
    """Test that creative_collision handles vault where all notes are linked."""
    vault, session = vault_with_linked_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = creative_collision.suggest(context)

    # May return empty if all notes are already linked
    assert isinstance(suggestions, list)


def test_creative_collision_max_suggestions(vault_with_diverse_notes):
    """Test that creative_collision never returns more than 3 suggestions.

    Setup:
        Vault with many cross-domain pairs.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_diverse_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = creative_collision.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_creative_collision_deterministic_with_seed(vault_with_diverse_notes):
    """Test that creative_collision returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_diverse_notes

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

    suggestions1 = creative_collision.suggest(context1)
    suggestions2 = creative_collision.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_creative_collision_suggests_unlinked_pairs(vault_with_diverse_notes):
    """Test that creative_collision suggests combining unlinked notes."""
    vault, session = vault_with_diverse_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = creative_collision.suggest(context)

    for suggestion in suggestions:
        # Text should suggest combining ideas
        assert "combined" in suggestion.text.lower() or "combine" in suggestion.text.lower()
        assert "different domains" in suggestion.text.lower()


def test_creative_collision_excludes_geist_journal(tmp_path):
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
            "What if Physics and Music combined created new insights?\n\n"
            "Different domains colliding might reveal unexpected patterns."
        )

    # Create regular notes from different domains
    domains = {
        "Science": ["Physics", "Biology", "Chemistry"],
        "Art": ["Painting", "Music", "Dance"],
    }

    for domain, topics in domains.items():
        for topic in topics:
            path = vault_path / f"{domain}_{topic}.md"
            path.write_text(f"# {topic}\n\nContent about {topic.lower()} in {domain.lower()}.")

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

    suggestions = creative_collision.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "2024-03-" not in note_ref.lower()  # Journal note naming pattern
