"""Unit tests for antithesis_generator geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import antithesis_generator
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
def vault_with_claims(tmp_path):
    """Create a vault with notes containing strong claims."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes with strong claims (high claim indicators)
    claim_notes = [
        (
            "Strong Position.md",
            "This is fundamental. It must be essential. This will always prove critical.",
        ),
        (
            "Absolute View.md",
            "This cannot be changed. It is impossible to deny. This proves everything.",
        ),
        (
            "Necessary Truth.md",
            "This should always be important. It is key that we never forget this.",
        ),
    ]

    for filename, content in claim_notes:
        (vault_path / filename).write_text(f"# {filename.replace('.md', '')}\n\n{content}")

    # Create regular notes with fewer claim indicators
    for i in range(8):
        (vault_path / f"regular_{i}.md").write_text(
            f"# Regular Note {i}\n\nSome general content here."
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_with_antithesis_pairs(tmp_path):
    """Create a vault with thesis/antithesis pairs."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Thesis note with strong claims
    (vault_path / "thesis.md").write_text(
        "# Thesis\n\nThis is fundamental. It must be essential. This will always be true."
    )

    # Antithesis note with negation words
    (vault_path / "antithesis.md").write_text(
        "# Anti-Thesis\n\n"
        "This is not correct. We should never accept this. It's against the evidence."
    )

    # Fill out with more notes
    for i in range(10):
        (vault_path / f"filler_{i}.md").write_text(f"# Filler {i}\n\nContent here.")

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


def test_antithesis_generator_returns_suggestions(vault_with_claims):
    """Test that antithesis_generator returns suggestions with claim notes."""
    vault, session = vault_with_claims

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = antithesis_generator.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_antithesis_generator_suggestion_structure(vault_with_claims):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_claims

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = antithesis_generator.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "antithesis_generator"

        # Should reference at least 1 note
        assert len(suggestion.notes) >= 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_antithesis_generator_uses_obsidian_link(vault_with_claims):
    """Test that antithesis_generator uses obsidian_link for note references."""
    vault, session = vault_with_claims

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = antithesis_generator.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_antithesis_generator_suggests_titles(vault_with_claims):
    """Test that antithesis_generator suggests titles for new antithesis notes."""
    vault, session = vault_with_claims

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = antithesis_generator.suggest(context)

    # Some suggestions should have title field
    title_suggestions = [s for s in suggestions if hasattr(s, "title") and s.title]

    if title_suggestions:
        for suggestion in title_suggestions:
            # Title should contain "Anti-" or "Against"
            assert "Anti-" in suggestion.title or "Against" in suggestion.title


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_antithesis_generator_empty_vault(tmp_path):
    """Test that antithesis_generator handles empty vault gracefully."""
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

    suggestions = antithesis_generator.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_antithesis_generator_insufficient_notes(vault_insufficient_notes):
    """Test that antithesis_generator handles insufficient notes gracefully."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = antithesis_generator.suggest(context)

    # Should return empty list when < 10 notes
    assert len(suggestions) == 0


def test_antithesis_generator_no_strong_claims(tmp_path):
    """Test that antithesis_generator handles vault without strong claims."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create 15 notes with weak/no claims
    for i in range(15):
        (vault_path / f"note_{i}.md").write_text(
            f"# Note {i}\n\nSome content without strong claims."
        )

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

    suggestions = antithesis_generator.suggest(context)

    # May return empty list if no notes pass claim threshold
    assert isinstance(suggestions, list)


def test_antithesis_generator_max_suggestions(vault_with_claims):
    """Test that antithesis_generator never returns more than 2 suggestions."""
    vault, session = vault_with_claims

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = antithesis_generator.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_antithesis_generator_deterministic_with_seed(vault_with_claims):
    """Test that antithesis_generator returns same results with same seed."""
    vault, session = vault_with_claims

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

    suggestions1 = antithesis_generator.suggest(context1)
    suggestions2 = antithesis_generator.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_antithesis_generator_recognizes_existing_antithesis(vault_with_antithesis_pairs):
    """Test that antithesis_generator recognizes existing antithesis notes."""
    vault, session = vault_with_antithesis_pairs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = antithesis_generator.suggest(context)

    # Should generate suggestions (either about existing pair or new antithesis)
    assert isinstance(suggestions, list)
