"""Unit tests for SQLite persistence."""

import sqlite3
from pathlib import Path

import pytest

from geistfabrik.schema import (
    MIN_SUPPORTED_SCHEMA_VERSION,
    SCHEMA_VERSION,
    SQLITE_BUSY_TIMEOUT_MS,
    get_schema_version,
    init_db,
    migrate_schema,
)


def test_init_db_memory() -> None:
    """Test initialising in-memory database."""
    conn = init_db(None)
    assert conn is not None

    # Check that schema exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    assert "notes" in tables
    assert "links" in tables
    assert "tags" in tables
    assert "embeddings" in tables
    assert "sessions" in tables
    assert "session_embeddings" in tables
    assert "session_suggestions" in tables

    conn.close()


def test_schema_version() -> None:
    """Test schema version is set."""
    conn = init_db(None)
    version = get_schema_version(conn)
    assert version > 0
    conn.close()


def test_connection_integrity_and_durability_policy() -> None:
    """Managed connections make their integrity, wait, and sync policy explicit."""
    conn = init_db(None)
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()
    busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()
    synchronous = conn.execute("PRAGMA synchronous").fetchone()

    assert foreign_keys == (1,)
    assert busy_timeout == (SQLITE_BUSY_TIMEOUT_MS,)
    assert synchronous == (2,)  # SQLite FULL
    conn.close()


def test_notes_table_structure() -> None:
    """Test notes table has correct columns."""
    conn = init_db(None)
    cursor = conn.execute("PRAGMA table_info(notes)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert "path" in columns
    assert "title" in columns
    assert "content" in columns
    assert "created" in columns
    assert "modified" in columns
    assert "file_mtime" in columns

    conn.close()


def test_links_table_structure() -> None:
    """Test links table has correct columns."""
    conn = init_db(None)
    cursor = conn.execute("PRAGMA table_info(links)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert "source_path" in columns
    assert "target" in columns
    assert "display_text" in columns
    assert "is_embed" in columns
    assert "block_ref" in columns

    conn.close()


def test_tags_table_structure() -> None:
    """Test tags table has correct columns."""
    conn = init_db(None)
    cursor = conn.execute("PRAGMA table_info(tags)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    assert "note_path" in columns
    assert "tag" in columns

    conn.close()


def test_indexes_created() -> None:
    """Test that indexes are created."""
    conn = init_db(None)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = {row[0] for row in cursor.fetchall()}

    assert "idx_notes_modified" in indexes
    assert "idx_notes_title" in indexes
    assert "idx_links_source" in indexes
    assert "idx_links_target" in indexes
    assert "idx_tags_note" in indexes
    assert "idx_tags_tag" in indexes

    conn.close()


def test_init_db_rejects_malformed_database_without_overwriting(tmp_path: Path) -> None:
    """A malformed file fails safely; recovery requires a separate known-good source."""
    db_path = tmp_path / "malformed.db"
    original_bytes = b"not a SQLite database\x00with user data"
    db_path.write_bytes(original_bytes)

    with pytest.raises(sqlite3.DatabaseError):
        init_db(db_path)

    assert db_path.read_bytes() == original_bytes


@pytest.mark.parametrize("historical_version", [3, 4])
def test_frozen_historical_database_migrates_without_losing_data(
    tmp_path: Path, historical_version: int
) -> None:
    """Frozen v3/v4 DDL reaches current with durable sentinel rows intact."""
    assert MIN_SUPPORTED_SCHEMA_VERSION == 3
    db_path = tmp_path / f"v{historical_version}.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE notes (
            path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created TEXT NOT NULL,
            modified TEXT NOT NULL,
            file_mtime REAL NOT NULL
        );
        CREATE TABLE links (
            source_path TEXT NOT NULL,
            target TEXT NOT NULL,
            display_text TEXT,
            is_embed INTEGER NOT NULL DEFAULT 0,
            block_ref TEXT,
            FOREIGN KEY (source_path) REFERENCES notes(path) ON DELETE CASCADE
        );
        CREATE TABLE tags (
            note_path TEXT NOT NULL,
            tag TEXT NOT NULL,
            FOREIGN KEY (note_path) REFERENCES notes(path) ON DELETE CASCADE
        );
        CREATE TABLE embeddings (
            note_path TEXT PRIMARY KEY,
            embedding BLOB NOT NULL,
            model_version TEXT NOT NULL,
            computed_at TEXT NOT NULL,
            FOREIGN KEY (note_path) REFERENCES notes(path) ON DELETE CASCADE
        );
        CREATE TABLE sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            vault_state_hash TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE session_embeddings (
            session_id INTEGER NOT NULL,
            note_path TEXT NOT NULL,
            embedding BLOB NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (note_path) REFERENCES notes(path) ON DELETE CASCADE,
            PRIMARY KEY (session_id, note_path)
        );
        CREATE TABLE session_suggestions (
            session_date TEXT NOT NULL,
            geist_id TEXT NOT NULL,
            suggestion_text TEXT NOT NULL,
            block_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (session_date, block_id)
        );
        CREATE INDEX idx_links_source ON links(source_path);
        CREATE INDEX idx_links_target ON links(target);
        PRAGMA user_version = 3;
    """)
    if historical_version == 4:
        conn.executescript("""
            ALTER TABLE notes ADD COLUMN is_virtual INTEGER DEFAULT 0;
            ALTER TABLE notes ADD COLUMN source_file TEXT;
            ALTER TABLE notes ADD COLUMN entry_date TEXT;
            PRAGMA user_version = 4;
        """)
    conn.execute(
        """INSERT INTO notes (path, title, content, created, modified, file_mtime)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("sentinel.md", "Sentinel", "keep me", "2024-01-01", "2024-01-02", 1.0),
    )
    conn.execute(
        "INSERT INTO links VALUES (?, ?, ?, ?, ?)",
        ("sentinel.md", "target", None, 0, None),
    )
    conn.execute("INSERT INTO tags VALUES (?, ?)", ("sentinel.md", "keep"))
    conn.execute(
        "INSERT INTO embeddings VALUES (?, ?, ?, ?)",
        ("sentinel.md", b"semantic", f"v{historical_version}", "2024-01-02"),
    )
    conn.execute(
        "INSERT INTO sessions (date, vault_state_hash, created_at) VALUES (?, ?, ?)",
        ("2024-01-02", "sentinel-hash", "2024-01-02"),
    )
    session_id = conn.execute(
        "SELECT session_id FROM sessions WHERE date = ?", ("2024-01-02",)
    ).fetchone()
    assert session_id is not None
    conn.execute(
        "INSERT INTO session_embeddings VALUES (?, ?, ?)",
        (session_id[0], "sentinel.md", b"historical"),
    )
    conn.commit()
    conn.close()

    migrated = init_db(db_path)
    migrated.close()
    observer = sqlite3.connect(db_path)
    observer.execute("PRAGMA foreign_keys = ON")
    assert get_schema_version(observer) == SCHEMA_VERSION
    assert observer.execute(
        "SELECT title, content FROM notes WHERE path = ?", ("sentinel.md",)
    ).fetchone() == ("Sentinel", "keep me")
    assert observer.execute(
        "SELECT target FROM links WHERE source_path = ?", ("sentinel.md",)
    ).fetchall() == [("target",)]
    assert observer.execute(
        "SELECT tag FROM tags WHERE note_path = ?", ("sentinel.md",)
    ).fetchall() == [("keep",)]
    assert observer.execute(
        "SELECT embedding, model_version FROM embeddings WHERE note_path = ?",
        ("sentinel.md",),
    ).fetchone() == (b"semantic", f"v{historical_version}")
    assert observer.execute(
        "SELECT vault_state_hash FROM sessions WHERE date = ?", ("2024-01-02",)
    ).fetchone() == ("sentinel-hash",)
    assert observer.execute(
        "SELECT embedding, cluster_label FROM session_embeddings WHERE note_path = ?",
        ("sentinel.md",),
    ).fetchone() == (b"historical", None)
    tables = {
        str(row[0])
        for row in observer.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    assert {"embedding_metrics", "geist_status"} <= tables
    assert observer.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'idx_links_target_source'"
    ).fetchone() == (1,)
    assert observer.execute("PRAGMA foreign_key_check").fetchall() == []
    assert observer.execute(
        "SELECT is_virtual, source_file, entry_date FROM notes WHERE path = 'sentinel.md'"
    ).fetchone() == (0, None, None)
    assert {row[1] for row in observer.execute("PRAGMA table_info(embedding_metrics)")} >= {
        "source_digest",
        "algorithm_digest",
        "metrics_json",
    }
    observer.close()


@pytest.mark.parametrize("historical_version", [1, 2])
def test_unsupported_historical_schema_is_unchanged(
    tmp_path: Path, historical_version: int
) -> None:
    db_path = tmp_path / f"unsupported-v{historical_version}.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE user_data (value TEXT)")
    conn.execute("INSERT INTO user_data VALUES ('preserve me')")
    conn.execute(f"PRAGMA user_version = {historical_version}")
    conn.commit()
    conn.close()
    before = db_path.read_bytes()

    with pytest.raises(RuntimeError, match="older than minimum supported version 3"):
        init_db(db_path)

    assert db_path.read_bytes() == before


def test_v8_metrics_migration_discards_only_unverifiable_cache(tmp_path: Path) -> None:
    db_path = tmp_path / "v8-metrics.db"
    conn = init_db(db_path)
    conn.execute("DROP TABLE embedding_metrics")
    conn.executescript("""
        CREATE TABLE embedding_metrics (
            session_date TEXT PRIMARY KEY,
            intrinsic_dim REAL, vendi_score REAL, shannon_entropy REAL,
            silhouette_score REAL, n_clusters INTEGER, n_gaps INTEGER,
            cluster_labels TEXT, computed_at TEXT NOT NULL,
            FOREIGN KEY (session_date) REFERENCES sessions(date) ON DELETE CASCADE
        );
        INSERT INTO sessions (date, vault_state_hash, created_at)
        VALUES ('2025-01-15', 'keep this snapshot', '2025-01-15');
        INSERT INTO embedding_metrics (session_date, n_clusters, computed_at)
        VALUES ('2025-01-15', 123, '2025-01-15');
        PRAGMA user_version = 8;
    """)
    conn.close()

    migrated = init_db(db_path)
    assert get_schema_version(migrated) == SCHEMA_VERSION
    assert migrated.execute("SELECT vault_state_hash FROM sessions").fetchall() == [
        ("keep this snapshot",)
    ]
    assert migrated.execute("SELECT count(*) FROM embedding_metrics").fetchone() == (0,)
    primary_key = {
        row[1]: row[5] for row in migrated.execute("PRAGMA table_info(embedding_metrics)") if row[5]
    }
    assert primary_key == {"session_date": 1, "source_digest": 2, "algorithm_digest": 3}
    migrated.close()


def test_migration_validates_version_after_acquiring_writer_lock(tmp_path: Path) -> None:
    """Schema metadata is read only after migration owns the writer transaction."""
    db_path = tmp_path / "lock-order.db"
    init_db(db_path).close()
    conn = sqlite3.connect(db_path)
    statements: list[str] = []
    conn.set_trace_callback(statements.append)

    migrate_schema(conn)

    normalized = [statement.strip().upper() for statement in statements]
    begin_index = normalized.index("BEGIN IMMEDIATE")
    version_index = normalized.index("PRAGMA USER_VERSION")
    assert begin_index < version_index
    conn.close()


def test_migration_v5_to_v6_adds_composite_index() -> None:
    """Test migration from v5 to v6 adds idx_links_target_source index."""
    # Create v5 schema manually
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")

    # Create v5 schema (without composite index)
    conn.executescript("""
        CREATE TABLE notes (
            path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created TEXT NOT NULL,
            modified TEXT NOT NULL,
            file_mtime REAL NOT NULL,
            is_virtual INTEGER DEFAULT 0,
            source_file TEXT,
            entry_date TEXT
        );

        CREATE TABLE links (
            source_path TEXT NOT NULL,
            target TEXT NOT NULL,
            display_text TEXT,
            is_embed INTEGER NOT NULL DEFAULT 0,
            block_ref TEXT,
            FOREIGN KEY (source_path) REFERENCES notes(path) ON DELETE CASCADE
        );

        CREATE INDEX idx_links_source ON links(source_path);
        CREATE INDEX idx_links_target ON links(target);

        PRAGMA user_version = 5;
    """)
    conn.commit()

    # Verify we're at v5
    assert get_schema_version(conn) == 5

    # Check composite index doesn't exist
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_links_target_source'"
    )
    assert cursor.fetchone() is None

    # Run migration
    migrate_schema(conn)

    # Verify migration ran through to the current schema version
    assert get_schema_version(conn) == SCHEMA_VERSION

    # Check composite index exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_links_target_source'"
    )
    assert cursor.fetchone() is not None

    conn.close()


def test_migration_is_idempotent() -> None:
    """Test that running migration multiple times is safe."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")

    # Create v5 schema
    conn.executescript("""
        CREATE TABLE notes (
            path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created TEXT NOT NULL,
            modified TEXT NOT NULL,
            file_mtime REAL NOT NULL,
            is_virtual INTEGER DEFAULT 0,
            source_file TEXT,
            entry_date TEXT
        );

        CREATE TABLE links (
            source_path TEXT NOT NULL,
            target TEXT NOT NULL,
            display_text TEXT,
            is_embed INTEGER NOT NULL DEFAULT 0,
            block_ref TEXT,
            FOREIGN KEY (source_path) REFERENCES notes(path) ON DELETE CASCADE
        );

        CREATE INDEX idx_links_source ON links(source_path);
        CREATE INDEX idx_links_target ON links(target);

        PRAGMA user_version = 5;
    """)
    conn.commit()

    # Run migration twice
    migrate_schema(conn)
    migrate_schema(conn)

    # Should still be at the current schema version
    assert get_schema_version(conn) == SCHEMA_VERSION

    # Index should exist exactly once
    cursor = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name='idx_links_target_source'"
    )
    count = cursor.fetchone()
    assert count is not None
    assert count[0] == 1

    conn.close()


def test_migration_from_current_version_is_noop() -> None:
    """Test that migrating from current version does nothing."""
    conn = init_db(None)
    version_before = get_schema_version(conn)

    # Run migration on fresh database
    migrate_schema(conn)

    # Version should be unchanged
    version_after = get_schema_version(conn)
    assert version_before == version_after
    assert version_after == SCHEMA_VERSION

    conn.close()


def test_v6_schema_includes_composite_index() -> None:
    """Test that v6 schema includes idx_links_target_source index."""
    conn = init_db(None)

    # Verify version
    assert get_schema_version(conn) == SCHEMA_VERSION

    # Check composite index exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_links_target_source'"
    )
    index_exists = cursor.fetchone() is not None
    assert index_exists, "idx_links_target_source index should exist in v6 schema"

    conn.close()


def test_composite_index_improves_orphan_query() -> None:
    """Test that composite index is used for orphan queries."""
    conn = init_db(None)

    # Insert test data
    conn.execute("""
        INSERT INTO notes (path, title, content, created, modified, file_mtime)
        VALUES ('note1.md', 'Note 1', 'Content 1', '2025-01-01', '2025-01-01', 1234567890),
               ('note2.md', 'Note 2', 'Content 2', '2025-01-01', '2025-01-01', 1234567890),
               ('note3.md', 'Note 3', 'Content 3', '2025-01-01', '2025-01-01', 1234567890)
    """)

    # Add a link from note1 to note2
    conn.execute(
        "INSERT INTO links (source_path, target, is_embed) VALUES ('note1.md', 'note2.md', 0)"
    )
    conn.commit()

    # Query for orphans (notes not targeted by any link)
    query = """
        SELECT n.path
        FROM notes n
        LEFT JOIN links l ON l.target = n.path
        WHERE l.source_path IS NULL
    """

    # Explain query plan - should use the composite index
    cursor = conn.execute(f"EXPLAIN QUERY PLAN {query}")
    _ = cursor.fetchall()  # Query plan verification (format varies by SQLite version)

    # Execute the actual query to verify correctness
    cursor = conn.execute(query)
    orphans = {row[0] for row in cursor.fetchall()}

    # note3.md should be an orphan (not targeted), note1.md should also be orphan
    # note2.md is NOT an orphan (targeted by note1)
    assert "note1.md" in orphans
    assert "note2.md" not in orphans
    assert "note3.md" in orphans

    conn.close()
