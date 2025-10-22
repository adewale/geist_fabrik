"""Assumption Challenger geist - identifies implicit assumptions in notes.

Looks for notes that make claims based on assumptions that might be questioned,
then suggests examining those assumptions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with questionable assumptions.

    Returns:
        List of suggestions challenging assumptions
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    if len(notes) < 10:
        return []

    # Assumption indicator phrases
    assumption_phrases = [
        "obviously", "clearly", "of course", "everyone knows",
        "it is well known", "naturally", "needless to say",
        "without a doubt", "certainly", "undoubtedly",
        "must be", "has to", "necessarily", "always",
    ]

    for note in vault.sample(notes, min(40, len(notes))):
        content = vault.read(note).lower()

        # Look for assumption indicators
        assumption_count = sum(1 for phrase in assumption_phrases if phrase in content)

        if assumption_count >= 2:
            # Find related notes that might challenge these assumptions
            similar = vault.neighbours(note, k=10)

            # Look for notes with contrasting language (hedging, uncertainty)
            contrast_phrases = [
                "maybe", "perhaps", "might", "could be",
                "possibly", "uncertain", "unclear", "debatable",
                "questionable", "depends", "varies", "sometimes",
            ]

            for other in similar:
                other_content = vault.read(other).lower()
                contrast_count = sum(1 for phrase in contrast_phrases if phrase in other_content)

                if contrast_count >= 2:
                    # High assumptions in one note, high uncertainty in similar note
                    text = (
                        f"[[{note.title}]] makes claims that seem certain, "
                        f"but [[{other.title}]] (semantically similar) expresses uncertainty "
                        f"about related topics. What assumptions underlie the certainty?"
                    )

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[note.title, other.title],
                            geist_id="assumption_challenger",
                        )
                    )
                    break

        # Also look for causal claims without evidence
        causal_patterns = [
            "because", "therefore", "thus", "hence",
            "leads to", "results in", "causes", "due to",
        ]

        causal_count = sum(1 for pattern in causal_patterns if pattern in content)

        if causal_count >= 3 and len(note.links) < 2:
            # Makes causal claims but doesn't link to supporting evidence
            text = (
                f"[[{note.title}]] makes causal claims but has few links to supporting notes. "
                f"What evidence or reasoning supports these cause-effect relationships?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.title],
                    geist_id="assumption_challenger",
                )
            )

    return vault.sample(suggestions, k=3)
