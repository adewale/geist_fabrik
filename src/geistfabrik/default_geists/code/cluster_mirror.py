"""Cluster Mirror geist - reveals semantic vault structure.

Shows automatically-named clusters with representative samples, then asks:
"What do these clusters remind you of?"

Pure pattern presentation without interpretation - a mirror that reflects
the unconscious organizational structure of your vault back to you.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Show named clusters and ask what they remind you of.

    Uses HDBSCAN clustering with c-TF-IDF labelling (+ MMR diversity filtering)
    to reveal the natural semantic structure of the vault. Shows 2-3 clusters
    with representative note examples, then asks a direct question without
    interpretation.

    Returns:
        Single suggestion showing cluster patterns
    """
    from geistfabrik import Suggestion

    # Get cluster assignments and labels
    clusters = vault.get_clusters(min_size=5)

    # Need at least 2 clusters to show patterns
    if len(clusters) < 2:
        return []

    # Sample 2-3 clusters to show
    cluster_ids = list(clusters.keys())
    selected_ids = vault.sample(cluster_ids, k=min(3, len(cluster_ids)))

    cluster_descriptions = []
    all_sampled_notes = []

    for cluster_id in selected_ids:
        cluster = clusters[cluster_id]

        # Use formatted phrase label
        label = cluster["formatted_label"]

        # Get 3 representative notes (closest to centroid)
        # Pass clusters to avoid redundant clustering
        representatives = vault.get_cluster_representatives(cluster_id, k=3, clusters=clusters)
        note_titles = [f"[[{n.obsidian_link}]]" for n in representatives]

        cluster_descriptions.append(f"{label}\n→ {', '.join(note_titles)}")
        all_sampled_notes.extend([n.obsidian_link for n in representatives])

    # Pure muse question: no interpretation, just pattern presentation
    text = "\n\n".join(cluster_descriptions) + "\n\nWhat do these clusters remind you of?"

    return [
        Suggestion(
            text=text,
            notes=all_sampled_notes,
            geist_id="cluster_mirror",
        )
    ]
