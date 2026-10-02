"""Task archaeology geist - finds old incomplete tasks.

Discovers forgotten or abandoned tasks in notes and suggests revisiting them.

A note qualifies when it has at least one open "- [ ]" task and has not been
modified for more than MIN_DAYS_STALE days. When two or more notes qualify,
two of them are paired in one "revive them, or archive them?" suggestion;
the rest of the output names single notes, with no note named twice.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext

MIN_DAYS_STALE = 30
CAP = 3
PAIR = 2


def _tasks(count: int) -> str:
    return f"{count} incomplete task{'s' if count != 1 else ''}"


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with old incomplete tasks.

    Returns:
        Up to CAP suggestions: a pair of stale task notes (when two or more
        qualify) followed by single notes
    """
    from geistfabrik import Suggestion

    stale: list[tuple[Note, int, int]] = []  # (note, incomplete, days since modified)
    for note in vault.notes():
        metadata = vault.metadata(note)

        has_tasks = metadata.get("has_tasks", False)
        task_count = metadata.get("task_count", 0)
        completed_count = metadata.get("completed_task_count", 0)
        days_since_modified = metadata.get("days_since_modified", 0)

        # Look for notes with uncompleted tasks that are old
        if has_tasks and task_count > completed_count and days_since_modified > MIN_DAYS_STALE:
            stale.append((note, task_count - completed_count, days_since_modified))

    picked = vault.sample(stale, CAP + 1)
    suggestions = []

    if len(picked) >= PAIR:
        pair, picked = picked[:PAIR], picked[PAIR:]
        lines = "\n".join(
            f"- [[{note.link_text}]] ({_tasks(incomplete)}, untouched for {days} days)"
            for note, incomplete, days in pair
        )
        suggestions.append(
            Suggestion(
                text=(
                    "These notes have incomplete tasks but haven't been updated "
                    f"recently:\n{lines}\n\nTime to revive them, or archive them?"
                ),
                notes=[note.link_text for note, _, _ in pair],
                geist_id="task_archaeology",
            )
        )

    for note, incomplete, days in picked[: CAP - len(suggestions)]:
        suggestions.append(
            Suggestion(
                text=(
                    f"What if you revisited the tasks in [[{note.link_text}]]? "
                    f"It has {_tasks(incomplete)} "
                    f"and hasn't been touched in {days} days. "
                    f"Are they still relevant?"
                ),
                notes=[note.link_text],
                geist_id="task_archaeology",
            )
        )

    return suggestions
