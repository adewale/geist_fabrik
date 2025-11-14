"""Burst Evolution geist - tracks how notes from burst days evolved over time.

Shows numerical drift scores for notes created together on burst days,
revealing which ideas crystallized vs. evolved.
"""

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Show how burst-day notes have evolved since creation.

    Uses EmbeddingTrajectoryCalculator to track drift from creation
    to current session for notes created together on burst days.

    Args:
        vault: The vault context with database access and session info

    Returns:
        Single suggestion showing drift scores (or empty list if no data)
    """
    from geistfabrik.temporal_analysis import EmbeddingTrajectoryCalculator

    # Find burst days (uses VaultContext aggregation method)
    burst_days_dict = vault.notes_grouped_by_creation_date(
        min_per_day=3, exclude_journal=True
    )

    if not burst_days_dict:
        return []

    # Try burst days until we find one with enough embedding history
    burst_days_list = list(burst_days_dict.items())
    for day_date, notes in vault.sample(burst_days_list, k=len(burst_days_list)):
        # Calculate drift for each note using EmbeddingTrajectoryCalculator
        drifts = []
        for note in notes:
            calc = EmbeddingTrajectoryCalculator(vault, note)
            snapshots = calc.snapshots()

            # Need at least 2 snapshots to calculate drift
            if len(snapshots) < 2:
                continue

            drift = calc.total_drift()
            drifts.append((note.path, drift))

        # Need at least 3 notes with drift data
        if len(drifts) >= 3:
            return [_generate_drift_observation(vault, day_date, drifts)]

    return []


def _drift_label(drift: float) -> str:
    """Convert drift score to human-readable label."""
    if drift < 0.10:
        return "mostly stable"
    elif drift < 0.25:
        return "moderate evolution"
    elif drift < 0.40:
        return "significant shift"
    else:
        return "major evolution"


def _generate_drift_observation(
    vault: "VaultContext", date: str, drifts: list[tuple[str, float]]
) -> Suggestion:
    """Generate declarative observation based on drift patterns."""
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
        drift_lines.append(f"- [[{note.obsidian_link}]]: {drift:.2f} drift ({label})")

    drift_text = "\n".join(drift_lines)

    # Generate declarative interpretation
    if avg_drift > 0.45:
        observation = (
            "That burst was asking questions, not stating answers. "
            "Early explorations that your understanding has completely transformed."
        )
    elif avg_drift < 0.15:
        observation = "That burst created foundational concepts that haven't needed revision."
    else:
        # Find stable anchors
        stable = [p for p, d in drifts if d < 0.15]
        if stable:
            stable_notes = [vault.get_note(p) for p in stable[:2]]
            stable_titles = ", ".join(
                [f"[[{n.obsidian_link}]]" for n in stable_notes if n is not None]
            )
            observation = (
                f"{stable_titles} are anchors—the stable core "
                f"around which other ideas orbit and evolve."
            )
        else:
            observation = "Early signs of which ideas are settling vs. still moving."

    # Calculate time elapsed
    try:
        burst_datetime = datetime.fromisoformat(date)
        current_datetime = datetime.now()
        days_ago = (current_datetime - burst_datetime).days

        if days_ago < 30:
            time_phrase = f"Only {days_ago} days have passed"
        elif days_ago < 365:
            months = days_ago // 30
            time_phrase = f"{months} months later"
        else:
            years = days_ago // 365
            time_phrase = f"{years} year{'s' if years > 1 else ''} later"
    except Exception:
        time_phrase = "Since then"

    text = (
        f"On {date}, you created {len(drifts)} notes. {time_phrase}:\n{drift_text}\n\n{observation}"
    )

    # Get all note titles
    notes = [vault.get_note(p) for p, _ in drifts]
    note_titles = [n.obsidian_link for n in notes if n is not None]

    return Suggestion(
        text=text,
        notes=note_titles,
        geist_id="burst_evolution",
    )
