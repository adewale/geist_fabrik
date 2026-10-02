"""Convergent Evolution geist - finds note vectors becoming more similar.

Identifies unlinked note pairs whose measured semantic similarity increased
across recorded sessions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find note pairs whose semantic similarity increased across sessions.

    Uses TemporalPatternFinder to identify pairs with increasing similarity
    (trend and net change), then keeps unlinked pairs that are at least
    weakly similar now.

    Returns:
        List of suggestions reporting increased measured similarity
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel
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
        # Only unlinked pairs: a link is what the suggestion invites
        if vault.links_between(note_a, note_b):
            continue

        # Similarities over the sessions both notes share; the last is now
        similarities = EmbeddingTrajectoryCalculator(vault, note_a).similarity_with_trajectory(
            EmbeddingTrajectoryCalculator(vault, note_b)
        )
        session_count = len(similarities)

        if session_count < 3:
            continue

        # "Became more similar" must hold today, not just at a past peak
        if similarities[-1] < SimilarityLevel.WEAK:
            continue

        text = (
            f"The stored semantic representations for [[{note_a.link_text}]] and "
            f"[[{note_b.link_text}]] became more similar across {session_count} "
            f"recorded sessions. Does inspecting the notes reveal a useful link?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note_a.link_text, note_b.link_text],
                geist_id="convergent_evolution",
            )
        )

    return vault.sample(suggestions, count=2)
