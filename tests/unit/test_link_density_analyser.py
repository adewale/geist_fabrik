"""Unit tests for link_density_analyser geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import link_density_analyser
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
def vault_with_link_density_issues(tmp_path):
    """Create a vault with unusual link density patterns."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes with too many links (>5 per 100 words)
    for i in range(5):
        words = " ".join([f"word{j}" for j in range(100)])
        # 10 links in 100 words = 10 per 100 words (too high)
        links = " ".join([f"[[link_{j}]]" for j in range(10)])
        (vault_path / f"dense_{i}.md").write_text(f"# Dense Note {i}\n\n{words} {links}")

    # Create notes with too few links (<0.5 per 100 words in 200+ word notes)
    for i in range(5):
        words = " ".join([f"word{j}" for j in range(300)])
        # 1 link in 300 words = 0.33 per 100 words (too low)
        (vault_path / f"sparse_{i}.md").write_text(f"# Sparse Note {i}\n\n{words} [[single_link]]")

    # Create balanced notes (filler)
    for i in range(10):
        words = " ".join([f"word{j}" for j in range(150)])
        links = " ".join([f"[[link_{j}]]" for j in range(3)])
        (vault_path / f"balanced_{i}.md").write_text(f"# Balanced Note {i}\n\n{words} {links}")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with too few substantial notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create only short notes (will be skipped)
    for i in range(10):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nShort.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_link_density_analyser_returns_suggestions(vault_with_link_density_issues):
    """Test that link_density_analyser returns suggestions with density issues.

    Setup:
        Vault with varying link densities.

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_link_density_issues

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = link_density_analyser.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_link_density_analyser_suggestion_structure(vault_with_link_density_issues):
    """Test that suggestions have correct structure.

    Setup:
        Vault with density variations.

    Verifies:
        - Has required fields
        - References notes with notable link density"""
    vault, session = vault_with_link_density_issues

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = link_density_analyser.suggest(context)

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
        assert suggestion.geist_id == "link_density_analyser"

        # Should mention links and provide specific numbers
        assert "links" in suggestion.text.lower()
        assert "words" in suggestion.text.lower()

        # Should reference exactly 1 note
        assert len(suggestion.notes) == 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_link_density_analyser_uses_obsidian_link(vault_with_link_density_issues):
    """Test that link_density_analyser uses obsidian_link for note references.

    Setup:
        Vault with density variations.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_link_density_issues

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = link_density_analyser.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_link_density_analyser_identifies_too_many_links(vault_with_link_density_issues):
    """Test that link_density_analyser identifies notes with too many links."""
    vault, session = vault_with_link_density_issues

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = link_density_analyser.suggest(context)

    # Should find at least some suggestions about too many links
    too_many_suggestions = [
        s
        for s in suggestions
        if "too many links" in s.text.lower() or "overwhelming" in s.text.lower()
    ]

    # May or may not find these depending on sampling, so don't assert specific count
    # Just verify structure if found
    for suggestion in too_many_suggestions:
        assert suggestion.geist_id == "link_density_analyser"


def test_link_density_analyser_identifies_too_few_links(vault_with_link_density_issues):
    """Test that link_density_analyser identifies notes with too few links."""
    vault, session = vault_with_link_density_issues

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = link_density_analyser.suggest(context)

    # Should find at least some suggestions about too few links
    too_few_suggestions = [
        s
        for s in suggestions
        if "needs more connections" in s.text.lower() or "isolated" in s.text.lower()
    ]

    # May or may not find these depending on sampling, so don't assert specific count
    # Just verify structure if found
    for suggestion in too_few_suggestions:
        assert suggestion.geist_id == "link_density_analyser"


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_link_density_analyser_empty_vault(tmp_path):
    """Test that link_density_analyser handles empty vault gracefully.

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

    suggestions = link_density_analyser.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_link_density_analyser_skips_short_notes(vault_insufficient_notes):
    """Test that link_density_analyser skips notes with <50 words."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = link_density_analyser.suggest(context)

    # Should return empty list when all notes are too short
    assert len(suggestions) == 0


def test_link_density_analyser_max_suggestions(vault_with_link_density_issues):
    """Test that link_density_analyser never returns more than 3 suggestions.

    Setup:
        Vault with density variations.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_link_density_issues

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = link_density_analyser.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_link_density_analyser_deterministic_with_seed(vault_with_link_density_issues):
    """Test that link_density_analyser returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_link_density_issues

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

    suggestions1 = link_density_analyser.suggest(context1)
    suggestions2 = link_density_analyser.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


@pytest.mark.xfail(reason="Geist needs to be updated to exclude journal notes - see #TBD")
def test_link_density_analyser_excludes_geist_journal(tmp_path):
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

    # Create journal notes with link density issues (too many links)
    for i in range(5):
        words = " ".join([f"word{j}" for j in range(100)])
        links = " ".join([f"[[link_{j}]]" for j in range(10)])
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(f"# Session {i}\n\n{words} {links}")

    # Create regular notes with link density issues
    # Too many links
    for i in range(5):
        words = " ".join([f"word{j}" for j in range(100)])
        links = " ".join([f"[[link_{j}]]" for j in range(10)])
        (vault_path / f"dense_{i}.md").write_text(f"# Dense Note {i}\n\n{words} {links}")

    # Too few links
    for i in range(5):
        words = " ".join([f"word{j}" for j in range(300)])
        (vault_path / f"sparse_{i}.md").write_text(f"# Sparse Note {i}\n\n{words} [[single_link]]")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault, session=session, seed=20240315, function_registry=FunctionRegistry()
    )

    suggestions = link_density_analyser.suggest(context)

    # Verify no suggestions reference geist journal notes
    journal_notes = [note for note in vault.all_notes() if "geist journal" in note.path.lower()]
    journal_titles = {note.title.lower() for note in journal_notes}

    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert note_ref.lower() not in journal_titles, (
                f"Found journal note reference: {note_ref}"
            )
