"""Question generator geist - turns statements into questions.

Finds declarative notes and suggests reframing them as questions to encourage
deeper exploration.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


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

        # Look for declarative titles that could be questions
        metadata = vault.metadata(note)
        word_count = metadata.get("word_count", 0)

        # Target notes that are developed enough to ask questions about
        if word_count > 50:
            # Generate question suggestions based on note title
            title = note.title

            question_frames = [
                f"Why is {title}?",
                f"How does {title} work?",
                f"What if {title} is wrong?",
                f"When does {title} apply?",
                f"Who benefits from {title}?",
            ]

            # Pick one question frame
            question = vault.sample(question_frames, k=1)[0]

            text = (
                f'What if you reframed [[{title}]] as a question: "{question}"? '
                f"Questions invite exploration where statements invite acceptance."
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[title],
                    geist_id="question_generator",
                    title=question,
                )
            )

    return vault.sample(suggestions, k=3)
