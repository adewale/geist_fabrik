"""Dialectic Triad - Create Hegelian thesis-antithesis-synthesis provocations.

This geist finds a note (thesis) and one of the notes least similar to it,
and invites reading the second as an antithesis and synthesizing them into
something new. Inspired by Hegelian dialectics.

Embedding similarity measures topic, not stance, so the distant note is not
claimed to *oppose* the thesis: the text only says it is far from it.
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
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []
    # One distant note per run: always taking the single least similar note
    # let a few global outliers be the "antithesis" of almost everything.
    used_antitheses: set[str] = set()

    # Sample some notes to use as thesis
    all_notes = vault.notes()
    candidate_notes = vault.sample(all_notes, min(5, len(all_notes)))

    for note in candidate_notes[:2]:  # Create up to 2 triads
        # contrarian_to returns bracketed links ("[[Title]]"), so resolve them
        # to notes and render with link_text - interpolating the raw link
        # produced "[[[[Title]]]]". Keep only genuinely distant notes.
        distant: list[Note] = []
        for link in vault.call_function("contrarian_to", note.title, 10):
            candidate = vault.resolve_link_target(link.strip("[]"))
            if (
                candidate is not None
                and candidate.path not in used_antitheses
                and vault.similarity(note, candidate) < SimilarityLevel.WEAK
            ):
                distant.append(candidate)

        if not distant:
            continue

        antithesis = vault.sample(distant, 1)[0]
        used_antitheses.add(antithesis.path)

        # Create dialectic suggestion
        text = (
            f"**Thesis**: [[{note.link_text}]]\n"
            f"**Far side**: [[{antithesis.link_text}]], one of the notes least like it\n"
            f"\nWhat if you read the second as an antithesis to the first? "
            f"What would a synthesis of the two look like?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.link_text, antithesis.link_text],
                geist_id="dialectic_triad",
            )
        )

    return suggestions
