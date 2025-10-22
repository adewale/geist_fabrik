"""Temporal Clustering geist - discovers automatic intellectual periods.

Uses temporal embeddings to find notes that naturally cluster by era, revealing
distinct "seasons" of thinking without manual tagging.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find temporal clusters that reveal intellectual periods.

    Returns:
        List of suggestions highlighting temporal thinking patterns
    """
    from geistfabrik import Suggestion

    suggestions = []

    try:
        notes = vault.notes()

        if len(notes) < 20:
            return []

        # Group notes by time periods (quarters)
        from datetime import datetime, timedelta

        now = datetime.now()

        # Define time windows (quarters going back 2 years)
        quarters = []
        for i in range(8):  # 8 quarters = 2 years
            end_date = now - timedelta(days=i * 90)
            start_date = end_date - timedelta(days=90)
            quarters.append((start_date, end_date, f"Q{(i % 4) + 1}-{end_date.year}"))

        # Group notes by quarter and find if distinct semantic clusters emerge
        quarter_groups = {}

        for note in notes:
            for start, end, label in quarters:
                if start <= note.created <= end:
                    if label not in quarter_groups:
                        quarter_groups[label] = []
                    quarter_groups[label].append(note)
                    break

        # Find quarters with distinct semantic character
        significant_clusters = []

        for label, quarter_notes in quarter_groups.items():
            if len(quarter_notes) < 5:
                continue

            # Calculate intra-cluster similarity (how similar are notes within this quarter)
            similarities = []
            sample = vault.sample(quarter_notes, min(10, len(quarter_notes)))

            for i, note_a in enumerate(sample):
                for note_b in sample[i + 1 :]:
                    sim = vault.similarity(note_a, note_b)
                    similarities.append(sim)

            if similarities:
                avg_similarity = sum(similarities) / len(similarities)

                # High intra-cluster similarity suggests a coherent intellectual period
                if avg_similarity > 0.5:
                    significant_clusters.append((label, quarter_notes, avg_similarity))

        # Report on significant temporal clusters
        if len(significant_clusters) >= 2:
            # Compare two different periods
            significant_clusters.sort(key=lambda x: x[2], reverse=True)
            cluster1_label, cluster1_notes, cluster1_sim = significant_clusters[0]
            cluster2_label, cluster2_notes, cluster2_sim = significant_clusters[1]

            sample1 = vault.sample(cluster1_notes, k=3)
            sample2 = vault.sample(cluster2_notes, k=3)

            names1 = ", ".join([f"[[{n.title}]]" for n in sample1])
            names2 = ", ".join([f"[[{n.title}]]" for n in sample2])

            text = (
                f"Your {cluster1_label} notes form a distinct semantic cluster "
                f"(including {names1}) separate from your {cluster2_label} notes "
                f"({names2}). Different intellectual seasons?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[n.title for n in sample1 + sample2],
                    geist_id="temporal_clustering",
                )
            )

    except Exception:
        return []

    return vault.sample(suggestions, k=2)
