"""Cluster Evolution Tracker geist.

Demonstrates ClusterAnalyser abstraction (Phase 3).
Tracks how notes move between clusters over time by comparing current
clusters with historical cluster assignments.
"""

from collections import Counter
from typing import TYPE_CHECKING

from geistfabrik.clustering_analysis import ClusterAnalyser
from geistfabrik.models import Suggestion

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes that have migrated between clusters over time.

    Uses ClusterAnalyser with session-scoped caching to efficiently compute
    current clusters, then compares with historical session data to find
    notes with shifting conceptual neighbourhoods.
    """
    notes = vault.notes()

    if len(notes) < 15:
        return []

    # Get previous sessions via VaultContext abstraction
    session_ids = vault.recent_session_ids(count=3)

    if len(session_ids) < 2:
        return []

    # Initialize cluster analyser (benefits from session-scoped cache)
    analyser = ClusterAnalyser(vault)

    # Get current clusters (cached for this session)
    current_clusters = analyser.get_clusters()
    if len(current_clusters) < 2:
        return []

    # Build a map of notes to their current cluster labels
    current_assignments: dict[str, str] = {}
    for cluster in current_clusters.values():
        for note in cluster.notes:
            current_assignments[note.path] = cluster.label

    # Previous-session labels for the currently clustered notes. Labels are
    # c-TF-IDF keywords recomputed from membership, so the SAME cluster gets a
    # different label string whenever any note joins or leaves it. Comparing
    # label strings would report every member of a cluster that merely gained
    # a note; match clusters across sessions by membership instead.
    prev_session_id = session_ids[1]  # Second most recent
    previous_assignments: dict[str, str] = {}
    for note in notes:
        if note.path in current_assignments:
            prev_label = vault.previous_cluster_label_for_note(note, prev_session_id)
            if prev_label and prev_label != "Noise":
                previous_assignments[note.path] = prev_label

    # Each previous cluster continues as the current cluster holding most of
    # its (still clustered) members; ties resolve by label for determinism.
    successor_votes: dict[str, Counter[str]] = {}
    for path, prev_label in previous_assignments.items():
        successor_votes.setdefault(prev_label, Counter())[current_assignments[path]] += 1
    successor = {
        prev_label: min(votes.items(), key=lambda item: (-item[1], item[0]))[0]
        for prev_label, votes in successor_votes.items()
    }

    suggestions = []

    # A note migrated when it is not in its previous cluster's successor
    for note in notes:
        prev_label = previous_assignments.get(note.path)
        if prev_label is None:
            continue

        current_label = current_assignments[note.path]
        # A note whose label string is unchanged did not visibly move, even if
        # most of its old cluster went elsewhere.
        if current_label != successor[prev_label] and current_label != prev_label:
            suggestions.append(
                Suggestion(
                    text=(
                        f"[[{note.link_text}]] migrated from "
                        f"'{prev_label}' cluster to '{current_label}' cluster. "
                        f"What conceptual shift occurred?"
                    ),
                    notes=[note.link_text],
                    geist_id="cluster_evolution_tracker",
                )
            )

            if len(suggestions) >= 3:
                break

    # Return up to 2 suggestions
    return vault.sample(suggestions, count=min(2, len(suggestions)))
