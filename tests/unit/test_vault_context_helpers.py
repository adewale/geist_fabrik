"""Tests for VaultContext helper functions (has_link, graph_neighbours)."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.embeddings import Session
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


def test_graph_neighbours_includes_outgoing(vault_context):
    """Test graph_neighbours includes notes linked to."""
    note_a = vault_context.get_note("note_a.md")
    note_b = vault_context.get_note("note_b.md")

    assert note_a is not None
    assert note_b is not None

    neighbours_a = vault_context.graph_neighbours(note_a)

    # A links to B, so B should be in neighbours
    assert note_b in neighbours_a


def test_graph_neighbours_includes_backlinks(vault_context):
    """Test graph_neighbours includes notes linking to this note."""
    note_a = vault_context.get_note("note_a.md")
    note_c = vault_context.get_note("note_c.md")

    assert note_a is not None
    assert note_c is not None

    neighbours_a = vault_context.graph_neighbours(note_a)

    # C links to A, so C should be in neighbours (backlink)
    assert note_c in neighbours_a


def test_graph_neighbours_deduplicates(vault_context):
    """Test bidirectional links don't appear twice."""
    note_a = vault_context.get_note("note_a.md")
    note_b = vault_context.get_note("note_b.md")

    assert note_a is not None
    assert note_b is not None

    neighbours_a = vault_context.graph_neighbours(note_a)

    # B should appear only once even though A→B and B→A
    assert neighbours_a.count(note_b) == 1


def test_graph_neighbours_empty_for_orphan(vault_context):
    """Test graph_neighbours returns empty list for orphan note."""
    note_d = vault_context.get_note("note_d.md")

    assert note_d is not None

    neighbours_d = vault_context.graph_neighbours(note_d)

    # D has no links, should have no neighbours
    assert neighbours_d == []


@pytest.fixture
def mixed_link_context(tmp_path):
    """Links written as plain names, aliases, full paths and journal headings."""
    files = {
        "note_a.md": "# Note A\n\n[[note_b]]",
        "note_b.md": "# Note B\n\nNo links back",
        "folder/Deep.md": "# Deep\n\nNested note",
        "Aliaser.md": "# Aliaser\n\n[[note_b|Bee]] and [[folder/Deep.md]]",
        "Journal.md": "## 2025-01-14\nMet [[note_a]]\n## 2025-01-15\nQuiet day",
        "Reader.md": "# Reader\n\n[[Journal#2025-01-15]]",
        "Loner.md": "# Loner\n\nNothing",
    }
    for path, content in files.items():
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(content)
    vault = Vault(str(tmp_path), ":memory:")
    vault.sync()
    session = Session(date=datetime(2025, 1, 20), db=vault.db)
    session.compute_embeddings(vault.all_notes())
    yield VaultContext(vault, session)
    vault.close()


def test_has_link_agrees_with_outgoing_links_in_either_direction(mixed_link_context):
    """has_link(x, y) holds exactly when y is among x's resolved outgoing links
    or x among y's, for every pair, including alias links, full-path links
    and links to and from virtual journal entries.

    outgoing_links comes from the cached link graph, a separate code path from
    has_link's per-pair resolution. Regressions caught: checking one direction
    only, or matching raw link text against titles instead of resolving it.
    """
    ctx = mixed_link_context
    notes = {n.path: n for n in ctx.notes()}
    entry_14 = notes["Journal.md/2025-01-14"]
    entry_15 = notes["Journal.md/2025-01-15"]
    assert entry_14.is_virtual and entry_15.is_virtual

    linked = set()
    for x in notes.values():
        for y in notes.values():
            if x.path == y.path:
                continue
            outgoing = y in ctx.outgoing_links(x) or x in ctx.outgoing_links(y)
            assert ctx.has_link(x, y) == outgoing, (x.path, y.path)
            if outgoing:
                linked.add(frozenset((x.path, y.path)))

    assert linked == {
        frozenset(("note_a.md", "note_b.md")),
        frozenset(("Aliaser.md", "note_b.md")),  # alias link
        frozenset(("Aliaser.md", "folder/Deep.md")),  # full-path link
        frozenset(("Journal.md/2025-01-14", "note_a.md")),  # from a virtual entry
        frozenset(("Reader.md", "Journal.md/2025-01-15")),  # to a virtual entry
    }


def test_outgoing_links_returns_targets(vault_context):
    """Test outgoing_links returns notes that this note links to."""
    note_a = vault_context.get_note("note_a.md")
    note_b = vault_context.get_note("note_b.md")

    assert note_a is not None
    assert note_b is not None

    outgoing = vault_context.outgoing_links(note_a)

    # A links to B
    assert note_b in outgoing


def test_outgoing_links_excludes_backlinks(vault_context):
    """Test outgoing_links does NOT include backlinks."""
    note_a = vault_context.get_note("note_a.md")
    note_c = vault_context.get_note("note_c.md")

    assert note_a is not None
    assert note_c is not None

    outgoing = vault_context.outgoing_links(note_a)

    # C links to A, but A doesn't link to C
    assert note_c not in outgoing


def test_outgoing_links_symmetric_with_backlinks(vault_context):
    """Test outgoing_links and backlinks are symmetric operations."""
    note_a = vault_context.get_note("note_a.md")
    note_b = vault_context.get_note("note_b.md")

    assert note_a is not None
    assert note_b is not None

    # A's outgoing should include B
    outgoing_a = vault_context.outgoing_links(note_a)
    assert note_b in outgoing_a

    # B's backlinks should include A
    backlinks_b = vault_context.backlinks(note_b)
    assert note_a in backlinks_b


def test_outgoing_links_empty_for_orphan(vault_context):
    """Test outgoing_links returns empty list for note with no outgoing links."""
    note_d = vault_context.get_note("note_d.md")

    assert note_d is not None

    outgoing = vault_context.outgoing_links(note_d)

    # D has no outgoing links
    assert outgoing == []


def test_graph_neighbours_equals_outgoing_plus_backlinks(vault_context):
    """Test graph_neighbours is union of outgoing_links and backlinks."""
    note_a = vault_context.get_note("note_a.md")

    assert note_a is not None

    outgoing = vault_context.outgoing_links(note_a)
    backlinks = vault_context.backlinks(note_a)
    neighbours = vault_context.graph_neighbours(note_a)

    # Convert to sets for comparison (graph_neighbours deduplicates)
    expected = set(outgoing + backlinks)
    actual = set(neighbours)

    assert expected == actual
