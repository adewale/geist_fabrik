"""SQLite schema for GeistFabrik."""

import sqlite3
from pathlib import Path
from typing import Optional

# Schema version for migrations
# Version 3: Removed unused `suggestions` and `suggestion_notes` tables
# Version 4: Added support for date-collection notes (virtual entries)
# Version 5: Added embedding_metrics table for stats command caching
# Version 6: Added composite index for orphans query performance
SCHEMA_VERSION = 6

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
CREATE TABLE IF NOT EXISTS session_embeddings (
    session_id INTEGER NOT NULL,
    note_path TEXT NOT NULL,
    embedding BLOB NOT NULL,
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
"""


def init_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Initialise database with schema.

    Args:
        db_path: Path to SQLite database file. If None, use in-memory database.

    Returns:
        SQLite connection with schema initialised.
    """
    if db_path is None:
        conn = sqlite3.connect(":memory:")
    else:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))

    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    # Execute schema
    conn.executescript(SCHEMA_SQL)

    # Set schema version
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    conn.commit()
    return conn


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version."""
    cursor = conn.execute("PRAGMA user_version")
    result = cursor.fetchone()
    if result is None:
        return 0
    return int(result[0])


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Migrate database schema to current version.

    Args:
        conn: SQLite connection
    """
    current_version = get_schema_version(conn)

    if current_version == SCHEMA_VERSION:
        return  # Already at current version

    # Migration from version 3 to 4: Add virtual entry columns
    if current_version < 4:
        # Check if columns already exist (defensive programming)
        cursor = conn.execute("PRAGMA table_info(notes)")
        columns = {row[1] for row in cursor.fetchall()}

        if "is_virtual" not in columns:
            conn.execute("ALTER TABLE notes ADD COLUMN is_virtual INTEGER DEFAULT 0")

        if "source_file" not in columns:
            conn.execute("ALTER TABLE notes ADD COLUMN source_file TEXT")

        if "entry_date" not in columns:
            conn.execute("ALTER TABLE notes ADD COLUMN entry_date TEXT")

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_source_file ON notes(source_file)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_entry_date ON notes(entry_date)")

        # Update version
        conn.execute("PRAGMA user_version = 4")
        conn.commit()

    # Migration from version 4 to 5: Add embedding_metrics table
    if current_version < 5:
        # Check if table already exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='embedding_metrics'"
        )
        if cursor.fetchone() is None:
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

        # Update version
        conn.execute("PRAGMA user_version = 5")
        conn.commit()

    # Migration from version 5 to 6: Add composite index for orphans query
    if current_version < 6:
        # Add composite index for better orphan query performance
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_links_target_source ON links(target, source_path)"
        )

        # Update version
        conn.execute("PRAGMA user_version = 6")
        conn.commit()
