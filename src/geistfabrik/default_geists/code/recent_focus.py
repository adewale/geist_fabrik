"""Recent focus geist - identifies what you've been thinking about lately.

Analyses recently modified notes to surface patterns in your current interests
and suggests related older notes you might want to revisit.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Identify recent focus areas and suggest connections.

    Returns:
        List of suggestions based on recent activity
    """
    from geistfabrik import Suggestion

    suggestions = []

    # Get recently modified notes
    recent = vault.recent_notes(k=5)

    if len(recent) < 2:
        return []

    # For each recent note, find old notes that are similar
    for recent_note in recent[:3]:  # Just check top 3
        # Find semantically similar notes
        similar = vault.neighbours(recent_note, k=10)

        # Filter to only old notes (not modified recently)
        old_similar = []
        for note in similar:
            metadata = vault.metadata(note)
            days_since_modified = metadata.get("days_since_modified", 0)

            if days_since_modified > 60:  # Not touched in 2 months
                old_similar.append(note)

        if old_similar:
            old_note = old_similar[0]  # Pick the most similar old note

            text = (
                f"What if your recent work on [[{recent_note.title}]] "
                f"connects to your older note [[{old_note.title}]]? "
                f"They're semantically similar - has your thinking evolved?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[recent_note.title, old_note.title],
                    geist_id="recent_focus",
                )
            )

    return suggestions[:3]
