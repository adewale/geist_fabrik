"""Link density analyzer geist - finds notes with unusual link patterns.

Identifies notes that have too many or too few links relative to their content,
suggesting opportunities for better integration or focus.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Analyze link density and suggest improvements.

    Returns:
        List of suggestions for link density improvements
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    for note in notes:
        metadata = vault.metadata(note)

        word_count = metadata.get("word_count", 0)
        link_count = metadata.get("link_count", 0)

        if word_count < 50:
            continue  # Too short to analyze

        # Calculate links per 100 words
        link_density = (link_count / word_count) * 100 if word_count > 0 else 0

        # Case 1: Too many links (> 5 per 100 words)
        if link_density > 5:
            text = (
                f"What if [[{note.title}]] has too many links? "
                f"With {link_count} links in {word_count} words, "
                f"it might be overwhelming. Consider focusing on key connections."
            )
            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.title],
                    geist_id="link_density_analyzer",
                )
            )

        # Case 2: Too few links (< 0.5 per 100 words)
        elif link_density < 0.5 and word_count > 200:
            text = (
                f"What if [[{note.title}]] needs more connections? "
                f"With only {link_count} links in {word_count} words, "
                f"it might be isolated from your knowledge graph."
            )
            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.title],
                    geist_id="link_density_analyzer",
                )
            )

    return vault.sample(suggestions, k=3)
