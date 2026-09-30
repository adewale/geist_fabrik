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
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []

    # The most recently modified notes. Geist journal session notes are
    # output, not work: filter them before ranking, or accumulated session
    # notes crowd every user note out of the window.
    ranked = sorted(vault.notes_excluding_journal(), key=lambda n: n.modified, reverse=True)
    # A note untouched for more than 60 days is "older", never "recent work"
    # (ranked is newest first, so filtering the top 5 is enough).
    recent = [n for n in ranked[:5] if vault.metadata(n)["days_since_modified"] <= 60]

    if len(recent) < 2:
        return []

    # For each recent note, find old notes that are similar
    for recent_note in recent[:3]:  # Just check top 3
        # Nearest neighbours come back even when nothing is close; the
        # suggestion claims similarity, so require at least a weak match.
        similar = vault.neighbours(recent_note, count=10, return_scores=True)

        # Filter to only old notes (not modified recently)
        old_similar = []
        for note, score in similar:
            if note.path.startswith("geist journal/") or score < SimilarityLevel.WEAK:
                continue
            metadata = vault.metadata(note)
            days_since_modified = metadata.get("days_since_modified", 0)

            if days_since_modified > 60:  # Not touched in 2 months
                old_similar.append(note)

        if old_similar:
            old_note = old_similar[0]  # Pick the most similar old note

            text = (
                f"What if your recent work on [[{recent_note.link_text}]] "
                f"connects to your older note [[{old_note.link_text}]]? "
                f"They're semantically similar - has your thinking evolved?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[recent_note.link_text, old_note.link_text],
                    geist_id="recent_focus",
                )
            )

    return suggestions[:3]
