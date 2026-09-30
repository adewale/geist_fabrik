"""Unit tests for the dialectic_triad geist.

dialectic_triad samples up to 5 notes and, for the first 2, pairs the note
(thesis) with its most contrarian note (antithesis, least similar via the
``contrarian_to`` vault function), asking for a synthesis. It returns at
most 2 suggestions.

Fixtures use the bag-of-words test stub: notes sharing words are similar;
disjoint vocabulary gives cosine ~0, i.e. the most contrarian note.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import dialectic_triad
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 2
CREATED = datetime(2024, 1, 1)
SHARED = "harbour lantern compass anchor"


def test_dialectic_triad_pairs_thesis_with_its_opposite(tmp_path: Path) -> None:
    """Contract: each thesis is paired with its least similar note, as plain wikilinks.

    Trigger: "Order" and "Chaos" share SHARED (cosine ~0.6); "Glacier" shares
    nothing, so it is the antithesis of both. Regression guarded: the
    antithesis was rendered from contrarian_to's already-bracketed link,
    giving "[[[[Glacier]]]]" in the text and "[[Glacier]]" in notes.
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
        assert s.text.startswith(f"**Thesis**: [[{thesis}]]\n**Antithesis**: [[{antithesis}]]\n")
        assert "[[[[" not in s.text and "]]]]" not in s.text
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

    The regular notes all share SHARED; the journal note shares nothing, so
    unfiltered it is the most contrarian note for every thesis, and it is a
    thesis candidate itself.
    """
    builder = VaultBuilder(tmp_path)
    regular = ["Order", "Chaos", "Balance"]
    builder.note("Order", f"{SHARED} tidy ledger", created=CREATED)
    builder.note("Chaos", f"{SHARED} tangle storm", created=CREATED)
    builder.note("Balance", f"{SHARED} scales poise", created=CREATED)
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
