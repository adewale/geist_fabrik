"""Island Hopper geist - finds notes that could bridge disconnected clusters.

Identifies notes that are semantically close to a cluster but not part of it,
suggesting they could serve as bridges to connect islands of thought.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes that could bridge disconnected graph clusters.

    Returns:
        List of suggestions for potential bridge notes
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []

    # Find disconnected clusters (notes with lots of internal links, few external)
    all_notes = vault.notes()

    if len(all_notes) < 10:
        return []

    # Build simple clusters using hub notes as cluster centers
    hubs = vault.hubs(k=5)

    for hub in hubs:
        # A cluster is the hub + notes that link to it
        backlinks = vault.backlinks(hub)
        cluster = [hub] + backlinks

        if len(cluster) < 3:
            continue

        # Find notes semantically near cluster but not in it
        boundary_notes = []

        cluster_set = set(n.path for n in cluster)
        candidate_notes = [note for note in all_notes if note.path not in cluster_set]

        if candidate_notes and cluster:
            # Compute similarities using individual calls to benefit from cache
            for note in candidate_notes:
                # Calculate average similarity to cluster members
                sims = [vault.similarity(note, cluster_member) for cluster_member in cluster]
                avg_sim = sum(sims) / len(sims) if sims else 0

                # Close enough to bridge, not so close it should be in cluster
                if SimilarityLevel.MODERATE < avg_sim < SimilarityLevel.HIGH:
                    boundary_notes.append((note, avg_sim))

        if boundary_notes:
            # Take the best bridge candidate
            boundary_notes.sort(key=lambda x: x[1], reverse=True)
            bridge, sim = boundary_notes[0]

            cluster_sample = vault.sample(cluster, k=2)
            cluster_names = ", ".join([f"[[{n.obsidian_link}]]" for n in cluster_sample])

            text = (
                f"[[{bridge.obsidian_link}]] could bridge your cluster around "
                f"[[{hub.obsidian_link}]] (which includes {cluster_names}). It's "
                f"semantically related but not yet connected."
            )

            notes_list = [bridge.obsidian_link, hub.obsidian_link]
            notes_list.extend([n.obsidian_link for n in cluster_sample])

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=notes_list,
                    geist_id="island_hopper",
                )
            )

    return vault.sample(suggestions, k=3)
