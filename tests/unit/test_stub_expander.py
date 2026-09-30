"""Unit tests for stub_expander geist.

Trigger arithmetic (see the geist source):
- a note qualifies when word_count < 50 (whitespace tokens of the whole
  note, including the 2-token "# Title" heading VaultBuilder writes for a
  one-word title) and it has at least one outgoing link or backlink;
- output is capped at 3 suggestions.
"""

from pathlib import Path

import pytest

from geistfabrik.default_geists.code import stub_expander
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEIST = "stub_expander"
CAP = 3
HEADING_TOKENS = 2


def _words(total_words: int) -> str:
    return " ".join(f"term{i}" for i in range(total_words - HEADING_TOKENS))


def _long_note(builder: VaultBuilder, title: str, extra: str = "") -> None:
    # 60 words: too long to be a stub, whatever its links.
    builder.note(title, f"{_words(60)} {extra}")


def test_short_connected_note_is_flagged(tmp_path: Path) -> None:
    # "Stub" (4 words + 1 link) qualifies; "Lonely" is short but unconnected;
    # "Essay" is connected but long.
    builder = VaultBuilder(tmp_path)
    builder.note("Stub", "Seed idea. [[Essay]]")
    builder.note("Lonely", "Seed idea.")
    _long_note(builder, "Essay")

    suggestions = stub_expander.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST)
    assert [s.notes for s in suggestions] == [["Stub"]]
    assert "only 5 words but has 1 connections" in suggestions[0].text


@pytest.mark.parametrize(("total_words", "fires"), [(49, True), (50, False)])
def test_word_count_boundary(tmp_path: Path, total_words: int, fires: bool) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Stub", _words(total_words - 1) + " [[Essay]]")
    _long_note(builder, "Essay")

    suggestions = stub_expander.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Stub"]] if fires else [])


@pytest.mark.parametrize(
    ("stub_body", "essay_extra", "fires"),
    [
        ("Seed idea.", "", False),  # no connections
        ("Seed idea. [[Essay]]", "", True),  # outgoing link only
        ("Seed idea.", "[[Stub]]", True),  # backlink only
    ],
)
def test_needs_at_least_one_connection(
    tmp_path: Path, stub_body: str, essay_extra: str, fires: bool
) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Stub", stub_body)
    _long_note(builder, "Essay", essay_extra)

    suggestions = stub_expander.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Stub"]] if fires else [])


def test_output_is_capped_when_more_notes_qualify(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    planted = [f"Stub {i}" for i in range(6)]
    for title in planted:
        builder.note(title, "Seed idea. [[Essay]]")
    _long_note(builder, "Essay")

    suggestions = stub_expander.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert len(suggestions) == CAP
    referenced = [ref for s in suggestions for ref in s.notes]
    assert len(set(referenced)) == CAP
    assert set(referenced) <= set(planted)


def test_geist_journal_notes_are_never_flagged(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Stub", "Seed idea. [[Essay]]")
    for i in range(4):
        builder.journal(f"Session Log {i}", "Short session. [[Essay]]")
    _long_note(builder, "Essay")

    suggestions = stub_expander.suggest(builder.build())

    assert_valid_suggestions(
        suggestions, GEIST, must_reference=["Stub"], must_not_reference=["Session Log"]
    )


def test_journal_mentions_do_not_count_as_connections(tmp_path: Path) -> None:
    # Regression: every session journal wikilinks the notes it suggested, so
    # counting journal backlinks turned any short note the engine had ever
    # mentioned into a "connected stub" - a feedback loop on its own output.
    builder = VaultBuilder(tmp_path)
    builder.note("Mentioned", "Seed idea.")
    builder.note("Stub", "Seed idea. [[Essay]]")
    builder.journal("Session Log", f"{_words(60)} [[Mentioned]]")
    _long_note(builder, "Essay")

    suggestions = stub_expander.suggest(builder.build())

    assert [s.notes for s in suggestions] == [["Stub"]]


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        builder.note(f"Stub {i}", "Seed idea. [[Essay]]")
    _long_note(builder, "Essay")

    first = [s.text for s in stub_expander.suggest(builder.build())]
    second = [s.text for s in stub_expander.suggest(builder.build())]

    assert first
    assert first == second
