"""Question generator geist - turns statements into questions.

Takes developed notes whose titles are not already questions and suggests
reframing them as questions to encourage deeper exploration.

The title is quoted inside each question frame, because a title is usually a
noun phrase ("Emotion Regulation, Creativity, and Cultural Research") and the
frames must stay grammatical whatever it is. Date-titled notes (daily notes
and date-collection entries) are skipped: "Who benefits from 2023-09-12?" is
not a question about an idea.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

_DATE_TITLE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Suggest reframing notes as questions.

    Returns:
        List of suggestions for question-based reframing
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    for note in notes:
        # Skip notes that are already questions
        if note.title.endswith("?"):
            continue

        # Skip date-titled notes: daily notes, date-collection entries (whose
        # title is the date heading, in any format) and titles with no words
        if (
            note.is_virtual
            or _DATE_TITLE.match(note.title)
            or not re.search(r"[^\W\d_]", note.title)
        ):
            continue

        # Look for declarative titles that could be questions
        metadata = vault.metadata(note)
        word_count = metadata.get("word_count", 0)

        # Target notes that are developed enough to ask questions about
        if word_count > 50:
            # Generate question suggestions based on note title
            title = note.title

            # Curly quotes: grammatical around any title, distinct from the
            # straight quotes around the whole question, and valid in a note
            # name (the question is also the suggested title).
            quoted = f"\u201c{title}\u201d"
            question_frames = [
                f"How does {quoted} work?",
                f"What if {quoted} is wrong?",
                f"When does {quoted} not apply?",
                f"Who benefits from {quoted}?",
                f"What question is {quoted} an answer to?",
            ]

            # Pick one question frame
            question = vault.sample(question_frames, count=1)[0]

            # link_text, not title: a date-collection entry's title is its
            # heading, which is not a linkable note name on its own.
            text = f'What if you reframed [[{note.link_text}]] as a question: "{question}"'

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text],
                    geist_id="question_generator",
                    title=question,
                )
            )

    return vault.sample(suggestions, count=3)
