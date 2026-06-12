"""This time last year geist - resurfaces notes from temporal anniversaries.

A reflective lens over the calendar: notes written around this date in
previous years carry the texture of where your thinking was then. This
geist samples one such note and asks what's different now — and what's
the same.
"""

from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Surface a note from around this date in previous years.

    Looks back 1-3 years from the session date with a +/- 7 day window
    around each anniversary. Uses the session date (not wall-clock time)
    so replayed sessions are reproducible.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion resurfacing an anniversary note
    """
    today = vault.session.date
    notes = vault.notes_excluding_journal()
    candidates = []

    for years_ago in (1, 2, 3):
        try:
            target_date = today.replace(year=today.year - years_ago)
        except ValueError:
            # Feb 29 in a non-leap target year — use Feb 28 instead
            target_date = today.replace(year=today.year - years_ago, day=28)

        window_start = (target_date - timedelta(days=7)).date()
        window_end = (target_date + timedelta(days=7)).date()

        for note in notes:
            if window_start <= note.created.date() <= window_end:
                candidates.append((note, years_ago))

    if not candidates:
        return []

    note, years = vault.sample(candidates, 1)[0]
    period = "a year" if years == 1 else f"{years} years"

    return [
        Suggestion(
            text=(
                f"Around this time {period} ago, you wrote [[{note.link_text}]]. "
                f"What's different now? What's the same?"
            ),
            notes=[note.link_text],
            geist_id="this_time_last_year",
        )
    ]
