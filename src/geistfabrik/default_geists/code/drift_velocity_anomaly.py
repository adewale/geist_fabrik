"""Drift Velocity Anomaly geist - detects notes whose drift suddenly accelerates.

Demonstrates the power of temporal_analysis.py abstractions. Uses
EmbeddingTrajectoryCalculator to detect notes whose drift rate increases
over time, potentially indicating conceptual breakthroughs or shifts.

This geist showcases how trajectory analysis enables complex temporal patterns
with minimal code (contrast with concept_drift.py's 60+ lines).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Detect notes whose drift rate is accelerating over sessions.

    Returns:
        List of 1-2 suggestions showing accelerating drift patterns
    """
    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import EmbeddingTrajectoryCalculator

    # Need multiple sessions for acceleration detection
    cursor = vault.db.execute("SELECT COUNT(*) FROM sessions")
    session_count = cursor.fetchone()[0]

    if session_count < 5:  # Need at least 5 sessions for windowed analysis
        return []

    notes = vault.notes()
    suggestions = []

    # Sample notes to check for acceleration
    for note in vault.sample(notes, min(30, len(notes))):
        calc = EmbeddingTrajectoryCalculator(vault, note)

        # Need enough snapshots for acceleration detection
        if len(calc.snapshots()) < 5:
            continue

        # Check if drift is accelerating
        if calc.is_accelerating(threshold=0.1):
            # Get drift metrics
            drift_rates = calc.windowed_drift_rates(window_size=3)

            if drift_rates:
                initial_rate = drift_rates[0]
                final_rate = drift_rates[-1]

                # Find what it's drifting toward
                neighbors = vault.neighbours(note, k=5)

                # Find most aligned neighbor by checking drift toward current neighbors
                best_neighbor = None
                best_similarity = -1.0

                # Simple heuristic: neighbor most similar to current embedding
                # is likely in drift direction
                for neighbor in neighbors:
                    if neighbor.path == note.path:
                        continue
                    sim = vault.similarity(note, neighbor)
                    if sim > best_similarity:
                        best_similarity = sim
                        best_neighbor = neighbor

                if best_neighbor and best_similarity > 0.5:
                    text = (
                        f"[[{note.obsidian_link}]] shows accelerating drift "
                        f"(velocity: {initial_rate:.2f} → {final_rate:.2f}). "
                        f"Rapidly evolving toward [[{best_neighbor.obsidian_link}]]—"
                        f"conceptual breakthrough?"
                    )

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[note.obsidian_link, best_neighbor.obsidian_link],
                            geist_id="drift_velocity_anomaly",
                        )
                    )

    # Return top 2 anomalies
    return vault.sample(suggestions, k=min(2, len(suggestions)))
