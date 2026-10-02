"""Antithesis Generator geist - generates contrarian viewpoints to existing notes.

For each note, suggests creating an antithesis that challenges or inverts its claims,
fostering dialectical thinking.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Suggest antithetical perspectives for notes.

    Returns:
        List of suggestions for contrarian viewpoints
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    if len(notes) < 10:
        return []

    # Cheap filter for notes that assert things (word presence, not stance)
    claim_indicators = [
        "is",
        "are",
        "must",
        "should",
        "always",
        "never",
        "will",
        "cannot",
        "impossible",
        "necessary",
        "essential",
        "fundamental",
        "critical",
        "key",
        "important",
        "proves",
    ]

    # OPTIMISATION: Early termination after finding enough suggestions
    # Final sampling only returns 2, so generating 5 is sufficient
    max_suggestions = 5
    suggestion_count = 0

    for note in vault.sample(notes, min(30, len(notes))):
        # Early exit if we have enough suggestions
        if suggestion_count >= max_suggestions:
            break
        content = vault.read(note).lower()

        # Count claim indicators
        claim_strength = sum(1 for indicator in claim_indicators if indicator in content)

        if claim_strength < 3:
            continue

        # The indicator count is a cheap "this note asserts things" filter, not
        # a measure of stance, so the text invites an antithesis without
        # claiming that one exists or that the claims are unusually strong.
        # (A "seems to challenge" branch and a "dialectically opposed"
        # synthesis pass were removed: their negation-word test matched almost
        # every neighbour, so they named arbitrary pairs.)
        text = (
            f"What if you wrote the antithesis of [[{note.link_text}]]—a note that "
            f"systematically challenges each of its claims? What would the opposite "
            f"perspective argue?"
        )

        # Generate a suggested title for the antithesis
        if "the" not in note.title.lower():
            antithesis_title = f"Anti-{note.title}"
        else:
            antithesis_title = f"Against {note.title}"

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.link_text],
                geist_id="antithesis_generator",
                title=antithesis_title,
            )
        )
        suggestion_count += 1

    return vault.sample(suggestions, count=2)
