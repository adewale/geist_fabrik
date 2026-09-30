"""Unit tests for task_archaeology geist.

Trigger arithmetic (see the geist source; metadata "now" is the session
date):
- a note qualifies when it has at least one open "- [ ]" task and
  days_since_modified > 30;
- output is capped at 3 suggestions.
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
    assert len(suggestions) == CAP
    referenced = [ref for s in suggestions for ref in s.notes]
    assert len(set(referenced)) == CAP
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
