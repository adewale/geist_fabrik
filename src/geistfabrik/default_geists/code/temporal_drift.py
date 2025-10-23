"""Temporal drift geist - finds notes whose content/meaning may have drifted over time.

Suggests revisiting notes that you haven't modified in a while to see if they still
represent your current thinking.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find stale notes that might benefit from revisiting.

    Returns:
        List of suggestions for potentially stale notes
    """
    from geistfabrik import Suggestion

    suggestions = []

    # Get old notes that have high link density (important but stale)
    old = vault.old_notes(k=20)

    for note in old:
        metadata = vault.metadata(note)
        staleness = metadata.get("staleness", 0)
        link_count = metadata.get("link_count", 0)

        # Only suggest notes that are both stale and well-connected
        if staleness > 0.7 and link_count >= 3:
            days = metadata.get("days_since_modified", 0)
            text = (
                f"What if [[{note.title}]] needs updating? "
                f"It's been {days} days since you modified it, "
                f"but it has {link_count} links - might your thinking have evolved?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.title],
                    geist_id="temporal_drift",
                )
            )

    return vault.sample(suggestions, k=3)
