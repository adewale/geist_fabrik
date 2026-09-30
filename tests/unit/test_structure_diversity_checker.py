"""Unit tests for structure_diversity_checker geist.

Trigger arithmetic (see the geist source):
- it looks at the 8 most recently modified non-journal notes and needs >= 5;
- each note is classified from its own markdown (tasks, list items, code
  fences, headings), densities per 100 words: task-oriented (> 2 tasks),
  list-heavy (> 5 list items), code-heavy, prose-heavy (< 2 headings and
  < 3 list items) or mixed;
- it fires when the recent notes span <= 2 types and the dominant type
  covers >= 70% of them (6 of 8, or 4 of 5), naming one older note of a
  different type as the example;
- it returns at most one suggestion.

Every fixture pins modification times relative to the session date, so
"recent" is deterministic.
"""

from datetime import timedelta
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import structure_diversity_checker
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

GEIST = "structure_diversity_checker"
LIST_BODY = "\n".join(f"- item {i}" for i in range(10))
PROSE_BODY = "Flowing narrative about soil and seasons, written as plain sentences."
TASK_BODY = "- [ ] prune roses\n- [ ] order seeds\n- [ ] rake leaves"


def _note(builder: VaultBuilder, title: str, body: str, *, age_days: int) -> None:
    stamp = SESSION_DATE - timedelta(days=age_days)
    builder.note(title, body, created=stamp, modified=stamp)


def _recent(builder: VaultBuilder, bodies: list[str]) -> None:
    for i, body in enumerate(bodies):
        _note(builder, f"Recent {i}", body, age_days=i + 1)


def test_uniform_list_writing_points_to_an_older_prose_note(tmp_path: Path) -> None:
    # Regression: list/code/heading counts came only from an optional example
    # metadata module, so without it every list note was "prose-heavy" and
    # this vault had no differing note to suggest.
    builder = VaultBuilder(tmp_path)
    _recent(builder, [LIST_BODY] * 8)
    _note(builder, "Old Prose", PROSE_BODY, age_days=100)

    suggestions = structure_diversity_checker.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST)
    assert [s.notes for s in suggestions] == [["Old Prose"]]
    assert "Your last 8 notes are structurally similar (8 are list-heavy)" in suggestions[0].text
    assert "[[Old Prose]] has a different structure (prose-heavy)" in suggestions[0].text


@pytest.mark.parametrize(("dominant", "fires"), [(5, False), (6, True)])
def test_dominance_threshold(tmp_path: Path, dominant: int, fires: bool) -> None:
    # 70% of 8 recent notes is 5.6: six list notes are enough, five are not.
    builder = VaultBuilder(tmp_path)
    _recent(builder, [LIST_BODY] * dominant + [PROSE_BODY] * (8 - dominant))
    _note(builder, "Old Prose", PROSE_BODY, age_days=100)

    suggestions = structure_diversity_checker.suggest(builder.build())

    assert (suggestions != []) is fires


def test_three_recent_structure_types_count_as_diverse(tmp_path: Path) -> None:
    # Six list notes dominate, but a third type among the recent notes means
    # the writing is not in a rut.
    builder = VaultBuilder(tmp_path)
    _recent(builder, [LIST_BODY] * 6 + [PROSE_BODY, TASK_BODY])
    _note(builder, "Old Prose", PROSE_BODY, age_days=100)

    assert structure_diversity_checker.suggest(builder.build()) == []


@pytest.mark.parametrize(("vault_size", "fires"), [(4, False), (5, True)])
def test_needs_five_recent_notes(tmp_path: Path, vault_size: int, fires: bool) -> None:
    builder = VaultBuilder(tmp_path)
    _recent(builder, [LIST_BODY] * (vault_size - 1))
    _note(builder, "Old Prose", PROSE_BODY, age_days=100)

    suggestions = structure_diversity_checker.suggest(builder.build())

    assert (suggestions != []) is fires


def test_journal_sessions_are_not_the_users_recent_writing(tmp_path: Path) -> None:
    # The engine writes a journal note every session, so journal notes are
    # always the most recently modified. The user's own recent notes are
    # prose; the eight newer list-shaped journal notes must not stand in for
    # them.
    builder = VaultBuilder(tmp_path)
    for i in range(8):
        _note(builder, f"Prose {i}", PROSE_BODY, age_days=10 + i)
    _note(builder, "Old List", LIST_BODY, age_days=100)
    stamp = SESSION_DATE - timedelta(days=1)
    for i in range(8):
        builder.journal(f"Session Log {i}", LIST_BODY, created=stamp, modified=stamp)

    suggestions = structure_diversity_checker.suggest(builder.build())

    assert_valid_suggestions(
        suggestions, GEIST, must_reference=["Old List"], must_not_reference=["Session Log"]
    )
    assert "(8 are prose-heavy)" in suggestions[0].text


def test_journal_notes_are_never_the_example(tmp_path: Path) -> None:
    # Prose-shaped journal notes outnumber the one regular prose note that
    # can legitimately be offered as the differing example.
    builder = VaultBuilder(tmp_path)
    _recent(builder, [LIST_BODY] * 8)
    _note(builder, "Old Prose", PROSE_BODY, age_days=100)
    stamp = SESSION_DATE - timedelta(days=200)
    for i in range(6):
        builder.journal(f"Session Log {i}", PROSE_BODY, created=stamp, modified=stamp)

    suggestions = structure_diversity_checker.suggest(builder.build())

    assert_valid_suggestions(
        suggestions, GEIST, must_reference=["Old Prose"], must_not_reference=["Session Log"]
    )


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    # Several differing notes, so the example is a seeded sample.
    builder = VaultBuilder(tmp_path)
    _recent(builder, [LIST_BODY] * 8)
    for i in range(5):
        _note(builder, f"Old Prose {i}", PROSE_BODY, age_days=100 + i)

    first = [s.text for s in structure_diversity_checker.suggest(builder.build())]
    second = [s.text for s in structure_diversity_checker.suggest(builder.build())]

    assert first
    assert first == second
