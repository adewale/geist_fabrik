"""Unit tests for the hidden_hub geist.

hidden_hub needs >= 20 notes. A note is a hidden hub when MORE than 10 of its
top-30 semantic neighbours have similarity > SimilarityLevel.HIGH (0.65) yet it
has fewer than 5 links (outgoing + incoming). It returns at most 3 suggestions.

Fixtures use the bag-of-words test stub: cluster members repeat the same 8
topic words twice and differ only in a numeric title suffix (ignored by the
stub), so members have cosine ~0.97 with each other; fillers use disjoint
vocabulary. In a cluster of N unlinked members each member has N - 1
high-similarity neighbours.
"""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import hidden_hub
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 3
MIN_NOTES = 20
CREATED = datetime(2024, 1, 1)
TOPIC = "tidepool anemone barnacle limpet kelp urchin starfish mussel"
CLUSTER = [f"Tide {i}" for i in range(12)]  # 12 members -> 11 high neighbours each


def _add_cluster(builder: VaultBuilder, titles: list[str]) -> None:
    for title in titles:
        builder.note(title, f"{TOPIC} {TOPIC}", created=CREATED)


def _add_fillers(builder: VaultBuilder, count: int, link_to: Sequence[str] = ()) -> None:
    links = " ".join(f"[[{t}]]" for t in link_to)
    for i in range(count):
        builder.note(f"Filler {i}", f"filler{i} loose{i} idle{i} {links}", created=CREATED)


def test_hidden_hub_flags_semantically_central_unlinked_note(tmp_path: Path) -> None:
    """Contract: an unlinked note with > 10 highly similar neighbours is a hidden hub.

    Trigger: 12 cluster members (11 high-similarity neighbours each > 10, 0
    links < 5) plus 8 fillers = 20 notes.
    """
    builder = VaultBuilder(tmp_path)
    _add_cluster(builder, CLUSTER)
    _add_fillers(builder, MIN_NOTES - len(CLUSTER))
    ctx = builder.build()

    suggestions = hidden_hub.suggest(ctx)

    assert_valid_suggestions(suggestions, "hidden_hub")
    for s in suggestions:
        assert set(s.notes) <= set(CLUSTER)
        assert len(s.notes) == 4  # the hub plus 3 sampled neighbours
        assert "is semantically related to 11 notes" in s.text
        assert "only has 0 links" in s.text


def test_hidden_hub_caps_at_three_distinct_hubs(tmp_path: Path) -> None:
    """Contract: 12 qualifying members -> exactly 3 suggestions about distinct hubs."""
    builder = VaultBuilder(tmp_path)
    _add_cluster(builder, CLUSTER)
    _add_fillers(builder, MIN_NOTES - len(CLUSTER))
    ctx = builder.build()

    suggestions = hidden_hub.suggest(ctx)

    assert_valid_suggestions(suggestions, "hidden_hub", min_count=CAP)
    assert len(suggestions) == CAP
    assert len({s.notes[0] for s in suggestions}) == CAP


@pytest.mark.parametrize(("cluster_size", "fires"), [(11, False), (12, True)])
def test_hidden_hub_needs_more_than_ten_similar_neighbours(
    tmp_path: Path, cluster_size: int, fires: bool
) -> None:
    """Contract: 10 high-similarity neighbours -> []; 11 -> hidden hub."""
    builder = VaultBuilder(tmp_path)
    _add_cluster(builder, CLUSTER[:cluster_size])
    _add_fillers(builder, MIN_NOTES - cluster_size)
    ctx = builder.build()

    suggestions = hidden_hub.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, "hidden_hub")
    else:
        assert suggestions == []


@pytest.mark.parametrize(("backlinks", "fires"), [(4, True), (5, False)])
def test_hidden_hub_requires_fewer_than_five_links(
    tmp_path: Path, backlinks: int, fires: bool
) -> None:
    """Contract: 4 links still counts as hidden; 5 links does not.

    The first ``backlinks`` fillers link to every cluster member, giving each
    member exactly that many incoming links. (Fillers mention "tide" 12 times
    but nothing else from the cluster, so their similarity stays low.)
    """
    builder = VaultBuilder(tmp_path)
    _add_cluster(builder, CLUSTER)
    _add_fillers(builder, backlinks, link_to=CLUSTER)
    for i in range(backlinks, MIN_NOTES - len(CLUSTER)):
        builder.note(f"Filler {i}", f"filler{i} loose{i} idle{i}", created=CREATED)
    ctx = builder.build()

    suggestions = hidden_hub.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, "hidden_hub")
        assert all(f"only has {backlinks} links" in s.text for s in suggestions)
    else:
        assert suggestions == []


def test_hidden_hub_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are neither hidden hubs nor cited neighbours.

    Six journal notes share the cluster's vocabulary: unfiltered they would be
    hidden hubs themselves and fill the members' neighbour lists.
    """
    builder = VaultBuilder(tmp_path)
    _add_cluster(builder, CLUSTER)
    journal = [f"Session {chr(65 + i)}" for i in range(6)]
    for title in journal:
        builder.journal(title, f"{TOPIC} {TOPIC}", created=CREATED)
    _add_fillers(builder, MIN_NOTES - len(CLUSTER))
    ctx = builder.build()

    suggestions = hidden_hub.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "hidden_hub",
        min_count=CAP,
        must_not_reference=["geist journal", *journal],
    )
    assert all(set(s.notes) <= set(CLUSTER) for s in suggestions)
    # Only the 11 regular cluster mates count as similar neighbours.
    assert all("is semantically related to 11 notes" in s.text for s in suggestions)
