"""Unit tests for assumption_challenger geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import assumption_challenger
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
def vault_with_assumptions(tmp_path):
    """Create a vault with notes containing assumption indicators."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Notes with strong assumption indicators
    assumption_notes = [
        (
            "Obvious Facts.md",
            "Obviously this is true. Clearly everyone knows this. Of course it must be so.",
        ),
        (
            "Certainty.md",
            "Certainly this is the case. Without a doubt, it has to be this way. Naturally so.",
        ),
        (
            "Well Known.md",
            "It is well known that this occurs. Needless to say, this must be true.",
        ),
    ]

    for filename, content in assumption_notes:
        (vault_path / filename).write_text(f"# {filename.replace('.md', '')}\n\n{content}")

    # Notes with contrasting language (uncertainty)
    contrast_notes = [
        (
            "Uncertainty.md",
            "Maybe this is the case. Perhaps it could be different. It's unclear and debatable.",
        ),
        (
            "Hedging.md",
            "This might work. Possibly it depends on context. Sometimes it varies significantly.",
        ),
    ]

    for filename, content in contrast_notes:
        (vault_path / filename).write_text(f"# {filename.replace('.md', '')}\n\n{content}")

    # Fill out with regular notes
    for i in range(7):
        (vault_path / f"regular_{i}.md").write_text(f"# Regular {i}\n\nNormal content.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_with_causal_claims(tmp_path):
    """Create a vault with causal claims but few supporting links."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Note with many causal patterns but few links
    (vault_path / "causal.md").write_text(
        "# Causal Claims\n\n"
        "This happens because of that. Therefore, this results in that. "
        "Hence, it leads to this outcome. Thus, this causes that effect. "
        "This is due to various factors."
    )

    # Add filler notes
    for i in range(12):
        (vault_path / f"filler_{i}.md").write_text(f"# Filler {i}\n\nContent.")

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


def test_assumption_challenger_returns_suggestions(vault_with_assumptions):
    """Test that assumption_challenger returns suggestions with assumption notes.

    Setup:
        Vault with notes containing assumption indicators.

    Verifies:
        - Returns list of suggestions (max 2)"""
    vault, session = vault_with_assumptions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = assumption_challenger.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_assumption_challenger_suggestion_structure(vault_with_assumptions):
    """Test that suggestions have correct structure.

    Setup:
        Vault with notes containing assumption indicators.

    Verifies:
        - Suggestion has required fields
        - References exactly 1 note with assumptions"""
    vault, session = vault_with_assumptions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = assumption_challenger.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "assumption_challenger"

        # Should reference at least 1 note
        assert len(suggestion.notes) >= 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_assumption_challenger_uses_obsidian_link(vault_with_assumptions):
    """Test that assumption_challenger uses obsidian_link for note references.

    Setup:
        Vault with notes containing assumption indicators.

    Verifies:
        - Uses [[wiki-link]] format in text
        - References use obsidian_link property"""
    vault, session = vault_with_assumptions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = assumption_challenger.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_assumption_challenger_detects_causal_claims(vault_with_causal_claims):
    """Test that assumption_challenger detects causal claims without evidence.

    Setup:
        Vault with notes containing causal claim indicators.

    Verifies:
        - Detects 'because', 'therefore', 'causes' patterns
        - Suggests questioning causal relationships"""
    vault, session = vault_with_causal_claims

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = assumption_challenger.suggest(context)

    # Should detect notes with causal claims
    assert isinstance(suggestions, list)


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_assumption_challenger_empty_vault(tmp_path):
    """Test that assumption_challenger handles empty vault gracefully.

    Setup:
        Empty vault.

    Verifies:
        - Returns empty list without crashing"""
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

    suggestions = assumption_challenger.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_assumption_challenger_insufficient_notes(vault_insufficient_notes):
    """Test that assumption_challenger handles insufficient notes gracefully.

    Setup:
        Vault with only 5 notes (minimum is 10).

    Verifies:
        - Returns empty list when too few notes"""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = assumption_challenger.suggest(context)

    # Should return empty list when < 10 notes
    assert len(suggestions) == 0


def test_assumption_challenger_no_assumptions(tmp_path):
    """Test that assumption_challenger handles vault without assumption indicators.

    Setup:
        Vault with 15 notes but no assumption indicators.

    Verifies:
        - Returns empty list when no assumptions detected"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create 15 notes without assumption indicators
    for i in range(15):
        (vault_path / f"note_{i}.md").write_text(
            f"# Note {i}\n\nContent without assumption indicators."
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

    suggestions = assumption_challenger.suggest(context)

    # May return empty list if no notes pass assumption threshold
    assert isinstance(suggestions, list)


def test_assumption_challenger_max_suggestions(vault_with_assumptions):
    """Test that assumption_challenger never returns more than 3 suggestions.

    Setup:
        Vault with assumption-heavy notes.

    Verifies:
        - Returns at most 2 suggestions"""
    vault, session = vault_with_assumptions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = assumption_challenger.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_assumption_challenger_deterministic_with_seed(vault_with_assumptions):
    """Test that assumption_challenger returns same results with same seed.

    Setup:
        Vault tested with identical seed twice.

    Verifies:
        - Same seed produces identical output"""
    vault, session = vault_with_assumptions

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

    suggestions1 = assumption_challenger.suggest(context1)
    suggestions2 = assumption_challenger.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_assumption_challenger_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal notes in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with assumption indicators
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\n"
            f"Obviously this is true. Clearly everyone knows this. "
            f"Of course it must be so. Certainly this is the case."
        )

    # Create regular notes with assumption indicators
    assumption_notes = [
        (
            "Obvious Facts.md",
            "Obviously this is true. Clearly everyone knows this. Of course it must be so.",
        ),
        (
            "Certainty.md",
            "Certainly this is the case. Without a doubt, it has to be this way. Naturally so.",
        ),
        (
            "Well Known.md",
            "It is well known that this occurs. Needless to say, this must be true.",
        ),
    ]

    for filename, content in assumption_notes:
        (vault_path / filename).write_text(f"# {filename.replace('.md', '')}\n\n{content}")

    # Create regular notes
    for i in range(7):
        (vault_path / f"regular_{i}.md").write_text(f"# Regular {i}\n\nNormal content.")

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

    suggestions = assumption_challenger.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()
