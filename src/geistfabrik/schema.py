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
# Version 9: Version embedding metric caches by exact source and algorithm inputs
# Version 10: Persist exact filesystem fingerprints for incremental vault sync
# Version 11: Atomic incremental lexical vectors and captured additions
# Version 12: Optional suggestion evidence identity for episode-level novelty
# Version 13: Cached lexical evidence diagnostics and durable evidence lookup
# Version 14: Compact stable-ID lexical presence projections
SCHEMA_VERSION = 14
MIN_SUPPORTED_SCHEMA_VERSION = 3
SQLITE_BUSY_TIMEOUT_MS = 5_000

SCHEMA_SQL = """
-- Notes table
CREATE TABLE IF NOT EXISTS notes (
    path TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created TEXT NOT NULL,
    modified TEXT NOT NULL,
    file_mtime REAL NOT NULL,  -- Retained for historical compatibility/reporting
    source_fingerprint TEXT,   -- Exact stat identity for incremental sync
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
-- It lets geists compare cluster membership across sessions (it was written
-- for cluster_evolution_tracker, since retired).
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
    evidence_key TEXT,
    PRIMARY KEY (session_date, block_id)
);

CREATE INDEX IF NOT EXISTS idx_session_suggestions_date ON session_suggestions(session_date);
CREATE INDEX IF NOT EXISTS idx_session_suggestions_geist ON session_suggestions(geist_id);
CREATE INDEX IF NOT EXISTS idx_session_suggestions_evidence
    ON session_suggestions(geist_id, evidence_key, session_date)
    WHERE evidence_key IS NOT NULL;

-- Embedding metrics cache (for stats command)
CREATE TABLE IF NOT EXISTS embedding_metrics (
    session_date TEXT NOT NULL,
    source_digest TEXT NOT NULL,
    algorithm_digest TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (session_date, source_digest, algorithm_digest),
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

-- Exact current lexical vectors and prospective observation evidence.
CREATE TABLE IF NOT EXISTS lexical_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO lexical_meta VALUES ('generation', '0');
CREATE TABLE IF NOT EXISTS lexical_terms (
    term TEXT PRIMARY KEY,
    documents INTEGER NOT NULL DEFAULT 0 CHECK(documents >= 0)
);
CREATE INDEX IF NOT EXISTS idx_lexical_terms_documents ON lexical_terms(documents);
-- IDs remain stable while either current prose or captured history may use them.
-- Presence is derived from the retained exact JSON vectors, never a new source.
CREATE TABLE IF NOT EXISTS lexical_presence_terms (
    term_id INTEGER PRIMARY KEY CHECK(term_id > 0),
    term TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS lexical_notes (
    path TEXT PRIMARY KEY REFERENCES notes(path) ON DELETE CASCADE,
    raw_hash TEXT NOT NULL,
    body_hash TEXT NOT NULL,
    cohort_day TEXT,
    provenance TEXT NOT NULL,
    counts_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    presence BLOB
);
CREATE INDEX IF NOT EXISTS idx_lexical_cohort ON lexical_notes(cohort_day);
CREATE TABLE IF NOT EXISTS lexical_events (
    path TEXT NOT NULL REFERENCES lexical_notes(path) ON DELETE CASCADE,
    bin_start TEXT NOT NULL,
    previous_at TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    terms_json TEXT NOT NULL,
    revisions_json TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    presence BLOB,
    PRIMARY KEY(path, bin_start)
);
CREATE INDEX IF NOT EXISTS idx_lexical_events_bin ON lexical_events(bin_start);
CREATE TABLE IF NOT EXISTS word_burst_cache (
    cache_key TEXT PRIMARY KEY,
    result_json TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TRIGGER IF NOT EXISTS lexical_note_insert AFTER INSERT ON lexical_notes BEGIN
    INSERT INTO lexical_terms(term, documents)
        SELECT key, 1 FROM json_each(NEW.counts_json) WHERE true
        ON CONFLICT(term) DO UPDATE SET documents = documents + 1;
    UPDATE lexical_meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'generation';
    DELETE FROM word_burst_cache;
END;
CREATE TRIGGER IF NOT EXISTS lexical_note_delete AFTER DELETE ON lexical_notes BEGIN
    UPDATE lexical_terms SET documents = documents - 1
        WHERE term IN (SELECT key FROM json_each(OLD.counts_json));
    UPDATE lexical_meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'generation';
    DELETE FROM word_burst_cache;
END;
CREATE TRIGGER IF NOT EXISTS lexical_note_update AFTER UPDATE ON lexical_notes
WHEN OLD.body_hash != NEW.body_hash OR OLD.cohort_day IS NOT NEW.cohort_day
    OR OLD.provenance != NEW.provenance OR OLD.counts_json != NEW.counts_json BEGIN
    UPDATE lexical_terms SET documents = documents - 1
        WHERE OLD.counts_json != NEW.counts_json
          AND term IN (SELECT key FROM json_each(OLD.counts_json));
    INSERT INTO lexical_terms(term, documents)
        SELECT key, 1 FROM json_each(NEW.counts_json) WHERE OLD.counts_json != NEW.counts_json
        ON CONFLICT(term) DO UPDATE SET documents = documents + 1;
    UPDATE lexical_meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'generation';
    DELETE FROM word_burst_cache;
END;
CREATE TRIGGER IF NOT EXISTS lexical_note_presence_invalid AFTER UPDATE OF counts_json
ON lexical_notes WHEN OLD.counts_json != NEW.counts_json BEGIN
    UPDATE lexical_notes SET presence = NULL WHERE path = NEW.path;
END;
CREATE TRIGGER IF NOT EXISTS lexical_event_insert AFTER INSERT ON lexical_events BEGIN
    UPDATE lexical_meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'generation';
    DELETE FROM word_burst_cache;
END;
CREATE TRIGGER IF NOT EXISTS lexical_event_update AFTER UPDATE ON lexical_events
WHEN OLD.path != NEW.path OR OLD.bin_start != NEW.bin_start
    OR OLD.previous_at != NEW.previous_at OR OLD.observed_at != NEW.observed_at
    OR OLD.terms_json != NEW.terms_json OR OLD.revisions_json != NEW.revisions_json
    OR OLD.evidence_hash != NEW.evidence_hash BEGIN
    UPDATE lexical_meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'generation';
    DELETE FROM word_burst_cache;
END;
CREATE TRIGGER IF NOT EXISTS lexical_event_delete AFTER DELETE ON lexical_events BEGIN
    UPDATE lexical_meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'generation';
    DELETE FROM word_burst_cache;
END;
CREATE TRIGGER IF NOT EXISTS lexical_event_presence_invalid AFTER UPDATE OF terms_json
ON lexical_events WHEN OLD.terms_json != NEW.terms_json BEGIN
    UPDATE lexical_events SET presence = NULL
        WHERE path = NEW.path AND bin_start = NEW.bin_start;
END;
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


def _upgrade_and_reconcile(conn: sqlite3.Connection, *, allow_empty_unversioned: bool) -> None:
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
        if 0 < current_version < MIN_SUPPORTED_SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {current_version} is older than minimum supported "
                f"version {MIN_SUPPORTED_SCHEMA_VERSION}; refusing to modify it"
            )

        if current_version > 0:
            _apply_ordered_migrations(conn, current_version)
        # user_version records migration intent, not structural truth. Repair
        # additive columns even when an interrupted/buggy older release stamped
        # a database current before completing its DDL.
        _reconcile_additive_columns(conn)
        _reconcile_metrics_cache(conn)
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
            ("source_fingerprint", "TEXT"),
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

    suggestions_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='session_suggestions'"
    ).fetchone()
    if suggestions_table is not None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(session_suggestions)")}
        if "evidence_key" not in columns:
            conn.execute("ALTER TABLE session_suggestions ADD COLUMN evidence_key TEXT")

    burst_cache = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='word_burst_cache'"
    ).fetchone()
    if burst_cache is not None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(word_burst_cache)")}
        if "diagnostics_json" not in columns:
            conn.execute(
                "ALTER TABLE word_burst_cache "
                "ADD COLUMN diagnostics_json TEXT NOT NULL DEFAULT '{}'"
            )
            # Old result-only cache rows cannot explain their evidence limits.
            # This is derived data; source vectors and saved questions survive.
            conn.execute("DELETE FROM word_burst_cache")

    for table in ("lexical_notes", "lexical_events"):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if exists is not None:
            columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if "presence" not in columns:
                # Backfilled from retained JSON on the first cold analysis.
                # Source prose, captured history and all other durable data stay intact.
                conn.execute(f"ALTER TABLE {table} ADD COLUMN presence BLOB")


def _apply_ordered_migrations(conn: sqlite3.Connection, current_version: int) -> None:
    """Apply required pre-reconciliation DDL without committing or stamping."""
    if current_version < 12:
        # v12 separates chronology/cache invalidation from dictionary updates.
        # Recreate this derived trigger inside the owned migration transaction.
        conn.execute("DROP TRIGGER IF EXISTS lexical_note_update")
    if current_version < 14:
        # Compact derived projections do not change captured historical evidence.
        conn.execute("DROP TRIGGER IF EXISTS lexical_event_update")
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


def _reconcile_metrics_cache(conn: sqlite3.Connection) -> None:
    """Discard unverifiable derived cache rows, preserving all durable source data."""
    columns = conn.execute("PRAGMA table_info(embedding_metrics)").fetchall()
    if not columns:
        return
    primary_key = {row[1]: row[5] for row in columns if row[5]}
    expected_key = {"session_date": 1, "source_digest": 2, "algorithm_digest": 3}
    if primary_key != expected_key or "metrics_json" not in {row[1] for row in columns}:
        # v8 and older cached only by date. There is no trustworthy provenance
        # to attach to those values; recomputation is the only safe migration.
        # SCHEMA_SQL recreates the cache in this same owned transaction.
        conn.execute("DROP TABLE embedding_metrics")
