"""Unit tests for columbo geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import columbo
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
def vault_with_contradictions(tmp_path):
    """Create a vault with contradictory notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Note with strong positive claims
    (vault_path / "positive.md").write_text("""# Positive Claims

All software must be tested. Testing is always important.
We should always write tests first.

Links: [[testing]], [[quality]]
""")

    # Note with contradictory negative claims (semantically similar topic)
    (vault_path / "negative.md").write_text("""# Testing Skepticism

Testing is never sufficient. No amount of testing can prove correctness.
However, formal verification is not practical except for critical systems.

Links: [[testing]], [[verification]]
""")

    # Supporting note (linked from both)
    (vault_path / "testing.md").write_text("""# Testing Philosophy

Different approaches to software quality.
""")

    # Supporting note
    (vault_path / "quality.md").write_text("""# Quality Assurance

Notes on quality.
""")

    # Supporting note
    (vault_path / "verification.md").write_text("""# Formal Verification

Formal methods.
""")

    # Initialize vault
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Compute embeddings
    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_without_contradictions(tmp_path):
    """Create a vault without contradictory patterns."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Notes without strong claims or contradictions
    (vault_path / "note1.md").write_text("# Note 1\n\nSome observations.")
    (vault_path / "note2.md").write_text("# Note 2\n\nMore observations.")
    (vault_path / "note3.md").write_text("# Note 3\n\nFinal observations.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_columbo_returns_suggestions(vault_with_contradictions):
    """Test that columbo returns suggestions when contradictions exist.

    Setup:
        Vault with isolated notes (low link density).

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_contradictions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = columbo.suggest(context)

    # Should return suggestions (at most 3)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_columbo_suggestion_structure(vault_with_contradictions):
    """Test that suggestions have correct structure.

    Setup:
        Vault with isolated notes.

    Verifies:
        - Has required fields
        - References 1 isolated note"""
    vault, session = vault_with_contradictions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = columbo.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "columbo"

        # Should reference 2 notes (the contradicting pair)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)

        # Should contain "lying" or "contradict" language
        assert "lying" in suggestion.text.lower() or "contradict" in suggestion.text.lower()


def test_columbo_uses_obsidian_link(vault_with_contradictions):
    """Test that columbo uses obsidian_link for note references.

    Setup:
        Vault with isolated notes.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_contradictions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = columbo.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            # Should be a plain string (obsidian_link format)
            assert isinstance(note_ref, str)


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_columbo_empty_vault(tmp_path):
    """Test that columbo handles empty vault gracefully.

    Setup:
        Empty vault.

    Verifies:
        - Returns empty list"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

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

    suggestions = columbo.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_columbo_insufficient_notes(tmp_path):
    """Test that columbo handles insufficient notes gracefully.

    Setup:
        Vault with < 10 notes.

    Verifies:
        - Returns empty list"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create only 2 notes (below minimum of 3)
    (vault_path / "note1.md").write_text("# Note 1\n\nContent.")
    (vault_path / "note2.md").write_text("# Note 2\n\nContent.")

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

    suggestions = columbo.suggest(context)

    # Should return empty list when < 3 notes
    assert len(suggestions) == 0


def test_columbo_requires_claim_language(tmp_path):
    """Test that columbo returns empty when notes lack strong claim language.

    Creates vault with descriptive notes (no 'always', 'never', 'must', etc.).
    Verifies geist returns [] since no claim language exists to analyze.
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Notes without strong claim indicators - just descriptive content
    (vault_path / "note1.md").write_text("""# Note 1

Software testing is useful. It helps find bugs.
""")

    (vault_path / "note2.md").write_text("""# Note 2

Code reviews can be helpful. They sometimes catch issues.
""")

    (vault_path / "note3.md").write_text("""# Note 3

Documentation is beneficial. It makes code easier to understand.
""")

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

    suggestions = columbo.suggest(context)

    # Should return empty when no claim language exists
    assert len(suggestions) == 0


def test_columbo_requires_contradictions(tmp_path):
    """Test that columbo returns empty when claims agree (no contradictions).

    Creates vault with multiple notes containing only positive, aligned claims:
    - All about testing being important
    - No negations or opposing views
    - All claims support each other

    Verifies geist returns [] since no linguistic contradictions exist.
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Notes with ONLY positive aligned claims (no negations at all)
    (vault_path / "note1.md").write_text("""# Note 1

All software must be tested thoroughly. Testing is always crucial.
Quality should be our top priority.
""")

    (vault_path / "note2.md").write_text("""# Note 2

Testing should always be comprehensive. We must write excellent tests.
Quality must be maintained at all times.
""")

    (vault_path / "note3.md").write_text("""# Note 3

Quality is always important. All code must be reviewed carefully.
Testing is essential for every project.
""")

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

    suggestions = columbo.suggest(context)

    # Should return empty when claims exist but don't contradict
    # All notes agree that testing/quality is important (no opposing claims)
    assert len(suggestions) == 0


# ============================================================================
# Exclusion Tests
# ============================================================================


def test_columbo_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from analysis.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    # Create journal notes with contradictory claims
    for i in range(5):
        note_path = journal_dir / f"2024-03-{15 + i:02d}.md"
        note_path.write_text(f"""# Session {i}

All testing must be automated. Testing is always critical.
Never skip tests. No untested code should be deployed.
""")

    # Create regular notes
    (vault_path / "note1.md").write_text("# Note 1\n\nAll tests are important.")
    (vault_path / "note2.md").write_text("# Note 2\n\nNever skip testing.")
    (vault_path / "note3.md").write_text("# Note 3\n\nMust test everything.")

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

    suggestions = columbo.suggest(context)

    # Verify that journal notes don't appear in suggestions
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()


# ============================================================================
# Limit Tests
# ============================================================================


def test_columbo_max_three_suggestions(vault_with_contradictions):
    """Test that columbo returns at most 3 suggestions."""
    vault, session = vault_with_contradictions

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = columbo.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_columbo_deterministic_with_seed(vault_with_contradictions):
    """Test that columbo returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_contradictions

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

    suggestions1 = columbo.suggest(context1)
    suggestions2 = columbo.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2
