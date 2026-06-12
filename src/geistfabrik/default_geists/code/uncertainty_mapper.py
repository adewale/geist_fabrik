"""Uncertainty mapper geist - surfaces notes with heavy hedging.

A reflective lens over epistemic voice: hedge words ("maybe", "perhaps",
"I think", "sort of") mark claims you are not yet ready to commit to.
This geist finds the note where you hedge the most and asks what is
holding you back.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion
from geistfabrik.voice_analysis import count_hedges


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes where you're hedging heavily.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion naming the most heavily hedged note
    """
    hedgy_notes = []
    for note in vault.notes_excluding_journal():
        hedging = vault.voice(note).hedging_ratio
        if hedging > 0.3:  # More than 0.3 hedges per sentence
            hedgy_notes.append((note, hedging))

    if not hedgy_notes:
        return []

    hedgy_notes.sort(key=lambda x: float(x[1]), reverse=True)
    note, _ratio = hedgy_notes[0]

    hedge_count = count_hedges(note.content)
    word_count = len(note.content.split())

    return [
        Suggestion(
            text=(
                f"[[{note.link_text}]] hedges {hedge_count} times "
                f"in {word_count} words. What are you not ready to commit to?"
            ),
            notes=[note.link_text],
            geist_id="uncertainty_mapper",
        )
    ]
