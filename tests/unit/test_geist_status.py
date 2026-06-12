"""Tests for persistent per-geist failure tracking (geist_status, schema v8).

Before this, GeistMetadata.failure_count lived only in memory and the executor
was rebuilt every command, so the documented "disable after N failures" could
never trigger in real use. These tests pin the store semantics (consecutive
failures, reset on success, persistence) and the executor wiring (a geist
disabled in a prior session stays disabled in the next).
"""

import sqlite3
from pathlib import Path

import pytest

from geistfabrik.geist_executor import GeistExecutor
from geistfabrik.geist_status import GeistStatusStore
from geistfabrik.schema import SCHEMA_VERSION, get_schema_version, init_db, migrate_schema


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


class TestSchemaV8:
    def test_fresh_schema_has_geist_status(self):
        db = init_db(None)
        assert "geist_status" in {
            r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert get_schema_version(db) == SCHEMA_VERSION
        assert _columns(db, "geist_status") == {
            "geist_id",
            "failure_count",
            "disabled",
            "last_error",
            "updated",
        }

    def test_migration_from_v7_adds_table(self):
        db = sqlite3.connect(":memory:")
        db.execute("PRAGMA user_version = 7")
        db.commit()
        migrate_schema(db)
        assert get_schema_version(db) == SCHEMA_VERSION
        # store works against the migrated DB
        GeistStatusStore(db).record_failure("g", "boom", max_failures=3)


class TestGeistStatusStore:
    @pytest.fixture
    def store(self):
        return GeistStatusStore(init_db(None))

    def test_failure_increments_until_disabled(self, store):
        s1 = store.record_failure("g", "err1", max_failures=3)
        assert (s1.failure_count, s1.disabled) == (1, False)
        s2 = store.record_failure("g", "err2", max_failures=3)
        assert (s2.failure_count, s2.disabled) == (2, False)
        s3 = store.record_failure("g", "err3", max_failures=3)
        assert (s3.failure_count, s3.disabled) == (3, True)
        assert store.load()["g"].disabled is True
        assert store.load()["g"].last_error == "err3"

    def test_success_resets_consecutive_count(self, store):
        store.record_failure("g", "e", max_failures=3)
        store.record_failure("g", "e", max_failures=3)
        store.record_success("g")
        assert store.load()["g"].failure_count == 0
        assert store.load()["g"].disabled is False
        # After a reset it takes the full N failures again to disable.
        store.record_failure("g", "e", max_failures=3)
        assert store.load()["g"].disabled is False

    def test_reset_clears_row(self, store):
        store.record_failure("g", "e", max_failures=1)  # disabled immediately
        assert store.load()["g"].disabled is True
        store.reset("g")
        assert "g" not in store.load()

    def test_load_empty(self, store):
        assert store.load() == {}

    def test_persists_across_store_instances(self):
        db = init_db(None)
        GeistStatusStore(db).record_failure("g", "e", max_failures=2)
        GeistStatusStore(db).record_failure("g", "e", max_failures=2)
        # A brand-new store over the same DB sees the disabled state.
        assert GeistStatusStore(db).load()["g"].disabled is True


# --- executor integration ---

GOOD_GEIST = "def suggest(vault):\n    return []\n"
BAD_GEIST = "def suggest(vault):\n    raise ValueError('boom')\n"


def _write_geist(directory: Path, name: str, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.py").write_text(body)


class _StubContext:
    """Minimal stand-in for VaultContext (failing geist never uses it)."""


class TestExecutorPersistence:
    def test_disabled_state_persists_into_a_new_executor(self, tmp_path):
        db = init_db(None)
        store = GeistStatusStore(db)
        geists_dir = tmp_path / "geists"
        _write_geist(geists_dir, "boom", BAD_GEIST)
        ctx = _StubContext()

        # Session 1: the geist fails three times across three "sessions"
        # (each a fresh executor over the SAME store), reaching the cap.
        for _ in range(3):
            ex = GeistExecutor(geists_dir, timeout=5, max_failures=3, status_store=store)
            ex.load_geists()
            ex.execute_geist("boom", ctx)  # type: ignore[arg-type]

        # Next session: a fresh executor seeds is_enabled=False from the store
        # and skips the geist without executing it.
        ex = GeistExecutor(geists_dir, timeout=5, max_failures=3, status_store=store)
        ex.load_geists()
        assert ex.geists["boom"].is_enabled is False
        ex.execute_geist("boom", ctx)  # type: ignore[arg-type]
        assert any(
            e.get("geist_id") == "boom" and e.get("status") == "skipped" for e in ex.execution_log
        )

    def test_success_reenables_after_failures(self, tmp_path):
        db = init_db(None)
        store = GeistStatusStore(db)
        geists_dir = tmp_path / "geists"

        # Two failures recorded out of band, then the geist is "fixed".
        store.record_failure("flip", "e", max_failures=3)
        store.record_failure("flip", "e", max_failures=3)
        _write_geist(geists_dir, "flip", GOOD_GEIST)

        ex = GeistExecutor(geists_dir, timeout=5, max_failures=3, status_store=store)
        ex.load_geists()
        assert ex.geists["flip"].failure_count == 2  # seeded from store
        ex.execute_geist("flip", _StubContext())  # type: ignore[arg-type]

        # A successful run clears the persisted count.
        assert store.load().get("flip", None) is None or store.load()["flip"].failure_count == 0

    def test_without_store_falls_back_to_in_memory(self, tmp_path):
        geists_dir = tmp_path / "geists"
        _write_geist(geists_dir, "boom", BAD_GEIST)
        ex = GeistExecutor(geists_dir, timeout=5, max_failures=2)  # no store
        ex.load_geists()
        ctx = _StubContext()
        ex.execute_geist("boom", ctx)  # type: ignore[arg-type]
        assert ex.geists["boom"].is_enabled is True  # 1 < 2
        ex.execute_geist("boom", ctx)  # type: ignore[arg-type]
        assert ex.geists["boom"].is_enabled is False  # 2 >= 2 (in-memory)
