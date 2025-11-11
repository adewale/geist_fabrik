"""Burst Evolution geist - tracks how notes from burst days evolved over time.

Shows numerical drift scores for notes created together on burst days,
revealing which ideas crystallized vs. evolved.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Show how burst-day notes have evolved since creation.

    Finds burst days (3+ notes), calculates drift for each note from
    creation to current session, and generates observations about
    evolution patterns.

    Args:
        vault: The vault context with database access and session info

    Returns:
        Single suggestion showing drift scores (or empty list if no data)
    """
    # Find burst days
    burst_days = _get_burst_days(vault)
    if not burst_days:
        return []

    # Try burst days until we find one with enough embedding history
    for day_date, note_paths in vault.sample(burst_days, k=len(burst_days)):
        # Find earliest session with these notes
        creation_session = _find_earliest_session_with_notes(vault, note_paths, day_date)
        if not creation_session:
            continue

        # Calculate drift for each note
        drifts = []
        for path in note_paths:
            creation_emb = _get_embedding_from_session(vault, path, creation_session)
            current_emb = _get_current_embedding(vault, path)

            if creation_emb is not None and current_emb is not None:
                drift = _calculate_drift(creation_emb, current_emb)
                drifts.append((path, drift))

        # Need at least 3 notes with drift data
        if len(drifts) >= 3:
            return [_generate_drift_observation(vault, day_date, drifts)]

    return []


def _get_burst_days(vault: "VaultContext") -> list[tuple[str, list[str]]]:
    """Get burst days with 3+ notes created."""
    cursor = vault.db.execute(
        """
        SELECT DATE(created) as creation_date,
               GROUP_CONCAT(path, '|') as note_paths
        FROM notes
        WHERE NOT path LIKE 'geist journal/%'
        GROUP BY DATE(created)
        HAVING COUNT(*) >= 3
        ORDER BY COUNT(*) DESC
        """
    )

    results = []
    for row in cursor.fetchall():
        date_str, paths_str = row
        paths = paths_str.split("|") if paths_str else []
        results.append((date_str, paths))

    return results


def _find_earliest_session_with_notes(
    vault: "VaultContext", note_paths: list[str], burst_date: str
) -> int | None:
    """Find earliest session that has embeddings for burst notes.

    Looks for session closest to (but not before) burst_date.
    """
    # Get all sessions on or after burst date
    cursor = vault.db.execute(
        """
        SELECT session_id, date
        FROM sessions
        WHERE date >= ?
        ORDER BY date ASC
        """,
        (burst_date,),
    )

    sessions = cursor.fetchall()
    if not sessions:
        return None

    # Find first session that has embeddings for most notes
    for session_id, _ in sessions:
        # Count how many notes have embeddings in this session
        cursor = vault.db.execute(
            """
            SELECT COUNT(DISTINCT note_path)
            FROM session_embeddings
            WHERE session_id = ? AND note_path IN ({})
            """.format(",".join("?" * len(note_paths))),
            [session_id] + note_paths,
        )

        count = cursor.fetchone()[0]

        # If at least 50% of notes have embeddings, use this session
        if count >= len(note_paths) * 0.5:
            return int(session_id)

    return None


def _get_embedding_from_session(
    vault: "VaultContext", note_path: str, session_id: int
) -> np.ndarray | None:
    """Get note embedding from specific session."""
    cursor = vault.db.execute(
        """
        SELECT embedding
        FROM session_embeddings
        WHERE session_id = ? AND note_path = ?
        """,
        (session_id, note_path),
    )

    row = cursor.fetchone()
    if row:
        return np.frombuffer(row[0], dtype=np.float32)
    return None


def _get_current_embedding(vault: "VaultContext", note_path: str) -> np.ndarray | None:
    """Get current embedding for note."""
    try:
        return vault._backend.get_embedding(note_path)
    except Exception:
        return None


def _calculate_drift(
    creation_emb: np.ndarray, current_emb: np.ndarray
) -> float:
    """Calculate drift between two embeddings.

    Drift = 1 - cosine_similarity
    """
    from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
        cosine_similarity as sklearn_cosine,
    )

    similarity = sklearn_cosine(
        creation_emb.reshape(1, -1), current_emb.reshape(1, -1)
    )
    return 1.0 - float(similarity[0, 0])


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
        observation = (
            "That burst created foundational concepts that haven't needed revision."
        )
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
        f"On {date}, you created {len(drifts)} notes. {time_phrase}:\n"
        f"{drift_text}\n\n{observation}"
    )

    # Get all note titles
    notes = [vault.get_note(p) for p, _ in drifts]
    note_titles = [n.title for n in notes if n is not None]

    return Suggestion(
        text=text,
        notes=note_titles,
        geist_id="burst_evolution",
    )
