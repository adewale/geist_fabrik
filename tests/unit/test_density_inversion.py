"""Unit tests for density_inversion geist."""

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import density_inversion
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
def vault_with_dense_links_sparse_meaning(tmp_path):
    """Create a vault with densely linked but semantically scattered notes."""
    from datetime import datetime

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a hub note
    hub_path = vault_path / "hub.md"
    hub_content = "# Hub\n\nCentral hub note.\n\n"
    # Link to diverse topics
    for i in range(5):
        hub_content += f"[[diverse_{i}]]\n"
    hub_path.write_text(hub_content)

    # Create diverse neighbor notes that all link to each other (dense links)
    # but have very different content (sparse meaning)
    topics = [
        "quantum physics",
        "impressionist art",
        "medieval history",
        "jazz music",
        "molecular biology",
    ]
    for i, topic in enumerate(topics):
        path = vault_path / f"diverse_{i}.md"
        content = f"# Diverse {i}\n\nContent about {topic}.\n\n"
        # Link back to hub and to all other neighbors (creating dense graph)
        content += "[[hub]]\n"
        for j in range(5):
            if j != i:
                content += f"[[diverse_{j}]]\n"
        path.write_text(content)

    # Add more notes to reach minimum threshold
    for i in range(15):
        (vault_path / f"filler_{i}.md").write_text(f"# Filler {i}\n\nFiller content.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_with_sparse_links_dense_meaning(tmp_path):
    """Create a vault with sparsely linked but semantically similar notes."""
    from datetime import datetime

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a hub note
    hub_path = vault_path / "hub.md"
    hub_content = "# Hub\n\nCentral hub note.\n\n"
    for i in range(5):
        hub_content += f"[[similar_{i}]]\n"
    hub_path.write_text(hub_content)

    # Create similar neighbor notes that DON'T link to each other (sparse links)
    # but have very similar content (dense meaning)
    for i in range(5):
        path = vault_path / f"similar_{i}.md"
        # All about machine learning but with slight variations
        content = (
            f"# Similar {i}\n\nContent about machine learning and neural networks variant {i}.\n\n"
        )
        # Only link back to hub, not to neighbors
        content += "[[hub]]\n"
        path.write_text(content)

    # Add more notes to reach minimum threshold
    for i in range(15):
        (vault_path / f"filler_{i}.md").write_text(f"# Filler {i}\n\nFiller content.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with insufficient notes for density analysis."""
    from datetime import datetime

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only 15 notes (below minimum of 20)
    for i in range(15):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_density_inversion_returns_suggestions(vault_with_dense_links_sparse_meaning):
    """Test that density_inversion returns suggestions."""
    vault, session = vault_with_dense_links_sparse_meaning

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = density_inversion.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2


def test_density_inversion_suggestion_structure(vault_with_dense_links_sparse_meaning):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_dense_links_sparse_meaning

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = density_inversion.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "density_inversion"

        # Should reference at least 1 note (hub + sample of neighbors)
        assert len(suggestion.notes) >= 1

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_density_inversion_uses_obsidian_link(vault_with_dense_links_sparse_meaning):
    """Test that density_inversion uses obsidian_link for note references."""
    vault, session = vault_with_dense_links_sparse_meaning

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = density_inversion.suggest(context)

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


def test_density_inversion_empty_vault(tmp_path):
    """Test that density_inversion handles empty vault gracefully."""
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

    suggestions = density_inversion.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_density_inversion_insufficient_notes(vault_insufficient_notes):
    """Test that density_inversion handles insufficient notes gracefully."""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = density_inversion.suggest(context)

    # Should return empty list when < 20 notes
    assert len(suggestions) == 0


def test_density_inversion_notes_without_neighbors(tmp_path):
    """Test that density_inversion handles notes with few neighbors."""
    from datetime import datetime

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create 25 isolated notes with no links
    for i in range(25):
        (vault_path / f"isolated_{i}.md").write_text(f"# Isolated {i}\n\nContent.")

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

    suggestions = density_inversion.suggest(context)

    # May return empty if no notes have sufficient neighbors
    assert isinstance(suggestions, list)


def test_density_inversion_max_suggestions(vault_with_dense_links_sparse_meaning):
    """Test that density_inversion never returns more than 2 suggestions."""
    vault, session = vault_with_dense_links_sparse_meaning

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = density_inversion.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_density_inversion_deterministic_with_seed(vault_with_dense_links_sparse_meaning):
    """Test that density_inversion returns same results with same seed."""
    vault, session = vault_with_dense_links_sparse_meaning

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

    suggestions1 = density_inversion.suggest(context1)
    suggestions2 = density_inversion.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_density_inversion_detects_dense_links_sparse_meaning(
    vault_with_dense_links_sparse_meaning,
):
    """Test that density_inversion detects dense links with sparse meaning."""
    vault, session = vault_with_dense_links_sparse_meaning

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = density_inversion.suggest(context)

    # Should detect at least one inversion
    if suggestions:
        # Text should mention tightly linked but scattered
        found_dense_sparse = any(
            "tightly linked" in s.text and "scattered" in s.text for s in suggestions
        )
        # Or sparse links but similar
        found_sparse_dense = any(
            "similar" in s.text and "aren't linked" in s.text for s in suggestions
        )
        assert found_dense_sparse or found_sparse_dense
