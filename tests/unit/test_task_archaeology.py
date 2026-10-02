"""Unit tests for task_archaeology geist.

Trigger arithmetic (see the geist source; metadata "now" is the session
date):
- a note qualifies when it has at least one open "- [ ]" task and
  days_since_modified > 30;
- with two or more qualifying notes, two of them are paired in one
  "revive them, or archive them?" suggestion (merged in from
  metadata_driven_discovery); the rest are named singly, no note twice;
- output is capped at 3 suggestions (4 notes: a pair and two singles).
"""

from datetime import timedelta
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import task_archaeology
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

GEIST = "task_archaeology"
CAP = 3
TASKS = "- [ ] prune roses\n- [ ] order seeds\n- [x] rake leaves"


def _note(builder: VaultBuilder, title: str, body: str, *, age_days: int) -> None:
    stamp = SESSION_DATE - timedelta(days=age_days)
    builder.note(title, body, created=stamp, modified=stamp)


def test_stale_open_tasks_are_surfaced(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    _note(builder, "Garden Plan", TASKS, age_days=45)
    _note(builder, "Fresh Plan", TASKS, age_days=3)
    _note(builder, "Old Prose", "No tasks here at all.", age_days=400)

    suggestions = task_archaeology.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST)
    assert [s.notes for s in suggestions] == [["Garden Plan"]]
    assert "2 incomplete tasks and hasn't been touched in 45 days" in suggestions[0].text


@pytest.mark.parametrize(("age_days", "fires"), [(30, False), (31, True)])
def test_staleness_boundary(tmp_path: Path, age_days: int, fires: bool) -> None:
    builder = VaultBuilder(tmp_path)
    _note(builder, "Garden Plan", TASKS, age_days=age_days)

    suggestions = task_archaeology.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Garden Plan"]] if fires else [])


def test_fully_completed_task_list_is_left_alone(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    _note(builder, "Done Plan", TASKS.replace("[ ]", "[x]"), age_days=200)

    assert task_archaeology.suggest(builder.build()) == []


def test_output_is_capped_when_more_notes_qualify(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    planted = [f"Plan {i}" for i in range(6)]
    for title in planted:
        _note(builder, title, TASKS, age_days=90)

    suggestions = task_archaeology.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert [len(s.notes) for s in suggestions] == [2, 1, 1]
    referenced = [ref for s in suggestions for ref in s.notes]
    assert len(set(referenced)) == 4
    assert set(referenced) <= set(planted)


def test_geist_journal_notes_are_never_surfaced(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    _note(builder, "Garden Plan", TASKS, age_days=90)
    stamp = SESSION_DATE - timedelta(days=90)
    for i in range(4):
        builder.journal(f"Session Log {i}", TASKS, created=stamp, modified=stamp)

    suggestions = task_archaeology.suggest(builder.build())

    assert_valid_suggestions(
        suggestions, GEIST, must_reference=["Garden Plan"], must_not_reference=["Session Log"]
    )


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        _note(builder, f"Plan {i}", TASKS, age_days=90)

    first = [s.text for s in task_archaeology.suggest(builder.build())]
    second = [s.text for s in task_archaeology.suggest(builder.build())]

    assert first
    assert first == second


@pytest.mark.parametrize(("stale", "expected_shape"), [(1, [1]), (2, [2]), (3, [2, 1])])
def test_two_stale_task_notes_are_paired_with_revive_or_archive(
    tmp_path: Path, stale: int, expected_shape: list[int]
) -> None:
    """Contract: two or more stale task notes yield one paired suggestion
    listing each note's open-task count and staleness, asking "revive them,
    or archive them?"; any others are named singly, and no note twice.

    Regression: the pairing was metadata_driven_discovery's pattern 3, which
    named the same stale task notes as this geist in the same session.
    """
    builder = VaultBuilder(tmp_path)
    ages = {"Garden Plan": 45, "Shed Plan": 75, "Pond Plan": 120}
    titles = list(ages)[:stale]
    for title in titles:
        _note(builder, title, TASKS, age_days=ages[title])

    suggestions = task_archaeology.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST)
    assert [len(s.notes) for s in suggestions] == expected_shape
    assert sorted(ref for s in suggestions for ref in s.notes) == sorted(titles)
    pairs = [s for s in suggestions if len(s.notes) == 2]
    assert [p.text for p in pairs] == [
        "These notes have incomplete tasks but haven't been updated recently:\n"
        + "\n".join(
            f"- [[{t}]] (2 incomplete tasks, untouched for {ages[t]} days)" for t in p.notes
        )
        + "\n\nTime to revive them, or archive them?"
        for p in pairs
    ]
