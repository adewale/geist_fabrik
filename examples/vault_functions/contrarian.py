"""Contrarian vault function - find semantically dissimilar notes.

This function finds notes that are semantically distant from a given note,
potentially representing contrarian or alternative viewpoints.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from geistfabrik import Note, VaultContext

from geistfabrik import vault_function


@vault_function("contrarian_to")
def find_contrarian(vault: "VaultContext", note_title: str, k: int = 3) -> List["Note"]:
    """Find notes that are semantically dissimilar to given note.

    Args:
        vault: VaultContext
        note_title: Title of note to find contrarians for
        k: Number of contrarian notes to return

    Returns:
        List of k most dissimilar notes
    """
    note = vault.get_note(note_title)
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

    # Return k least similar
    return [n for n, _ in similarities[:k]]
