"""Unit tests for stub_expander geist.

Trigger arithmetic (see the geist source):
- a note qualifies when word_count < 50 (whitespace tokens of the body,
  frontmatter excluded, including the 2-token "# Title" heading VaultBuilder
  writes for a one-word title) and at least one other user note links to it
  (outgoing links alone do not count);
- a well-linked stub (merged in from the retired complexity_mismatch) also
  qualifies: word_count < 100 and at least 5 notes link to it;
- the most linked-to stubs come first; output is capped at 3 suggestions.
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
    # 120 words: too long to be a stub, whatever its links.
    builder.note(title, f"{_words(120)} {extra}")


def test_short_linked_to_note_is_flagged(tmp_path: Path) -> None:
    """Contract: the text states the body word count and how many notes link
    to the stub, with correct plurals.

    Regression: the text said "has 1 connections", counting raw outgoing
    links (duplicates, embeds, unresolved targets) as connections.
    """
    # "Stub" (5 words) is linked from "Essay"; "Lonely" is short but
    # unconnected; "Essay" is linked from "Stub" but long.
    builder = VaultBuilder(tmp_path)
    builder.note("Stub", "Seed idea. [[Essay]]")
    builder.note("Lonely", "Seed idea.")
    _long_note(builder, "Essay", "[[Stub]]")

    suggestions = stub_expander.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST)
    assert [(s.text, s.notes) for s in suggestions] == [
        (
            "[[Stub]] has only 5 words, but 1 note links to it. "
            "Is it a seed waiting to grow, or finished as it is?",
            ["Stub"],
        )
    ]


@pytest.mark.parametrize(("total_words", "fires"), [(49, True), (50, False)])
def test_word_count_boundary(tmp_path: Path, total_words: int, fires: bool) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Stub", _words(total_words - 1) + " [[Essay]]")
    _long_note(builder, "Essay", "[[Stub]]")

    suggestions = stub_expander.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Stub"]] if fires else [])


@pytest.mark.parametrize(
    ("stub_body", "essay_extra", "fires"),
    [
        ("Seed idea.", "", False),  # no connections
        ("Seed idea. [[Essay]]", "", False),  # outgoing link only
        ("Seed idea. [[Trips]] [[Kyoto]] [[Japan]]", "", False),  # unresolved links
        ("Seed idea.", "[[Stub]]", True),  # backlink only
    ],
)
def test_needs_at_least_one_backlink(
    tmp_path: Path, stub_body: str, essay_extra: str, fires: bool
) -> None:
    """Contract: a stub is worth expanding when another note links to it.

    Regression: any outgoing link qualified a note, so daily notes embedding
    a template and frontmatter-only notes listing unresolved links were
    suggested as "connected stubs". (Updated: the outgoing-only row used to
    expect a suggestion.)
    """
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
    _long_note(builder, "Essay", " ".join(f"[[{t}]]" for t in planted))

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
    _long_note(builder, "Essay", "[[Stub]] [[Session Log 0]]")

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
    _long_note(builder, "Essay", "[[Stub]]")

    suggestions = stub_expander.suggest(builder.build())

    assert [s.notes for s in suggestions] == [["Stub"]]


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        builder.note(f"Stub {i}", "Seed idea. [[Essay]]")
    _long_note(builder, "Essay", " ".join(f"[[Stub {i}]]" for i in range(6)))

    first = [s.text for s in stub_expander.suggest(builder.build())]
    second = [s.text for s in stub_expander.suggest(builder.build())]

    assert first
    assert first == second


def test_most_linked_to_stub_is_always_named(tmp_path: Path) -> None:
    """Contract: stubs are ranked by backlinks; the seed only breaks ties.

    Regression: a uniform sample of 3 from every candidate meant the best
    stub (a thin note many notes link to, like "Obsidian" with 6 backlinks
    in the real run) was often not named.
    """
    builder = VaultBuilder(tmp_path)
    minor = [f"Minor {i}" for i in range(7)]
    for title in [*minor, "Hub Stub"]:
        builder.note(title, "Seed idea.")
    _long_note(builder, "Essay", " ".join(f"[[{t}]]" for t in [*minor, "Hub Stub"]))
    _long_note(builder, "Review", "[[Hub Stub]]")
    _long_note(builder, "Survey", "[[Hub Stub]]")
    ctx = builder.build()

    suggestions = stub_expander.suggest(ctx)

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert len(suggestions) == CAP
    assert suggestions[0].notes == ["Hub Stub"]
    assert "but 3 notes link to it" in suggestions[0].text
    assert {ref for s in suggestions[1:] for ref in s.notes} <= set(minor)


def _linkers(builder: VaultBuilder, target: str, count: int) -> None:
    for i in range(count):
        _long_note(builder, f"Linker {i}", f"[[{target}]]")


@pytest.mark.parametrize(("backlinks", "fires"), [(4, False), (5, True)])
def test_well_linked_note_under_100_words_is_a_stub(
    tmp_path: Path, backlinks: int, fires: bool
) -> None:
    """Contract: a note of 50-99 words that at least 5 notes link to is a
    stub worth expanding; with 4 backlinks it is not.

    Regression: complexity_mismatch's "highly connected but only N words"
    case lived in a separate geist that named the same notes as this one;
    before the merge stub_expander ignored every note of 50+ words.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Pillar", _words(70))
    _linkers(builder, "Pillar", backlinks)

    suggestions = stub_expander.suggest(builder.build())

    expected = [
        (
            "[[Pillar]] has only 70 words, but 5 notes link to it. Is its brevity "
            "intentional, a hinge that works because it is short, or a placeholder "
            "waiting to grow?",
            ["Pillar"],
        )
    ]
    assert [(s.text, s.notes) for s in suggestions] == (expected if fires else [])


@pytest.mark.parametrize(("total_words", "fires"), [(99, True), (100, False)])
def test_well_linked_stub_word_boundary(tmp_path: Path, total_words: int, fires: bool) -> None:
    """Contract: a well-linked note is a stub only under 100 words.

    Regression: complexity_mismatch's bound (< 100 words with >= 5
    backlinks) carried over unchanged.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Pillar", _words(total_words))
    _linkers(builder, "Pillar", 5)

    suggestions = stub_expander.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Pillar"]] if fires else [])


def test_journal_mentions_do_not_make_a_note_well_linked(tmp_path: Path) -> None:
    """Contract: only user notes count towards the 5 backlinks.

    Regression (from complexity_mismatch): session journals wikilink every
    note they suggest, so journal mentions made a note "highly connected" on
    the strength of the engine's own output.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Pillar", _words(70))
    builder.note("Stub", "Seed idea.")
    for i in range(5):
        builder.journal(f"Session Log {i}", "Suggested [[Pillar]].")
    _long_note(builder, "Essay", "[[Stub]]")

    suggestions = stub_expander.suggest(builder.build())

    assert [s.notes for s in suggestions] == [["Stub"]]
