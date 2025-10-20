"""Example geist: Suggest exploring semantically similar notes."""

from geistfabrik import Suggestion


def suggest(vault):
    """Find semantically similar notes to explore connections."""
    notes = vault.sample(vault.notes(), k=1)
    if not notes:
        return []

    note = notes[0]
    neighbors = vault.neighbors(note, k=3)

    suggestions = []
    for neighbor in neighbors:
        text = f"[[{note.title}]] and [[{neighbor.title}]] seem related. What's the connection?"
        suggestions.append(
            Suggestion(text=text, notes=[note.title, neighbor.title], geist_id="semantic_neighbors")
        )

    return suggestions
