"""Stable semantic identity plus interval overlap for repeated observations.

The interval:v1 protocol treats overlapping inclusive intervals with the same
identity as the same episode. Rolling-window clipping and changing endpoints
therefore do not manufacture novelty. Non-interval keys retain exact matching.
"""

import hashlib
import json
import sqlite3
from collections.abc import Sequence
from datetime import date


def factual_evidence_key(identity: Sequence[str], facts: Sequence[str]) -> str:
    """Identify a factual lens by its full inputs, independently of its wording.

    Callers include the analysis policy and source identity in ``identity`` and
    complete factual inputs (such as original note prose) in ``facts``. Counts
    alone are insufficient: different observations can have the same totals.
    Length-delimited JSON avoids concatenation ambiguities while bounding the
    persisted payload; inputs remain local and never enter diagnostic output.
    """
    payload = json.dumps([list(identity), list(facts)], ensure_ascii=True)
    return "facts:v1:" + hashlib.sha256(payload.encode()).hexdigest()


def interval_evidence_key(identity: Sequence[str], start: str, end: str) -> str:
    """Encode a bounded identity and an inclusive, validated calendar interval."""
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first > last:
        raise ValueError("evidence interval starts after it ends")
    digest = hashlib.sha256(json.dumps(list(identity)).encode()).hexdigest()
    return f"interval:v1:{digest}:{first.isoformat()}:{last.isoformat()}"


def evidence_interval(key: str) -> tuple[str, date, date] | None:
    """Parse the optional interval protocol; opaque/malformed keys stay opaque."""
    parts = key.split(":")
    if len(parts) != 5 or parts[:2] != ["interval", "v1"]:
        return None
    identity, start, end = parts[2:]
    if len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
        return None
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError:
        return None
    if first > last:
        return None
    return identity, first, last


def evidence_was_seen(db: sqlite3.Connection, geist_id: str, key: str | None, before: str) -> bool:
    """Indexed exact/overlapping evidence lookup, shared by generation and filtering."""
    if key is None:
        return False
    if db.execute(
        "SELECT 1 FROM session_suggestions "
        "WHERE geist_id = ? AND evidence_key = ? AND session_date < ? LIMIT 1",
        (geist_id, key, before),
    ).fetchone():
        return True

    interval = evidence_interval(key)
    if interval is None:
        return False
    identity, first, last = interval
    prefix = f"interval:v1:{identity}:"
    # Valid keys sort by their first ISO day. ';' follows ':' and therefore
    # includes every interval starting on `last` while excluding later days.
    # The final-day predicate avoids fetching disjoint older episodes.
    cursor = db.execute(
        "SELECT evidence_key FROM session_suggestions "
        "WHERE geist_id = ? AND evidence_key >= ? AND evidence_key < ? "
        "AND session_date < ? AND substr(evidence_key, -10) >= ?",
        (
            geist_id,
            prefix,
            prefix + last.isoformat() + ";",
            before,
            first.isoformat(),
        ),
    )
    for (old_key,) in cursor:
        old = evidence_interval(old_key)
        # Treat opaque/malformed persisted keys as exact-only identities.
        if old is not None and old[0] == identity and first <= old[2] and old[1] <= last:
            return True
    return False
