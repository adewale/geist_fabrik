"""Burst Evolution geist - compares burst-day representations over time.

Shows numerical semantic-distance scores for notes created together on burst
days without inferring the author's mental state from those vectors.
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion

# Smallest semantic drift worth reporting (below this the text is unchanged
# or trivially edited)
MIN_MEANINGFUL_DRIFT = 0.05


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Show measured semantic distance for burst-day notes.

    Uses EmbeddingTrajectoryCalculator to measure drift from each note's
    first session snapshot to the current session, for notes created together
    on burst days (on or before the session date).

    Args:
        vault: The vault context with database access and session info

    Returns:
        Single suggestion showing drift scores (or empty list if no data)
    """
    from geistfabrik.temporal_analysis import EmbeddingTrajectoryCalculator

    # Find burst days (uses VaultContext aggregation method)
    burst_days_dict = vault.notes_grouped_by_creation_date(min_per_day=3, exclude_journal=True)

    if not burst_days_dict:
        return []

    # Session date, not wall-clock: a --date replay must not report burst days
    # that, at that date, had not happened yet
    session_day = vault.session.date.date()

    # Try burst days until we find one with enough embedding history
    burst_days_list = [
        (day, notes)
        for day, notes in burst_days_dict.items()
        if datetime.fromisoformat(day).date() <= session_day
    ]
    for day_date, notes in vault.sample(burst_days_list, count=len(burst_days_list)):
        # Calculate drift for each note using EmbeddingTrajectoryCalculator
        drifts = []
        first_seen: list[datetime] = []
        for note in notes:
            calc = EmbeddingTrajectoryCalculator(vault, note)
            snapshots = calc.snapshots()

            # Need at least 2 snapshots to calculate drift
            if len(snapshots) < 2:
                continue

            # Clamp float noise: identical vectors can give -0.00
            drift = max(0.0, calc.total_drift())
            drifts.append((note.path, drift))
            first_seen.append(snapshots[0][0])

        # Need at least 3 notes with drift data, and at least one note whose
        # text actually changed (semantic drift is 0 for unedited notes, so an
        # all-zero table has nothing to say)
        if len(drifts) >= 3 and max(d for _, d in drifts) >= MIN_MEANINGFUL_DRIFT:
            return [
                _generate_drift_observation(vault, day_date, len(notes), drifts, min(first_seen))
            ]

    return []


def _span_phrase(days: int) -> str:
    """Describe a span of days as days, months or years (singular-aware)."""
    if days < 30:
        count, unit = days, "day"
    elif days < 365:
        count, unit = days // 30, "month"
    else:
        count, unit = days // 365, "year"
    return f"{count} {unit}{'' if count == 1 else 's'}"


def _drift_label(drift: float) -> str:
    """Convert drift score to human-readable label."""
    if drift < 0.10:
        return "small change"
    elif drift < 0.25:
        return "moderate change"
    elif drift < 0.40:
        return "large change"
    else:
        return "very large change"


def _generate_drift_observation(
    vault: "VaultContext",
    date: str,
    created_count: int,
    drifts: list[tuple[str, float]],
    first_seen: datetime,
) -> Suggestion:
    """Generate declarative observation based on drift patterns.

    Drift is measured between each note's first and latest session snapshot,
    so the time span reported is from the earliest first snapshot to this
    session, not from the burst day.
    """
    # Sort by drift (highest first)
    drifts_sorted = sorted(drifts, key=lambda x: x[1], reverse=True)
    avg_drift = sum(d for _, d in drifts) / len(drifts)

    # Build drift listing
    drift_lines = []
    for path, drift in drifts_sorted[:7]:  # Show up to 7
        note = vault.get_note(path)
        if note is None:
            continue
        label = _drift_label(drift)
        drift_lines.append(f"- [[{note.link_text}]]: {drift:.2f} semantic distance ({label})")

    drift_text = "\n".join(drift_lines)

    # Describe only the measurement; leave interpretation to the user.
    if avg_drift > 0.45:
        observation = (
            "This group has a high average representation change. What do the actual edits show?"
        )
    elif avg_drift < 0.15:
        observation = (
            "This group has a low average representation change. "
            "Does the source text still serve its purpose?"
        )
    else:
        # Find stable anchors
        stable = [p for p, d in drifts if d < 0.15]
        if stable:
            stable_notes = [vault.get_note(p) for p in stable[:2]]
            stable_links = [f"[[{n.link_text}]]" for n in stable_notes if n is not None]
            verb = "has" if len(stable_links) == 1 else "have"
            observation = (
                f"{', '.join(stable_links)} {verb} the smallest measured changes in this group. "
                f"How do they compare with the other notes on inspection?"
            )
        else:
            observation = "The measured changes vary; inspect the notes for an explanation."

    # Drift is measured from the first session that saw these notes
    span_days = max(0, (vault.session.date.date() - first_seen.date()).days)
    time_phrase = (
        f"Over the {_span_phrase(span_days)} since your first session with them "
        f"({first_seen:%Y-%m-%d})"
    )

    text = (
        f"On {date}, you created {created_count} notes. {time_phrase}:\n{drift_text}"
        f"\n\n{observation}"
    )

    # Get all note titles
    notes = [vault.get_note(p) for p, _ in drifts]
    note_titles = [n.link_text for n in notes if n is not None]

    return Suggestion(
        text=text,
        notes=note_titles,
        geist_id="burst_evolution",
    )
