"""This time last year geist - resurfaces notes from temporal anniversaries.

A reflective lens over the calendar: notes written around this date in
previous years carry the texture of where your thinking was then. This
geist samples one such note and asks what's different now, and what's
the same.

It looks back over every earlier year, in three tiers, and says exactly
which tier it found:

1. A note written on this very day (month and day) of an earlier year:
   "One year ago today, ..." / "3 years ago today, ...".
2. Otherwise, a note written within 7 days of this date in an earlier year:
   "Around this time a year ago, ...".
3. Otherwise, a note written in this same season of an earlier season-year
   (December belongs to the following year's winter): "Last spring, ..." /
   "3 springs ago, ...".

Dates come from Note.created (the declared date where the note has one).
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.models import Note
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion
from geistfabrik.temporal_analysis import get_season

WINDOW_DAYS = 7
QUESTION = "What's different now? What's the same?"


def _anniversary(today: datetime, years_ago: int) -> datetime:
    """``today`` moved back ``years_ago`` years (Feb 29 becomes Feb 28)."""
    try:
        return today.replace(year=today.year - years_ago)
    except ValueError:
        return today.replace(year=today.year - years_ago, day=28)


def _season_year(date: datetime) -> int:
    """Year a date's season belongs to: December starts the next year's winter."""
    return date.year + 1 if date.month == 12 else date.year


def _years(years_ago: int) -> str:
    return "a year" if years_ago == 1 else f"{years_ago} years"


def _same_day(today: datetime, notes: list["Note"]) -> list[tuple["Note", int]]:
    """Notes written on today's month and day in an earlier year."""
    return [
        (note, today.year - note.created.year)
        for note in notes
        if note.created.month == today.month
        and note.created.day == today.day
        and note.created.year < today.year
    ]


def _around(today: datetime, notes: list["Note"]) -> list[tuple["Note", int]]:
    """Notes within WINDOW_DAYS of an anniversary of today, in any earlier year."""
    if not notes:
        return []
    earliest_year = min(note.created.year for note in notes)
    found: list[tuple[Note, int]] = []
    # One extra year: a window around early January reaches into December
    # of the year before.
    for years_ago in range(1, today.year - earliest_year + 2):
        target = _anniversary(today, years_ago)
        start = (target - timedelta(days=WINDOW_DAYS)).date()
        end = (target + timedelta(days=WINDOW_DAYS)).date()
        found.extend((note, years_ago) for note in notes if start <= note.created.date() <= end)
    return found


def _same_season(today: datetime, notes: list["Note"]) -> list[tuple["Note", int]]:
    """Notes from today's season in an earlier season-year."""
    season, year = get_season(today), _season_year(today)
    return [
        (note, year - _season_year(note.created))
        for note in notes
        if get_season(note.created) == season and _season_year(note.created) < year
    ]


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Surface a note from this date, this week or this season in earlier years.

    Uses the session date (not wall-clock time) so replayed sessions are
    reproducible.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion resurfacing an anniversary note
    """
    today = vault.session.date
    notes = vault.notes()

    same_day = _same_day(today, notes)
    if same_day:
        note, years_ago = vault.sample(same_day, 1)[0]
        opening = f"{'One year' if years_ago == 1 else f'{years_ago} years'} ago today"
    else:
        around = _around(today, notes)
        if around:
            note, years_ago = vault.sample(around, 1)[0]
            opening = f"Around this time {_years(years_ago)} ago"
        else:
            seasonal = _same_season(today, notes)
            if not seasonal:
                return []
            note, years_ago = vault.sample(seasonal, 1)[0]
            season = get_season(today).lower()
            opening = f"Last {season}" if years_ago == 1 else f"{years_ago} {season}s ago"

    return [
        Suggestion(
            text=f"{opening}, you wrote [[{note.link_text}]]. {QUESTION}",
            notes=[note.link_text],
            geist_id="this_time_last_year",
        )
    ]
