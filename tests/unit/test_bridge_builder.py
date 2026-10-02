"""Unit tests for the bridge_builder geist.

bridge_builder walks the top hubs (most-backlinked notes) and suggests linking
a hub to any semantic neighbour whose similarity exceeds SimilarityLevel.HIGH
(0.65), that it is not linked to, and with which it shares no graph neighbour
(no note links to or from both). Each unordered pair is reported once. It
returns at most 3 suggestions.

Fixtures use the bag-of-words test stub: a note's embedding is its word
counts (title included), so a hub and a "twin" sharing 8 of their 10 content
words have cosine ~0.8, and notes with disjoint vocabulary have ~0.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import bridge_builder
from geistfabrik.models import Note
from geistfabrik.similarity_analysis import SimilarityLevel
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 3
CREATED = datetime(2024, 1, 1)

# Four disjoint 8-word topics. Hub i and Twin i share all 8 topic words; their
# 2-word titles differ, so cosine ~ 8/10 = 0.8 > HIGH (0.65).
TOPICS = [
    "orchard pruning grafting apple blossom cider rootstock scion",
    "glacier moraine crevasse icefall serac firn cirque tarn",
    "violin bowing rosin fingerboard vibrato luthier spruce bridgework",
    "bakery sourdough levain crumb proofing banneton flour oven",
]
HUBS = ["Orchard Hub", "Glacier Hub", "Violin Hub", "Bakery Hub"]
TWINS = ["Pomology Twin", "Icefield Twin", "Stringed Twin", "Loaves Twin"]


def _add_hub_with_twin(builder: VaultBuilder, i: int, twin_body: str | None = None) -> None:
    """Hub i (with one backlink) plus an unlinked twin note."""
    builder.note(HUBS[i], TOPICS[i], created=CREATED)
    builder.note(TWINS[i], twin_body or TOPICS[i], created=CREATED)
    # The linker makes HUBS[i] a hub; it shares only the hub's title words.
    builder.note(f"Linker {i}", f"See [[{HUBS[i]}]] quokka{i} wombat{i}", created=CREATED)


def _get(ctx: VaultContext, title: str) -> Note:
    note = ctx.resolve_link_target(title)
    assert note is not None, title
    return note


def test_bridge_builder_suggests_unlinked_twin_of_hub(tmp_path: Path) -> None:
    """Contract: a hub and its unlinked near-duplicate are suggested as a bridge.

    Regression caught: the similarity/link filter inverted, or hubs/neighbours
    wired wrongly, so the planted pair is not suggested.
    """
    builder = VaultBuilder(tmp_path)
    _add_hub_with_twin(builder, 0)
    ctx = builder.build()
    assert ctx.similarity(_get(ctx, HUBS[0]), _get(ctx, TWINS[0])) > SimilarityLevel.HIGH

    suggestions = bridge_builder.suggest(ctx)

    assert_valid_suggestions(suggestions, "bridge_builder", must_reference=[HUBS[0], TWINS[0]])
    assert [s.notes for s in suggestions] == [[HUBS[0], TWINS[0]]]
    assert suggestions[0].text == (
        f"What if [[{HUBS[0]}]] and [[{TWINS[0]}]] were connected? They're semantically "
        "similar but in different parts of your vault: no link joins them, directly or "
        "through a shared neighbour. A link might bridge important concepts."
    )


def test_bridge_builder_caps_at_three_distinct_pairs(tmp_path: Path) -> None:
    """Contract: with 4 qualifying hub/twin pairs, exactly 3 distinct pairs return."""
    builder = VaultBuilder(tmp_path)
    for i in range(4):
        _add_hub_with_twin(builder, i)
    ctx = builder.build()

    suggestions = bridge_builder.suggest(ctx)

    assert_valid_suggestions(suggestions, "bridge_builder", min_count=CAP)
    assert len(suggestions) == CAP
    pairs = {tuple(s.notes) for s in suggestions}
    assert len(pairs) == CAP
    assert pairs <= set(zip(HUBS, TWINS))


@pytest.mark.parametrize(
    ("shared_words", "fires"),
    [
        # Twin keeps 6 of the 8 topic words -> cosine ~6/10 = 0.6 <= 0.65.
        (6, False),
        # Twin keeps 7 of the 8 topic words -> cosine ~7/10 = 0.7 > 0.65.
        (7, True),
    ],
)
def test_bridge_builder_similarity_threshold_boundary(
    tmp_path: Path, shared_words: int, fires: bool
) -> None:
    """Contract: only neighbours ABOVE SimilarityLevel.HIGH are bridge candidates."""
    topic = TOPICS[0].split()
    replacements = ["kumquat", "tamarind", "persimmon", "loquat"]
    twin_body = " ".join(topic[:shared_words] + replacements[: len(topic) - shared_words])
    builder = VaultBuilder(tmp_path)
    _add_hub_with_twin(builder, 0, twin_body=twin_body)
    ctx = builder.build()
    sim = ctx.similarity(_get(ctx, HUBS[0]), _get(ctx, TWINS[0]))
    if fires:
        assert SimilarityLevel.HIGH < sim < SimilarityLevel.VERY_HIGH
        assert_valid_suggestions(bridge_builder.suggest(ctx), "bridge_builder")
    else:
        assert SimilarityLevel.MODERATE < sim <= SimilarityLevel.HIGH
        assert bridge_builder.suggest(ctx) == []


def test_bridge_builder_skips_already_linked_neighbours(tmp_path: Path) -> None:
    """Contract: a highly similar neighbour that is already linked is not suggested."""
    builder = VaultBuilder(tmp_path)
    builder.note(HUBS[0], TOPICS[0], created=CREATED)
    # The twin links to the hub, so it is both the backlink and the neighbour.
    builder.note(TWINS[0], f"{TOPICS[0]} [[{HUBS[0]}]]", created=CREATED)
    ctx = builder.build()
    assert ctx.similarity(_get(ctx, HUBS[0]), _get(ctx, TWINS[0])) > SimilarityLevel.HIGH

    assert bridge_builder.suggest(ctx) == []


def test_bridge_builder_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are never bridge partners or hubs.

    A journal note that duplicates Hub 0's topic would qualify as its unlinked
    twin, and a linked-to journal note would qualify as a hub. The regular twin
    must still be suggested.
    """
    builder = VaultBuilder(tmp_path)
    _add_hub_with_twin(builder, 0)
    builder.journal("Session Echo", TOPICS[0], created=CREATED)
    # A journal "hub" (backlinked) with its own unlinked regular-looking twin.
    builder.journal("Session Hub", TOPICS[1], created=CREATED)
    builder.note("Journal Linker", "See [[Session Hub]] marmot", created=CREATED)
    builder.note("Session Twin", TOPICS[1], created=CREATED)
    ctx = builder.build()

    suggestions = bridge_builder.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "bridge_builder",
        must_reference=[HUBS[0], TWINS[0]],
        must_not_reference=["geist journal", "Session Echo", "Session Hub"],
    )


def test_bridge_builder_reports_each_pair_once_when_both_are_hubs(tmp_path: Path) -> None:
    """Contract: an unordered pair is suggested once.

    Regression: when both notes were hubs the pair was emitted twice (A -> B
    from A's neighbours and B -> A from B's), filling the cap with repeats.
    """
    builder = VaultBuilder(tmp_path)
    _add_hub_with_twin(builder, 0)
    # A second linker makes the twin a hub too.
    builder.note("Twin Linker", f"See [[{TWINS[0]}]] marmot tapir", created=CREATED)
    ctx = builder.build()
    assert {n.title for n in ctx.hubs()} == {HUBS[0], TWINS[0]}

    suggestions = bridge_builder.suggest(ctx)

    assert len(suggestions) == 1
    assert sorted(suggestions[0].notes) == sorted([HUBS[0], TWINS[0]])


def test_bridge_builder_skips_pairs_with_a_shared_graph_neighbour(tmp_path: Path) -> None:
    """Contract: notes two hops apart (a note links both) are not "in different
    parts of your vault", so they are not suggested.

    Regression: only a direct link was checked, so a hub and a twin that the
    same note links to were described as being in different parts of the vault.
    """
    builder = VaultBuilder(tmp_path)
    builder.note(HUBS[0], TOPICS[0], created=CREATED)
    builder.note(TWINS[0], TOPICS[0], created=CREATED)
    builder.note("Linker", f"See [[{HUBS[0]}]] and [[{TWINS[0]}]] quokka", created=CREATED)
    ctx = builder.build()
    assert ctx.similarity(_get(ctx, HUBS[0]), _get(ctx, TWINS[0])) > SimilarityLevel.HIGH
    assert not ctx.links_between(_get(ctx, HUBS[0]), _get(ctx, TWINS[0]))

    assert bridge_builder.suggest(ctx) == []
