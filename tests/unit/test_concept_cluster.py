"""Unit tests for the concept_cluster geist.

concept_cluster needs >= 5 notes, samples 5 seed notes, and for each seed
forms a cluster of the seed plus its 3 nearest neighbours. If the cluster's
average pairwise similarity exceeds SimilarityLevel.HIGH (0.65) it suggests
naming the cluster. At most 2 suggestions are returned.

Fixtures use the bag-of-words test stub: a group is 4 notes whose bodies
repeat the same 8 topic words twice, so within-group cosine is ~0.9 and
across groups (disjoint vocabulary) ~0.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import concept_cluster
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 2
CREATED = datetime(2024, 1, 1)
GROUP_SIZE = 4  # seed + 3 neighbours
TOPICS = {
    "Orchard": "orchard pruning grafting apple blossom cider rootstock scion",
    "Glacier": "glacier moraine crevasse icefall serac firn cirque tarn",
    "Violin": "violin bowing rosin fingerboard vibrato luthier spruce purfling",
    "Bakery": "bakery sourdough levain crumb proofing banneton flour oven",
    "Comet": "comet orbit perihelion nucleus coma telescope sungrazer ecliptic",
}


def _add_group(builder: VaultBuilder, name: str, *, journal: bool = False) -> list[str]:
    titles = [f"{name} {'Session' if journal else 'Idea'} {i}" for i in range(GROUP_SIZE)]
    for title in titles:
        add = builder.journal if journal else builder.note
        add(title, f"{TOPICS[name]} {TOPICS[name]}", created=CREATED)
    return titles


def _filler(builder: VaultBuilder) -> None:
    builder.note("Lone Filler", "quokka wombat platypus echidna", created=CREATED)


def test_concept_cluster_names_a_tight_group(tmp_path: Path) -> None:
    """Contract: 4 mutually similar notes are suggested as one emerging cluster.

    Trigger: 5 notes (>= 5), all sampled as seeds; each group seed's 3
    neighbours are its group mates, average pairwise cosine ~0.9 > 0.65.
    """
    builder = VaultBuilder(tmp_path)
    group = _add_group(builder, "Orchard")
    _filler(builder)
    ctx = builder.build()

    suggestions = concept_cluster.suggest(ctx)

    assert_valid_suggestions(suggestions, "concept_cluster", must_reference=group)
    for s in suggestions:
        assert sorted(s.notes) == sorted(group)
        assert s.text.startswith(
            f"What if you recognised an emerging cluster around [[{s.notes[0]}]]"
        )


def test_concept_cluster_reports_each_cluster_once(tmp_path: Path) -> None:
    """Contract: seeds from the same group describe one cluster, reported once.

    All 4 group notes are seeds and all produce the same 4-note set.
    """
    builder = VaultBuilder(tmp_path)
    _add_group(builder, "Orchard")
    _filler(builder)
    ctx = builder.build()

    suggestions = concept_cluster.suggest(ctx)

    assert_valid_suggestions(suggestions, "concept_cluster")
    assert len(suggestions) == 1


def test_concept_cluster_caps_at_two_distinct_clusters(tmp_path: Path) -> None:
    """Contract: with more than 2 clusters found, exactly 2 distinct ones return.

    Five disjoint groups (20 notes); the 5 sampled seeds land in 3+ groups.
    """
    builder = VaultBuilder(tmp_path)
    groups = [frozenset(_add_group(builder, name)) for name in TOPICS]
    ctx = builder.build()

    suggestions = concept_cluster.suggest(ctx)

    assert_valid_suggestions(suggestions, "concept_cluster", min_count=CAP)
    assert len(suggestions) == CAP
    found = {frozenset(s.notes) for s in suggestions}
    assert len(found) == CAP
    assert found <= set(groups)


@pytest.mark.parametrize(("with_filler", "fires"), [(False, False), (True, True)])
def test_concept_cluster_needs_five_notes(tmp_path: Path, with_filler: bool, fires: bool) -> None:
    """Contract: a vault of 4 notes -> [] even if they cluster; 5 notes -> fires."""
    builder = VaultBuilder(tmp_path)
    _add_group(builder, "Orchard")
    if with_filler:
        _filler(builder)
    ctx = builder.build()

    suggestions = concept_cluster.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, "concept_cluster")
    else:
        assert suggestions == []


def test_concept_cluster_ignores_loose_neighbourhoods(tmp_path: Path) -> None:
    """Contract: seeds whose neighbours are unrelated (cosine ~0) form no cluster."""
    builder = VaultBuilder(tmp_path)
    for name, topic in TOPICS.items():
        builder.note(f"{name} Idea", topic, created=CREATED)
    ctx = builder.build()

    assert concept_cluster.suggest(ctx) == []


def test_concept_cluster_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are neither seeds nor cluster members.

    Four journal notes share the Orchard group's vocabulary, so unfiltered
    they would be as close to every Orchard seed as its real group mates.
    """
    builder = VaultBuilder(tmp_path)
    group = _add_group(builder, "Orchard")
    journal = _add_group(builder, "Orchard", journal=True)
    _filler(builder)
    ctx = builder.build()

    suggestions = concept_cluster.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "concept_cluster",
        must_reference=group,
        must_not_reference=["geist journal", *journal],
    )
