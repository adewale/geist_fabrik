"""Unit tests for question_generator geist.

Trigger arithmetic (see the geist source):
- a note qualifies when its title does not end with "?", is not date-titled
  (starts with YYYY-MM-DD, has no letters, or is a date-collection entry),
  and its word_count
  (whitespace tokens of the whole note, including the 2-token "# Title"
  heading VaultBuilder writes for a one-word title) is > 50;
- each qualifying note yields one suggestion whose ``title`` is a question
  built from the note title, quoted in curly quotes;
- output is capped at 3 suggestions.
"""

from pathlib import Path

import pytest

from geistfabrik.default_geists.code import question_generator
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.vault_context import VaultContext
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
    assert suggestions[0].text == (
        f'What if you reframed [[Compost]] as a question: "{question}"'
    )
    # Regression: the template closed the quoted question with a second
    # "?", printing '..."How does “Compost” work?"? Questions...'.
    assert '?"?' not in suggestions[0].text


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


def test_date_titled_notes_are_not_reframed(tmp_path: Path) -> None:
    """Contract: daily notes and date-collection entries are not reframed;
    a date is not a statement to question.

    Regression: "Who benefits from 2023-09-12?" was proposed for daily notes.
    (This replaces a test that a date-collection entry was linked by its
    deeplink: entries are titled by their date heading, so they are now
    skipped altogether.)
    """
    builder = VaultBuilder(tmp_path)
    builder.note("2023-09-12", _words(80))
    builder.note("2023-09-12 Meeting with Steph", _words(80))
    builder.note("Compost", _words(80))
    (tmp_path / "Diary.md").write_text(
        f"## 2024-01-10\n\n{_words(80)}\n\n## January 11, 2024\n\n{_words(80)}\n"
    )
    ctx = builder.build()
    assert sum(n.is_virtual for n in ctx.notes()) == 2

    suggestions = question_generator.suggest(ctx)

    assert [s.notes for s in suggestions] == [["Compost"]]


def test_question_frames_quote_the_title_and_stay_grammatical(tmp_path: Path) -> None:
    """Contract: every frame quotes the title, and none is "Why is <title>?",
    which is ungrammatical for a noun-phrase title.

    Regression: output included "Why is Emotion Regulation, Creativity, and
    Cultural Research?" and the unquoted "When does Temporal Embeddings
    Research and New Geist Proposals apply?", also used as suggested titles.
    """
    title = "Emotion Regulation, Creativity, and Cultural Research"
    builder = VaultBuilder(tmp_path)
    builder.note(title, _words(80))
    base = builder.build()
    quoted = f"\u201c{title}\u201d"
    allowed = {
        f"How does {quoted} work?",
        f"What if {quoted} is wrong?",
        f"When does {quoted} not apply?",
        f"Who benefits from {quoted}?",
        f"What question is {quoted} an answer to?",
    }

    questions = {
        s.title
        for seed in range(30)
        for s in question_generator.suggest(
            VaultContext(base.vault, base.session, seed=seed, function_registry=FunctionRegistry())
        )
    }

    assert questions == allowed


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        builder.note(f"Topic {i}", _words(80))

    first = [(s.text, s.title) for s in question_generator.suggest(builder.build())]
    second = [(s.text, s.title) for s in question_generator.suggest(builder.build())]

    assert first
    assert first == second
