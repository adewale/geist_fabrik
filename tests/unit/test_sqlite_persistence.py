"""Unit tests for SQLite persistence."""

from geistfabrik.schema import get_schema_version, init_db


def test_init_db_memory() -> None:
    """Test initializing in-memory database."""
    conn = init_db(None)
    assert conn is not None

    # Check that schema exists
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    assert "notes" in tables
    assert "links" in tables
    assert "tags" in tables
    assert "embeddings" in tables
    assert "suggestions" in tables
    assert "suggestion_notes" in tables

    conn.close()


def test_schema_version() -> None:
    """Test schema version is set."""
    conn = init_db(None)
    version = get_schema_version(conn)
    assert version > 0
    conn.close()


def test_foreign_keys_enabled() -> None:
    """Test that foreign keys are enabled."""
    conn = init_db(None)
    cursor = conn.execute("PRAGMA foreign_keys")
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == 1
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


def test_corrupted_database_recovery() -> None:
    """Test handling of database that might be corrupted."""
    # For now, just test we can reinitialize
    conn = init_db(None)
    # Simulate corruption by dropping a table
    conn.execute("DROP TABLE IF EXISTS notes")

    # Reinitialize should recreate tables
    conn.executescript("BEGIN; ROLLBACK;")  # Reset any transaction
    conn.close()

    # Create new connection and init
    conn = init_db(None)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "notes" in tables
    conn.close()
