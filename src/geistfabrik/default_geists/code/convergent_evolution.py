"""Convergent Evolution geist - finds notes developing toward each other.

Identifies pairs of notes whose embeddings have been converging across sessions,
suggesting ideas that are independently developing in the same direction.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes whose understanding is converging across sessions.

    Uses TemporalPatternFinder to identify converging pairs, then filters
    for unlinked notes that are developing in the same direction.

    Returns:
        List of suggestions showing convergent development
    """
    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import (
        EmbeddingTrajectoryCalculator,
        TemporalPatternFinder,
    )

    notes = vault.notes()

    if len(notes) < 10:
        return []

    # Generate candidate pairs from sampled notes
    sample_notes = vault.sample(notes, min(30, len(notes)))
    pairs = []
    for i, note_a in enumerate(sample_notes):
        for note_b in sample_notes[i + 1 :]:
            pairs.append((note_a, note_b))

    # Sample pairs to check (limit to 100 as original did)
    sampled_pairs = vault.sample(pairs, min(100, len(pairs)))

    # Find converging pairs using TemporalPatternFinder
    finder = TemporalPatternFinder(vault)
    converging = finder.find_converging_pairs(sampled_pairs, threshold=0.15)

    if not converging:
        return []

    suggestions = []
    for note_a, note_b in converging:
        # Check if they're currently similar but not linked
        if vault.links_between(note_a, note_b):
            continue

        # Get session count for context
        calc = EmbeddingTrajectoryCalculator(vault, note_a)
        session_count = len(calc.snapshots())

        if session_count < 3:
            continue

        text = (
            f"[[{note_a.obsidian_link}]] and "
            f"[[{note_b.obsidian_link}]] have been converging "
            f"semantically across your last {session_count} sessions. "
            f"Two ideas independently developing in the same direction—"
            f"time to link them?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note_a.obsidian_link, note_b.obsidian_link],
                geist_id="convergent_evolution",
            )
        )

    return vault.sample(suggestions, k=2)
