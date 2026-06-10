"""Temporal voice geist - contrasts past-focused and future-focused notes.

A reflective lens over linguistic voice: some notes dwell in memory
(past-tense), others reach toward plans and anticipation (future-tense).
This geist finds a semantically related pair with opposite temporal
orientation and asks what bridges reflection and anticipation.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with contrasting temporal orientations.

    Performs a bounded search (at most 5 past notes x 20 future notes)
    using individual similarity() calls, which are session-cache-aware
    and allow early termination as soon as a close pair is found.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion pairing a past-focused and a future-focused note
    """
    notes = vault.notes_excluding_journal()
    past_notes = [n for n in notes if vault.metadata(n).get("temporal_orientation") == "past"]
    future_notes = [n for n in notes if vault.metadata(n).get("temporal_orientation") == "future"]

    if not past_notes or not future_notes:
        return []

    # Bounded search for a semantically related pair with opposite voice.
    # Individual similarity() calls are the right tool here: cache-aware,
    # with early return on the first sufficiently close pair.
    future_candidates = vault.sample(future_notes, min(20, len(future_notes)))
    for past_note in vault.sample(past_notes, min(5, len(past_notes))):
        for future_note in future_candidates:
            if vault.similarity(past_note, future_note) > 0.5:
                return [
                    Suggestion(
                        text=(
                            f"[[{past_note.obsidian_link}]] looks backward. "
                            f"[[{future_note.obsidian_link}]] looks forward. "
                            f"They're semantically close — what bridges "
                            f"reflection and anticipation here?"
                        ),
                        notes=[past_note.obsidian_link, future_note.obsidian_link],
                        geist_id="temporal_voice",
                    )
                ]

    # Fallback: any contrast between the two voices
    past = vault.sample(past_notes, 1)[0]
    future = vault.sample(future_notes, 1)[0]
    return [
        Suggestion(
            text=(
                f"[[{past.obsidian_link}]] dwells in the past. "
                f"[[{future.obsidian_link}]] reaches toward the future. "
                f"What would a present-tense note about these topics say?"
            ),
            notes=[past.obsidian_link, future.obsidian_link],
            geist_id="temporal_voice",
        )
    ]
