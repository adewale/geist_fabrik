"""Unit tests for the dialectic_triad geist.

dialectic_triad samples up to 5 notes and, for the first 2, pairs the note
(thesis) with a note sampled from its 10 least similar notes (the
``contrarian_to`` vault function) that is below SimilarityLevel.WEAK and not
already used in this run, asking for a synthesis. It returns at most 2
suggestions. The distant note is not claimed to oppose the thesis.

Fixtures use the bag-of-words test stub: notes sharing words are similar;
disjoint vocabulary gives cosine ~0, i.e. the most contrarian note.
"""

import random
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import dialectic_triad
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 2
CREATED = datetime(2024, 1, 1)
SHARED = "harbour lantern compass anchor"


def test_dialectic_triad_pairs_thesis_with_a_distant_note(tmp_path: Path) -> None:
    """Contract: each thesis is paired with a distant note, as plain wikilinks,
    and the text claims distance, not opposition.

    Trigger: "Order" and "Chaos" share SHARED (cosine ~0.6, too similar to
    pair); "Glacier" shares nothing, so it is the only distant note for both.
    Regressions guarded: the antithesis was rendered from contrarian_to's
    already-bracketed link, giving "[[[[Glacier]]]]" in the text and
    "[[Glacier]]" in notes; and the text labelled the least similar note an
    "Antithesis" and the pair "opposites", which similarity cannot establish.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Order", f"{SHARED} tidy ledger", created=CREATED)
    builder.note("Chaos", f"{SHARED} tangle storm", created=CREATED)
    builder.note("Glacier", "moraine crevasse serac firn", created=CREATED)
    ctx = builder.build()

    suggestions = dialectic_triad.suggest(ctx)

    assert_valid_suggestions(suggestions, "dialectic_triad", must_reference=["Glacier"])
    for s in suggestions:
        thesis, antithesis = s.notes
        assert s.text == (
            f"**Thesis**: [[{thesis}]]\n"
            f"**Far side**: [[{antithesis}]], one of the notes least like it\n"
            "\nWhat if you read the second as an antithesis to the first? "
            "What would a synthesis of the two look like?"
        )
        if thesis in ("Order", "Chaos"):
            assert antithesis == "Glacier"
        assert thesis != antithesis


def test_dialectic_triad_caps_at_two_distinct_theses(tmp_path: Path) -> None:
    """Contract: with 4 candidate theses, exactly 2 triads with distinct theses."""
    builder = VaultBuilder(tmp_path)
    for word in ["orchard", "glacier", "violin", "bakery"]:
        builder.note(word.title(), f"{word} {word}x {word}y", created=CREATED)
    ctx = builder.build()

    suggestions = dialectic_triad.suggest(ctx)

    assert_valid_suggestions(suggestions, "dialectic_triad", min_count=CAP)
    assert len(suggestions) == CAP
    assert len({s.notes[0] for s in suggestions}) == CAP


@pytest.mark.parametrize(("notes", "fires"), [(1, False), (2, True)])
def test_dialectic_triad_needs_an_antithesis(tmp_path: Path, notes: int, fires: bool) -> None:
    """Contract: a lone note has no antithesis -> []; two notes -> a triad."""
    builder = VaultBuilder(tmp_path)
    builder.note("Order", f"{SHARED} tidy ledger", created=CREATED)
    if notes == 2:
        builder.note("Glacier", "moraine crevasse serac firn", created=CREATED)
    ctx = builder.build()

    suggestions = dialectic_triad.suggest(ctx)

    if fires:
        assert_valid_suggestions(
            suggestions, "dialectic_triad", must_reference=["Order", "Glacier"]
        )
    else:
        assert suggestions == []


def test_dialectic_triad_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are neither theses nor antitheses.

    The regular notes share one word (cosine ~0.2, distant enough to pair);
    the journal note shares nothing, so unfiltered it is the most contrarian
    note for every thesis, and it is a thesis candidate itself.
    """
    builder = VaultBuilder(tmp_path)
    regular = ["Order", "Chaos", "Balance"]
    builder.note("Order", "harbour tidy ledger quill", created=CREATED)
    builder.note("Chaos", "harbour tangle storm gust", created=CREATED)
    builder.note("Balance", "harbour scales poise fulcrum", created=CREATED)
    builder.journal("Session Echo", "moraine crevasse serac firn", created=CREATED)
    ctx = builder.build()

    suggestions = dialectic_triad.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "dialectic_triad",
        min_count=CAP,
        must_not_reference=["geist journal", "Session Echo"],
    )
    assert all(set(s.notes) <= set(regular) for s in suggestions)


def test_dialectic_triad_does_not_reuse_a_distant_note(tmp_path: Path) -> None:
    """Contract: within one run, no note is the far side of two triads.

    Trigger: six notes share SHARED (too similar to pair with each other);
    "Glacier" shares nothing, so it is the only distant note for all six.
    Regression: the antithesis was always the single least similar note, so
    one outlier was the "antithesis" of both triads (on a real vault, two
    notes covered 45% of all theses).
    """
    builder = VaultBuilder(tmp_path)
    for word in ["tidy", "storm", "scales", "quill", "gust", "poise"]:
        builder.note(word.title(), f"{SHARED} {word}", created=CREATED)
    builder.note("Glacier", "moraine crevasse serac firn", created=CREATED)
    ctx = builder.build()

    suggestions = dialectic_triad.suggest(ctx)

    assert [s.notes[1] for s in suggestions] == ["Glacier"]


def test_dialectic_triad_samples_among_distant_notes(tmp_path: Path) -> None:
    """Contract: the far side is sampled from the thesis's distant notes, not
    always the single least similar one.

    Regression: rank 1 of contrarian_to was always taken, so a thesis met the
    same "antithesis" every session.
    """
    builder = VaultBuilder(tmp_path)
    for word in ["orchard", "glacier", "violin", "bakery", "comet"]:
        builder.note(word.title(), f"{word} {word}x {word}y", created=CREATED)
    ctx = builder.build()

    far_sides: set[str] = set()
    for seed in range(30):
        ctx.rng = random.Random(seed)
        far_sides.update(
            s.notes[1] for s in dialectic_triad.suggest(ctx) if s.notes[0] == "Orchard"
        )

    assert len(far_sides) > 1
