"""Unit tests for the cluster_mirror geist.

cluster_mirror runs HDBSCAN clustering (min_cluster_size from config, default
5), drops geist journal notes from every cluster (discarding clusters left
below min size), needs at least 2 clusters, and returns ONE suggestion that
shows up to 3 sampled clusters with 3 representative notes each.

Fixtures use the bag-of-words test stub: each topic group is 6 notes sharing
the same 8 words (cosine ~0.8 within a group, ~0 across groups), so HDBSCAN
finds one dense cluster per group.
"""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import cluster_mirror
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CREATED = datetime(2024, 1, 1)
SHOWN_CLUSTERS = 3
REPRESENTATIVES = 3
TOPICS = {
    "Orchard": "orchard pruning grafting apple blossom cider rootstock scion",
    "Glacier": "glacier moraine crevasse icefall serac firn cirque tarn",
    "Violin": "violin bowing rosin fingerboard vibrato luthier spruce purfling",
    "Bakery": "bakery sourdough levain crumb proofing banneton flour oven",
}
GROUP_SIZE = 6


def _add_group(builder: VaultBuilder, name: str, *, journal: bool = False) -> list[str]:
    titles = [f"{name} {'Session' if journal else 'Note'} {chr(65 + i)}" for i in range(GROUP_SIZE)]
    for title in titles:
        add = builder.journal if journal else builder.note
        add(title, TOPICS[name], created=CREATED)
    return titles


def _build(tmp_path: Path, regular: Sequence[str], journal: Sequence[str] = ()) -> VaultContext:
    builder = VaultBuilder(tmp_path)
    for name in regular:
        _add_group(builder, name)
    for name in journal:
        _add_group(builder, name, journal=True)
    return builder.build()


def _shown_groups(text: str) -> set[str]:
    """Topic names whose notes appear in a '→ [[...]]' representatives line."""
    return {name for name in TOPICS if f"[[{name} " in text}


def test_cluster_mirror_shows_each_planted_cluster(tmp_path: Path) -> None:
    """Contract: two planted topic clusters are both shown with 3 representatives.

    Trigger: 12 notes (>= 2 x min_size 5) in 2 disjoint-vocabulary groups of 6.
    """
    ctx = _build(tmp_path, ["Orchard", "Glacier"])

    suggestions = cluster_mirror.suggest(ctx)

    assert_valid_suggestions(suggestions, "cluster_mirror", must_reference=["Orchard", "Glacier"])
    assert len(suggestions) == 1
    text = suggestions[0].text
    assert text.endswith("What do these clusters remind you of?")
    assert text.count("→") == 2
    assert len(suggestions[0].notes) == 2 * REPRESENTATIVES
    for line in (ln for ln in text.splitlines() if ln.startswith("→")):
        # Each representatives line lists notes of exactly one planted group.
        assert len(_shown_groups(line)) == 1
        assert line.count("[[") == REPRESENTATIVES


def test_cluster_mirror_shows_at_most_three_clusters(tmp_path: Path) -> None:
    """Contract: with 4 clusters, exactly 3 distinct clusters are shown."""
    ctx = _build(tmp_path, list(TOPICS))
    assert len(ctx.get_clusters()) == 4

    suggestions = cluster_mirror.suggest(ctx)

    assert_valid_suggestions(suggestions, "cluster_mirror")
    assert len(suggestions) == 1
    assert suggestions[0].text.count("→") == SHOWN_CLUSTERS
    assert len(_shown_groups(suggestions[0].text)) == SHOWN_CLUSTERS
    assert len(set(suggestions[0].notes)) == SHOWN_CLUSTERS * REPRESENTATIVES


@pytest.mark.parametrize(("regular_in_second", "fires"), [(4, False), (5, True)])
def test_cluster_mirror_needs_two_clusters_of_min_size_after_journal_removal(
    tmp_path: Path, regular_in_second: int, fires: bool
) -> None:
    """Contract: a cluster counts only if >= min_size (5) regular notes remain,
    and fewer than 2 counted clusters -> [].

    HDBSCAN finds two 6-note clusters (the second group mixes regular and
    journal notes with identical vocabulary). With 4 regular notes left the
    second cluster is dropped, leaving 1 cluster -> []; with 5 it survives.
    """
    builder = VaultBuilder(tmp_path)
    _add_group(builder, "Orchard")
    for i in range(GROUP_SIZE):
        title = f"Glacier Mixed {chr(65 + i)}"
        add = builder.note if i < regular_in_second else builder.journal
        add(title, TOPICS["Glacier"], created=CREATED)
    ctx = builder.build()
    assert sorted(c.size for c in ctx.get_clusters().values()) == [GROUP_SIZE, GROUP_SIZE]

    suggestions = cluster_mirror.suggest(ctx)

    if not fires:
        assert suggestions == []
    else:
        assert_valid_suggestions(
            suggestions, "cluster_mirror", must_reference=["Orchard", "Glacier"]
        )
        journal_titles = [
            f"Glacier Mixed {chr(65 + i)}" for i in range(regular_in_second, GROUP_SIZE)
        ]
        assert not set(suggestions[0].notes) & set(journal_titles)


def test_cluster_mirror_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal-only clusters are dropped and never shown.

    Two regular clusters plus one all-journal cluster: unfiltered, all 3 fit
    under the 3-cluster display limit, so a leak would always be visible.
    """
    ctx = _build(tmp_path, ["Orchard", "Glacier"], journal=["Violin"])
    assert len(ctx.get_clusters()) == 3

    suggestions = cluster_mirror.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "cluster_mirror",
        must_reference=["Orchard", "Glacier"],
        must_not_reference=["geist journal", "Violin"],
    )
    assert suggestions[0].text.count("→") == 2
