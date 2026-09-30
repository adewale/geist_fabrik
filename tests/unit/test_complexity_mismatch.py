"""Unit tests for complexity_mismatch geist.

Trigger arithmetic (see the geist source), with N = non-journal note count:
- importance = (outgoing links + 2 * backlinks) / N;
- "expand" fires when importance > 0.1 and word_count < 100;
- "simplify" fires when importance < 0.05, word_count > 300 and fewer than
  2 outgoing links;
- word_count counts whitespace tokens of the whole note, including the
  "# Title" heading VaultBuilder writes (2 tokens for a one-word title);
- output is capped at 3 suggestions.
"""

from pathlib import Path

import pytest

from geistfabrik.default_geists.code import complexity_mismatch
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEIST = "complexity_mismatch"
CAP = 3


def _words(count: int) -> str:
    return " ".join(f"term{i}" for i in range(count))


def _fillers(builder: VaultBuilder, count: int) -> None:
    for i in range(count):
        builder.note(f"Filler {i}", "Brief plain remark.")


def test_connected_stub_and_long_isolated_note_are_both_flagged(tmp_path: Path) -> None:
    # 10 notes. "Hub" has two backlinks: importance (0 + 2*2)/10 = 0.4 > 0.1
    # with 4 words -> expand. "Tome" has 2 + 400 words and no links:
    # importance 0 -> simplify. The linkers have importance 1/10 = 0.1, which
    # is not > 0.1, so they stay silent.
    builder = VaultBuilder(tmp_path)
    builder.note("Hub", "Seed idea.")
    builder.note("Linker A", "See [[Hub]].")
    builder.note("Linker B", "See [[Hub]].")
    builder.note("Tome", _words(400))
    _fillers(builder, 6)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=2)
    by_note = {s.notes[0]: s.text for s in suggestions}
    assert set(by_note) == {"Hub", "Tome"}
    assert by_note["Hub"].startswith("What if you expanded [[Hub]]?")
    assert "402 words" in by_note["Tome"]
    assert by_note["Tome"].startswith("What if you simplified [[Tome]]?")


@pytest.mark.parametrize(("outgoing_links", "fires"), [(2, False), (3, True)])
def test_importance_boundary_for_expand(tmp_path: Path, outgoing_links: int, fires: bool) -> None:
    # 20 notes: importance = links / 20, so 2 links = 0.1 (not > 0.1) and
    # 3 links = 0.15. Each linked filler gets 1 backlink = 2/20 = 0.1: silent.
    builder = VaultBuilder(tmp_path)
    links = " ".join(f"[[Filler {i}]]" for i in range(outgoing_links))
    builder.note("Stub", f"Short. {links}")
    _fillers(builder, 19)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Stub"]] if fires else [])


def test_backlinks_weigh_double_in_importance(tmp_path: Path) -> None:
    # 15 notes: one backlink gives importance 2/15 = 0.13 > 0.1 because
    # backlinks count twice; the linker's single outgoing link gives 1/15.
    builder = VaultBuilder(tmp_path)
    builder.note("Stub", "Seed idea.")
    builder.note("Linker", "See [[Stub]].")
    _fillers(builder, 13)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert [s.notes for s in suggestions] == [["Stub"]]
    assert "(1 links)" in suggestions[0].text


@pytest.mark.parametrize(("body_words", "fires"), [(298, False), (299, True)])
def test_word_count_boundary_for_simplify(tmp_path: Path, body_words: int, fires: bool) -> None:
    # word_count = 2 heading tokens + body: 300 is not > 300, 301 is.
    builder = VaultBuilder(tmp_path)
    builder.note("Tome", _words(body_words))
    _fillers(builder, 9)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Tome"]] if fires else [])


@pytest.mark.parametrize(("outgoing_links", "fires"), [(1, True), (2, False)])
def test_link_count_boundary_for_simplify(tmp_path: Path, outgoing_links: int, fires: bool) -> None:
    # 41 notes keep importance below 0.05 for both cases (2/41 = 0.049), so
    # only the "fewer than 2 links" rule separates them. Linked fillers get
    # importance 2/41 and are short, so they never fire either way.
    builder = VaultBuilder(tmp_path)
    links = " ".join(f"[[Filler {i}]]" for i in range(outgoing_links))
    builder.note("Tome", f"{_words(400)} {links}")
    _fillers(builder, 40)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Tome"]] if fires else [])


def test_output_is_capped_when_more_notes_qualify(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    planted = [f"Tome {i}" for i in range(6)]
    for title in planted:
        builder.note(title, _words(400))
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
    builder.note("Tome", _words(400))
    for i in range(4):
        builder.journal(f"Session Log {i}", _words(400))
    _fillers(builder, 9)

    suggestions = complexity_mismatch.suggest(builder.build())

    assert_valid_suggestions(
        suggestions, GEIST, must_reference=["Tome"], must_not_reference=["Session Log"]
    )


def test_journal_mentions_do_not_make_a_note_important(tmp_path: Path) -> None:
    # Regression: session journals wikilink every note they suggest. Counted
    # as backlinks, two journal mentions gave "Mentioned" importance 4/10 and
    # a "highly connected" expand prompt built on the geist's own output.
    builder = VaultBuilder(tmp_path)
    builder.note("Mentioned", "Seed idea.")
    builder.journal("Session Log 0", "Suggested [[Mentioned]].")
    builder.journal("Session Log 1", "Suggested [[Mentioned]] again.")
    _fillers(builder, 9)

    assert complexity_mismatch.suggest(builder.build()) == []


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        builder.note(f"Tome {i}", _words(400))
    _fillers(builder, 4)

    first = [s.text for s in complexity_mismatch.suggest(builder.build())]
    second = [s.text for s in complexity_mismatch.suggest(builder.build())]

    assert first
    assert first == second
