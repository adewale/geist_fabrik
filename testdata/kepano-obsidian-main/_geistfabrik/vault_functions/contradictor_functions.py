"""Vault functions for the Contradictor geist.

These functions enable Tracery-based geists to work with note titles
and generate opposites/contradictions.
"""

from geistfabrik import vault_function


@vault_function("random_note_title")
def random_note_title(vault):
    """Get a random note title.

    Returns:
        The title of a random note from the vault
    """
    random_notes = vault.random_notes(k=1)
    if not random_notes:
        return "untitled"
    return random_notes[0].title


@vault_function("opposite_of")
def opposite_of(vault, title):
    """Generate an opposite/contradictory version of a title.

    This uses simple heuristic-based pattern matching to generate
    opposites. For more sophisticated results, consider using an LLM.

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
