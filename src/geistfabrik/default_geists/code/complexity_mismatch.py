"""Complexity mismatch geist - finds notes where complexity doesn't match importance.

Suggests either simplifying over-complex notes or deepening under-developed
important notes.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with complexity/importance mismatches.

    Returns:
        List of suggestions for complexity mismatches
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    for note in notes:
        metadata = vault.metadata(note)

        # Get metrics
        word_count = metadata.get("word_count", 0)
        link_count = metadata.get("link_count", 0)
        backlinks = len(vault.backlinks(note))

        # Importance score (based on connectivity)
        importance = (link_count + backlinks * 2) / max(1, len(notes))

        # Complexity score (based on length)
        complexity = word_count / 100  # Scale: 0-10+ for 0-1000+ words

        # Case 1: High importance, low complexity (underdeveloped)
        if importance > 0.1 and complexity < 1 and word_count < 100:
            text = (
                f"What if you expanded [[{note.obsidian_link}]]? "
                f"It's highly connected ({link_count + backlinks} links) "
                f"but only {word_count} words. Might it deserve more depth?"
            )
            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link],
                    geist_id="complexity_mismatch",
                )
            )

        # Case 2: Low importance, high complexity (overcomplicated)
        elif importance < 0.05 and complexity > 3 and link_count < 2:
            text = (
                f"What if you simplified [[{note.obsidian_link}]]? "
                f"It's {word_count} words but only {link_count} links. "
                f"Could it be more focused or split into multiple notes?"
            )
            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link],
                    geist_id="complexity_mismatch",
                )
            )

    return vault.sample(suggestions, k=3)
