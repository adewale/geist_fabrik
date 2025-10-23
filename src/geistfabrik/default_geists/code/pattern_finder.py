"""Pattern Finder geist - identifies repeated themes across unconnected notes.

Discovers patterns, phrases, or conceptual themes that appear in multiple notes
that aren't linked to each other, suggesting implicit recurring interests.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find repeated themes across unconnected notes.

    Returns:
        List of suggestions highlighting hidden patterns
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    if len(notes) < 15:
        return []

    # Look for repeated significant phrases (2-3 word combinations)
    phrase_to_notes = defaultdict(list)

    for note in notes:
        content = vault.read(note).lower()
        words = content.split()

        # Extract 2-3 word phrases
        for i in range(len(words) - 2):
            # Skip common words
            phrase = " ".join(words[i : i + 3])

            # Filter out common phrases
            if len(phrase) > 15 and not any(
                common in phrase for common in ["the", "and", "but", "with", "from", "this", "that"]
            ):
                phrase_to_notes[phrase].append(note)

    # Find phrases that appear in multiple unlinked notes
    for phrase, phrase_notes in phrase_to_notes.items():
        if len(phrase_notes) >= 3:
            # Check if these notes are connected
            unlinked_group = []

            for i, note_a in enumerate(phrase_notes):
                is_isolated = True
                for note_b in phrase_notes:
                    if note_a.path != note_b.path and vault.links_between(note_a, note_b):
                        is_isolated = False
                        break

                if is_isolated:
                    unlinked_group.append(note_a)

            if len(unlinked_group) >= 3:
                sample = vault.sample(unlinked_group, k=3)
                note_names = ", ".join([f"[[{n.title}]]" for n in sample])

                text = (
                    f'The phrase "{phrase}" appears in multiple unconnected notes: {note_names}. '
                    f"Recurring theme you haven't explicitly connected?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[n.title for n in sample],
                        geist_id="pattern_finder",
                    )
                )

    # Also look for semantic clusters of unlinked notes
    # Group notes by semantic similarity
    clusters = []
    unclustered = list(notes)

    while len(unclustered) > 5:
        # Pick a seed note
        seed = vault.sample(unclustered, k=1)[0]
        unclustered.remove(seed)

        # Find similar notes
        cluster = [seed]
        for note in unclustered[:]:
            if vault.similarity(seed, note) > 0.7:  # Very similar
                cluster.append(note)
                unclustered.remove(note)

            if len(cluster) >= 5:  # Limit cluster size
                break

        if len(cluster) >= 3:
            clusters.append(cluster)

        if len(clusters) >= 3:  # Enough clusters found
            break

    # Report on clusters of unlinked but similar notes
    for cluster in clusters:
        # Check if cluster notes are linked
        link_count = sum(
            1
            for i, n1 in enumerate(cluster)
            for n2 in cluster[i + 1 :]
            if vault.links_between(n1, n2)
        )

        if link_count == 0:  # No internal links
            sample = vault.sample(cluster, k=3)
            note_names = ", ".join([f"[[{n.title}]]" for n in sample])

            text = (
                f"Found a semantic cluster of similar notes with no links between them: "
                f"{note_names}. What's the common theme you haven't named yet?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[n.title for n in sample],
                    geist_id="pattern_finder",
                )
            )

    return vault.sample(suggestions, k=2)
