"""SQLite schema for GeistFabrik."""

import sqlite3
from pathlib import Path

# Schema version for migrations
# Version 3: Removed unused `suggestions` and `suggestion_notes` tables
# Version 4: Added support for date-collection notes (virtual entries)
# Version 5: Added embedding_metrics table for stats command caching
# Version 6: Added composite index for orphans query performance
# Version 7: Added session_embeddings.cluster_label (per-session cluster assignments)
# Version 8: Added geist_status table (persistent per-geist failure tracking)
SCHEMA_VERSION = 8
SQLITE_BUSY_TIMEOUT_MS = 5_000

SCHEMA_SQL = """
-- Notes table
CREATE TABLE IF NOT EXISTS notes (
    path TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created TEXT NOT NULL,
    modified TEXT NOT NULL,
    file_mtime REAL NOT NULL,  -- For incremental sync
    is_virtual INTEGER DEFAULT 0,  -- True for virtual entries from date-collection notes
    source_file TEXT,  -- Original file path for virtual entries
    entry_date TEXT  -- Date extracted from heading for virtual entries
);

CREATE INDEX IF NOT EXISTS idx_notes_modified ON notes(modified);
CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title);
CREATE INDEX IF NOT EXISTS idx_notes_source_file ON notes(source_file);
CREATE INDEX IF NOT EXISTS idx_notes_entry_date ON notes(entry_date);

-- Links table
CREATE TABLE IF NOT EXISTS links (
    source_path TEXT NOT NULL,
    target TEXT NOT NULL,
    display_text TEXT,
    is_embed INTEGER NOT NULL DEFAULT 0,
    block_ref TEXT,
    FOREIGN KEY (source_path) REFERENCES notes(path) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_path);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target);
CREATE INDEX IF NOT EXISTS idx_links_target_source ON links(target, source_path);

-- Tags table
CREATE TABLE IF NOT EXISTS tags (
    note_path TEXT NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (note_path) REFERENCES notes(path) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tags_note ON tags(note_path);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

-- Embeddings table (note-level embeddings)
CREATE TABLE IF NOT EXISTS embeddings (
    note_path TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model_version TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    FOREIGN KEY (note_path) REFERENCES notes(path) ON DELETE CASCADE
);

-- Sessions table (for temporal tracking)
CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    vault_state_hash TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);

-- Session embeddings table (temporal embeddings)
-- cluster_label records which semantic cluster the note belonged to in that
-- session (written when clusters are computed; NULL for noise/unclustered).
-- It is what lets cluster_evolution_tracker compare assignments across time.
CREATE TABLE IF NOT EXISTS session_embeddings (
    session_id INTEGER NOT NULL,
    note_path TEXT NOT NULL,
    embedding BLOB NOT NULL,
    cluster_label TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY (note_path) REFERENCES notes(path) ON DELETE CASCADE,
    PRIMARY KEY (session_id, note_path)
);

CREATE INDEX IF NOT EXISTS idx_session_embeddings_path ON session_embeddings(note_path);

-- Session suggestions (for novelty filtering and history tracking)
-- NOTE: This table serves the same purpose as the previously-defined
-- "suggestions" + "suggestion_notes" tables but with a denormalized design.
-- The normalised tables were never used and have been removed (see commit history).
CREATE TABLE IF NOT EXISTS session_suggestions (
    session_date TEXT NOT NULL,
    geist_id TEXT NOT NULL,
    suggestion_text TEXT NOT NULL,
    block_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_date, block_id)
);

CREATE INDEX IF NOT EXISTS idx_session_suggestions_date ON session_suggestions(session_date);
CREATE INDEX IF NOT EXISTS idx_session_suggestions_geist ON session_suggestions(geist_id);

-- Embedding metrics cache (for stats command)
CREATE TABLE IF NOT EXISTS embedding_metrics (
    session_date TEXT PRIMARY KEY,
    intrinsic_dim REAL,
    vendi_score REAL,
    shannon_entropy REAL,
    silhouette_score REAL,
    n_clusters INTEGER,
    n_gaps INTEGER,
    cluster_labels TEXT,  -- JSON: {0: "ml, neural, networks", 1: "philosophy, ethics"}
    computed_at TEXT NOT NULL,
    FOREIGN KEY (session_date) REFERENCES sessions(date) ON DELETE CASCADE
);

-- Geist status: persistent per-geist failure tracking. A geist is disabled
-- after N consecutive failures (threshold from config); a successful run
-- resets the count. State persists across sessions because the executor is
-- rebuilt every command (an in-memory counter could never reach the cap).
CREATE TABLE IF NOT EXISTS geist_status (
    geist_id TEXT PRIMARY KEY,
    failure_count INTEGER NOT NULL DEFAULT 0,
    disabled INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    updated TEXT
);
"""


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Initialise a database in one owned schema transaction.

    Existing supported schemas are migrated, reconciled with ``SCHEMA_SQL``,
    and stamped current only after every DDL statement succeeds. On failure,
    the whole upgrade is rolled back and the newly opened connection is closed.
    """
    if db_path is None:
        conn = sqlite3.connect(":memory:")
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))

    try:
        # Per-connection policy: enforce relational integrity, wait briefly for
        # the single writer, and require full fsync discipline at transaction
        # boundaries. Journal mode remains compatible with either SQLite's
        # rollback journal or an existing WAL database.
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA synchronous = FULL")
        _upgrade_and_reconcile(conn, allow_empty_unversioned=True)
        return conn
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        conn.close()
        raise


def _execute_schema_sql(conn: sqlite3.Connection) -> None:
    """Execute ``SCHEMA_SQL`` statement-by-statement without implicit commits."""
    statement = ""
    for line in SCHEMA_SQL.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            conn.execute(statement)
            statement = ""
    if statement.strip():
        raise RuntimeError("Incomplete statement in SCHEMA_SQL")


def _upgrade_and_reconcile(
    conn: sqlite3.Connection, *, allow_empty_unversioned: bool
) -> None:
    """Validate, migrate, and reconcile while holding the schema writer lock."""
    if conn.in_transaction:
        raise RuntimeError("Schema migration requires ownership of the SQLite transaction")
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Read both structural and version metadata only after acquiring the
        # writer lock. Otherwise a newer process can stamp a future version
        # between validation and this process's final user_version write.
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        current_version = get_schema_version(conn)
        if current_version > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {current_version} is newer than supported "
                f"version {SCHEMA_VERSION}; refusing to downgrade"
            )
        if current_version == 0 and (tables or not allow_empty_unversioned):
            if tables:
                raise RuntimeError(
                    "Existing database has application tables but no supported schema version; "
                    "refusing to modify an ambiguous legacy database"
                )
            raise RuntimeError("Cannot migrate an unversioned application database")

        if current_version > 0:
            _apply_ordered_migrations(conn, current_version)
        # user_version records migration intent, not structural truth. Repair
        # additive columns even when an interrupted/buggy older release stamped
        # a database current before completing its DDL.
        _reconcile_additive_columns(conn)
        _execute_schema_sql(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    except BaseException:
        if conn.in_transaction:
            conn.rollback()
        raise


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version."""
    cursor = conn.execute("PRAGMA user_version")
    result = cursor.fetchone()
    if result is None:
        return 0
    return int(result[0])


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Migrate and reconcile a supported database in one owned transaction."""
    _upgrade_and_reconcile(conn, allow_empty_unversioned=False)


def _reconcile_additive_columns(conn: sqlite3.Connection) -> None:
    """Repair columns that ``CREATE TABLE IF NOT EXISTS`` cannot reconcile."""
    notes_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes'"
    ).fetchone()
    if notes_table is not None:
        note_columns = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
        for name, declaration in (
            ("is_virtual", "INTEGER DEFAULT 0"),
            ("source_file", "TEXT"),
            ("entry_date", "TEXT"),
        ):
            if name not in note_columns:
                conn.execute(f"ALTER TABLE notes ADD COLUMN {name} {declaration}")

    embeddings_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_embeddings'"
    ).fetchone()
    if embeddings_table is not None:
        embedding_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(session_embeddings)")
        }
        if "cluster_label" not in embedding_columns:
            conn.execute("ALTER TABLE session_embeddings ADD COLUMN cluster_label TEXT")


def _apply_ordered_migrations(conn: sqlite3.Connection, current_version: int) -> None:
    """Apply required pre-reconciliation DDL without committing or stamping."""
    if current_version < 4:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(notes)").fetchall()}
        if "is_virtual" not in columns:
            conn.execute("ALTER TABLE notes ADD COLUMN is_virtual INTEGER DEFAULT 0")
        if "source_file" not in columns:
            conn.execute("ALTER TABLE notes ADD COLUMN source_file TEXT")
        if "entry_date" not in columns:
            conn.execute("ALTER TABLE notes ADD COLUMN entry_date TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_source_file ON notes(source_file)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_entry_date ON notes(entry_date)")

    if current_version < 5:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embedding_metrics (
                session_date TEXT PRIMARY KEY,
                intrinsic_dim REAL,
                vendi_score REAL,
                shannon_entropy REAL,
                silhouette_score REAL,
                n_clusters INTEGER,
                n_gaps INTEGER,
                cluster_labels TEXT,
                computed_at TEXT NOT NULL,
                FOREIGN KEY (session_date) REFERENCES sessions(date) ON DELETE CASCADE
            )
        """)

    if current_version < 6:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_links_target_source ON links(target, source_path)"
        )

    if current_version < 7:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_embeddings'"
        ).fetchone()
        if table is not None:
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(session_embeddings)").fetchall()
            }
            if "cluster_label" not in columns:
                conn.execute("ALTER TABLE session_embeddings ADD COLUMN cluster_label TEXT")

    if current_version < 8:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS geist_status (
                geist_id TEXT PRIMARY KEY,
                failure_count INTEGER NOT NULL DEFAULT 0,
                disabled INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                updated TEXT
            )
        """)
