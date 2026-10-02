"""Voice absence geist - identifies missing voices in the vault.

A reflective lens over what is NOT written: a vault that almost never
uses the future tense, rarely looks backward, or almost never asks a
question reveals a voice you never use. This geist counts linguistic
registers across the whole vault and names one that is conspicuously
absent. (The missing "we" voice is self_and_other's question.)

Each count is exactly what its sentence says: "use the future tense"
counts notes with any future marker (will/shall/won't/going to/gonna),
and "contain questions" counts notes with any question mark outside code.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def _verb(count: int, verb: str) -> str:
    """Agree a present-tense verb with its count ("1 note uses", "3 notes use")."""
    return f"{verb}s" if count == 1 else verb


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
    has_future = 0
    has_questions = 0
    total = 0

    for note in vault.notes():
        voice = vault.voice(note)
        total += 1

        orientation = voice.temporal_orientation
        orientations[orientation] += 1

        # Any future marker (will/shall/won't/going to/gonna). The "future"
        # orientation needs > 40% of detected verbs to be future, which
        # almost no real note reaches, so counting it made "look forward"
        # fire on nearly every vault.
        if voice.future_tense_ratio > 0:
            has_future += 1

        if voice.question_density > 0:
            has_questions += 1

    if total < 20:
        return []

    suggestions = []

    # Check for missing temporal orientations
    if has_future < total * 0.05:
        suggestions.append(
            Suggestion(
                text=(
                    f"Only {has_future} of your {total} notes {_verb(has_future, 'use')} "
                    f"the future tense ('will', 'going to'). "
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
                    f"Only {orientations['past']} of your {total} notes "
                    f"{_verb(orientations['past'], 'look')} backward. "
                    f"What from your past haven't you processed on paper?"
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
                    f"Only {has_questions} of your {total} notes "
                    f"{_verb(has_questions, 'contain')} questions. "
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
