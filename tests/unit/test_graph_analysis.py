"""Unit tests for GraphPatternFinder (graph_analysis.py) and the canonical
link-target resolution it relies on.

graph_analysis is the documented extension API for graph-structural geists
(docs/WRITING_GOOD_GEISTS.md) but previously had zero tests - and its own
private notion of "are these notes linked" (title-only) that disagreed with
links_between()/backlinks(). The TestLinkResolutionAgreement class locks all
code paths to the single models.link_target_forms() definition.
"""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from geistfabrik import Session, Vault
from geistfabrik.graph_analysis import GraphPatternFinder, _are_linked
from geistfabrik.models import link_target_forms
from geistfabrik.vault_context import VaultContext

SESSION_DATE = datetime(2024, 3, 15)


def _build_context(notes: dict[str, str]) -> VaultContext:
    tmpdir = TemporaryDirectory()
    vault_path = Path(tmpdir.name)
    for name, content in notes.items():
        (vault_path / name).write_text(content)
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    session = Session(SESSION_DATE, vault.db)
    session.compute_embeddings(vault.all_notes())
    ctx = VaultContext(vault, session, seed=20240315)
    ctx._tmpdir = tmpdir  # type: ignore[attr-defined]  # keep tempdir alive
    return ctx


@pytest.fixture
def linked_vault():
    """hub -> a, b, c (chain a -> b); island1 <-> island2 disconnected; loner."""
    return _build_context(
        {
            "hub.md": "# Hub\nLinks to [[a]] and [[b]] and [[c]].",
            "a.md": "# a\nGoes to [[b]].",
            "b.md": "# b\nLeaf content.",
            "c.md": "# c\nLeaf content too.",
            "island1.md": "# Island1\nConnected to [[island2]].",
            "island2.md": "# Island2\nBack to [[island1]].",
            "loner.md": "# Loner\nNo links at all.",
        }
    )


class TestLinkTargetForms:
    def test_forms_for_regular_note(self):
        forms = link_target_forms("dir/note.md", "My Title")
        assert forms == frozenset({"dir/note.md", "dir/note", "My Title"})

    def test_forms_without_extension(self):
        forms = link_target_forms("plain", "plain")
        assert forms == frozenset({"plain"})

    def test_note_method_delegates(self, linked_vault):
        note = next(n for n in linked_vault.notes() if n.path == "a.md")
        assert note.link_target_forms() == link_target_forms("a.md", "a")


class TestLinkResolutionAgreement:
    """Every 'are these linked' code path must agree with link_target_forms."""

    def test_are_linked_matches_links_between(self, linked_vault):
        notes = {n.path: n for n in linked_vault.notes()}
        for x in notes.values():
            for y in notes.values():
                if x.path >= y.path:
                    continue
                assert _are_linked(x, y) == bool(linked_vault.links_between(x, y)), (
                    f"_are_linked and links_between disagree for {x.path} / {y.path}"
                )

    def test_backlinks_agree_with_forms(self, linked_vault):
        notes = {n.path: n for n in linked_vault.notes()}
        b = notes["b.md"]
        backlink_paths = {n.path for n in linked_vault.backlinks(b)}
        # hub.md and a.md both link to [[b]] (the path-without-extension form).
        assert backlink_paths == {"hub.md", "a.md"}

    def test_orphans_agree(self, linked_vault):
        orphan_paths = {n.path for n in linked_vault.orphans()}
        assert orphan_paths == {"loner.md"}
        finder = GraphPatternFinder(linked_vault)
        assert {n.path for n in finder.find_orphans()} == {"loner.md"}


class TestGraphPatternFinder:
    def test_find_hubs_sorted_by_backlinks(self, linked_vault):
        finder = GraphPatternFinder(linked_vault)
        hubs = finder.find_hubs(min_backlinks=2)
        assert hubs, "b has two backlinks (hub, a) and must qualify"
        assert hubs[0].path == "b.md"
        # Threshold respected: nothing with fewer than 2 backlinks
        for note in hubs:
            assert len(linked_vault.backlinks(note)) >= 2

    def test_shortest_path_follows_links(self, linked_vault):
        notes = {n.path: n for n in linked_vault.notes()}
        finder = GraphPatternFinder(linked_vault)

        path = finder.shortest_path(notes["hub.md"], notes["b.md"])
        assert path is not None
        # Direct link hub -> b: two-node path beats hub -> a -> b.
        assert [n.path for n in path] == ["hub.md", "b.md"]

    def test_shortest_path_none_when_disconnected(self, linked_vault):
        notes = {n.path: n for n in linked_vault.notes()}
        finder = GraphPatternFinder(linked_vault)
        assert finder.shortest_path(notes["hub.md"], notes["island1.md"]) is None

    def test_shortest_path_self_is_single_node(self, linked_vault):
        notes = {n.path: n for n in linked_vault.notes()}
        finder = GraphPatternFinder(linked_vault)
        path = finder.shortest_path(notes["a.md"], notes["a.md"])
        assert path is not None and [n.path for n in path] == ["a.md"]

    def test_k_hop_neighborhood(self, linked_vault):
        notes = {n.path: n for n in linked_vault.notes()}
        finder = GraphPatternFinder(linked_vault)

        assert finder.k_hop_neighborhood(notes["hub.md"], 0) == []
        one_hop = {n.path for n in finder.k_hop_neighborhood(notes["hub.md"], 1)}
        assert one_hop == {"a.md", "b.md", "c.md"}
        # Two hops adds nothing new (a -> b already reached).
        two_hop = {n.path for n in finder.k_hop_neighborhood(notes["hub.md"], 2)}
        assert two_hop == one_hop

    def test_connected_components(self, linked_vault):
        finder = GraphPatternFinder(linked_vault)
        components = finder.find_connected_components()
        component_sets = sorted(
            ({n.path for n in comp} for comp in components), key=lambda s: (len(s), min(s))
        )
        assert {"loner.md"} in component_sets
        assert {"island1.md", "island2.md"} in component_sets
        assert {"hub.md", "a.md", "b.md", "c.md"} in component_sets

    def test_find_bridges_detects_unlinked_similar_pair(self, linked_vault):
        finder = GraphPatternFinder(linked_vault)
        # min_similarity=-1 makes every unlinked connected pair a bridge,
        # which pins the structure logic independent of stub embeddings.
        bridges = finder.find_bridges(min_similarity=-1.0)
        triples = {(a.path, mid.path, b.path) for a, mid, b in bridges}
        # hub connects b and c, which are not linked to each other.
        assert any(mid == "hub.md" and {x, y} == {"b.md", "c.md"} for x, mid, y in triples)
        # Linked pairs (a-b) never appear as endpoints around hub.
        assert not any({x, y} == {"a.md", "b.md"} for x, _, y in triples)

    def test_detect_structural_holes_cross_component_only(self, linked_vault):
        finder = GraphPatternFinder(linked_vault)
        holes = finder.detect_structural_holes(min_similarity=-1.0)
        assert holes, "with min_similarity=-1 every cross-component pair qualifies"
        note_to_comp = {}
        for i, comp in enumerate(finder.find_connected_components()):
            for n in comp:
                note_to_comp[n.path] = i
        for a, b in holes:
            assert note_to_comp[a.path] != note_to_comp[b.path], (
                "structural holes must span different components"
            )

    def test_detect_structural_holes_respects_candidate_limit(self, linked_vault):
        finder = GraphPatternFinder(linked_vault)
        capped = finder.detect_structural_holes(min_similarity=-1.0, candidate_limit=3)
        endpoints = {n.path for pair in capped for n in pair}
        assert len(endpoints) <= 3
