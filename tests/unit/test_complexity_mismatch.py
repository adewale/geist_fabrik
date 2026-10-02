"""Unit tests for complexity_mismatch geist.

Trigger arithmetic (see the geist source); thresholds are absolute, not
scaled by vault size:
- "expand" fires when >= 5 non-journal notes link to a note of < 100 words;
- "simplify" fires when a note has > 1500 words, no outgoing links and no
  backlinks;
- word_count counts whitespace tokens of the note body, including the
  "# Title" heading VaultBuilder writes (2 tokens for a one-word title);
- output is capped at 3 suggestions.
"""

from pathlib import Path

import pytest

from geistfabrik.default_geists.code import complexity_mismatch
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEIST = "complexity_mismatch"
CAP = 3
LONG = 1600  # body words of a note long enough to simplify


def _words(count: int) -> str:
    return " ".join(f"term{i}" for i in range(count))


def _fillers(builder: VaultBuilder, count: int) -> None:
    for i in range(count):
        builder.note(f"Filler {i}", "Brief plain remark.")


def _linkers(builder: VaultBuilder, target: str, count: int) -> None:
    for i in range(count):
        builder.note(f"Linker {i}", f"See [[{target}]].")


def test_connected_stub_and_long_isolated_note_are_both_flagged(tmp_path: Path) -> None:
    """Contract: a stub with >= 5 backlinks gets "expand"; a > 1500-word note
    with no links in or out gets "simplify". The linkers (1 outgoing link,
    3 words) match neither case."""
    builder = VaultBuilder(tmp_path)
    builder.note("Hub", "Seed idea.")
    _linkers(builder, "Hub", 5)
    builder.note("Tome", _words(LONG))
    _fillers(builder, 3)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=2)
    assert sorted(s.text for s in suggestions) == [
        "What if you expanded [[Hub]]? It's highly connected (5 notes link to it) but "
        "only 4 words. Might it deserve more depth?",
        "What if you simplified [[Tome]]? It's 1602 words with no links in or out. "
        "Could it be more focused or split into multiple notes?",
    ]


@pytest.mark.parametrize(("backlinks", "fires"), [(4, False), (5, True)])
def test_backlink_boundary_for_expand(tmp_path: Path, backlinks: int, fires: bool) -> None:
    """Contract: "highly connected" means at least 5 notes link to the stub."""
    builder = VaultBuilder(tmp_path)
    builder.note("Stub", "Seed idea.")
    _linkers(builder, "Stub", backlinks)
    _fillers(builder, 5)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Stub"]] if fires else [])


def test_small_vault_does_not_inflate_importance(tmp_path: Path) -> None:
    """Contract: connectivity is not scaled by vault size.

    Regression: importance was (links + 2 * backlinks) / N, so in a 10-note
    vault a stub with 2 backlinks (or 3 outgoing links) scored 0.4 and was
    called "highly connected", a bar no note could reach in a large vault.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Stub", "Seed idea. [[Filler 0]] [[Filler 1]] [[Filler 2]]")
    builder.note("Linked", "Seed idea.")
    _linkers(builder, "Linked", 2)
    _fillers(builder, 5)

    assert complexity_mismatch.suggest(builder.build()) == []


@pytest.mark.parametrize(("body_words", "fires"), [(1498, False), (1499, True)])
def test_word_count_boundary_for_simplify(tmp_path: Path, body_words: int, fires: bool) -> None:
    """Contract: "long" means more than 1500 words (2 heading tokens + body)."""
    builder = VaultBuilder(tmp_path)
    builder.note("Tome", _words(body_words))
    _fillers(builder, 9)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Tome"]] if fires else [])


def test_moderately_long_note_is_not_flagged(tmp_path: Path) -> None:
    """Regression: any note over 300 words with < 2 links was told to simplify,
    which in a real vault is most long notes (27 of 77 in the audit vault)."""
    builder = VaultBuilder(tmp_path)
    builder.note("Essay", _words(900))
    _fillers(builder, 9)

    assert complexity_mismatch.suggest(builder.build()) == []


@pytest.mark.parametrize("link", ["outgoing", "backlink"])
def test_any_link_in_or_out_prevents_simplify(tmp_path: Path, link: str) -> None:
    """Contract: "no links in or out" is literally true of a flagged note.

    Regression: the text said "only 1 links" for a note with one outgoing link
    and ignored backlinks entirely.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Tome", f"{_words(LONG)} [[Filler 0]]" if link == "outgoing" else _words(LONG))
    if link == "backlink":
        builder.note("Pointer", "See [[Tome]].")
    _fillers(builder, 9)

    assert complexity_mismatch.suggest(builder.build()) == []


def test_output_is_capped_when_more_notes_qualify(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    planted = [f"Tome {i}" for i in range(6)]
    for title in planted:
        builder.note(title, _words(LONG))
    _fillers(builder, 4)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert len(suggestions) == CAP
    referenced = [ref for s in suggestions for ref in s.notes]
    assert len(set(referenced)) == CAP
    assert set(referenced) <= set(planted)


def test_geist_journal_notes_are_never_flagged(tmp_path: Path) -> None:
    # Journal notes are long and unlinked, exactly like the regular "Tome".
    builder = VaultBuilder(tmp_path)
    builder.note("Tome", _words(LONG))
    for i in range(4):
        builder.journal(f"Session Log {i}", _words(LONG))
    _fillers(builder, 9)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert_valid_suggestions(
        suggestions, GEIST, must_reference=["Tome"], must_not_reference=["Session Log"]
    )


def test_journal_mentions_do_not_make_a_note_important(tmp_path: Path) -> None:
    # Regression: session journals wikilink every note they suggest. Counted
    # as backlinks, journal mentions made a stub "highly connected" on the
    # strength of the geist's own output.
    builder = VaultBuilder(tmp_path)
    builder.note("Mentioned", "Seed idea.")
    for i in range(5):
        builder.journal(f"Session Log {i}", "Suggested [[Mentioned]].")
    _fillers(builder, 9)

    assert complexity_mismatch.suggest(builder.build()) == []


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        builder.note(f"Tome {i}", _words(LONG))
    _fillers(builder, 4)

    first = [s.text for s in complexity_mismatch.suggest(builder.build())]
    second = [s.text for s in complexity_mismatch.suggest(builder.build())]

    assert first
    assert first == second
