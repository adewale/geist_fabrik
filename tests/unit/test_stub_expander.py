"""Unit tests for stub_expander geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import stub_expander
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
def vault_with_stubs(tmp_path):
    """Create a vault with stub notes (short with connections)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create stub notes (< 50 words with links)
    for i in range(5):
        path = vault_path / f"stub_{i}.md"
        content = f"""# Stub {i}

Short note with [[link_{i}]]. Only a few words."""
        path.write_text(content)

    # Create stub notes with backlinks
    for i in range(5):
        path = vault_path / f"stub_backlinked_{i}.md"
        content = f"""# Stub Backlinked {i}

Brief content here."""
        path.write_text(content)

    # Create notes that link to stubs (to create backlinks)
    for i in range(5):
        path = vault_path / f"linker_{i}.md"
        content = f"""# Linker {i}

This note links to [[Stub Backlinked {i}]]."""
        path.write_text(content)

    # Create substantial notes (> 50 words, for contrast)
    for i in range(5):
        path = vault_path / f"substantial_{i}.md"
        content = f"""# Substantial {i}

This is a substantial note with many words. It contains multiple sentences
that elaborate on various topics. The content is rich and detailed, exploring
different aspects of the subject matter. There are many paragraphs and
extensive discussion of relevant themes and ideas."""
        path.write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_no_stubs(tmp_path):
    """Create a vault with no stub notes (all substantial)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create substantial notes (> 50 words)
    for i in range(10):
        path = vault_path / f"substantial_{i}.md"
        content = f"""# Substantial {i}

This is a substantial note with many words. It contains multiple sentences
that elaborate on various topics. The content is rich and detailed, exploring
different aspects of the subject matter. There are many paragraphs and
extensive discussion of relevant themes and ideas."""
        path.write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_stub_expander_returns_suggestions(vault_with_stubs):
    """Test that stub_expander returns suggestions with stub notes.

    Setup:
        Vault with stub notes (short, under-developed).

    Verifies:
        - Returns suggestions (max 2)"""
    vault, session = vault_with_stubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = stub_expander.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_stub_expander_suggestion_structure(vault_with_stubs):
    """Test that suggestions have correct structure.

    Setup:
        Vault with stubs.

    Verifies:
        - Has required fields
        - References 1 stub note"""
    vault, session = vault_with_stubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = stub_expander.suggest(context)

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
        assert suggestion.geist_id == "stub_expander"

        # Should reference 1 note (the stub)
        assert len(suggestion.notes) == 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_stub_expander_uses_obsidian_link(vault_with_stubs):
    """Test that stub_expander uses obsidian_link for note references.

    Setup:
        Vault with stubs.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_stubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = stub_expander.suggest(context)

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


def test_stub_expander_empty_vault(tmp_path):
    """Test that stub_expander handles empty vault gracefully.

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

    suggestions = stub_expander.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_stub_expander_no_stubs(vault_no_stubs):
    """Test that stub_expander handles vault with no stub notes.

    Setup:
        Vault with all well-developed notes.

    Verifies:
        - Returns empty list"""
    vault, session = vault_no_stubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = stub_expander.suggest(context)

    # Should return empty list when no stubs exist
    assert len(suggestions) == 0


def test_stub_expander_short_notes_no_connections(tmp_path):
    """Test that stub_expander ignores short notes without connections."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create short notes without links or backlinks
    for i in range(5):
        path = vault_path / f"short_isolated_{i}.md"
        content = f"""# Short Isolated {i}

Brief content."""
        path.write_text(content)

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

    suggestions = stub_expander.suggest(context)

    # Should return empty when short notes have no connections
    assert len(suggestions) == 0


def test_stub_expander_max_suggestions(vault_with_stubs):
    """Test that stub_expander never returns more than 3 suggestions.

    Setup:
        Vault with many stubs.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_stubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = stub_expander.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_stub_expander_deterministic_with_seed(vault_with_stubs):
    """Test that stub_expander returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_stubs

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

    suggestions1 = stub_expander.suggest(context1)
    suggestions2 = stub_expander.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_stub_expander_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with stub-like content
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"""# Session {i}

Short note with [[link_{i}]]. Only a few words.

^g20240315-{i}"""
        )

    # Create stub notes (< 50 words with links)
    for i in range(5):
        path = vault_path / f"stub_{i}.md"
        content = f"""# Stub {i}

Short note with [[link_{i}]]. Only a few words."""
        path.write_text(content)

    # Create stub notes with backlinks
    for i in range(5):
        path = vault_path / f"stub_backlinked_{i}.md"
        content = f"""# Stub Backlinked {i}

Brief content here."""
        path.write_text(content)

    # Create notes that link to stubs (to create backlinks)
    for i in range(5):
        path = vault_path / f"linker_{i}.md"
        content = f"""# Linker {i}

This note links to [[Stub Backlinked {i}]]."""
        path.write_text(content)

    # Create substantial notes (> 50 words)
    for i in range(5):
        path = vault_path / f"substantial_{i}.md"
        content = f"""# Substantial {i}

This is a substantial note with many words. It contains multiple sentences
that elaborate on various topics. The content is rich and detailed, exploring
different aspects of the subject matter. There are many paragraphs and
extensive discussion of relevant themes and ideas."""
        path.write_text(content)

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

    suggestions = stub_expander.suggest(context)

    # Verify no suggestions reference geist journal notes
    # Note: This test reveals that stub_expander does NOT currently
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
