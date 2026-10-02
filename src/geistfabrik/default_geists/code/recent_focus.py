"""Recent focus geist - connects what you've been working on lately to older notes.

Samples notes you have modified in the last RECENT_DAYS days and, for each,
finds the most similar note you have not touched for longer than that. When
the older note is closer to the recent one than ANY other recently modified
note is (measured against all of them, not a sample), it says so: you may be
circling back to an old idea. Otherwise it asks the gentler "what if they
connect?". When the older note was written at least a year before the recent
one, the real number of years is given.

(Absorbs the former anachronism_detector geist.)
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext

# Modified within this many days of the session = recent work; otherwise older.
RECENT_DAYS = 60
MAX_SUGGESTIONS = 3


def _year_gap(older: "Note", recent: "Note") -> str:
    """Return "(written N years earlier)", with a leading space, when ``older``
    was created at least a year before ``recent``; else "" (never rounding up
    to a year that did not pass)."""
    years = (recent.created - older.created).days // 365
    if years < 1:
        return ""
    return f" (written {years} year{'s' if years != 1 else ''} earlier)"


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Connect recently modified notes to similar older notes.

    Returns:
        Up to MAX_SUGGESTIONS suggestions, one per sampled recent note
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel

    def days_since_modified(note: "Note") -> int:
        return int(vault.metadata(note)["days_since_modified"])

    recent = [n for n in vault.notes() if days_since_modified(n) <= RECENT_DAYS]

    if len(recent) < 2:
        return []

    suggestions = []
    # Sample, don't rank: any recent note can be the starting point, not only
    # the few most recently modified.
    for recent_note in vault.sample(recent, MAX_SUGGESTIONS):
        # Nearest neighbours come back even when nothing is close; the
        # suggestion claims similarity, so require at least a weak match.
        similar = vault.neighbours(recent_note, count=10, return_scores=True)
        older = [
            note
            for note, score in similar
            if score >= SimilarityLevel.WEAK and days_since_modified(note) > RECENT_DAYS
        ]
        if not older:
            continue

        old_note = older[0]  # The most similar older note
        old_similarity = vault.similarity(recent_note, old_note)
        closest_recent = max(
            vault.similarity(recent_note, other)
            for other in recent
            if other.path != recent_note.path
        )
        gap = _year_gap(old_note, recent_note)

        if old_similarity > closest_recent:
            text = (
                f"[[{recent_note.link_text}]], which you've worked on lately, resembles "
                f"[[{old_note.link_text}]]{gap} more than anything else you've worked on "
                f"in the last {RECENT_DAYS} days. Circling back to an old idea?"
            )
        else:
            text = (
                f"What if your recent work on [[{recent_note.link_text}]] "
                f"connects to your older note [[{old_note.link_text}]]{gap}? "
                f"They're semantically similar - has your thinking evolved?"
            )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[recent_note.link_text, old_note.link_text],
                geist_id="recent_focus",
            )
        )

    return suggestions
