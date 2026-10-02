"""Voice absence geist - identifies missing voices in the vault.

A reflective lens over what is NOT written: a vault that almost never
uses the future tense or almost never asks a question reveals a voice you
never use. This geist counts linguistic
registers across the whole vault and names one that is conspicuously
absent. (The missing "we" voice is self_and_other's question.)

Each count is exactly what its sentence says: "use the future tense"
counts notes with any future marker (will/shall/won't/going to/gonna),
and "contain questions" counts notes with any question mark outside code.
There is no "looks backward" check: the past orientation (more than 60% of
detected verbs ending in -ed and the like) counts status tables and
"used"/"enabled" as retrospection, so a count of it would not mean what the
sentence says.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.models import Note
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def _verb(count: int, verb: str) -> str:
    """Agree a present-tense verb with its count ("1 note uses", "3 notes use")."""
    return f"{verb}s" if count == 1 else verb


def _named(notes: list["Note"]) -> str:
    """Wikilinks for up to two notes, joined with "and"."""
    return " and ".join(f"[[{note.link_text}]]" for note in notes)


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Identify missing linguistic patterns in the vault.

    Requires at least 20 notes for the proportions to be meaningful.
    Several absences may apply; one is picked deterministically so the
    session is reproducible.

    Every suggestion names notes, because the quality filter drops a
    suggestion that names none: the few notes that do use the voice, or,
    when none does, one recently changed note to start from.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion naming an absent voice
    """
    future_notes: list[Note] = []
    question_notes: list[Note] = []
    total = 0

    for note in vault.notes():
        voice = vault.voice(note)
        total += 1

        # Any future marker (will/shall/won't/going to/gonna). The "future"
        # orientation needs > 40% of detected verbs to be future, which
        # almost no real note reaches, so counting it made "look forward"
        # fire on nearly every vault.
        if voice.future_tense_ratio > 0:
            future_notes.append(note)

        if voice.question_density > 0:
            question_notes.append(note)

    if total < 20:
        return []

    recent = vault.recent_notes(count=5)
    suggestions = []

    # Check for a missing future tense
    if len(future_notes) < total * 0.05:
        count = len(future_notes)
        if future_notes:
            named = vault.sample(future_notes, min(2, count))
            text = (
                f"Only {count} of your {total} notes {_verb(count, 'use')} the future "
                f"tense ('will', 'going to'), among them {_named(named)}. "
                f"What are you anticipating that you haven't written about?"
            )
        elif recent:
            named = vault.sample(recent, 1)
            text = (
                f"None of your {total} notes use the future tense ('will', 'going to'). "
                f"What is {_named(named)} anticipating that it doesn't say?"
            )
        else:
            named = []
        if named:
            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text for note in named],
                    geist_id="voice_absence",
                )
            )

    # Check for missing questions
    if len(question_notes) < total * 0.1:
        count = len(question_notes)
        if question_notes:
            named = vault.sample(question_notes, min(2, count))
            text = (
                f"Only {count} of your {total} notes {_verb(count, 'contain')} "
                f"questions, among them {_named(named)}. What aren't you asking?"
            )
        elif recent:
            named = vault.sample(recent, 1)
            text = (
                f"None of your {total} notes contain questions. "
                f"What question is {_named(named)} answering?"
            )
        else:
            named = []
        if named:
            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text for note in named],
                    geist_id="voice_absence",
                )
            )

    if not suggestions:
        return []

    # Return at most one, picked deterministically
    return vault.sample(suggestions, 1)
