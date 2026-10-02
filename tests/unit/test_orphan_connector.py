"""Unit tests for the orphan_connector geist (a code geist; it was Tracery).

Trigger arithmetic (see the geist source):
- an orphan is a note with no links in or out (VaultContext.orphans());
  geist journal notes are never orphans, and a journal mention is not a
  backlink;
- one suggestion samples among the 10 most recently modified orphans;
- one more names a long orphan (> 1500 body words, merged in from the
  retired complexity_mismatch) with "split it, or link it?";
- each suggestion names the orphan's two nearest notes by meaning, and no
  orphan is the subject of two suggestions.

word_count counts whitespace tokens of the body, including the 2-token
"# Title" heading VaultBuilder writes for a one-word title.
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import orphan_connector
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEIST = "orphan_connector"
QUESTIONS = orphan_connector.QUESTIONS
HEADING_TOKENS = 2


def _words(total_words: int) -> str:
    return " ".join(f"term{i}" for i in range(total_words - HEADING_TOKENS))


def _garden(builder: VaultBuilder) -> None:
    """Two linked notes sharing the orphan's vocabulary; Bed is the closer."""
    builder.note("Bed", "compost mulch seedling trowel [[Shed]]")
    builder.note("Shed", "compost mulch rake hoe [[Bed]]")
    builder.note("Harbour", "ferry quay tide mooring [[Bed]]")


def _texts(question_tail: str, orphan: str) -> set[str]:
    return {f"[[{orphan}]] has no links in or out. {q}{question_tail}" for q in QUESTIONS}


def test_names_an_orphan_and_its_nearest_notes(tmp_path: Path) -> None:
    """Contract: the orphan is named with its two nearest notes by meaning,
    as places it might link to; linked notes are never named as the orphan.

    Regression: the Tracery grammar said "what if it relates to a larger
    theme?" and never named a note to link to.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Seedbank", "compost mulch seedling trowel")
    _garden(builder)

    suggestions = orphan_connector.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST)
    assert [s.notes for s in suggestions] == [["Seedbank", "Bed", "Shed"]]
    tail = " Could it link to [[Bed]] or [[Shed]], the notes closest to it in meaning?"
    assert suggestions[0].text in _texts(tail, "Seedbank")


def test_single_neighbour_is_named_in_the_singular(tmp_path: Path) -> None:
    """Contract: with one other note, the text says "the note closest"."""
    builder = VaultBuilder(tmp_path)
    builder.note("Seedbank", "compost mulch seedling trowel")
    builder.note("Bed", "compost mulch seedling [[Nowhere]]")  # not an orphan

    suggestions = orphan_connector.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST)
    assert [s.notes for s in suggestions] == [["Seedbank", "Bed"]]
    tail = " Could it link to [[Bed]], the note closest to it in meaning?"
    assert suggestions[0].text in _texts(tail, "Seedbank")


@pytest.mark.parametrize(("total_words", "long"), [(1500, False), (1501, True)])
def test_long_orphan_is_asked_split_it_or_link_it(
    tmp_path: Path, total_words: int, long: bool
) -> None:
    """Contract: an orphan of more than 1500 words gets "split it into
    smaller notes, or link it to ..." with its word count, in addition to
    the recent-orphan suggestion about a different note.

    Regression: the long-unlinked-note case lived in complexity_mismatch
    ("simplify it"), a separate geist naming the same orphans as this one;
    orphan_connector never looked at length.
    """
    builder = VaultBuilder(tmp_path)
    vocabulary = ["compost", "mulch", "seedling", "trowel"]
    tome = " ".join(vocabulary[i % 4] for i in range(total_words - HEADING_TOKENS))
    builder.note("Tome", tome, modified=datetime(2023, 1, 1))
    builder.note("Seedbank", "ferry quay tide mooring", modified=datetime(2024, 3, 1))
    _garden(builder)
    ctx = builder.build()
    tome_note = ctx.resolve_link_target("Tome")
    assert tome_note is not None
    assert ctx.metadata(tome_note)["word_count"] == total_words

    suggestions = orphan_connector.suggest(ctx)

    assert_valid_suggestions(suggestions, GEIST)
    long_texts = [s.text for s in suggestions if "runs to" in s.text]
    expected = [
        f"[[Tome]] runs to {total_words} words with no links in or out. Could you split "
        "it into smaller notes, or link it to [[Bed]] or [[Shed]], the notes closest "
        "to it in meaning?"
    ]
    assert long_texts == (expected if long else [])
    assert len(suggestions) == (2 if long else 1)
    orphans_named = [s.notes[0] for s in suggestions]
    assert len(set(orphans_named)) == len(orphans_named)


@pytest.mark.parametrize("link", ["outgoing", "backlink", "unresolved"])
def test_any_link_in_or_out_makes_a_note_no_orphan(tmp_path: Path, link: str) -> None:
    """Contract: "no links in or out" is literally true of every named orphan:
    an outgoing link (resolved or not) or a backlink disqualifies a note.
    """
    builder = VaultBuilder(tmp_path)
    bodies = {
        "outgoing": f"{_words(1600)} [[Bed]]",
        "backlink": _words(1600),
        "unresolved": f"{_words(1600)} [[Nowhere]]",
    }
    builder.note("Tome", bodies[link])
    if link == "backlink":
        builder.note("Pointer", "See [[Tome]] [[Bed]].")
    builder.note("Seedbank", "compost mulch seedling trowel")
    _garden(builder)

    suggestions = orphan_connector.suggest(builder.build())

    assert [s.notes[0] for s in suggestions] == ["Seedbank"]


def test_rotates_among_recent_orphans(tmp_path: Path) -> None:
    """Contract: across sessions each of the recent orphans gets named.

    Regression (from the Tracery geist): $vault.orphans(1) named the single
    most recently modified orphan in every session.
    """
    builder = VaultBuilder(tmp_path)
    orphans = [f"Orphan{i}" for i in range(4)]
    for i, title in enumerate(orphans):
        builder.note(title, f"stray{i} thought{i}", modified=datetime(2024, 1, 1 + i))
    _garden(builder)

    named = {
        s.notes[0] for seed in range(20) for s in orphan_connector.suggest(builder.build(seed=seed))
    }

    assert named == set(orphans)


def test_only_the_ten_most_recent_orphans_are_sampled(tmp_path: Path) -> None:
    """Contract: the recent-orphan suggestion draws from the 10 most
    recently modified orphans (the Tracery geist's $vault.orphans(10))."""
    builder = VaultBuilder(tmp_path)
    start = datetime(2024, 1, 1)
    titles = [f"Orphan{i:02d}" for i in range(12)]
    for i, title in enumerate(titles):
        builder.note(title, f"stray{i} thought{i}", modified=start + timedelta(days=i))
    _garden(builder)

    named = {
        s.notes[0] for seed in range(40) for s in orphan_connector.suggest(builder.build(seed=seed))
    }

    assert named == set(titles[2:])


def test_no_orphans_no_suggestions(tmp_path: Path) -> None:
    """Contract: with every note linked, the geist says nothing."""
    builder = VaultBuilder(tmp_path)
    _garden(builder)

    assert orphan_connector.suggest(builder.build()) == []


def test_journal_notes_are_never_named_and_their_mentions_do_not_link(tmp_path: Path) -> None:
    """Contract: geist journal notes are never orphans or neighbours, and a
    note the journal mentions is still an orphan.

    Regression guard: session journals wikilink the notes they suggest;
    counted as backlinks, they would hide every orphan the engine ever named.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Seedbank", "compost mulch seedling trowel")
    builder.journal("Session Log", "compost mulch seedling trowel [[Seedbank]]")
    _garden(builder)

    suggestions = orphan_connector.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, must_not_reference=["Session Log"])
    assert [s.notes for s in suggestions] == [["Seedbank", "Bed", "Shed"]]


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Tome", _words(1600))
    for i in range(4):
        builder.note(f"Orphan{i}", f"stray{i} thought{i}")
    _garden(builder)

    first = [s.text for s in orphan_connector.suggest(builder.build())]
    second = [s.text for s in orphan_connector.suggest(builder.build())]

    assert first
    assert first == second
