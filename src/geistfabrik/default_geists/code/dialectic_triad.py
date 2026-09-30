"""Dialectic Triad - Create Hegelian thesis-antithesis-synthesis provocations.

This geist finds a note (thesis), its semantic opposite (antithesis),
and suggests synthesizing them into something new. Inspired by Hegelian
dialectics, it encourages exploring the tension between opposing ideas.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Note, VaultContext

from geistfabrik import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Create dialectic thesis-antithesis-synthesis suggestions.

    Args:
        vault: VaultContext with access to vault data

    Returns:
        List of dialectic triad suggestions
    """
    suggestions = []

    # Sample some notes to use as thesis (session journal output is not a thesis)
    all_notes = vault.notes_excluding_journal()
    candidate_notes = vault.sample(all_notes, min(5, len(all_notes)))

    for note in candidate_notes[:2]:  # Create up to 2 triads
        # Find the most contrarian non-journal note (antithesis). contrarian_to
        # returns bracketed links ("[[Title]]"), so resolve them to notes and
        # render with link_text - interpolating the raw link produced
        # "[[[[Title]]]]". Over-fetch so journal notes cannot use up the list.
        antithesis: Note | None = None
        for link in vault.call_function("contrarian_to", note.title, 10):
            candidate = vault.resolve_link_target(link.strip("[]"))
            if candidate is not None and not candidate.path.startswith("geist journal/"):
                antithesis = candidate
                break

        if antithesis is None:
            continue

        # Create dialectic suggestion
        text = (
            f"**Thesis**: [[{note.link_text}]]\n"
            f"**Antithesis**: [[{antithesis.link_text}]]\n"
            f"\nWhat if you synthesized both into a new note? "
            f"What emerges when you hold these opposites together?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.link_text, antithesis.link_text],
                geist_id="dialectic_triad",
            )
        )

    return suggestions
