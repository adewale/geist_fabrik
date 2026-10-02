"""Concept cluster geist - identifies tight concept clusters.

Finds groups of semantically related notes that might represent a theme or
area of interest worth naming and organising. (Nothing about the group's age
is checked, so the suggestion does not call it "emerging".)

Absorbed the retired semantic_neighbours Tracery geist (its closing
questions; the YAML lives on in examples/geists/tracery/ as the cluster-pattern
demo) and pattern_finder's semantic-cluster branch ("no links between them",
said here only after checking every pair in the cluster for a link).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext
    from geistfabrik.models import Note

# One is sampled to close a suggestion about a cluster that has internal links.
CLOSERS = (
    "Could they be organised under a shared theme?",
    "What's the common thread?",
    "What do they share?",
    "What pattern emerges?",
)


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Identify potential concept clusters.

    Samples 5 seeds; a seed plus its 3 nearest neighbours is a cluster when
    their average pairwise similarity exceeds SimilarityLevel.HIGH. Up to 2
    distinct clusters are sampled and worded: one with no link between any of
    its notes says so, any other ends with a sampled closer.

    Returns:
        List of suggestions for concept clusters
    """
    from geistfabrik.similarity_analysis import SimilarityLevel

    clusters: list[list[Note]] = []
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
            clusters.append(cluster_notes)

    return [_describe(vault, cluster) for cluster in vault.sample(clusters, count=2)]


def _describe(vault: "VaultContext", cluster: list["Note"]) -> "Suggestion":
    """Word one cluster (seed first), noting when none of its notes link."""
    from geistfabrik import Suggestion

    note_titles = [n.link_text for n in cluster]
    formatted_titles = "]], [[".join(note_titles)
    unlinked = not any(
        vault.links_between(a, b) for i, a in enumerate(cluster) for b in cluster[i + 1 :]
    )
    if unlinked:
        body = (
            f"These notes are tightly related, but none of them links to another: "
            f"[[{formatted_titles}]]. What's the theme you haven't named yet?"
        )
    else:
        closer = vault.sample(CLOSERS, count=1)[0]
        body = f"These notes are tightly related: [[{formatted_titles}]]. {closer}"

    return Suggestion(
        text=f"What if you named the cluster around [[{cluster[0].link_text}]]? {body}",
        notes=note_titles,
        geist_id="concept_cluster",
    )
