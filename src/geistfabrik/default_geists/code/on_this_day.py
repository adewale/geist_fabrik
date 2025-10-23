"""On This Day geist - surfaces notes from same calendar date in previous years.

This geist identifies notes created on the same calendar date (month and day)
in previous years, creating connections across time and highlighting personal
history. It's a universal temporal pattern that works globally without
hemisphere-specific seasonal assumptions.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> List[Suggestion]:
    """Surface notes from same calendar date in previous years.

    This geist finds notes created on the same month and day as today,
    but in different years, allowing reflection on personal history
    and how thinking has evolved over time.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        List of suggestions highlighting notes from the same date in past years
    """
    today = datetime.now()
    same_date_notes = []

    for note in vault.notes():
        created = note.created
        # Same month and day, different year, and in the past
        if (
            created.month == today.month
            and created.day == today.day
            and created.year < today.year
        ):
            years_ago = today.year - created.year
            same_date_notes.append((note, years_ago))

    # Sort by years ago (most recent first)
    same_date_notes.sort(key=lambda x: x[1])

    suggestions = []
    for note, years_ago in same_date_notes[:3]:  # Limit to 3 most recent
        if years_ago == 1:
            time_phrase = "One year ago today"
        else:
            time_phrase = f"{years_ago} years ago today"

        text = f"{time_phrase}, you wrote [[{note.title}]]. What's changed since then?"
        suggestions.append(
            Suggestion(text=text, notes=[note.title], geist_id="on_this_day")
        )

    # Sample up to 2 suggestions
    return vault.sample(suggestions, min(2, len(suggestions)))
