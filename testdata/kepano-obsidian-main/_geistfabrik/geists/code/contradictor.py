"""Contradictor geist: Suggests the opposite of existing note titles."""

from geistfabrik import Suggestion


def suggest(vault):
    """Suggest creating notes with opposite/contradictory titles.

    This geist picks a random note and suggests creating a note
    with the opposite concept, encouraging dialectical thinking.
    """
    # Get a random note
    random_notes = vault.random_notes(k=1)

    if not random_notes:
        return []

    note = random_notes[0]
    title = note.title

    # Generate opposite suggestion
    # This is a simple implementation - could be enhanced with NLP/LLMs
    opposite = _generate_opposite(title)

    text = f"[[{title}]] exists - what about '{opposite}'?"

    return [
        Suggestion(
            text=text,
            notes=[title],
            geist_id="contradictor",
            title=opposite
        )
    ]


def _generate_opposite(title: str) -> str:
    """Generate an opposite/contradictory version of a title.

    This is a simple heuristic-based approach. For production use,
    you might want to use an LLM or more sophisticated NLP.

    Args:
        title: The original note title

    Returns:
        A suggested opposite title
    """
    # Common patterns to flip
    replacements = {
        # Positive/Negative
        "benefits of": "costs of",
        "advantages of": "disadvantages of",
        "pros of": "cons of",
        "success": "failure",
        "winning": "losing",
        "growth": "decline",
        "rise of": "fall of",

        # Modality
        "how to": "how not to",
        "why you should": "why you shouldn't",
        "always": "never",
        "everything": "nothing",

        # Direction
        "up": "down",
        "increase": "decrease",
        "more": "less",
        "faster": "slower",
        "better": "worse",

        # Temporal
        "past": "future",
        "old": "new",
        "traditional": "modern",
        "ancient": "contemporary",

        # Scale
        "macro": "micro",
        "big": "small",
        "large": "small",
        "maximum": "minimum",

        # Truth/Knowledge
        "truth": "myth",
        "fact": "fiction",
        "known": "unknown",
        "certain": "uncertain",
    }

    # Try to find and replace patterns
    title_lower = title.lower()

    for pattern, opposite in replacements.items():
        if pattern in title_lower:
            # Replace while preserving case
            return title.replace(pattern, opposite).replace(pattern.title(), opposite.title())

    # If no pattern matches, use general contradiction patterns
    if title.startswith("The "):
        return f"The opposite of {title[4:]}"
    elif title.startswith("A "):
        return f"The opposite of {title[2:]}"
    else:
        return f"The opposite of {title}"
