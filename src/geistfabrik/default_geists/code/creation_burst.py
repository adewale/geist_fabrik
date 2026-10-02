"""Creation Burst geist - surfaces days when multiple notes were created.

Identifies "burst days" when you created 3+ notes and asks what was special
about those moments of creative activity. When some of that day's notes have
since been rewritten (their content-derived meaning vector moved at least
REWRITE_DRIFT from the first session that recorded them), one sentence names
them. (Absorbs the former burst_evolution geist.)
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.models import Note
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion

# More notes "created" on one day than max(MIN_IMPORT_SIZE, IMPORT_SHARE of the
# vault) is treated as an import artefact rather than a creative burst.
MIN_IMPORT_SIZE = 20
IMPORT_SHARE = 0.25
# Smallest first-to-latest semantic drift that counts as a rewrite (vectors
# are cached by content, so any drift means the text was edited; below this
# the edit is trivial).
REWRITE_DRIFT = 0.05
MAX_NAMED_REWRITES = 3


def _rewritten_sentence(vault: "VaultContext", notes: list["Note"]) -> str:
    """One sentence naming the burst-day notes rewritten since their first
    recorded session, or "" when none was."""
    from geistfabrik.temporal_analysis import EmbeddingTrajectoryCalculator

    rewritten: list[tuple[str, datetime]] = []
    for note in notes:
        calc = EmbeddingTrajectoryCalculator(vault, note)
        snapshots = calc.snapshots()
        if len(snapshots) >= 2 and calc.total_drift() >= REWRITE_DRIFT:
            rewritten.append((note.link_text, snapshots[0][0]))

    if not rewritten:
        return ""

    first_seen = min(date for _, date in rewritten)
    links = [f"[[{link}]]" for link, _ in rewritten[:MAX_NAMED_REWRITES]]
    more = len(rewritten) - len(links)
    if more:
        named = f"{', '.join(links)} and {more} more"
    elif len(links) == 1:
        named = links[0]
    else:
        named = f"{', '.join(links[:-1])} and {links[-1]}"
    return (
        f" Since your first session with them ({first_seen:%Y-%m-%d}), you have rewritten {named}."
    )


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find days when 3+ notes were created and ask what was special.

    Detects "burst days" of creative activity by grouping notes by
    creation date and identifying days with 3+ notes created. Days that look
    like bulk imports and days after the session date are ignored. Randomly
    samples one such day and generates a provocation based on the count.

    Args:
        vault: The vault context with database access and utilities

    Returns:
        Single suggestion about a burst day (or empty list if no bursts found)
    """
    # Use VaultContext aggregation method instead of direct SQL
    # This respects architectural layering and hides database implementation
    burst_days_dict = vault.notes_grouped_by_creation_date(min_per_day=3, exclude_journal=True)

    # A day on which a large share of the vault was "created" is a bulk import,
    # clone or sync (every file stamped with the same time), not a burst; and on
    # a --date replay, days after the session date have not happened yet.
    import_size = max(MIN_IMPORT_SIZE, IMPORT_SHARE * len(vault.notes()))
    session_day = vault.session.date.strftime("%Y-%m-%d")
    burst_days = [
        (day, notes)
        for day, notes in burst_days_dict.items()
        if len(notes) <= import_size and day <= session_day
    ]

    if not burst_days:
        return []

    # Randomly select one burst day (deterministic via vault's RNG)
    day_date, notes = vault.sample(burst_days, count=1)[0]
    count = len(notes)

    if not notes:
        return []

    # Get obsidian link text for each note (handles both regular and virtual notes)
    note_links = [note.link_text for note in notes]

    # Limit to showing first 8 notes to avoid overwhelming output
    display_links = note_links[:8]
    more_count = len(note_links) - len(display_links)

    # Build note list for suggestion text
    title_list = ", ".join([f"[[{link}]]" for link in display_links])
    if more_count > 0:
        title_list += f", and {more_count} more"

    # Generate question based on count
    if count >= 6:
        question = "What was special about that day?"
    else:  # 3-5 notes
        question = "What were you circling around that day?"

    rewritten = _rewritten_sentence(vault, notes)
    text = (
        f"On {day_date}, you created {count} notes in one day: {title_list}.{rewritten} {question}"
    )

    return [
        Suggestion(
            text=text,
            notes=note_links,  # All notes (obsidian links), not just displayed ones
            geist_id="creation_burst",
        )
    ]
