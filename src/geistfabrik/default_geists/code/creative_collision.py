"""Creative collision geist - suggests unexpected combinations of notes.

Finds unlinked, only loosely related notes (similarity between
SimilarityLevel.NOISE and SimilarityLevel.WEAK) and suggests combining them
for creative insights.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Suggest creative collisions between unrelated notes.

    Returns:
        List of suggestions for creative note combinations
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []
    # Random draws can repeat a pair; suggest each pair at most once
    seen_pairs: set[frozenset[str]] = set()

    # Get random pairs of notes
    notes = vault.notes()

    if len(notes) < 2:
        return []

    # Collect candidate pairs
    for _ in range(10):
        pair = vault.sample(notes, count=2)
        if len(pair) != 2:
            continue

        note_a, note_b = pair
        pair_key = frozenset((note_a.path, note_b.path))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        # Check if they're unlinked and dissimilar
        if vault.links_between(note_a, note_b):
            continue

        # Compute similarity using individual call to benefit from cache
        similarity = vault.similarity(note_a, note_b)

        # Loosely related: distant, but not completely unrelated. (Up to
        # MODERATE admitted most random pairs in a vault: ~70% on a real one.)
        if SimilarityLevel.NOISE < similarity < SimilarityLevel.WEAK:
            text = (
                f"What if you combined ideas from [[{note_a.link_text}]] and "
                f"[[{note_b.link_text}]]? They're unlinked and only loosely "
                f"related, which might spark something unexpected."
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note_a.link_text, note_b.link_text],
                    geist_id="creative_collision",
                )
            )

    return vault.sample(suggestions, count=3)
