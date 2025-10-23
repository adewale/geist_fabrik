"""Dialectic Triad - Create Hegelian thesis-antithesis-synthesis provocations.

This geist finds a note (thesis), its semantic opposite (antithesis),
and suggests synthesizing them into something new. Inspired by Hegelian
dialectics, it encourages exploring the tension between opposing ideas.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import VaultContext

from geistfabrik import Suggestion


def suggest(vault: "VaultContext") -> list[Suggestion]:
    """Create dialectic thesis-antithesis-synthesis suggestions.

    Args:
        vault: VaultContext with access to vault data

    Returns:
        List of dialectic triad suggestions
    """
    suggestions = []

    # Sample some notes to use as thesis
    candidate_notes = vault.sample(vault.notes(), min(5, len(vault.notes())))

    for note in candidate_notes[:2]:  # Create up to 2 triads
        # Find the most contrarian note (antithesis) - returns List[str]
        contrarian_titles = vault.call_function("contrarian_to", note.title, 1)

        if not contrarian_titles:
            continue

        antithesis_title = contrarian_titles[0]

        # Create dialectic suggestion
        text = (
            f"**Thesis**: [[{note.title}]]\n"
            f"**Antithesis**: [[{antithesis_title}]]\n"
            f"\nWhat if you synthesized both into a new note? "
            f"What emerges when you hold these opposites together?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.title, antithesis_title],
                geist_id="dialectic_triad",
            )
        )

    return suggestions
