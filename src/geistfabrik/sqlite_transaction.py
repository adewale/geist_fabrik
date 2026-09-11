"""Explicit transaction ownership for shared GeistFabrik SQLite connections."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def owned_transaction(db: sqlite3.Connection, operation: str) -> Iterator[None]:
    """Run one top-level write operation in an exception-atomic transaction.

    GeistFabrik shares one connection between several components during a CLI
    command. A top-level writer must therefore start from an idle connection and
    commit only its own work. Rejecting nested/pre-existing transactions prevents
    one component from accidentally committing another component's pending rows.

    Args:
        db: SQLite connection whose transaction is being owned.
        operation: Human-readable operation name used in errors.

    Raises:
        RuntimeError: If another transaction is already active, or rollback of a
            failed operation itself fails.
    """
    if db.in_transaction:
        raise RuntimeError(f"{operation} requires an idle SQLite connection")

    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.commit()
    except BaseException:
        if db.in_transaction:
            try:
                db.rollback()
            except sqlite3.Error as rollback_error:
                raise RuntimeError(
                    f"{operation} failed and its SQLite transaction could not be rolled back"
                ) from rollback_error
        raise
