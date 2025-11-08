"""Creation Burst geist - surfaces days when multiple notes were created.

Identifies "burst days" when you created 5+ notes and asks what was special
about those moments of creative productivity.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> List[Suggestion]:
    """Find days when 5+ notes were created and ask what was special.

    Detects "burst days" of high creative activity by grouping notes by
    creation date and identifying days with 5+ notes created. Randomly
    samples one such day and generates a provocation about what conditions
    led to that productivity.

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
               GROUP_CONCAT(title, '|') as note_titles
        FROM notes
        WHERE NOT path LIKE 'geist journal/%'
        GROUP BY DATE(created)
        HAVING note_count >= 5
        ORDER BY note_count DESC
        """
    )

    burst_days = cursor.fetchall()

    if not burst_days:
        return []

    # Randomly select one burst day (deterministic via vault's RNG)
    day_date, count, titles_str = vault.sample(burst_days, k=1)[0]

    # Parse note titles
    note_titles = titles_str.split("|") if titles_str else []

    # Limit to showing first 8 titles to avoid overwhelming output
    display_titles = note_titles[:8]
    more_count = len(note_titles) - len(display_titles)

    # Build note list for suggestion text
    title_list = ", ".join([f"[[{title}]]" for title in display_titles])
    if more_count > 0:
        title_list += f", and {more_count} more"

    # Generate provocation based on patterns
    if count >= 10:
        # Exceptional burst
        text = (
            f"On {day_date}, you created {count} notes in a single day—an exceptional burst. "
            f"What conditions created that flow state? {title_list}"
        )
    elif count >= 7:
        # High burst
        text = (
            f"On {day_date}, you created {count} notes: {title_list}. "
            f"What was special about that day?"
        )
    else:
        # Standard burst (5-6 notes)
        text = (
            f"On {day_date}, you created {count} notes in one day: {title_list}. "
            f"What sparked that productivity?"
        )

    return [
        Suggestion(
            text=text,
            notes=note_titles,  # All notes, not just displayed ones
            geist_id="creation_burst",
        )
    ]
