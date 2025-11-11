"""Creation Burst geist - surfaces days when multiple notes were created.

Identifies "burst days" when you created 3+ notes and asks what was special
about those moments of creative activity.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> List[Suggestion]:
    """Find days when 3+ notes were created and ask what was special.

    Detects "burst days" of creative activity by grouping notes by
    creation date and identifying days with 3+ notes created. Randomly
    samples one such day and generates a provocation based on the count.

    Args:
        vault: The vault context with database access and utilities

    Returns:
        Single suggestion about a burst day (or empty list if no bursts found)
    """
    # Query: Group notes by creation date, count per day
    # Exclude geist journal to avoid noise from session output
    cursor = vault.db.execute(
        """
        SELECT DATE(created) as creation_date,
               COUNT(*) as note_count,
               GROUP_CONCAT(path, '|') as note_paths
        FROM notes
        WHERE NOT path LIKE 'geist journal/%'
        GROUP BY DATE(created)
        HAVING note_count >= 3
        ORDER BY note_count DESC
        """
    )

    burst_days = cursor.fetchall()

    if not burst_days:
        return []

    # Randomly select one burst day (deterministic via vault's RNG)
    day_date, count, paths_str = vault.sample(burst_days, k=1)[0]

    # Parse note paths and get Note objects to access obsidian_link
    note_paths = paths_str.split("|") if paths_str else []
    notes = [vault.get_note(path) for path in note_paths]
    notes = [note for note in notes if note is not None]  # Filter out any None results

    if not notes:
        return []

    # Get obsidian link text for each note (handles both regular and virtual notes)
    note_links = [note.obsidian_link for note in notes]

    # Limit to showing first 8 notes to avoid overwhelming output
    display_links = note_links[:8]
    more_count = len(note_links) - len(display_links)

    # Build note list for suggestion text
    title_list = ", ".join([f"[[{link}]]" for link in display_links])
    if more_count > 0:
        title_list += f", and {more_count} more"

    # Generate question based on count
    if count >= 6:
        question = "What was special about that day?"
    else:  # 3-5 notes
        question = "Does today feel generative?"

    text = f"On {day_date}, you created {count} notes in one day: {title_list}. {question}"

    return [
        Suggestion(
            text=text,
            notes=note_links,  # All notes (obsidian links), not just displayed ones
            geist_id="creation_burst",
        )
    ]
