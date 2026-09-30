"""Unit tests for the creative_collision geist.

creative_collision draws 10 random note pairs and suggests combining any
unlinked pair whose similarity is in the "different but not unrelated"
window SimilarityLevel.NOISE (0.15) < sim < SimilarityLevel.MODERATE (0.5).
It returns at most 3 suggestions.

Fixtures use the bag-of-words test stub. Each note has a 2-word unique
title, 5 unique body words and 3 words shared by every note, so any two notes
have cosine ~3/10 = 0.3: inside the window.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import creative_collision
from geistfabrik.similarity_analysis import SimilarityLevel
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 3
CREATED = datetime(2024, 1, 1)
SHARED = "lantern compass harbour"
UNIQUE = [
    "orchard pruning grafting cider scion",
    "glacier moraine crevasse serac firn",
    "violin bowing rosin vibrato luthier",
    "sourdough levain crumb proofing banneton",
    "comet orbit perihelion nucleus coma",
    "beehive honeycomb pollen nectar apiary",
    "loom weaving warp weft heddle",
    "volcano magma caldera fumarole tephra",
]
TITLES = [
    "Apple Grove",
    "Ice Field",
    "String Craft",
    "Bread Baking",
    "Sky Watch",
    "Bee Keeping",
    "Cloth Making",
    "Fire Mountain",
]


def _note(builder: VaultBuilder, i: int, body: str | None = None) -> str:
    builder.note(TITLES[i], body or f"{UNIQUE[i]} {SHARED}", created=CREATED)
    return TITLES[i]


def _sim(ctx: VaultContext, a: str, b: str) -> float:
    na, nb = ctx.resolve_link_target(a), ctx.resolve_link_target(b)
    assert na is not None and nb is not None
    return ctx.similarity(na, nb)


def test_creative_collision_pairs_moderately_related_notes(tmp_path: Path) -> None:
    """Contract: an unlinked pair inside the similarity window is suggested once.

    Two notes: every random draw is the same pair, which must be reported
    once, not once per draw.
    """
    builder = VaultBuilder(tmp_path)
    a, b = _note(builder, 0), _note(builder, 1)
    ctx = builder.build()
    assert SimilarityLevel.NOISE < _sim(ctx, a, b) < SimilarityLevel.MODERATE

    suggestions = creative_collision.suggest(ctx)

    assert_valid_suggestions(suggestions, "creative_collision", must_reference=[a, b])
    assert len(suggestions) == 1
    assert set(suggestions[0].notes) == {a, b}
    assert f"[[{a}]]" in suggestions[0].text and f"[[{b}]]" in suggestions[0].text


def test_creative_collision_caps_at_three_distinct_pairs(tmp_path: Path) -> None:
    """Contract: with 28 qualifying pairs (8 notes), exactly 3 distinct pairs return."""
    builder = VaultBuilder(tmp_path)
    titles = [_note(builder, i) for i in range(len(TITLES))]
    ctx = builder.build()

    suggestions = creative_collision.suggest(ctx)

    assert_valid_suggestions(suggestions, "creative_collision", min_count=CAP)
    assert len(suggestions) == CAP
    pairs = {frozenset(s.notes) for s in suggestions}
    assert len(pairs) == CAP
    assert all(pair <= set(titles) for pair in pairs)


@pytest.mark.parametrize(
    ("body_b", "reason"),
    [
        # Same body as note A: cosine ~0.8 >= MODERATE (too similar to collide).
        (f"{UNIQUE[0]} {SHARED}", "too similar"),
        # Disjoint vocabulary: cosine ~0 <= NOISE (unrelated, not a collision).
        ("marmot quokka platypus echidna wombat", "unrelated"),
    ],
    ids=["too_similar", "unrelated"],
)
def test_creative_collision_rejects_pairs_outside_window(
    tmp_path: Path, body_b: str, reason: str
) -> None:
    """Contract: pairs at or beyond either end of the window are never suggested."""
    builder = VaultBuilder(tmp_path)
    a, b = _note(builder, 0), _note(builder, 1, body=body_b)
    ctx = builder.build()
    sim = _sim(ctx, a, b)
    if reason == "too similar":
        assert sim >= SimilarityLevel.MODERATE
    else:
        assert sim <= SimilarityLevel.NOISE

    assert creative_collision.suggest(ctx) == []


def test_creative_collision_skips_linked_pairs(tmp_path: Path) -> None:
    """Contract: an in-window pair that is already linked is not a collision."""
    builder = VaultBuilder(tmp_path)
    a = _note(builder, 0)
    b = _note(builder, 1, body=f"{UNIQUE[1]} {SHARED} [[{TITLES[0]}]]")
    ctx = builder.build()
    assert SimilarityLevel.NOISE < _sim(ctx, a, b) < SimilarityLevel.MODERATE

    assert creative_collision.suggest(ctx) == []


def test_creative_collision_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are never collided with.

    Four journal notes share the same 3 words, so every journal/regular pair
    is inside the window; unfiltered, 14 of the 15 pairs involve one.
    """
    builder = VaultBuilder(tmp_path)
    a, b = _note(builder, 0), _note(builder, 1)
    journal = []
    for i in range(2, 6):
        title = f"Session {i}"
        builder.journal(title, f"{UNIQUE[i]} {SHARED}", created=CREATED)
        journal.append(title)
    ctx = builder.build()

    suggestions = creative_collision.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "creative_collision",
        must_reference=[a, b],
        must_not_reference=["geist journal", *journal],
    )
