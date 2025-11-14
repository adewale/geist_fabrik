"""Cluster Evolution Tracker geist.

Demonstrates ClusterAnalyser abstraction (Phase 3).
Tracks how notes move between clusters over time by comparing current
clusters with historical cluster assignments.
"""

from typing import TYPE_CHECKING

from geistfabrik.clustering_analysis import ClusterAnalyser
from geistfabrik.models import Suggestion

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes that have migrated between clusters over time.

    Uses ClusterAnalyser with session-scoped caching to efficiently compute
    current clusters, then compares with historical session data to find
    notes with shifting conceptual neighborhoods.
    """
    # Exclude geist journal to avoid tracking session output migrations
    notes = vault.notes_excluding_journal()

    if len(notes) < 15:
        return []

    # Get previous sessions from database
    cursor = vault.db.execute(
        """
        SELECT session_id FROM sessions
        ORDER BY date DESC
        LIMIT 3
        """,
    )
    session_rows = cursor.fetchall()

    if len(session_rows) < 2:
        return []

    # Initialize cluster analyser (benefits from session-scoped cache)
    analyser = ClusterAnalyser(vault, min_size=3)

    # Get current clusters (cached for this session)
    current_clusters = analyser.get_clusters()
    if len(current_clusters) < 2:
        return []

    # Build a map of notes to their current cluster labels
    current_assignments: dict[str, str] = {}
    for cluster in current_clusters.values():
        for note in cluster.notes:
            # Only track non-journal notes
            if not note.path.startswith("geist journal/"):
                current_assignments[note.path] = cluster.label

    suggestions = []

    # Check each note to see if it changed clusters
    for note in notes:
        if note.path not in current_assignments:
            continue

        current_label = current_assignments[note.path]

        # Check previous session assignments
        prev_session_id = session_rows[1][0]  # Second most recent
        prev_clusters = vault.db.execute(
            """
            SELECT cluster_id, cluster_label
            FROM session_embeddings
            WHERE session_id = ? AND note_path = ?
            """,
            (prev_session_id, note.path),
        ).fetchone()

        if prev_clusters and prev_clusters[1]:
            prev_label = prev_clusters[1]

            # Note migrated to a different cluster
            if prev_label != current_label and prev_label != "Noise":
                suggestions.append(
                    Suggestion(
                        text=(
                            f"[[{note.obsidian_link}]] migrated from "
                            f"'{prev_label}' cluster to '{current_label}' cluster. "
                            f"What conceptual shift occurred?"
                        ),
                        notes=[note.title],
                        geist_id="cluster_evolution_tracker",
                    )
                )

            if len(suggestions) >= 3:
                break

    # Return up to 2 suggestions
    return vault.sample(suggestions, k=min(2, len(suggestions)))
