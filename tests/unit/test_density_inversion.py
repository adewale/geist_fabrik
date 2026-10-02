"""Unit tests for the density_inversion geist.

density_inversion needs >= 20 notes. For each sampled note with >= 3 graph
neighbours it compares how interlinked those neighbours are (graph density)
with how similar they are (semantic density):
  - dense links, sparse meaning: graph density > 0.6 and semantic < 0.3
  - sparse links, dense meaning: graph density < 0.3 and semantic > 0.6
It returns at most 2 suggestions.

Fixtures use the bag-of-words test stub. Semantically scattered notes each
have 20 words of their own, so two clique members share only the few title
words that their links contribute (cosine ~0.1). Semantically dense notes
repeat the same 8 topic words (cosine ~0.9).
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import density_inversion
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 2
MIN_NOTES = 20
CREATED = datetime(2024, 1, 1)
CLIQUE = ["Anchor", "Bramble", "Cobalt", "Dune", "Ember"]
TOPIC = "orchard pruning grafting apple blossom cider rootstock scion"


def _own_words(title: str) -> str:
    """20 words nobody else uses."""
    return " ".join(f"{title.lower()}word{i}" for i in range(20))


def _add_clique(builder: VaultBuilder, titles: list[str]) -> None:
    """Every pair linked (earlier note links to later ones); disjoint vocabulary."""
    for i, title in enumerate(titles):
        links = " ".join(f"[[{t}]]" for t in titles[i + 1 :])
        builder.note(title, f"{_own_words(title)} {links}", created=CREATED)


def _add_fillers(builder: VaultBuilder, count: int) -> None:
    """Unlinked notes: no graph neighbours, so never analysed."""
    for i in range(count):
        builder.note(f"Filler {i}", f"filler{i} loose{i} idle{i}", created=CREATED)


def test_density_inversion_flags_dense_links_with_scattered_meaning(tmp_path: Path) -> None:
    """Contract (case 1): a fully linked 5-clique of unrelated notes is flagged.

    Trigger: each member's 4 graph neighbours are all interlinked (density
    1.0 > 0.6) but share only link-title words (semantic ~0.1 < 0.3).
    """
    builder = VaultBuilder(tmp_path)
    _add_clique(builder, CLIQUE)
    _add_fillers(builder, MIN_NOTES - len(CLIQUE))
    ctx = builder.build()

    suggestions = density_inversion.suggest(ctx)

    assert_valid_suggestions(suggestions, "density_inversion", min_count=CAP)
    for s in suggestions:
        assert set(s.notes) <= set(CLIQUE)
        assert len(s.notes) == 4  # focal note + 3 sampled neighbours
        assert "tightly linked to each other but semantically scattered" in s.text


def test_density_inversion_flags_similar_but_unlinked_neighbours(tmp_path: Path) -> None:
    """Contract (case 2): a hub whose near-identical spokes are not interlinked is flagged.

    Trigger: the hub's 4 spokes share TOPIC (semantic ~0.9 > 0.6) and have no
    links among themselves (graph density 0 < 0.3). Spokes have only one graph
    neighbour (the hub), so the hub is the only analysable note.
    """
    builder = VaultBuilder(tmp_path)
    spokes = [f"Grove {i}" for i in range(4)]
    builder.note("Hub Index", " ".join(f"[[{s}]]" for s in spokes), created=CREATED)
    for spoke in spokes:
        builder.note(spoke, f"{TOPIC} {TOPIC}", created=CREATED)
    _add_fillers(builder, MIN_NOTES - 5)
    ctx = builder.build()

    suggestions = density_inversion.suggest(ctx)

    assert_valid_suggestions(suggestions, "density_inversion", must_reference=["Hub Index"])
    assert len(suggestions) == 1
    assert suggestions[0].notes[0] == "Hub Index"
    assert set(suggestions[0].notes[1:]) <= set(spokes)
    assert "semantically similar but aren't linked to each other" in suggestions[0].text


def test_density_inversion_caps_at_two_distinct_notes(tmp_path: Path) -> None:
    """Contract: 5 qualifying clique members -> exactly 2 suggestions, distinct focal notes."""
    builder = VaultBuilder(tmp_path)
    _add_clique(builder, CLIQUE)
    _add_fillers(builder, MIN_NOTES - len(CLIQUE))
    ctx = builder.build()

    suggestions = density_inversion.suggest(ctx)

    assert_valid_suggestions(suggestions, "density_inversion", min_count=CAP)
    assert len(suggestions) == CAP
    assert len({s.notes[0] for s in suggestions}) == CAP


@pytest.mark.parametrize(("clique_size", "fires"), [(3, False), (4, True)])
def test_density_inversion_needs_three_graph_neighbours(
    tmp_path: Path, clique_size: int, fires: bool
) -> None:
    """Contract: notes with 2 graph neighbours are skipped; 3 are analysed.

    A 3-clique gives each member 2 neighbours; a 4-clique gives 3.
    """
    builder = VaultBuilder(tmp_path)
    _add_clique(builder, CLIQUE[:clique_size])
    _add_fillers(builder, MIN_NOTES - clique_size)
    ctx = builder.build()

    suggestions = density_inversion.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, "density_inversion")
    else:
        assert suggestions == []


@pytest.mark.parametrize(("total_notes", "fires"), [(MIN_NOTES - 1, False), (MIN_NOTES, True)])
def test_density_inversion_needs_twenty_notes(
    tmp_path: Path, total_notes: int, fires: bool
) -> None:
    """Contract: a qualifying clique is ignored in a 19-note vault, flagged in a 20-note one."""
    builder = VaultBuilder(tmp_path)
    _add_clique(builder, CLIQUE)
    _add_fillers(builder, total_notes - len(CLIQUE))
    ctx = builder.build()

    suggestions = density_inversion.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, "density_inversion")
    else:
        assert suggestions == []


def test_density_inversion_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are neither analysed nor named as neighbours.

    Two journal session notes link to every member of a regular 4-clique, as
    real session notes do. Unfiltered, each journal note is itself a flagged
    focal note (its neighbours form the clique) and appears among the clique
    members' graph neighbours.
    """
    builder = VaultBuilder(tmp_path)
    regular = CLIQUE[:4]
    _add_clique(builder, regular)
    journal = ["Session Alpha", "Session Beta"]
    for title in journal:
        builder.journal(title, " ".join(f"[[{t}]]" for t in regular), created=CREATED)
    _add_fillers(builder, MIN_NOTES - len(regular))
    ctx = builder.build()

    suggestions = density_inversion.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "density_inversion",
        min_count=CAP,
        must_not_reference=["geist journal", *journal],
    )
    assert all(set(s.notes) <= set(regular) for s in suggestions)


def test_density_inversion_output_does_not_depend_on_hash_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same date + vault = same output, whatever PYTHONHASHSEED a process has.

    Regression: graph_neighbours() came from a set of Notes, so the list the
    geist samples from followed string-hash order. Salting Note.__hash__
    stands in for a different hash seed within one process.
    """
    from geistfabrik.models import Note

    builder = VaultBuilder(tmp_path)
    _add_clique(builder, CLIQUE)
    _add_fillers(builder, MIN_NOTES - len(CLIQUE))
    baseline = [s.text for s in density_inversion.suggest(builder.build())]
    assert baseline

    for salt in ("a", "b", "c", "d", "e", "f"):
        monkeypatch.setattr(Note, "__hash__", lambda self, salt=salt: hash(salt + self.path))
        assert [s.text for s in density_inversion.suggest(builder.build())] == baseline, salt


def _reference_densities(ctx, neighbours: list) -> tuple[int, float]:
    """The pre-vectorisation computation: links_between and similarity() per pair."""
    edges = 0
    similarities = []
    for i, n1 in enumerate(neighbours):
        for n2 in neighbours[i + 1 :]:
            if ctx.links_between(n1, n2):
                edges += 1
            similarities.append(ctx.similarity(n1, n2))
    return edges, sum(similarities) / len(similarities)


def _mixed_vault(tmp_path: Path):
    """Cliques, hubs with similar spokes, and random cross links (incl. one-way)."""
    import random

    rng = random.Random(7)
    builder = VaultBuilder(tmp_path)
    titles = [f"Node {i:02d}" for i in range(48)]
    words = ["orchard", "graft", "cider", "tide", "harbour", "sail", "ledger", "audit"]
    for i, title in enumerate(titles):
        topic = words[i % 4 * 2 : i % 4 * 2 + 2] * 4
        targets = rng.sample(titles, rng.randint(0, 9))
        if i < 6:  # a clique among the first six notes
            targets += titles[:6]
        body = " ".join(topic + [f"own{i}x{k}" for k in range(rng.randint(0, 12))])
        builder.note(title, body + " " + " ".join(f"[[{t}]]" for t in targets), created=CREATED)
    return builder


def test_density_inversion_densities_match_per_pair_reference(tmp_path: Path) -> None:
    """Equivalence: adjacency-set link counts and the similarity matrix mean
    equal the original per-pair links_between()/similarity() computation for
    every analysable note (counts exactly, means to float tolerance)."""
    ctx = _mixed_vault(tmp_path).build()
    reference_ctx = _mixed_vault(tmp_path).build()
    adjacency = {n.path: {m.path for m in ctx.graph_neighbours(n)} for n in ctx.notes()}
    checked = 0
    for note in ctx.notes():
        neighbours = ctx.graph_neighbours(note)
        if len(neighbours) < 3:
            continue
        ref_neighbours = reference_ctx.graph_neighbours(reference_ctx.get_note(note.path))
        assert [n.path for n in ref_neighbours] == [n.path for n in neighbours]
        edges, semantic = _reference_densities(reference_ctx, ref_neighbours)
        assert density_inversion._link_count(neighbours, lambda n: adjacency[n.path]) == edges
        assert density_inversion._semantic_density(ctx, neighbours) == pytest.approx(
            semantic, rel=0, abs=1e-12
        )
        checked += 1
    assert checked >= 20


def _reference_suggest(vault) -> list:
    """density_inversion.suggest() as it was before vectorisation."""
    from geistfabrik import Suggestion

    suggestions = []
    notes = vault.notes()
    if len(notes) < 20:
        return []
    for note in vault.sample(notes, min(30, len(notes))):
        graph_neighbours = vault.graph_neighbours(note)
        if len(graph_neighbours) < 3:
            continue
        edges, semantic_density = _reference_densities(vault, graph_neighbours)
        max_possible_edges = len(graph_neighbours) * (len(graph_neighbours) - 1) / 2
        graph_density = edges / max_possible_edges
        if graph_density > 0.6 and semantic_density < 0.3:
            sample = vault.sample(graph_neighbours, count=3)
            text = f"scattered {note.path} " + ", ".join(n.link_text for n in sample)
        elif graph_density < 0.3 and semantic_density > 0.6:
            sample = vault.sample(graph_neighbours, count=3)
            text = f"missing {note.path} " + ", ".join(n.link_text for n in sample)
        else:
            continue
        notes_out = [note.link_text] + [n.link_text for n in sample]
        suggestions.append(Suggestion(text=text, notes=notes_out, geist_id="density_inversion"))
    return vault.sample(suggestions, count=2)


def _kind_and_notes(suggestion) -> tuple[str, list[str]]:
    kind = "missing" if "Missing connections" in suggestion.text else "scattered"
    if suggestion.text.startswith(("missing ", "scattered ")):
        kind = suggestion.text.split(" ", 1)[0]
    return kind, suggestion.notes


@pytest.mark.parametrize("fixture", ["mixed", "both_cases"])
def test_density_inversion_suggestions_match_reference(tmp_path: Path, fixture: str) -> None:
    """Equivalence: same vault and seed give the same suggestions (kind, focal
    note, sampled neighbours) as the per-pair implementation."""
    if fixture == "mixed":
        builder = _mixed_vault(tmp_path)
    else:
        builder = VaultBuilder(tmp_path)
        _add_clique(builder, CLIQUE)
        spokes = [f"Grove {i}" for i in range(4)]
        builder.note("Hub Index", " ".join(f"[[{s}]]" for s in spokes), created=CREATED)
        for spoke in spokes:
            builder.note(spoke, f"{TOPIC} {TOPIC}", created=CREATED)
        _add_fillers(builder, MIN_NOTES)

    actual = [_kind_and_notes(s) for s in density_inversion.suggest(builder.build())]
    expected = [_kind_and_notes(s) for s in _reference_suggest(builder.build())]

    assert actual == expected
    if fixture == "both_cases":
        assert actual


@pytest.mark.timeout(20)
def test_density_inversion_dense_clique_is_not_cubic(tmp_path: Path) -> None:
    """Regression: a 120-note clique took ~48 s (links_between rescans both
    notes' links for each of ~7k neighbour pairs, for 30 sampled notes); with
    adjacency sets and one similarity matrix per note it takes well under 1 s."""
    builder = VaultBuilder(tmp_path)
    titles = [f"Member {i:03d}" for i in range(120)]
    for title in titles:
        links = " ".join(f"[[{t}]]" for t in titles if t != title)
        builder.note(title, f"{_own_words(title.replace(' ', ''))} {links}", created=CREATED)
    ctx = builder.build()

    suggestions = density_inversion.suggest(ctx)

    assert isinstance(suggestions, list)
    assert len(ctx.graph_neighbours(ctx.notes()[0])) == 119
