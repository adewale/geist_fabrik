"""Task archaeology geist - finds old incomplete tasks.

Discovers forgotten or abandoned tasks in notes and suggests revisiting them.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with old incomplete tasks.

    Returns:
        List of suggestions for old tasks
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    for note in notes:
        metadata = vault.metadata(note)

        has_tasks = metadata.get("has_tasks", False)
        task_count = metadata.get("task_count", 0)
        completed_count = metadata.get("completed_task_count", 0)
        days_since_modified = metadata.get("days_since_modified", 0)

        # Look for notes with uncompleted tasks that are old
        if has_tasks and task_count > completed_count and days_since_modified > 30:
            incomplete = task_count - completed_count

            text = (
                f"What if you revisited the tasks in [[{note.obsidian_link}]]? "
                f"It has {incomplete} incomplete task{'s' if incomplete > 1 else ''} "
                f"and hasn't been touched in {days_since_modified} days. "
                f"Are they still relevant?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link],
                    geist_id="task_archaeology",
                )
            )

    return vault.sample(suggestions, k=3)
