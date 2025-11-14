"""Divergent Evolution geist - finds linked notes growing semantically apart.

Identifies notes that are linked but whose embeddings have been diverging across
sessions, suggesting old connections that may no longer hold.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find linked notes whose understanding is diverging across sessions.

    Uses TemporalPatternFinder to identify diverging pairs from linked notes,
    suggesting connections that may have become outdated.

    Returns:
        List of suggestions showing divergent development
    """
    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import (
        EmbeddingTrajectoryCalculator,
        TemporalPatternFinder,
    )

    # Find linked note pairs
    notes = vault.notes()
    linked_pairs = []

    for note in vault.sample(notes, min(30, len(notes))):
        for target_note in vault.outgoing_links(note)[:5]:  # Check first 5 links
            linked_pairs.append((note, target_note))

    if len(linked_pairs) < 2:
        return []

    # Sample pairs to check (limit to 50 as original did)
    sampled_pairs = vault.sample(linked_pairs, min(50, len(linked_pairs)))

    # Find diverging pairs using TemporalPatternFinder
    finder = TemporalPatternFinder(vault)
    diverging = finder.find_diverging_pairs(sampled_pairs, threshold=0.15)

    if not diverging:
        return []

    suggestions = []
    for note_a, note_b in diverging:
        # Get session count for context
        calc = EmbeddingTrajectoryCalculator(vault, note_a)
        session_count = len(calc.snapshots())

        if session_count < 3:
            continue

        text = (
            f"[[{note_a.obsidian_link}]] and [[{note_b.obsidian_link}]] are linked, "
            f"but they've been semantically diverging across your last "
            f"{session_count} sessions. They were similar when connected "
            f"but have drifted apart—does the link still make sense?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note_a.obsidian_link, note_b.obsidian_link],
                geist_id="divergent_evolution",
            )
        )

    return vault.sample(suggestions, k=2)
