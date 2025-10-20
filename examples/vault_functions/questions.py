"""Question vault functions - find notes that pose questions.

These functions help find notes that are questions or that might benefit
from being framed as questions.
"""

from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from geistfabrik import Note, VaultContext

from geistfabrik import vault_function


@vault_function("find_questions")
def find_question_notes(vault: "VaultContext", k: int = 5) -> List["Note"]:
    """Find notes that are phrased as questions.

    Args:
        vault: VaultContext
        k: Number of question notes to return

    Returns:
        List of up to k notes with titles ending in '?'
    """
    questions = [n for n in vault.notes() if n.title.endswith("?")]
    return vault.sample(questions, k)


@vault_function("notes_with_metadata")
def notes_with_metadata(
    vault: "VaultContext", key: str, value: Any = None, k: int = 10
) -> List["Note"]:
    """Find notes with specific metadata key/value.

    Args:
        vault: VaultContext
        key: Metadata key to search for
        value: Optional value to match. If None, any value matches.
        k: Maximum number of notes to return

    Returns:
        List of up to k notes with matching metadata
    """
    matching = []
    for note in vault.notes():
        metadata = vault.metadata(note)
        if key in metadata:
            if value is None or metadata[key] == value:
                matching.append(note)

    return vault.sample(matching, k)
