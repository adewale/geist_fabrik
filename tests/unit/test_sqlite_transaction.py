"""Tests for explicit SQLite transaction ownership."""

import sqlite3

import pytest

from geistfabrik.sqlite_transaction import owned_transaction


class CommitFailingConnection(sqlite3.Connection):
    """Real SQLite connection with one deterministic commit fault."""

    fail_next_commit = False

    def commit(self) -> None:
        if self.fail_next_commit:
            self.fail_next_commit = False
            raise sqlite3.OperationalError("injected commit failure")
        super().commit()


def test_owned_transaction_rolls_back_commit_failure() -> None:
    """A failed commit leaves neither pending nor externally visible work."""
    db = sqlite3.connect(":memory:", factory=CommitFailingConnection)
    db.execute("CREATE TABLE values_for_test (value TEXT NOT NULL)")
    db.commit()
    db.fail_next_commit = True

    with pytest.raises(sqlite3.OperationalError, match="injected commit failure"):
        with owned_transaction(db, "test write"):
            db.execute("INSERT INTO values_for_test VALUES ('pending')")

    assert db.in_transaction is False
    assert db.execute("SELECT value FROM values_for_test").fetchall() == []
    db.close()


def test_owned_transaction_rejects_and_preserves_callers_transaction() -> None:
    """A writer cannot silently commit or roll back work it does not own."""
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE values_for_test (value TEXT NOT NULL)")
    db.commit()
    db.execute("BEGIN")
    db.execute("INSERT INTO values_for_test VALUES ('callers')")

    with pytest.raises(RuntimeError, match="requires an idle SQLite connection"):
        with owned_transaction(db, "nested write"):
            db.execute("INSERT INTO values_for_test VALUES ('nested')")

    assert db.in_transaction is True
    assert db.execute("SELECT value FROM values_for_test").fetchall() == [("callers",)]
    db.rollback()
    assert db.execute("SELECT value FROM values_for_test").fetchall() == []
    db.close()
