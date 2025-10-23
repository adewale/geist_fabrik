"""Example geist: Suggest exploring semantically similar notes."""

from geistfabrik import Suggestion


def suggest(vault):
    """Find semantically similar notes to explore connections."""
    notes = vault.sample(vault.notes(), k=1)
    if not notes:
        return []

    note = notes[0]
    neighbours = vault.neighbours(note, k=3)

    suggestions = []
    for neighbour in neighbours:
        text = f"[[{note.title}]] and [[{neighbour.title}]] seem related. What's the connection?"
        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.title, neighbour.title],
                geist_id="semantic_neighbors",
            )
        )

    return suggestions
