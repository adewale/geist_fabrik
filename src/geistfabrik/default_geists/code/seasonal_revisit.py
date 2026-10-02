"""Seasonal Revisit - Surface notes from the same season.

This geist finds notes created in the same season (Spring/Summer/Autumn/Winter)
as the current date, revealing seasonal patterns in your thinking and
encouraging reflection on yearly rhythms.
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import VaultContext

from geistfabrik import Suggestion
from geistfabrik.temporal_analysis import get_season


def _season_year(date: datetime) -> int:
    """Year a date's season belongs to: December starts the next year's winter."""
    return date.year + 1 if date.month == 12 else date.year


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes from the same season for seasonal reflection.

    Args:
        vault: VaultContext with access to vault data

    Returns:
        List of suggestions about seasonal patterns
    """
    suggestions = []

    # Determine current season
    # Session date, not wall-clock: keeps --date replays deterministic
    today = vault.session.date
    current_season = get_season(today)
    current_year = _season_year(today)

    # Find notes from same season in previous years
    seasonal_notes = []
    # Session output is not part of the vault's history.
    all_notes = vault.notes()
    for note in all_notes:
        note_season = get_season(note.created)
        note_year = _season_year(note.created)

        # Same season of an earlier season-year (looking back); December and
        # the following January/February are the same winter.
        if note_season == current_season and note_year < current_year:
            years_ago = current_year - note_year
            seasonal_notes.append((note, years_ago))

    if not seasonal_notes:
        return []

    # Sample from every eligible note: truncating to the first few (in vault
    # order) named the same notes for a whole season of sessions.
    for note, years_ago in vault.sample(seasonal_notes, 2):
        if years_ago == 1:
            time_phrase = "last year"
        else:
            time_phrase = f"{years_ago} years ago"

        text = (
            f"**{current_season} again**. {time_phrase.capitalize()} in {current_season.lower()}, "
            f"you wrote [[{note.link_text}]]. What patterns repeat with the seasons?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.link_text],
                geist_id="seasonal_revisit",
            )
        )

    return suggestions
