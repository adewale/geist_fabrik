"""Temporal Mirror - Compare notes from different time periods.

Divides vault notes into 10 temporal periods and juxtaposes notes from
different eras to reveal how thinking has evolved over time.
"""

from typing import TYPE_CHECKING

from geistfabrik.models import Suggestion

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext


def suggest(vault: "VaultContext") -> list[Suggestion]:
    """Compare notes from different temporal periods.

    Divides all notes (excluding geist journal) into 10 time periods based on
    creation date, then randomly selects 2 periods and 1 note from each to
    create a temporal juxtaposition.

    Args:
        vault: The vault context with notes and utilities

    Returns:
        Single suggestion comparing notes from different time periods
    """
    # Get all notes excluding geist journal
    all_notes = vault.notes()
    non_journal_notes = [n for n in all_notes if not n.path.startswith("geist journal/")]

    if len(non_journal_notes) < 2:
        return []

    # Sort notes by creation date
    sorted_notes = sorted(non_journal_notes, key=lambda n: n.created)

    # Divide into 10 periods
    total = len(sorted_notes)
    period_size = max(1, total // 10)

    periods = []
    for i in range(10):
        start_idx = i * period_size
        if i == 9:  # Last period gets any remainder
            end_idx = total
        else:
            end_idx = start_idx + period_size

        period_notes = sorted_notes[start_idx:end_idx]
        if period_notes:  # Only add non-empty periods
            periods.append(period_notes)

    # Need at least 2 periods with notes
    if len(periods) < 2:
        return []

    # Randomly select 2 different periods (deterministic via vault's RNG)
    selected_periods = vault.sample(list(range(len(periods))), k=2)
    period1_idx = selected_periods[0]
    period2_idx = selected_periods[1]

    # Get 1 note from each period
    note1 = vault.sample(periods[period1_idx], k=1)[0]
    note2 = vault.sample(periods[period2_idx], k=1)[0]

    # Calculate which period each note is in (1-indexed for readability)
    period1_num = period1_idx + 1
    period2_num = period2_idx + 1

    # Generate suggestion with temporal framing
    relationships = [
        "might answer questions raised in",
        "contradicts assumptions from",
        "shows how far your thinking has traveled since",
        "reveals patterns you couldn't see when writing",
        "completes ideas that began in",
        "challenges the worldview of",
        "echoes themes first explored in",
        "represents a return to ideas from",
    ]

    relationship = vault.sample(relationships, k=1)[0]

    suggestion_text = (
        f"From period {period1_num}, [[{note1.obsidian_link}]] {relationship} "
        f"period {period2_num}'s [[{note2.obsidian_link}]]."
    )

    return [
        Suggestion(
            text=suggestion_text,
            notes=[note1.obsidian_link, note2.obsidian_link],
            geist_id="temporal_mirror",
        )
    ]
