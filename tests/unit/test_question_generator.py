"""Unit tests for question_generator geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import question_generator
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
def vault_with_declarative_notes(tmp_path):
    """Create a vault with declarative notes (not questions)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Declarative notes with substantial content (>50 words)
    declarative_content = "This is a declarative statement about a topic. " * 10  # ~80 words

    declarative_notes = [
        "Technology Adoption",
        "Market Dynamics",
        "Learning Process",
        "Innovation Patterns",
        "Social Behavior",
    ]

    for title in declarative_notes:
        (vault_path / f"{title}.md").write_text(f"# {title}\n\n{declarative_content}")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_with_questions(tmp_path):
    """Create a vault with notes that are already questions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    question_notes = [
        "Why does this happen?",
        "How can we improve?",
        "What if we tried differently?",
    ]

    for title in question_notes:
        (vault_path / f"{title}.md").write_text(f"# {title}\n\nSome content here.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_with_short_notes(tmp_path):
    """Create a vault with notes too short to generate questions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Notes with <50 words
    for i in range(5):
        (vault_path / f"short_{i}.md").write_text(f"# Short Note {i}\n\nBrief.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_question_generator_returns_suggestions(vault_with_declarative_notes):
    """Test that question_generator returns suggestions with declarative notes."""
    vault, session = vault_with_declarative_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = question_generator.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_question_generator_suggestion_structure(vault_with_declarative_notes):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_declarative_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = question_generator.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "question_generator"

        # Should reference 1 note
        assert len(suggestion.notes) == 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_question_generator_uses_obsidian_link(vault_with_declarative_notes):
    """Test that question_generator uses obsidian_link for note references."""
    vault, session = vault_with_declarative_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = question_generator.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_question_generator_suggests_question_titles(vault_with_declarative_notes):
    """Test that question_generator suggests question-based titles."""
    vault, session = vault_with_declarative_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = question_generator.suggest(context)

    # All suggestions should have title field
    for suggestion in suggestions:
        assert hasattr(suggestion, "title")
        assert suggestion.title is not None
        # Title should end with question mark
        assert suggestion.title.endswith("?")


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_question_generator_empty_vault(tmp_path):
    """Test that question_generator handles empty vault gracefully."""
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

    suggestions = question_generator.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_question_generator_skips_existing_questions(vault_with_questions):
    """Test that question_generator skips notes that are already questions."""
    vault, session = vault_with_questions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = question_generator.suggest(context)

    # Should return empty list since all notes are already questions
    assert len(suggestions) == 0


def test_question_generator_skips_short_notes(vault_with_short_notes):
    """Test that question_generator skips notes with <50 words."""
    vault, session = vault_with_short_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = question_generator.suggest(context)

    # Should return empty list since all notes are too short
    assert len(suggestions) == 0


def test_question_generator_max_suggestions(vault_with_declarative_notes):
    """Test that question_generator never returns more than 3 suggestions."""
    vault, session = vault_with_declarative_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = question_generator.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_question_generator_deterministic_with_seed(vault_with_declarative_notes):
    """Test that question_generator returns same results with same seed."""
    vault, session = vault_with_declarative_notes

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

    suggestions1 = question_generator.suggest(context1)
    suggestions2 = question_generator.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2
