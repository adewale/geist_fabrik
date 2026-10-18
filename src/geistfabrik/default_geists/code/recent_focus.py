"""Recent focus geist - connects what you've been working on lately to older notes.

Samples physical notes modified in the last RECENT_DAYS days and journal
entries dated within that period. A journal file's modification time is not
evidence that any particular entry changed. For each recent note, finds the
most similar older note using the same date scope. When
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

# Physical modification or virtual heading date within this many days = recent.
RECENT_DAYS = 60
MAX_SUGGESTIONS = 3


def _year_gap(older: "Note", recent: "Note") -> str:
    """State a whole-year creation gap, describing virtual headings as dated.

    Never round up to a year that did not pass.
    """
    years = (recent.created - older.created).days // 365
    if years < 1:
        return ""
    dating = "dated" if older.is_virtual or recent.is_virtual else "written"
    return f" ({dating} {years} year{'s' if years != 1 else ''} earlier)"


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Connect recently modified physical notes or dated entries to older notes.

    Returns:
        Up to MAX_SUGGESTIONS suggestions, one per sampled recent note
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel

    def reference_age(note: "Note") -> int | None:
        if note.is_virtual:
            # Entry dates describe dated cohorts, not the time an entry was
            # written or edited. Source mtime must never stand in for that.
            if note.entry_date is None:
                return None
            return (vault.session.date.date() - note.entry_date).days
        return (vault.session.date.date() - note.modified.date()).days

    notes = vault.notes()
    ages = {n.path: reference_age(n) for n in notes}
    recent = [n for n in notes if (age := ages[n.path]) is not None and 0 <= age <= RECENT_DAYS]

    if len(recent) < 2:
        return []

    suggestions = []
    # Sample, don't rank: any recent note can be the starting point, not only
    # the few most recently modified.
    sampled = vault.sample(recent, MAX_SUGGESTIONS)
    for recent_note, similar in zip(sampled, vault.neighbours_many(sampled, count=10)):
        # Nearest neighbours come back even when nothing is close; the
        # suggestion claims similarity, so require at least a weak match.
        older = [
            note
            for note, score in similar
            if score >= SimilarityLevel.WEAK
            and (age := ages.get(note.path)) is not None
            and age > RECENT_DAYS
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

        if recent_note.is_virtual:
            # Say precisely what is known, including for a newly seen entry:
            # its heading date is recent; its writing/edit date is unknown.
            text = (
                f"What if your entry [[{recent_note.link_text}]], dated "
                f"{recent_note.entry_date}, connects to your older note "
                f"[[{old_note.link_text}]]{gap}? They're semantically similar "
                "- has your thinking evolved?"
            )
        elif old_similarity > closest_recent:
            recent_scope = (
                "any other recent note"
                if any(n.is_virtual for n in recent)
                else "anything else you've worked on"
            )
            text = (
                f"[[{recent_note.link_text}]], which you've worked on lately, resembles "
                f"[[{old_note.link_text}]]{gap} more than {recent_scope} "
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
