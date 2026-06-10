"""Regression tests for per-session cluster label persistence (schema v7).

cluster_evolution_tracker compares each note's current cluster against the
label stored in session_embeddings.cluster_label for a previous session. The
column historically did not exist and nothing wrote it, so the reader raised
sqlite3.OperationalError on every run and the geist never worked. These tests
lock down the schema column, the v6->v7 migration, the writer
(VaultContext.persist_cluster_labels) and the reader
(previous_cluster_label_for_note).
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest

from geistfabrik import Session, Vault
from geistfabrik.schema import SCHEMA_VERSION, get_schema_version, init_db, migrate_schema
from geistfabrik.vault_context import VaultContext


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


class TestSchemaV7:
    def test_fresh_schema_has_cluster_label_column(self):
        db = init_db(None)
        assert "cluster_label" in _columns(db, "session_embeddings")
        assert get_schema_version(db) == SCHEMA_VERSION

    def test_migration_from_v6_adds_cluster_label(self):
        """A v6 database (no cluster_label column) is migrated in place."""
        db = sqlite3.connect(":memory:")
        db.execute(
            """
            CREATE TABLE session_embeddings (
                session_id INTEGER NOT NULL,
                note_path TEXT NOT NULL,
                embedding BLOB NOT NULL,
                PRIMARY KEY (session_id, note_path)
            )
            """
        )
        db.execute("PRAGMA user_version = 6")
        db.commit()
        assert "cluster_label" not in _columns(db, "session_embeddings")

        migrate_schema(db)

        assert "cluster_label" in _columns(db, "session_embeddings")
        assert get_schema_version(db) == SCHEMA_VERSION

    def test_migration_is_idempotent(self):
        db = init_db(None)  # already v7 with the column
        migrate_schema(db)  # must not raise on re-run
        assert "cluster_label" in _columns(db, "session_embeddings")


@pytest.fixture
def context_with_two_sessions():
    """VaultContext for session 2 of a vault that already had session 1."""
    with TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        for i in range(6):
            (vault_path / f"note{i}.md").write_text(f"# Note {i}\nContent about topic {i}.")

        vault = Vault(vault_path)
        vault.sync()

        session1 = Session(datetime(2023, 6, 1), vault.db)
        session1.compute_embeddings(vault.all_notes())
        session2 = Session(datetime(2023, 6, 15), vault.db)
        session2.compute_embeddings(vault.all_notes())

        try:
            yield vault, session1, session2
        finally:
            vault.close()


class TestPersistAndRead:
    def test_reader_returns_none_instead_of_raising(self, context_with_two_sessions):
        """Regression: this call used to raise OperationalError (no such column)."""
        vault, session1, session2 = context_with_two_sessions
        ctx = VaultContext(vault, session2)
        note = ctx.notes()[0]
        assert ctx.previous_cluster_label_for_note(note, session1.session_id) is None

    def test_persisted_label_is_readable_by_later_session(self, context_with_two_sessions):
        vault, session1, session2 = context_with_two_sessions

        # Session 1 persists its assignments...
        ctx1 = VaultContext(vault, session1)
        note = ctx1.notes()[0]
        ctx1.persist_cluster_labels({note.path: "ai, ml, agents"})

        # ...and session 2 can read them back for comparison.
        ctx2 = VaultContext(vault, session2)
        assert ctx2.previous_cluster_label_for_note(note, session1.session_id) == "ai, ml, agents"
        # Unlabelled notes stay None (noise/unclustered).
        other = next(n for n in ctx2.notes() if n.path != note.path)
        assert ctx2.previous_cluster_label_for_note(other, session1.session_id) is None

    def test_persist_only_touches_own_session(self, context_with_two_sessions):
        vault, session1, session2 = context_with_two_sessions
        ctx2 = VaultContext(vault, session2)
        note = ctx2.notes()[0]

        ctx2.persist_cluster_labels({note.path: "later topics"})

        # Session 1's row for the same note is untouched.
        assert ctx2.previous_cluster_label_for_note(note, session1.session_id) is None
        assert ctx2.previous_cluster_label_for_note(note, session2.session_id) == "later topics"

    def test_persist_empty_assignments_is_noop(self, context_with_two_sessions):
        vault, _session1, session2 = context_with_two_sessions
        ctx = VaultContext(vault, session2)
        ctx.persist_cluster_labels({})  # must not raise

    def test_get_clusters_persists_labels_when_clusters_form(self, context_with_two_sessions):
        """When HDBSCAN finds clusters, the assignments land in the database."""
        vault, _session1, session2 = context_with_two_sessions
        ctx = VaultContext(vault, session2)

        clusters = ctx.get_clusters(min_size=2)

        stored = vault.db.execute(
            "SELECT COUNT(*) FROM session_embeddings "
            "WHERE session_id = ? AND cluster_label IS NOT NULL",
            (session2.session_id,),
        ).fetchone()[0]
        clustered_note_count = sum(len(c.notes) for c in clusters.values())
        assert stored == clustered_note_count

    def test_cluster_evolution_tracker_runs_without_error(self, context_with_two_sessions):
        """End-to-end regression: the geist must not raise with >=2 sessions.

        Before the fix it raised sqlite3.OperationalError whenever it got far
        enough to query previous labels; with stub embeddings clustering may
        find nothing (returning []), but it must never crash.
        """
        from geistfabrik.default_geists.code import cluster_evolution_tracker

        vault, _session1, session2 = context_with_two_sessions
        ctx = VaultContext(vault, session2)
        suggestions = cluster_evolution_tracker.suggest(ctx)
        assert isinstance(suggestions, list)

    def test_embeddings_unaffected_by_label_update(self, context_with_two_sessions):
        """Writing labels must not corrupt the stored embedding blobs."""
        vault, _session1, session2 = context_with_two_sessions
        ctx = VaultContext(vault, session2)
        note = ctx.notes()[0]

        before = ctx.get_embedding(note.path)
        ctx.persist_cluster_labels({note.path: "anything"})
        after = ctx.get_embedding(note.path)

        assert before is not None and after is not None
        assert np.array_equal(before, after)
