"""Unit tests for the island_hopper geist.

island_hopper needs >= 10 notes. For each of the top 5 hubs it forms a
cluster of the hub plus its backlinkers (>= 3 notes), then picks the
non-member whose AVERAGE similarity to the cluster is inside the bridge window
SimilarityLevel.MODERATE (0.5) < avg < SimilarityLevel.HIGH (0.65): close
enough to bridge, not so close it belongs in the cluster. One suggestion per
hub, at most 3 in total.

Fixtures use the bag-of-words test stub. Cluster members carry the same 16
topic words; a bridge carries 9 of them plus 7 words of its own, so its
average cosine to the cluster is ~0.57 (inside the window). A near-copy
carrying 14 of them is ~0.8 (too close).
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import island_hopper
from geistfabrik.similarity_analysis import SimilarityLevel
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 3
MIN_NOTES = 10
CREATED = datetime(2024, 1, 1)
TOPICS = {
    "Orchard": "orchard pruning grafting apple blossom cider rootstock scion "
    "espalier codling russet pippin quince medlar perry windfall",
    "Glacier": "glacier moraine crevasse icefall serac firn cirque tarn "
    "nunatak drumlin esker arete bergschrund ablation calving sastrugi",
    "Violin": "violin bowing rosin fingerboard vibrato luthier spruce purfling "
    "scroll pegbox tailpiece chinrest soundpost fholes varnish maple",
    "Bakery": "bakery sourdough levain crumb proofing banneton flour oven "
    "brioche baguette focaccia ciabatta starter lame couche hydration",
}
BRIDGES = {"Orchard": "Wayfarer", "Glacier": "Pilgrim", "Violin": "Nomad", "Bakery": "Drifter"}
BRIDGE_SHARED = 9  # avg cosine ~0.57


def _bridge_body(name: str, shared: int) -> str:
    words = TOPICS[name].split()
    own = [f"{name.lower()}bridge{i}" for i in range(len(words) - shared)]
    return " ".join(words[:shared] + own)


def _add_island(
    builder: VaultBuilder, name: str, *, linkers: int = 2, bridge_shared: int = BRIDGE_SHARED
) -> str:
    """Hub ``name`` plus ``linkers`` backlinkers on the same topic, and a bridge note."""
    builder.note(name, TOPICS[name], created=CREATED)
    for i in range(linkers):
        builder.note(f"{name} Linker {i}", f"{TOPICS[name]} [[{name}]]", created=CREATED)
    bridge = BRIDGES[name]
    builder.note(bridge, _bridge_body(name, bridge_shared), created=CREATED)
    return bridge


def _add_fillers(builder: VaultBuilder, count: int) -> None:
    for i in range(count):
        builder.note(f"Filler {i}", f"filler{i} loose{i} idle{i}", created=CREATED)


def _avg_sim_to_cluster(ctx: VaultContext, title: str, hub: str) -> float:
    note, hub_note = ctx.resolve_link_target(title), ctx.resolve_link_target(hub)
    assert note is not None and hub_note is not None
    cluster = [hub_note, *ctx.backlinks(hub_note)]
    return float(ctx.batch_similarity([note], cluster).mean())


def test_island_hopper_proposes_bridge_to_hub_cluster(tmp_path: Path) -> None:
    """Contract: a note moderately close to a hub's cluster is proposed as its bridge.

    Trigger: hub + 2 backlinkers (cluster of 3 >= 3), bridge avg ~0.57 in
    (0.5, 0.65), 10 notes total.
    """
    builder = VaultBuilder(tmp_path)
    bridge = _add_island(builder, "Orchard")
    _add_fillers(builder, MIN_NOTES - 4)
    ctx = builder.build()
    avg = _avg_sim_to_cluster(ctx, bridge, "Orchard")
    assert SimilarityLevel.MODERATE < avg < SimilarityLevel.HIGH

    suggestions = island_hopper.suggest(ctx)

    assert_valid_suggestions(suggestions, "island_hopper", must_reference=[bridge, "Orchard"])
    assert len(suggestions) == 1
    assert suggestions[0].notes[:2] == [bridge, "Orchard"]
    assert set(suggestions[0].notes[2:]) <= {"Orchard", "Orchard Linker 0", "Orchard Linker 1"}
    assert suggestions[0].text.startswith(
        f"[[{bridge}]] could bridge your cluster around [[Orchard]]"
    )


def test_island_hopper_caps_at_three_distinct_hubs(tmp_path: Path) -> None:
    """Contract: 4 hubs each with a bridge -> exactly 3 suggestions, distinct hubs."""
    builder = VaultBuilder(tmp_path)
    bridges = {name: _add_island(builder, name) for name in TOPICS}
    ctx = builder.build()

    suggestions = island_hopper.suggest(ctx)

    assert_valid_suggestions(suggestions, "island_hopper", min_count=CAP)
    assert len(suggestions) == CAP
    hubs = [s.notes[1] for s in suggestions]
    assert len(set(hubs)) == CAP
    assert all(s.notes[0] == bridges[s.notes[1]] for s in suggestions)


@pytest.mark.parametrize(("linkers", "fires"), [(1, False), (2, True)])
def test_island_hopper_needs_cluster_of_three(tmp_path: Path, linkers: int, fires: bool) -> None:
    """Contract: hub + 1 backlinker (cluster of 2) -> []; hub + 2 -> bridge proposed."""
    builder = VaultBuilder(tmp_path)
    _add_island(builder, "Orchard", linkers=linkers)
    _add_fillers(builder, MIN_NOTES - 2 - linkers)
    ctx = builder.build()

    suggestions = island_hopper.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, "island_hopper", must_reference=[BRIDGES["Orchard"]])
    else:
        assert suggestions == []


def test_island_hopper_rejects_notes_too_close_to_the_cluster(tmp_path: Path) -> None:
    """Contract: a note above the HIGH bound belongs in the cluster, not bridging it."""
    builder = VaultBuilder(tmp_path)
    bridge = _add_island(builder, "Orchard", bridge_shared=14)
    _add_fillers(builder, MIN_NOTES - 4)
    ctx = builder.build()
    assert _avg_sim_to_cluster(ctx, bridge, "Orchard") >= SimilarityLevel.HIGH

    assert island_hopper.suggest(ctx) == []


def test_island_hopper_picks_the_closest_in_window_bridge(tmp_path: Path) -> None:
    """Contract: of several in-window candidates, the most similar one is proposed."""
    builder = VaultBuilder(tmp_path)
    weaker = _add_island(builder, "Orchard")  # ~0.57
    builder.note("Stronger", _bridge_body("Orchard", BRIDGE_SHARED + 1), created=CREATED)  # ~0.61
    _add_fillers(builder, MIN_NOTES - 5)
    ctx = builder.build()
    assert (
        SimilarityLevel.MODERATE
        < _avg_sim_to_cluster(ctx, weaker, "Orchard")
        < _avg_sim_to_cluster(ctx, "Stronger", "Orchard")
        < SimilarityLevel.HIGH
    )

    suggestions = island_hopper.suggest(ctx)

    assert_valid_suggestions(suggestions, "island_hopper", must_reference=["Stronger"])
    assert suggestions[0].notes[0] == "Stronger"


def test_island_hopper_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are neither cluster members nor bridges.

    Two journal sessions link to the hub (so, unfiltered, they join its
    cluster and can be sampled as members), and a journal note with 10 shared
    topic words is a closer in-window bridge candidate (~0.61) than the
    regular one (~0.57).
    """
    builder = VaultBuilder(tmp_path)
    bridge = _add_island(builder, "Orchard")
    journal = ["Session Alpha", "Session Beta"]
    for title in journal:
        builder.journal(title, f"[[Orchard]] {TOPICS['Orchard']}", created=CREATED)
    builder.journal("Session Gamma", _bridge_body("Orchard", BRIDGE_SHARED + 1), created=CREATED)
    journal.append("Session Gamma")
    _add_fillers(builder, MIN_NOTES - 4)
    ctx = builder.build()

    suggestions = island_hopper.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "island_hopper",
        must_reference=[bridge, "Orchard"],
        must_not_reference=["geist journal", *journal],
    )
