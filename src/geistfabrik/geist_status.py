"""Persistent per-geist failure tracking (the spec's geist_status table).

A geist that keeps failing is disabled after N *consecutive* failures, and the
disabled state persists across sessions. This persistence is the whole point:
the executor is rebuilt fresh on every CLI command and each geist runs once per
session, so an in-memory counter can never reach the threshold (it was dead
code). A successful run resets the count (transient failures should not
permanently penalise a geist).

Per the two-layer rule, geists never touch this store - only GeistExecutor
does, via constructor injection. The threshold (max_failures) lives in config;
the state lives here in the vault DB.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

_MAX_ERROR_CHARS = 2000


@dataclass
class GeistStatus:
    """A geist's persisted failure state."""

    geist_id: str
    failure_count: int
    disabled: bool
    last_error: str | None = None


class GeistStatusStore:
    """Reads and writes per-geist failure state in the geist_status table."""

    def __init__(self, db: sqlite3.Connection):
        """Initialise the store.

        Args:
            db: The vault database connection (already has the geist_status
                table from the schema/migration).
        """
        self.db = db

    def load(self) -> dict[str, GeistStatus]:
        """Load all recorded geist statuses.

        Returns:
            Mapping of geist_id -> GeistStatus for every geist with a row.
            Geists with no row have never failed (count 0, enabled).
        """
        cursor = self.db.execute(
            "SELECT geist_id, failure_count, disabled, last_error FROM geist_status"
        )
        return {
            row[0]: GeistStatus(
                geist_id=row[0],
                failure_count=int(row[1]),
                disabled=bool(row[2]),
                last_error=row[3],
            )
            for row in cursor.fetchall()
        }

    def record_failure(self, geist_id: str, error: str, max_failures: int) -> GeistStatus:
        """Increment a geist's consecutive-failure count, disabling at the cap.

        Args:
            geist_id: The geist that failed
            error: Error message/summary (truncated when stored)
            max_failures: Disable the geist once the count reaches this

        Returns:
            The new persisted GeistStatus (with the incremented count and the
            resulting disabled flag).
        """
        row = self.db.execute(
            "SELECT failure_count FROM geist_status WHERE geist_id = ?", (geist_id,)
        ).fetchone()
        new_count = (int(row[0]) if row else 0) + 1
        disabled = new_count >= max_failures
        truncated = error[:_MAX_ERROR_CHARS]
        self.db.execute(
            """
            INSERT OR REPLACE INTO geist_status
                (geist_id, failure_count, disabled, last_error, updated)
            VALUES (?, ?, ?, ?, ?)
            """,
            (geist_id, new_count, int(disabled), truncated, datetime.now().isoformat()),
        )
        self.db.commit()
        return GeistStatus(geist_id, new_count, disabled, truncated)

    def record_success(self, geist_id: str) -> None:
        """Reset a geist's failure state after a successful run.

        Consecutive-failure semantics: one good run clears the count and
        re-enables the geist. No row is created for geists that never failed.

        Args:
            geist_id: The geist that succeeded
        """
        self.db.execute(
            "UPDATE geist_status SET failure_count = 0, disabled = 0, updated = ? "
            "WHERE geist_id = ?",
            (datetime.now().isoformat(), geist_id),
        )
        self.db.commit()

    def reset(self, geist_id: str) -> None:
        """Explicitly clear a geist's failure state (manual re-enable).

        Args:
            geist_id: The geist to re-enable
        """
        self.db.execute("DELETE FROM geist_status WHERE geist_id = ?", (geist_id,))
        self.db.commit()
