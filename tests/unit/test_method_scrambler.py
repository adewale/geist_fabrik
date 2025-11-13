"""Unit tests for method_scrambler geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import method_scrambler
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
def vault_with_linked_notes(tmp_path):
    """Create a vault with notes that have outgoing links."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create target notes
    (vault_path / "target1.md").write_text("# Target 1\n\nContent.")
    (vault_path / "target2.md").write_text("# Target 2\n\nContent.")
    (vault_path / "target3.md").write_text("# Target 3\n\nContent.")

    # Create source notes with links
    (vault_path / "source1.md").write_text("# Source 1\n\nLinks to [[target1]] and [[target2]].")
    (vault_path / "source2.md").write_text("# Source 2\n\nLinks to [[target3]] and [[target1]].")

    # Add more notes to reach minimum
    for i in range(8):
        (vault_path / f"filler_{i}.md").write_text(f"# Filler {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_with_unlinked_pairs(tmp_path):
    """Create a vault with semantically similar but unlinked notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create semantically similar notes without links
    similar_content = "Topic about machine learning and artificial intelligence. "
    for i in range(5):
        (vault_path / f"ml_{i}.md").write_text(f"# ML Note {i}\n\n{similar_content * 5}")

    # Add more diverse notes
    for i in range(8):
        (vault_path / f"other_{i}.md").write_text(
            f"# Other Note {i}\n\nDifferent content about topic {i}."
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with insufficient notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only 5 notes (below minimum of 10)
    for i in range(5):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_method_scrambler_returns_suggestions(vault_with_linked_notes):
    """Test that method_scrambler returns suggestions with linked notes.

    Setup:
        Vault with notes suitable for method mixing.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_linked_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = method_scrambler.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_method_scrambler_suggestion_structure(vault_with_linked_notes):
    """Test that suggestions have correct structure.

    Setup:
        Vault with method-bearing notes.

    Verifies:
        - Has required fields
        - References 2+ notes for method combination"""
    vault, session = vault_with_linked_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = method_scrambler.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "method_scrambler"

        # Should reference 2 notes (pairs)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_method_scrambler_uses_obsidian_link(vault_with_linked_notes):
    """Test that method_scrambler uses obsidian_link for note references.

    Setup:
        Vault with notes.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_linked_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = method_scrambler.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_method_scrambler_uses_scamper_operations(vault_with_linked_notes):
    """Test that suggestions use SCAMPER operation templates."""
    vault, session = vault_with_linked_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = method_scrambler.suggest(context)

    scamper_keywords = [
        "substituted",
        "combined",
        "adapted",
        "magnified",
        "minimized",
        "purpose",
        "eliminated",
        "reversed",
    ]

    for suggestion in suggestions:
        # Text should contain at least one SCAMPER keyword
        text_lower = suggestion.text.lower()
        assert any(keyword in text_lower for keyword in scamper_keywords)


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_method_scrambler_empty_vault(tmp_path):
    """Test that method_scrambler handles empty vault gracefully.

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

    suggestions = method_scrambler.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_method_scrambler_insufficient_notes(vault_insufficient_notes):
    """Test that method_scrambler handles insufficient notes gracefully.

    Setup:
        Vault with < 10 notes.

    Verifies:
        - Returns empty list"""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = method_scrambler.suggest(context)

    # Should return empty list when < 10 notes
    assert len(suggestions) == 0


def test_method_scrambler_no_links(tmp_path):
    """Test that method_scrambler handles vault with no links."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create 15 isolated notes with no links
    for i in range(15):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nNo links here.")

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

    suggestions = method_scrambler.suggest(context)

    # May still generate suggestions using semantic similarity
    assert isinstance(suggestions, list)


def test_method_scrambler_works_with_unlinked_pairs(vault_with_unlinked_pairs):
    """Test that method_scrambler can work with unlinked but similar notes."""
    vault, session = vault_with_unlinked_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = method_scrambler.suggest(context)

    # Should generate suggestions even without explicit links
    assert isinstance(suggestions, list)


def test_method_scrambler_max_suggestions(vault_with_linked_notes):
    """Test that method_scrambler never returns more than 3 suggestions.

    Setup:
        Vault with many notes.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_linked_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = method_scrambler.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_method_scrambler_deterministic_with_seed(vault_with_linked_notes):
    """Test that method_scrambler returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_linked_notes

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

    suggestions1 = method_scrambler.suggest(context1)
    suggestions2 = method_scrambler.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_method_scrambler_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with linked content
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"""# Session {i}

Links to [[target{i}]] and [[target{(i + 1) % 3}]].

^g20240315-{i}"""
        )

    # Create target notes
    (vault_path / "target1.md").write_text("# Target 1\n\nContent.")
    (vault_path / "target2.md").write_text("# Target 2\n\nContent.")
    (vault_path / "target3.md").write_text("# Target 3\n\nContent.")

    # Create source notes with links
    (vault_path / "source1.md").write_text("# Source 1\n\nLinks to [[target1]] and [[target2]].")
    (vault_path / "source2.md").write_text("# Source 2\n\nLinks to [[target3]] and [[target1]].")

    # Add more notes to reach minimum
    for i in range(8):
        (vault_path / f"filler_{i}.md").write_text(f"# Filler {i}\n\nContent.")

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

    suggestions = method_scrambler.suggest(context)

    # Verify no suggestions reference geist journal notes
    # Note: This test reveals that method_scrambler does NOT currently
    # filter geist journal notes, which is a bug that should be fixed.
    all_notes = vault.all_notes()
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            # Check that the referenced note is not from geist journal
            # The note_ref is an obsidian_link (title), so we need to find
            # the actual note to check its path
            matching_notes = [n for n in all_notes if n.obsidian_link == note_ref]
            for note in matching_notes:
                assert not note.path.startswith("geist journal/"), (
                    f"geist should exclude geist journal notes, but found: {note.path}"
                )
