"""Question vault functions - find notes that pose questions.

These functions help find notes that are questions or that might benefit
from being framed as questions.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from geistfabrik import VaultContext

from geistfabrik import vault_function


@vault_function("find_questions")
def find_question_notes(vault: "VaultContext", count: int = 5) -> list[str]:
    """Find notes that are phrased as questions.

    Args:
        vault: VaultContext
        count: Number of question notes to return

    Returns:
        List of up to count bracketed links with titles ending in '?'
    """
    questions = [n for n in vault.notes() if n.title.endswith("?")]
    return [f"[[{note.link_text}]]" for note in vault.sample(questions, count)]


@vault_function("notes_with_metadata")
def notes_with_metadata(
    vault: "VaultContext", key: str, value: Any = None, count: int = 10
) -> list[str]:
    """Find notes with specific metadata key/value.

    Args:
        vault: VaultContext
        key: Metadata key to search for
        value: Optional value to match. If None, any value matches.
        count: Maximum number of notes to return

    Returns:
        List of up to count bracketed links with matching metadata
    """
    matching = []
    for note in vault.notes():
        metadata = vault.metadata(note)
        if key in metadata:
            if value is None or metadata[key] == value:
                matching.append(note)

    return [f"[[{note.link_text}]]" for note in vault.sample(matching, count)]
