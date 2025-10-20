"""SQLite schema for GeistFabrik."""

import sqlite3
from pathlib import Path
from typing import Optional

# Schema version for migrations
# Version 3: Removed unused `suggestions` and `suggestion_notes` tables
SCHEMA_VERSION = 3

SCHEMA_SQL = """
-- Notes table
CREATE TABLE IF NOT EXISTS notes (
    path TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created TEXT NOT NULL,
    modified TEXT NOT NULL,
    file_mtime REAL NOT NULL  -- For incremental sync
);

CREATE INDEX IF NOT EXISTS idx_notes_modified ON notes(modified);
CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title);

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
-- The normalized tables were never used and have been removed (see commit history).
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
"""


def init_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Initialize database with schema.

    Args:
        db_path: Path to SQLite database file. If None, use in-memory database.

    Returns:
        SQLite connection with schema initialized.
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
