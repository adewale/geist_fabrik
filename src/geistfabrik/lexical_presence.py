"""Compact exact term-presence projections for current and captured lexical rows.

The retained JSON remains the exact frequency/history source. Each projection is
a sorted little-endian uint64 vector of stable dictionary IDs, with one ID per
present term. IDs are SQLite positive signed integers; the storage format therefore
cannot silently wrap an ID into a smaller numeric type. Writers never commit and
must run inside the same owned transaction as the source lexical mutation.
"""

import json
import sqlite3
from collections.abc import Collection, Iterator
from datetime import date
from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray

_ID_DTYPE = np.dtype(np.uint64).newbyteorder("<")
_MAX_ID = 2**63 - 1


class PresenceWriter:
    """Resolve only changed rows' terms, caching touched IDs for this transaction.

    The indexed maximum allocates stable IDs without loading retained vocabulary.
    Missing IDs are looked up in bounded batches, never one query per presence.
    """

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self._ids: dict[str, int] = {}
        self._next_id: int | None = None
        self._has_existing_terms = False

    def encode(self, terms: Collection[str]) -> bytes:
        """Encode exact presence without serializing term strings into each row again."""
        if not self.db.in_transaction:
            raise RuntimeError("Lexical presence writes require an owned transaction")
        if not terms:
            return b""
        if self._next_id is None:
            row = self.db.execute(
                "SELECT coalesce(max(term_id), 0) FROM lexical_presence_terms"
            ).fetchone()
            maximum = int(row[0])
            self._next_id = maximum + 1
            self._has_existing_terms = maximum > 0
        unique_terms = dict.fromkeys(terms)
        unresolved = [term for term in unique_terms if term not in self._ids]
        if self._has_existing_terms:
            for offset in range(0, len(unresolved), 900):
                batch = unresolved[offset : offset + 900]
                placeholders = ",".join("?" for _ in batch)
                rows = self.db.execute(
                    "SELECT term_id, term FROM lexical_presence_terms "
                    f"WHERE term IN ({placeholders})",
                    batch,
                )
                self._ids.update((term, term_id) for term_id, term in rows)
        # An initially empty dictionary needs no database lookups: every ID in
        # this transaction was allocated by this writer and is already cached.
        missing = [term for term in unresolved if term not in self._ids]
        if len(missing) > _MAX_ID - self._next_id + 1:
            raise OverflowError("Lexical presence dictionary exhausted SQLite integer IDs")
        additions = [(self._next_id + i, term) for i, term in enumerate(missing)]
        self.db.executemany(
            "INSERT INTO lexical_presence_terms(term_id, term) VALUES (?, ?)", additions
        )
        self._ids.update((term, term_id) for term_id, term in additions)
        self._next_id += len(additions)
        ids = np.fromiter(
            (self._ids[term] for term in unique_terms), dtype=_ID_DTYPE, count=len(unique_terms)
        )
        ids.sort()
        return ids.tobytes()


def decode_presence(blob: bytes) -> NDArray[np.uint64]:
    """Return a read-only zero-copy vector, rejecting malformed/corrupt projections."""
    if len(blob) % _ID_DTYPE.itemsize:
        raise ValueError("Lexical presence must contain complete uint64 IDs")
    # NumPy's overloads lose the scalar type for a byte-order-specific dtype.
    # The format above fixes the runtime dtype to uint64 without any numeric cast.
    ids = cast(NDArray[np.uint64], np.frombuffer(blob, dtype=_ID_DTYPE))
    if ids.size and (int(ids[0]) == 0 or int(ids[-1]) > _MAX_ID or np.any(ids[1:] <= ids[:-1])):
        raise ValueError("Lexical presence IDs must be positive, sorted and unique")
    return ids


def presence_terms(db: sqlite3.Connection, *, min_documents: int = 0) -> Iterator[tuple[int, str]]:
    """Stream IDs in lexical term order, optionally screened by current frequency.

    Historical additions must use the unscreened dictionary: a term absent from
    current prose can still be present in captured historical observations.
    """
    if min_documents:
        rows = db.execute(
            "SELECT p.term_id, p.term FROM lexical_presence_terms p "
            "JOIN lexical_terms t ON t.term = p.term WHERE t.documents >= ? ORDER BY p.term",
            (min_documents,),
        )
    else:
        rows = db.execute("SELECT term_id, term FROM lexical_presence_terms ORDER BY term")
    for term_id, term in rows:
        yield int(term_id), str(term)


def ensure_presence(db: sqlite3.Connection) -> None:
    """Backfill legacy projections from stored JSON within the caller's transaction.

    This never reads Markdown, modifies frequencies/history, or advances generation.
    A failed transaction rolls back projections and dictionary additions together.
    """
    if not db.in_transaction:
        raise RuntimeError("Lexical presence backfill requires an owned transaction")
    writer = PresenceWriter(db)
    _fill_notes(
        db,
        writer,
        db.execute("SELECT path, counts_json FROM lexical_notes WHERE presence IS NULL"),
    )
    _fill_events(
        db,
        writer,
        db.execute("SELECT path, bin_start, terms_json FROM lexical_events WHERE presence IS NULL"),
    )


def ensure_selected_presence(
    db: sqlite3.Connection,
    *,
    history_mode: Literal["dated_cohorts", "observed_additions"],
    first: date,
    end_day: date,
) -> None:
    """Backfill only the selected analysis population, leaving unrelated rows lazy.

    Current cohorts use declared dates; captured additions use their observation
    cutoff and selected weekly frame. Empty captured vectors remain observations.
    The existing all-row ``ensure_presence`` contract remains available to callers
    that deliberately need the complete projection.
    """
    if not db.in_transaction:
        raise RuntimeError("Lexical presence backfill requires an owned transaction")
    if first > end_day:
        raise ValueError("Lexical presence window must start on or before its cutoff")
    writer = PresenceWriter(db)
    if history_mode == "dated_cohorts":
        _fill_notes(
            db,
            writer,
            db.execute(
                "SELECT path, counts_json FROM lexical_notes WHERE presence IS NULL "
                "AND cohort_day BETWEEN ? AND ? AND counts_json != '{}'",
                (first.isoformat(), end_day.isoformat()),
            ),
        )
    elif history_mode == "observed_additions":
        # Analysis bins span the complete final week even at a midweek cutoff.
        # Clamp the final Sunday so date.max remains a valid supported cutoff.
        final_sunday = date.fromordinal(
            min(date.max.toordinal(), end_day.toordinal() - end_day.weekday() + 6)
        )
        _fill_events(
            db,
            writer,
            db.execute(
                "SELECT path, bin_start, terms_json FROM lexical_events WHERE presence IS NULL "
                "AND bin_start BETWEEN ? AND ? AND observed_at <= ?",
                (
                    first.isoformat(),
                    final_sunday.isoformat(),
                    end_day.isoformat() + "T23:59:59.999999+00:00",
                ),
            ),
        )
    else:
        raise ValueError(f"Unknown lexical history mode: {history_mode}")


def _fill_notes(
    db: sqlite3.Connection, writer: PresenceWriter, rows: Iterator[tuple[str, str]]
) -> None:
    for path, vector in rows:
        db.execute(
            "UPDATE lexical_notes SET presence=? WHERE path=?",
            (writer.encode(json.loads(vector)), path),
        )


def _fill_events(
    db: sqlite3.Connection, writer: PresenceWriter, rows: Iterator[tuple[str, str, str]]
) -> None:
    for path, bin_start, vector in rows:
        db.execute(
            "UPDATE lexical_events SET presence=? WHERE path=? AND bin_start=?",
            (writer.encode(set(json.loads(vector))), path, bin_start),
        )
