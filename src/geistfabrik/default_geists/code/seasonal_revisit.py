"""Seasonal Revisit - Surface notes from the same season.

This geist finds notes created in the same season (Spring/Summer/Fall/Winter)
as the current date, revealing seasonal patterns in your thinking and
encouraging reflection on yearly rhythms.
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import VaultContext

from geistfabrik import Suggestion


def suggest(vault: "VaultContext") -> list[Suggestion]:
    """Find notes from the same season for seasonal reflection.

    Args:
        vault: VaultContext with access to vault data

    Returns:
        List of suggestions about seasonal patterns
    """
    suggestions = []

    # Determine current season
    today = datetime.now()
    current_season = _get_season(today)
    current_year = today.year

    # Find notes from same season in previous years
    seasonal_notes = []
    all_notes = vault.notes()
    for note in all_notes:
        note_season = _get_season(note.created)
        note_year = note.created.year

        # Same season, but not current year (looking back)
        if note_season == current_season and note_year < current_year:
            years_ago = current_year - note_year
            seasonal_notes.append((note, years_ago))

    if not seasonal_notes:
        return []

    # Sort by years ago (most recent first)
    seasonal_notes.sort(key=lambda x: x[1])

    # Create suggestions for recent seasonal matches
    for note, years_ago in seasonal_notes[:3]:
        if years_ago == 1:
            time_phrase = "last year"
        else:
            time_phrase = f"{years_ago} years ago"

        text = (
            f"**{current_season} again**. {time_phrase.capitalize()} in {current_season.lower()}, "
            f"you wrote [[{note.obsidian_link}]]. What patterns repeat with the seasons?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.obsidian_link],
                geist_id="seasonal_revisit",
            )
        )

    # Sample to avoid too many suggestions
    return vault.sample(suggestions, min(2, len(suggestions)))


def _get_season(date: datetime) -> str:
    """Determine the season for a given date (Northern Hemisphere).

    Args:
        date: Date to check

    Returns:
        Season name: "Spring", "Summer", "Fall", or "Winter"
    """
    month = date.month

    if month in (3, 4, 5):
        return "Spring"
    elif month in (6, 7, 8):
        return "Summer"
    elif month in (9, 10, 11):
        return "Fall"
    else:  # 12, 1, 2
        return "Winter"
