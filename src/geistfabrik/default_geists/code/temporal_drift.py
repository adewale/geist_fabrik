"""Temporal drift geist - finds notes whose content/meaning may have drifted over time.

Suggests revisiting notes that you haven't modified in a while but that other
notes still depend on, to see if they still represent your current thinking.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

# Built-in staleness is 1 - 1 / (1 + days / 30): > 0.7 means > 70 days.
STALENESS_THRESHOLD = 0.7
# "Well-connected" means other user notes link to it: an old note matters when
# other notes lean on it. Raw outgoing link counts included code samples,
# duplicates and links to notes that don't exist.
MIN_BACKLINKS = 2


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find stale notes that other notes still link to.

    Scans every user note (not just the least recently modified few), so a
    linked-to note is found however many older unlinked notes the vault has.

    Returns:
        List of suggestions for potentially stale notes
    """
    from geistfabrik import Suggestion

    suggestions = []

    for note in vault.notes():
        metadata = vault.metadata(note)
        if metadata.get("staleness", 0) <= STALENESS_THRESHOLD:
            continue
        backlink_count = len(vault.backlinks(note))
        if backlink_count < MIN_BACKLINKS:
            continue

        days = metadata.get("days_since_modified", 0)
        text = (
            f"What if [[{note.link_text}]] needs updating? "
            f"It's been {days} days since you modified it, "
            f"but {backlink_count} notes link to it - might your thinking have evolved?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.link_text],
                geist_id="temporal_drift",
            )
        )

    return vault.sample(suggestions, count=3)
