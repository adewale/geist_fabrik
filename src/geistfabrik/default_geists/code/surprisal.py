"""Surprisal geist - surfaces informationally unexpected notes.

A reflective lens over semantic neighbourhoods: a note with high
surprisal sits far from the centroid of its own nearest neighbours —
it says something different from everything around it. Such a note is
either a seed of new thinking or a stray thought.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find the note that least fits its semantic neighbourhood.

    Uses the session-cached, vectorised VaultContext.surprisal_scores()
    (one blocked matrix pass shared across all geists), never a per-note
    similarity loop.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion naming the most surprising note
    """
    scores = vault.surprisal_scores()
    if not scores:
        return []  # Tiny vault — surprisal is meaningless

    path = max(scores, key=lambda p: scores[p])
    note = vault.get_note(path)
    if note is None:
        return []

    neighbours = vault.neighbours(note, count=3)
    if not neighbours:
        return []

    neighbour_titles = ", ".join(f"[[{n.obsidian_link}]]" for n in neighbours)

    return [
        Suggestion(
            text=(
                f"[[{note.obsidian_link}]] doesn't quite fit. "
                f"Its neighbours are {neighbour_titles}, but it says something different. "
                f"Is it a seed of new thinking, or a stray thought?"
            ),
            notes=[note.obsidian_link] + [n.obsidian_link for n in neighbours],
            geist_id="surprisal",
        )
    ]
