"""Anachronism Detector geist - finds temporally displaced notes.

Identifies recent notes that semantically resemble older thinking, or old notes
that feel contemporary, suggesting cyclical thinking or ideas out of their time.
"""

from typing import TYPE_CHECKING

from geistfabrik.similarity_analysis import SimilarityLevel

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext
    from geistfabrik.models import Note


def _years_between(earlier: "Note", later: "Note") -> str:
    """Whole years between two notes' creation dates, at least 1, pluralised."""
    years = max(1, (later.created - earlier.created).days // 365)
    return f"{years} year{'s' if years != 1 else ''}"


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes that feel temporally displaced.

    Returns:
        List of suggestions highlighting temporal outliers
    """
    from datetime import timedelta

    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    if len(notes) < 30:
        return []

    # Session date, not wall-clock: keeps --date replays deterministic
    now = vault.session.date

    # Get recent notes (last 3 months, never after the session date)
    recent_cutoff = now - timedelta(days=90)
    recent_notes = [n for n in notes if recent_cutoff < n.created <= now]

    # Get old notes (more than 1 year ago)
    old_cutoff = now - timedelta(days=365)
    old_notes = [n for n in notes if n.created < old_cutoff]

    if len(recent_notes) < 5 or len(old_notes) < 5:
        return []

    # Find recent notes that are more similar to an old note than to ANY other
    # recent note (max vs max: a sample maximum always beats a sample mean)
    for recent_note in vault.sample(recent_notes, min(20, len(recent_notes))):
        # Compare to every other recent note, so "more than your current
        # thinking" is checked, not estimated
        recent_similarities = []
        for other_recent in recent_notes:
            if other_recent.path != recent_note.path:
                sim = vault.similarity(recent_note, other_recent)
                recent_similarities.append(sim)

        # Compare to old notes
        old_similarities = []
        old_matches = []
        for old_note in vault.sample(old_notes, min(10, len(old_notes))):
            sim = vault.similarity(recent_note, old_note)
            old_similarities.append(sim)
            old_matches.append((old_note, sim))

        if recent_similarities and old_similarities:
            max_recent_sim = max(recent_similarities)
            max_old_sim = max(old_similarities)

            # Recent note is more similar to old thinking than current thinking
            if max_old_sim > max_recent_sim and max_old_sim > SimilarityLevel.HIGH:
                best_old_match = max(old_matches, key=lambda x: x[1])
                old_note, similarity = best_old_match

                text = (
                    f"[[{recent_note.link_text}]] (written recently) semantically resembles "
                    f"[[{old_note.link_text}]], written "
                    f"{_years_between(old_note, recent_note)} earlier, more than it "
                    f"resembles any of your other recent notes. Circling back to old ideas?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[recent_note.link_text, old_note.link_text],
                        geist_id="anachronism_detector",
                    )
                )

    # Also find old notes that feel contemporary
    for old_note in vault.sample(old_notes, min(20, len(old_notes))):
        # Find most similar recent notes
        recent_matches = []
        for recent_note in vault.sample(recent_notes, min(10, len(recent_notes))):
            sim = vault.similarity(old_note, recent_note)
            recent_matches.append((recent_note, sim))

        if recent_matches:
            best_match = max(recent_matches, key=lambda x: x[1])
            recent_note, similarity = best_match

            if similarity > SimilarityLevel.VERY_HIGH:  # Very high similarity across time
                text = (
                    f"[[{old_note.link_text}]], written "
                    f"{_years_between(old_note, recent_note)} before your recent "
                    f"[[{recent_note.link_text}]], feels remarkably contemporary—the two "
                    f"are very similar. Some ideas are timeless?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[old_note.link_text, recent_note.link_text],
                        geist_id="anachronism_detector",
                    )
                )

    return vault.sample(suggestions, count=2)
