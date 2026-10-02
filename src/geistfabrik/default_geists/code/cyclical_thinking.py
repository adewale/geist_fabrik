"""Cyclical Thinking geist - notes edited away from a version and back.

Uses TemporalPatternFinder to find notes whose stored vector moved away from
its first recorded state and returned to it at least twice. Vectors are
cached by content, so each move is an edit: the suggestion says so rather
than claiming a shift in how the note is read.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Detect notes that cycle through semantic states over sessions.

    Returns:
        List of 1-2 suggestions showing cyclical thinking patterns
    """
    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import TemporalPatternFinder

    # Two cycles need 5 snapshots: the first state, then low, high, low, high
    # (TemporalPatternFinder requires 2 * min_cycles + 1).
    if vault.session_count() < 5:
        return []

    notes = vault.notes()
    finder = TemporalPatternFinder(vault)

    # Find notes with cyclical patterns
    cycling_notes = finder.find_cycling_notes(notes, min_cycles=2)

    if not cycling_notes:
        return []

    suggestions = []

    # Sample candidates (taking the first five in vault order meant later
    # notes could never be shown)
    for note in vault.sample(cycling_notes, 5):
        # Session dates for context (>= 5, since cycling needs 5 snapshots)
        session_dates = vault.session_dates_for_note(note)
        first_date = session_dates[0][:7]
        last_date = session_dates[-1][:7]

        text = (
            f"Your edits to [[{note.link_text}]] have moved it away from its first "
            f"recorded version and back again more than once ({first_date} to {last_date}). "
            f"What recurring theme keeps drawing you back?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.link_text],
                geist_id="cyclical_thinking",
            )
        )

    # Sample up to 2 of them (sample, don't rank)
    return vault.sample(suggestions, count=min(2, len(suggestions)))
