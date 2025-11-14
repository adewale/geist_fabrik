"""Anachronism Detector geist - finds temporally displaced notes.

Identifies recent notes that semantically resemble older thinking, or old notes
that feel contemporary, suggesting cyclical thinking or ideas out of their time.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext
from geistfabrik.similarity_analysis import SimilarityLevel


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes that feel temporally displaced.

    Returns:
        List of suggestions highlighting temporal outliers
    """
    from datetime import datetime, timedelta

    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    if len(notes) < 30:
        return []

    now = datetime.now()

    # Get recent notes (last 3 months)
    recent_cutoff = now - timedelta(days=90)
    recent_notes = [n for n in notes if n.created > recent_cutoff]

    # Get old notes (more than 1 year ago)
    old_cutoff = now - timedelta(days=365)
    old_notes = [n for n in notes if n.created < old_cutoff]

    if len(recent_notes) < 5 or len(old_notes) < 5:
        return []

    # Find recent notes that are more similar to old notes than to other recent notes
    for recent_note in vault.sample(recent_notes, min(20, len(recent_notes))):
        # Compare to other recent notes
        recent_similarities = []
        for other_recent in vault.sample(recent_notes, min(10, len(recent_notes))):
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
            avg_recent_sim = sum(recent_similarities) / len(recent_similarities)
            max_old_sim = max(old_similarities)

            # Recent note is more similar to old thinking than current thinking
            if max_old_sim > avg_recent_sim + 0.15:
                best_old_match = max(old_matches, key=lambda x: x[1])
                old_note, similarity = best_old_match

                years_apart = recent_note.created.year - old_note.created.year

                text = (
                    f"[[{recent_note.obsidian_link}]] (written recently) semantically resembles "
                    f"[[{old_note.obsidian_link}]] from {years_apart} years ago more than it "
                    f"resembles your current thinking. Circling back to old ideas?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[recent_note.obsidian_link, old_note.obsidian_link],
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
                years_apart = recent_note.created.year - old_note.created.year

                text = (
                    f"[[{old_note.obsidian_link}]] from {years_apart} years ago feels "
                    f"remarkably contemporary—it's very similar to your recent "
                    f"[[{recent_note.obsidian_link}]]. Some ideas are timeless?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[old_note.obsidian_link, recent_note.obsidian_link],
                        geist_id="anachronism_detector",
                    )
                )

    return vault.sample(suggestions, k=2)
