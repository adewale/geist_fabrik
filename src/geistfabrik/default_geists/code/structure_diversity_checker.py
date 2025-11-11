"""Structure Diversity Checker - Identify when writing structure becomes too uniform.

This geist analyzes the structural diversity of recent notes and alerts you
when your writing patterns become too repetitive. It suggests breaking
out of structural ruts by pointing to notes with different structures.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Note, VaultContext

from geistfabrik import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Check for structural diversity in recent notes.

    Args:
        vault: VaultContext with access to vault data

    Returns:
        List of suggestions about structural diversity
    """
    suggestions = []

    # Get recent notes
    recent = vault.recent_notes(k=8)
    if len(recent) < 5:
        return []

    # Classify structure type for each recent note
    recent_structures = []
    for note in recent:
        structure_type = _classify_structure(vault, note)
        recent_structures.append((note, structure_type))

    # Check if recent structures are too uniform
    structure_types = [s for _, s in recent_structures]
    unique_types = set(structure_types)

    # If 80%+ of recent notes have same structure type, flag it
    if len(unique_types) <= 2:
        dominant_type = max(set(structure_types), key=structure_types.count)
        dominant_count = structure_types.count(dominant_type)

        if dominant_count >= len(recent) * 0.7:
            # Find a note with different structure as an example
            different_example = _find_different_structure(vault, dominant_type)

            if different_example:
                different_structure = _classify_structure(vault, different_example)
                text = (
                    f"Your last {len(recent)} notes are structurally similar "
                    f"({dominant_count} are {dominant_type}). "
                    f"\n\n[[{different_example.obsidian_link}]] has a different structure "
                    f"({different_structure}). What if you tried that style again?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[different_example.obsidian_link],
                        geist_id="structure_diversity_checker",
                    )
                )

    return suggestions


def _classify_structure(vault: "VaultContext", note: "Note") -> str:
    """Classify the structural style of a note.

    Args:
        vault: VaultContext for metadata access
        note: Note to classify

    Returns:
        Structure type: "list-heavy", "task-oriented", "prose-heavy",
        "code-heavy", or "mixed"
    """
    metadata = vault.metadata(note)

    list_count = metadata.get("list_item_count", 0)
    task_count = metadata.get("task_count", 0)
    code_block_count = metadata.get("code_block_count", 0)
    heading_count = metadata.get("heading_count", 0)
    word_count = len(note.content.split())

    # Normalise by word count to get density
    list_density = list_count / max(1, word_count / 100)
    task_density = task_count / max(1, word_count / 100)
    code_density = code_block_count / max(1, word_count / 200)

    # Classify based on dominant structural element
    if task_density > 2:
        return "task-oriented"
    elif list_density > 5:
        return "list-heavy"
    elif code_density > 1:
        return "code-heavy"
    elif heading_count < 2 and list_count < 3:
        return "prose-heavy"
    else:
        return "mixed"


def _find_different_structure(vault: "VaultContext", avoid_type: str) -> "Note | None":
    """Find a note with a different structure type.

    Args:
        vault: VaultContext for accessing notes
        avoid_type: Structure type to avoid

    Returns:
        A note with different structure, or None if not found
    """
    # Look through older notes for different structures
    all_notes = vault.notes()

    different_notes = []
    for note in all_notes:
        structure_type = _classify_structure(vault, note)
        if structure_type != avoid_type:
            different_notes.append(note)

    if different_notes:
        # Sample one
        sampled = vault.sample(different_notes, 1)
        if sampled:
            return sampled[0]  # type: ignore[no-any-return]

    return None
