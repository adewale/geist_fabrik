"""Unit tests for the creative_collision geist.

creative_collision draws 10 random note pairs and suggests combining any
unlinked pair whose similarity is in the "loosely related" window
SimilarityLevel.NOISE (0.15) < sim < SimilarityLevel.WEAK (0.35).
It returns at most 3 suggestions. A pair created >= 2 years apart is worded
across eras with real dates (absorbed from temporal_mirror); other pairs get
one of three neutral templates (absorbed from note_combinations).

Fixtures use the bag-of-words test stub. Each note has a 2-word unique
title, 5 unique body words and 3 words shared by every note, so any two notes
have cosine ~3/10 = 0.3: inside the window.
"""

from datetime import datetime, timedelta
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
    assert SimilarityLevel.NOISE < _sim(ctx, a, b) < SimilarityLevel.WEAK

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
        # Same body as note A: cosine ~0.8 >= WEAK (too similar to collide).
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
        assert sim >= SimilarityLevel.WEAK
    else:
        assert sim <= SimilarityLevel.NOISE

    assert creative_collision.suggest(ctx) == []


def test_creative_collision_skips_linked_pairs(tmp_path: Path) -> None:
    """Contract: an in-window pair that is already linked is not a collision.

    The link text adds A's two title words to B, so B shares only one SHARED
    word to stay in the window (3 shared words of 10: cosine ~0.3).
    """
    builder = VaultBuilder(tmp_path)
    a = _note(builder, 0)
    b = _note(builder, 1, body=f"{UNIQUE[1]} lantern [[{TITLES[0]}]]")
    ctx = builder.build()
    assert SimilarityLevel.NOISE < _sim(ctx, a, b) < SimilarityLevel.WEAK

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


def test_creative_collision_rejects_clearly_related_pairs(tmp_path: Path) -> None:
    """Contract: a pair sharing real vocabulary (similarity ~0.42, between WEAK
    and MODERATE) is not a distant collision; the text claims only what is
    checked (unlinked, loosely related).

    Regression: the window ran up to MODERATE (0.5), which admitted ~70% of all
    pairs on a real vault, and the text called same-project notes "from
    different domains".
    """
    builder = VaultBuilder(tmp_path)
    close = f"{SHARED} beacon anchor"  # 5 shared words of 12: cosine ~0.42
    a = _note(builder, 0, body=f"{UNIQUE[0]} {close}")
    b = _note(builder, 1, body=f"{UNIQUE[1]} {close}")
    c = _note(builder, 2)
    ctx = builder.build()
    assert SimilarityLevel.WEAK < _sim(ctx, a, b) < SimilarityLevel.MODERATE

    suggestions = creative_collision.suggest(ctx)

    assert {frozenset(s.notes) for s in suggestions} == {frozenset({a, c}), frozenset({b, c})}
    assert all("unlinked and only loosely related" in s.text for s in suggestions)
    assert not any("different domains" in s.text for s in suggestions)


def test_creative_collision_frames_a_pair_created_years_apart_across_eras(
    tmp_path: Path,
) -> None:
    """Contract: an in-window pair created >= 2 years apart names both real
    creation dates, older note first, and the whole-year gap.

    Regression: temporal_mirror (now retired into this geist) juxtaposed notes
    as "From period 7: [[A]]. From period 2: [[B]]", a label that said nothing
    about when either note was written; creative_collision said nothing about
    time at all.
    """
    builder = VaultBuilder(tmp_path)
    old = datetime(2019, 3, 10)
    new = datetime(2024, 6, 1)
    builder.note(TITLES[1], f"{UNIQUE[1]} {SHARED}", created=new, modified=new)
    builder.note(TITLES[0], f"{UNIQUE[0]} {SHARED}", created=old, modified=old)
    ctx = builder.build()

    suggestions = creative_collision.suggest(ctx)

    assert [(s.text, s.notes) for s in suggestions] == [
        (
            f"[[{TITLES[0]}]] was created in March 2019 and [[{TITLES[1]}]] in June 2024, "
            "5 years later. They're unlinked and only loosely related. "
            "What would each era make of the other?",
            [TITLES[0], TITLES[1]],
        )
    ]


@pytest.mark.parametrize(
    ("days_apart", "cross_era"), [(729, False), (730, True)], ids=["1y364d", "2y"]
)
def test_creative_collision_cross_era_boundary_is_two_years(
    tmp_path: Path, days_apart: int, cross_era: bool
) -> None:
    """Contract: the era framing needs a gap of at least 2 * 365 days; anything
    shorter gets a neutral pairing template that mentions no dates."""
    builder = VaultBuilder(tmp_path)
    first = datetime(2022, 1, 1)
    second = first + timedelta(days=days_apart)
    builder.note(TITLES[0], f"{UNIQUE[0]} {SHARED}", created=first, modified=first)
    builder.note(TITLES[1], f"{UNIQUE[1]} {SHARED}", created=second, modified=second)
    ctx = builder.build()

    (suggestion,) = creative_collision.suggest(ctx)

    assert ("2 years later" in suggestion.text) is cross_era, suggestion.text
    assert ("January 2022" in suggestion.text) is cross_era, suggestion.text


def test_creative_collision_rotates_neutral_pairing_templates(tmp_path: Path) -> None:
    """Contract: same-era pairs are worded with one of three neutral templates
    (absorbed from note_combinations), each claiming only "unlinked and only
    loosely related"; over several sessions all three are used.

    Regression: every collision read "What if you combined ideas from ..."; the
    retired note_combinations Tracery geist carried the other pairings.
    """
    builder = VaultBuilder(tmp_path)
    for i in range(len(TITLES)):
        _note(builder, i)

    openings = set()
    for seed in range(12):
        ctx = builder.build(seed=seed)
        for s in creative_collision.suggest(ctx):
            assert "unlinked and only loosely related" in s.text, s.text
            assert s.text.startswith(("What if you combined", "Consider connecting", "[[")), s.text
            openings.add(s.text.split()[0] if not s.text.startswith("[[") else "[[")

    assert openings == {"What", "Consider", "[["}
