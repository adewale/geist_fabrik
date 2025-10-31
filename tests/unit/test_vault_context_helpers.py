"""Tests for VaultContext helper functions (has_link, graph_neighbors)."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.embeddings import Session
from geistfabrik.models import Note
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


@pytest.fixture
def temp_vault():
    """Create a temporary vault with test notes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create test notes with links
        # Note A links to B
        (vault_path / "note_a.md").write_text("# Note A\n\nLinks to [[note_b]]")

        # Note B links to A (bidirectional)
        (vault_path / "note_b.md").write_text("# Note B\n\nLinks to [[note_a]]")

        # Note C links to A (unidirectional)
        (vault_path / "note_c.md").write_text("# Note C\n\nLinks to [[note_a]]")

        # Note D has no links (orphan)
        (vault_path / "note_d.md").write_text("# Note D\n\nNo links here")

        yield vault_path


@pytest.fixture
def vault_context(temp_vault):
    """Create VaultContext with test vault."""
    vault = Vault(temp_vault)
    vault.sync()

    # Create session with embeddings
    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())

    return VaultContext(vault, session)


def test_has_link_bidirectional(vault_context):
    """Test has_link returns True for bidirectional links."""
    note_a = vault_context.get_note("note_a.md")
    note_b = vault_context.get_note("note_b.md")

    assert note_a is not None
    assert note_b is not None

    # Should detect link in both directions
    assert vault_context.has_link(note_a, note_b)
    assert vault_context.has_link(note_b, note_a)


def test_has_link_unidirectional(vault_context):
    """Test has_link returns True for unidirectional links."""
    note_a = vault_context.get_note("note_a.md")
    note_c = vault_context.get_note("note_c.md")

    assert note_a is not None
    assert note_c is not None

    # C links to A, so should detect in both directions
    assert vault_context.has_link(note_c, note_a)
    assert vault_context.has_link(note_a, note_c)


def test_has_link_returns_false(vault_context):
    """Test has_link returns False for unlinked notes."""
    note_b = vault_context.get_note("note_b.md")
    note_d = vault_context.get_note("note_d.md")

    assert note_b is not None
    assert note_d is not None

    # No link between B and D
    assert not vault_context.has_link(note_b, note_d)
    assert not vault_context.has_link(note_d, note_b)


def test_graph_neighbors_includes_outgoing(vault_context):
    """Test graph_neighbors includes notes linked to."""
    note_a = vault_context.get_note("note_a.md")
    note_b = vault_context.get_note("note_b.md")

    assert note_a is not None
    assert note_b is not None

    neighbors_a = vault_context.graph_neighbors(note_a)

    # A links to B, so B should be in neighbors
    assert note_b in neighbors_a


def test_graph_neighbors_includes_backlinks(vault_context):
    """Test graph_neighbors includes notes linking to this note."""
    note_a = vault_context.get_note("note_a.md")
    note_c = vault_context.get_note("note_c.md")

    assert note_a is not None
    assert note_c is not None

    neighbors_a = vault_context.graph_neighbors(note_a)

    # C links to A, so C should be in neighbors (backlink)
    assert note_c in neighbors_a


def test_graph_neighbors_deduplicates(vault_context):
    """Test bidirectional links don't appear twice."""
    note_a = vault_context.get_note("note_a.md")
    note_b = vault_context.get_note("note_b.md")

    assert note_a is not None
    assert note_b is not None

    neighbors_a = vault_context.graph_neighbors(note_a)

    # B should appear only once even though A→B and B→A
    assert neighbors_a.count(note_b) == 1


def test_graph_neighbors_bidirectional(vault_context):
    """Test graph_neighbors returns same set for bidirectionally linked notes."""
    note_a = vault_context.get_note("note_a.md")
    note_b = vault_context.get_note("note_b.md")

    assert note_a is not None
    assert note_b is not None

    neighbors_a = vault_context.graph_neighbors(note_a)
    neighbors_b = vault_context.graph_neighbors(note_b)

    # A should be in B's neighbors
    assert note_a in neighbors_b

    # B should be in A's neighbors
    assert note_b in neighbors_a


def test_graph_neighbors_empty_for_orphan(vault_context):
    """Test graph_neighbors returns empty list for orphan note."""
    note_d = vault_context.get_note("note_d.md")

    assert note_d is not None

    neighbors_d = vault_context.graph_neighbors(note_d)

    # D has no links, should have no neighbors
    assert neighbors_d == []


def test_graph_neighbors_returns_notes_not_links(vault_context):
    """Test graph_neighbors returns Note objects, not Link objects."""
    note_a = vault_context.get_note("note_a.md")

    assert note_a is not None

    neighbors = vault_context.graph_neighbors(note_a)

    # Should return Note objects
    assert all(isinstance(n, Note) for n in neighbors)


def test_has_link_equivalent_to_links_between(vault_context):
    """Test has_link is equivalent to checking len(links_between) > 0."""
    note_a = vault_context.get_note("note_a.md")
    note_b = vault_context.get_note("note_b.md")
    note_d = vault_context.get_note("note_d.md")

    assert note_a is not None
    assert note_b is not None
    assert note_d is not None

    # Linked notes
    assert vault_context.has_link(note_a, note_b) == (
        len(vault_context.links_between(note_a, note_b)) > 0
    )

    # Unlinked notes
    assert vault_context.has_link(note_a, note_d) == (
        len(vault_context.links_between(note_a, note_d)) > 0
    )
