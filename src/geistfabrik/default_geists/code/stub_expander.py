"""Stub expander geist - finds short notes that might benefit from expansion.

Identifies stub notes (very short notes with links) that could be developed
into more substantial notes.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find stub notes worth expanding.

    Returns:
        List of suggestions for expanding stubs
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes_excluding_journal()

    for note in notes:
        metadata = vault.metadata(note)

        word_count = metadata.get("word_count", 0)
        link_count = metadata.get("link_count", 0)
        backlink_count = len(vault.backlinks(note))

        # Look for short notes with connections (stubs)
        if word_count < 50 and (link_count > 0 or backlink_count > 0):
            total_links = link_count + backlink_count

            text = (
                f"What if you expanded [[{note.obsidian_link}]]? "
                f"It's only {word_count} words but has {total_links} connections. "
                f"This stub might be worth developing."
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link],
                    geist_id="stub_expander",
                )
            )

    return vault.sample(suggestions, k=3)
