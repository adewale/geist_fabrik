"""Concept cluster geist - identifies tight concept clusters.

Finds groups of semantically related notes that might represent a theme or
area of interest worth naming and organising. (Nothing about the group's age
is checked, so the suggestion does not call it "emerging".)
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
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []
    # Seeds from the same group find the same cluster; report each set once
    reported: set[frozenset[str]] = set()

    notes = vault.notes()

    if len(notes) < 5:
        return []

    # Sample some notes and find their neighbourhoods
    seed_notes = vault.sample(notes, count=5)

    for seed in seed_notes:
        # Get neighbours of this note
        neighbours = vault.neighbours(seed, count=5)

        if len(neighbours) < 3:
            continue

        # Check if these neighbours are also similar to each other
        # (indicating a cluster, not just a hub-and-spoke)
        cluster_notes = [seed] + neighbours[:3]
        cluster_key = frozenset(n.path for n in cluster_notes)
        if cluster_key in reported:
            continue

        # Calculate average pairwise similarity within cluster
        # Use individual similarity() calls to benefit from session cache
        similarities = []
        for i in range(len(cluster_notes)):
            for j in range(i + 1, len(cluster_notes)):
                sim = vault.similarity(cluster_notes[i], cluster_notes[j])
                similarities.append(sim)

        avg_similarity = sum(similarities) / len(similarities) if similarities else 0

        # If average similarity is high, this is a real cluster
        if avg_similarity > SimilarityLevel.HIGH:
            reported.add(cluster_key)
            note_titles = [n.link_text for n in cluster_notes]
            formatted_titles = "]], [[".join(note_titles)

            text = (
                f"What if you named the cluster around [[{seed.link_text}]]? "
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

    return vault.sample(suggestions, count=2)
