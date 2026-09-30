"""Unit tests for question_generator geist.

Trigger arithmetic (see the geist source):
- a note qualifies when its title does not end with "?" and its word_count
  (whitespace tokens of the whole note, including the 2-token "# Title"
  heading VaultBuilder writes for a one-word title) is > 50;
- each qualifying note yields one suggestion whose ``title`` is a question
  built from the note title;
- output is capped at 3 suggestions.
"""

from pathlib import Path

import pytest

from geistfabrik.default_geists.code import question_generator
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEIST = "question_generator"
CAP = 3
HEADING_TOKENS = 2


def _words(total_words: int) -> str:
    return " ".join(f"term{i}" for i in range(total_words - HEADING_TOKENS))


def test_developed_note_is_reframed_as_a_question(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Compost", _words(80))
    builder.note("Seedling", "Too short to question.")

    suggestions = question_generator.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST)
    assert [s.notes for s in suggestions] == [["Compost"]]
    question = suggestions[0].title
    assert question is not None and question.endswith("?") and "Compost" in question
    assert f'reframed [[Compost]] as a question: "{question}"' in suggestions[0].text


@pytest.mark.parametrize(("total_words", "fires"), [(50, False), (51, True)])
def test_word_count_boundary(tmp_path: Path, total_words: int, fires: bool) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Compost", _words(total_words))

    suggestions = question_generator.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Compost"]] if fires else [])


@pytest.mark.parametrize(("title", "fires"), [("Why compost", True), ("Why compost?", False)])
def test_titles_already_questions_are_skipped(tmp_path: Path, title: str, fires: bool) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note(title, _words(80))

    suggestions = question_generator.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([[title]] if fires else [])


def test_output_is_capped_when_more_notes_qualify(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    planted = [f"Topic {i}" for i in range(6)]
    for title in planted:
        builder.note(title, _words(80))

    suggestions = question_generator.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert len(suggestions) == CAP
    referenced = [ref for s in suggestions for ref in s.notes]
    assert len(set(referenced)) == CAP
    assert set(referenced) <= set(planted)


def test_geist_journal_notes_are_never_reframed(tmp_path: Path) -> None:
    # Journal session notes are long statements too; only "Compost" may appear.
    builder = VaultBuilder(tmp_path)
    builder.note("Compost", _words(80))
    for i in range(4):
        builder.journal(f"Session Log {i}", _words(80))

    suggestions = question_generator.suggest(builder.build())

    assert_valid_suggestions(
        suggestions, GEIST, must_reference=["Compost"], must_not_reference=["Session Log"]
    )


def test_date_collection_entry_is_linked_by_its_deeplink(tmp_path: Path) -> None:
    # A note with two date headings is split into virtual entries whose link
    # text is "<file>#<heading>". Linking the bare heading ("[[2024-01-10]]")
    # points at a note that does not exist.
    (tmp_path / "Diary.md").write_text(
        f"## 2024-01-10\n\n{_words(80)}\n\n## 2024-01-11\n\nShort entry.\n"
    )
    ctx = VaultBuilder(tmp_path).build()
    entry = next(n for n in ctx.notes() if n.is_virtual and "2024-01-10" in n.title)

    suggestions = question_generator.suggest(ctx)

    assert_valid_suggestions(suggestions, GEIST)
    assert [s.notes for s in suggestions] == [[entry.link_text]]
    assert f"[[{entry.link_text}]]" in suggestions[0].text


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        builder.note(f"Topic {i}", _words(80))

    first = [(s.text, s.title) for s in question_generator.suggest(builder.build())]
    second = [(s.text, s.title) for s in question_generator.suggest(builder.build())]

    assert first
    assert first == second
