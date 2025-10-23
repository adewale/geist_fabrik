"""Concept cluster geist - identifies emergent concept clusters.

Finds groups of semantically related notes that might represent an emerging
theme or area of interest worth naming and organising.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Identify potential concept clusters.

    Returns:
        List of suggestions for concept clusters
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    if len(notes) < 5:
        return []

    # Sample some notes and find their neighbourhoods
    seed_notes = vault.sample(notes, k=5)

    for seed in seed_notes:
        # Get neighbours of this note
        neighbours = vault.neighbours(seed, k=5)

        if len(neighbours) < 3:
            continue

        # Check if these neighbours are also similar to each other
        # (indicating a cluster, not just a hub-and-spoke)
        cluster_notes = [seed] + neighbours[:3]

        # Calculate average pairwise similarity within cluster
        total_sim = 0.0
        pairs = 0
        for i, note_a in enumerate(cluster_notes):
            for note_b in cluster_notes[i + 1 :]:
                total_sim += vault.similarity(note_a, note_b)
                pairs += 1

        avg_similarity = total_sim / pairs if pairs > 0 else 0

        # If average similarity is high, this is a real cluster
        if avg_similarity > 0.6:
            note_titles = [n.title for n in cluster_notes]
            formatted_titles = "]], [[".join(note_titles)

            text = (
                f"What if you recognised an emerging cluster around [[{seed.title}]]? "
                f"These notes are tightly related: [[{formatted_titles}]]. "
                f"Could they be organised under a shared theme?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=note_titles,
                    geist_id="concept_cluster",
                )
            )

    return vault.sample(suggestions, k=2)
