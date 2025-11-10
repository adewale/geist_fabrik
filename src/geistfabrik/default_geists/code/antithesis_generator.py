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

    # Look for notes that make strong claims
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

        # Check if an antithesis note already exists
        # Look for semantically opposite notes
        similar = vault.neighbours(note, k=20)

        # Look for negation words in similar notes
        negation_words = ["not", "no", "never", "contra", "anti", "against", "opposite", "reverse"]

        antithesis_candidates = []
        for other in similar:
            other_content = vault.read(other).lower()
            negation_count = sum(1 for word in negation_words if word in other_content)

            # Also check title for opposition
            if "anti" in other.title.lower() or "contra" in other.title.lower():
                negation_count += 2

            if negation_count >= 2:
                antithesis_candidates.append(other)

        if antithesis_candidates:
            # Suggest strengthening the existing antithesis
            antithesis = vault.sample(antithesis_candidates, k=1)[0]

            text = (
                f"[[{note.obsidian_link}]] makes strong claims. "
                f"[[{antithesis.obsidian_link}]] seems to challenge it—what if you "
                f"developed this into a full dialectical pair? Thesis vs. antithesis?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link, antithesis.obsidian_link],
                    geist_id="antithesis_generator",
                )
            )
            suggestion_count += 1
        else:
            # Suggest creating an antithesis
            text = (
                f"[[{note.obsidian_link}]] makes strong claims. "
                f"What if you wrote its antithesis—a note that systematically "
                f"challenges each claim? What would the opposite perspective argue?"
            )

            # Generate a suggested title for the antithesis
            if "the" not in note.title.lower():
                antithesis_title = f"Anti-{note.title}"
            else:
                antithesis_title = f"Against {note.title}"

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link],
                    geist_id="antithesis_generator",
                    title=antithesis_title,
                )
            )
            suggestion_count += 1

    # Also look for dialectical triads (thesis + antithesis without synthesis)
    for note in vault.sample(notes, min(20, len(notes))):
        # Early exit if we have enough suggestions
        if suggestion_count >= max_suggestions:
            break
        # Find potential antithesis (OP-9: get scores to avoid recomputation)
        similar_with_scores = vault.neighbours(note, k=10, return_scores=True)

        for other, similarity in similar_with_scores:
            # Check if they seem opposed (already have similarity from neighbours)
            if similarity > 0.5:  # Related but not too similar
                note_content = vault.read(note).lower()
                other_content = vault.read(other).lower()

                # Look for opposition markers
                note_positive = sum(1 for w in ["yes", "always", "must", "is"] if w in note_content)
                other_negative = sum(
                    1 for w in ["no", "never", "not", "isn't"] if w in other_content
                )

                if note_positive >= 2 and other_negative >= 2:
                    # Potential thesis/antithesis pair - suggest synthesis
                    text = (
                        f"[[{note.obsidian_link}]] and [[{other.obsidian_link}]] seem "
                        f"dialectically opposed. What would their synthesis be? What "
                        f"higher-level perspective reconciles them?"
                    )

                    synthesis_title = f"Synthesis: {note.title} + {other.title}"

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[note.obsidian_link, other.obsidian_link],
                            geist_id="antithesis_generator",
                            title=synthesis_title,
                        )
                    )
                    suggestion_count += 1

    return vault.sample(suggestions, k=2)
