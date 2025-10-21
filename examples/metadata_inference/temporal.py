"""Temporal metadata inference module.

Infers staleness, modification patterns, and other temporal properties.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from geistfabrik import Note, VaultContext


def infer(note: "Note", vault: "VaultContext") -> Dict[str, Any]:
    """Infer temporal metadata for a note.

    Args:
        note: Note to analyse
        vault: VaultContext for accessing vault data

    Returns:
        Dictionary with temporal metrics:
        - staleness: 0-1 score based on time since last modification
        - days_since_modified: Days since last modification
        - days_since_created: Days since creation
        - is_recent: True if modified in last 7 days
        - is_old: True if not modified in last 90 days
    """
    now = datetime.now()
    days_since_modified = (now - note.modified).days
    days_since_created = (now - note.created).days

    # Staleness: 0 (fresh) to 1 (very stale), asymptotic curve
    # 30 days = 0.5, 90 days = 0.75, 365 days = ~0.9
    staleness = 1 - (1 / (1 + days_since_modified / 30))

    is_recent = days_since_modified < 7
    is_old = days_since_modified > 90

    return {
        "staleness": round(staleness, 3),
        "days_since_modified": days_since_modified,
        "days_since_created": days_since_created,
        "is_recent": is_recent,
        "is_old": is_old,
    }
