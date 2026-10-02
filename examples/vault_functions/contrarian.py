"""Contrarian vault function - find semantically dissimilar notes.

This function finds the notes least similar in topic to a given note. Despite
the name, they are not contrarian: embedding similarity measures topic, not
stance, so a note that argues against this one is on-topic and scores high.
Treat the result as "far away", like the bundled ``contrarian_to``.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import VaultContext

from geistfabrik import vault_function


@vault_function("example_contrarian_to")
def find_contrarian(vault: "VaultContext", note_title: str, count: int = 3) -> list[str]:
    """Find the notes least similar in topic to the given note.

    Args:
        vault: VaultContext
        note_title: Title, path or link target of the note to start from
        count: Number of distant notes to return

    Returns:
        List of count bracketed links to the most dissimilar notes
    """
    note = vault.resolve_link_target(note_title)
    if note is None:
        return []

    all_notes = vault.notes()

    # Get similarity scores for all notes
    similarities = []
    for n in all_notes:
        if n.path == note.path:
            continue  # Skip self
        sim = vault.similarity(note, n)
        similarities.append((n, sim))

    # Sort by similarity ascending (least similar first)
    similarities.sort(key=lambda x: x[1])

    # Return the least similar notes as Tracery-safe Obsidian links. The
    # example name is deliberately distinct from the bundled contrarian_to.
    return [f"[[{note.link_text}]]" for note, _ in similarities[:count]]
