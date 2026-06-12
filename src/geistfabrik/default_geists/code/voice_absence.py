"""Voice absence geist - identifies missing voices in the vault.

A reflective lens over what is NOT written: a vault with no future-
focused notes, no "we" notes, or almost no questions reveals a voice
you never use. This geist counts linguistic registers across the whole
vault and names one that is conspicuously absent.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Identify missing linguistic patterns in the vault.

    Requires at least 20 notes for the proportions to be meaningful.
    Several absences may apply; one is picked deterministically so the
    session is reproducible.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion naming an absent voice (with notes=[])
    """
    orientations = {"past": 0, "present": 0, "future": 0, "mixed": 0}
    has_we = 0
    has_questions = 0
    total = 0

    for note in vault.notes_excluding_journal():
        voice = vault.voice(note)
        total += 1

        orientation = voice.temporal_orientation
        orientations[orientation] += 1

        if voice.first_person_plural > 1.0:
            has_we += 1

        if voice.question_density > 0.5:
            has_questions += 1

    if total < 20:
        return []

    suggestions = []

    # Check for missing temporal orientations
    if orientations["future"] < total * 0.05:
        suggestions.append(
            Suggestion(
                text=(
                    f"Only {orientations['future']} of your {total} notes look forward. "
                    f"What are you anticipating that you haven't written about?"
                ),
                notes=[],
                geist_id="voice_absence",
            )
        )

    if orientations["past"] < total * 0.05:
        suggestions.append(
            Suggestion(
                text=(
                    f"Only {orientations['past']} of your {total} notes look backward. "
                    f"What from your past haven't you processed on paper?"
                ),
                notes=[],
                geist_id="voice_absence",
            )
        )

    # Check for missing "we"
    if has_we < total * 0.05:
        suggestions.append(
            Suggestion(
                text=(
                    f"Only {has_we} of your {total} notes say 'we'. "
                    f"Who could you be thinking with?"
                ),
                notes=[],
                geist_id="voice_absence",
            )
        )

    # Check for missing questions
    if has_questions < total * 0.1:
        suggestions.append(
            Suggestion(
                text=(
                    f"Only {has_questions} of your {total} notes contain questions. "
                    f"What aren't you asking?"
                ),
                notes=[],
                geist_id="voice_absence",
            )
        )

    if not suggestions:
        return []

    # Return at most one, picked deterministically
    return vault.sample(suggestions, 1)
