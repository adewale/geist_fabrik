"""Island Hopper geist - finds notes that could bridge disconnected clusters.

Identifies notes that are semantically close to a cluster (a hub and the notes
linking to it) but not linked to any of its notes, asking whether they could
serve as bridges to connect islands of thought.
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
    hubs = vault.hubs(count=5)

    for hub in hubs:
        # A cluster is the hub + notes that link to it
        backlinks = vault.backlinks(hub)
        cluster = [hub] + backlinks

        if len(cluster) < 3:
            continue

        # Find notes semantically near cluster but not in it
        boundary_notes = []

        # "Not yet connected" must hold: skip members and any note linked to
        # or from a member (e.g. a note the hub itself links to).
        excluded = {n.path for n in cluster}
        for member in cluster:
            excluded.update(n.path for n in vault.graph_neighbours(member))
        candidate_notes = [note for note in all_notes if note.path not in excluded]

        if candidate_notes and cluster:
            # Compute the candidate×cluster similarity matrix in one vectorised,
            # cache-aware operation rather than an O(candidates×cluster) loop of
            # individual similarity() calls (the matrix use-case batch_similarity()
            # is designed for - see CLAUDE.md). Average each candidate's similarity
            # across the cluster members.
            sim_matrix = vault.batch_similarity(candidate_notes, cluster)
            avg_sims = sim_matrix.mean(axis=1)
            for note, avg in zip(candidate_notes, avg_sims):
                avg_sim = float(avg)

                # Close enough to bridge, not so close it should be in cluster
                if SimilarityLevel.MODERATE < avg_sim < SimilarityLevel.HIGH:
                    boundary_notes.append((note, avg_sim))

        if boundary_notes:
            # Take the best bridge candidate
            boundary_notes.sort(key=lambda x: x[1], reverse=True)
            bridge, sim = boundary_notes[0]

            # Sample members other than the hub, which is already named
            cluster_sample = vault.sample(backlinks, count=2)
            cluster_names = ", ".join([f"[[{n.link_text}]]" for n in cluster_sample])

            text = (
                f"[[{bridge.link_text}]] is semantically close to your cluster around "
                f"[[{hub.link_text}]] (which includes {cluster_names}) but isn't "
                f"linked to any of its notes. Could it bridge that island to the rest "
                f"of your thinking?"
            )

            notes_list = [bridge.link_text, hub.link_text]
            notes_list.extend([n.link_text for n in cluster_sample])

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=notes_list,
                    geist_id="island_hopper",
                )
            )

    return vault.sample(suggestions, count=3)
