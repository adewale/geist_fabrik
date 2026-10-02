"""Complexity mismatch geist - finds notes where complexity doesn't match importance.

Suggests either simplifying over-complex notes or deepening under-developed
important notes.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

# "Highly connected": at least this many (non-journal) notes link to it
MIN_BACKLINKS_FOR_IMPORTANT = 5
# A note under this many words is a stub
MAX_STUB_WORDS = 100
# A note over this many words is long enough to consider splitting
MIN_LONG_WORDS = 1500


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

        # Get metrics. Thresholds are absolute: normalising connectivity by
        # vault size made "highly connected" unreachable in large vaults and
        # trivial in small ones.
        word_count = metadata.get("word_count", 0)
        link_count = metadata.get("link_count", 0)
        backlinks = len(vault.backlinks(note))

        # Case 1: many notes rely on it, but it is a stub (underdeveloped)
        if backlinks >= MIN_BACKLINKS_FOR_IMPORTANT and word_count < MAX_STUB_WORDS:
            text = (
                f"What if you expanded [[{note.link_text}]]? "
                f"It's highly connected ({backlinks} notes link to it) "
                f"but only {word_count} words. Might it deserve more depth?"
            )
            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text],
                    geist_id="complexity_mismatch",
                )
            )

        # Case 2: very long and entirely unconnected (overcomplicated)
        elif word_count > MIN_LONG_WORDS and link_count == 0 and backlinks == 0:
            text = (
                f"What if you simplified [[{note.link_text}]]? "
                f"It's {word_count} words with no links in or out. "
                f"Could it be more focused or split into multiple notes?"
            )
            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text],
                    geist_id="complexity_mismatch",
                )
            )

    return vault.sample(suggestions, count=3)
