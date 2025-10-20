"""Vault class for Obsidian vault management."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .markdown_parser import parse_markdown
from .models import Link, Note
from .schema import init_db


class Vault:
    """Raw vault data access and SQLite sync."""

    def __init__(self, vault_path: Path | str, db_path: Optional[Path | str] = None):
        """Initialize vault.

        Args:
            vault_path: Path to Obsidian vault directory
            db_path: Path to SQLite database. If None, uses in-memory database.
        """
        self.vault_path = Path(vault_path)
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault path does not exist: {vault_path}")
        if not self.vault_path.is_dir():
            raise NotADirectoryError(f"Vault path is not a directory: {vault_path}")

        # Initialize database
        if db_path is None:
            self.db = init_db(None)
        else:
            self.db = init_db(Path(db_path))

    def sync(self) -> int:
        """Incrementally update database with changed files.

        Returns:
            Number of notes processed (new or modified)
        """
        processed_count = 0

        # Get all markdown files in vault
        md_files = list(self.vault_path.rglob("*.md"))

        for md_file in md_files:
            # Get relative path from vault root
            rel_path = str(md_file.relative_to(self.vault_path))

            # Get file modification time
            file_mtime = md_file.stat().st_mtime

            # Check if file needs to be processed
            cursor = self.db.execute("SELECT file_mtime FROM notes WHERE path = ?", (rel_path,))
            row = cursor.fetchone()

            if row is not None:
                db_mtime = row[0]
                if abs(db_mtime - file_mtime) < 0.01:  # Tolerance for float comparison
                    # File unchanged, skip
                    continue

            # File is new or modified, process it
            try:
                content = md_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Handle invalid UTF-8 by skipping the file
                continue

            # Parse markdown
            title, clean_content, links, tags = parse_markdown(rel_path, content)

            # Get file timestamps
            stat = md_file.stat()
            created = datetime.fromtimestamp(stat.st_ctime)
            modified = datetime.fromtimestamp(stat.st_mtime)

            # Update database
            self._update_note(
                rel_path,
                title,
                content,
                created,
                modified,
                file_mtime,
                links,
                tags,
            )

            processed_count += 1

        # Remove notes that no longer exist in filesystem
        all_db_paths = [row[0] for row in self.db.execute("SELECT path FROM notes").fetchall()]
        existing_paths = {str(f.relative_to(self.vault_path)) for f in md_files}

        for db_path in all_db_paths:
            if db_path not in existing_paths:
                self.db.execute("DELETE FROM notes WHERE path = ?", (db_path,))

        self.db.commit()
        return processed_count

    def _update_note(
        self,
        path: str,
        title: str,
        content: str,
        created: datetime,
        modified: datetime,
        file_mtime: float,
        links: List[Link],
        tags: List[str],
    ) -> None:
        """Update a note and its relationships in the database."""
        # Insert or replace note
        self.db.execute(
            """
            INSERT OR REPLACE INTO notes (path, title, content, created, modified, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                path,
                title,
                content,
                created.isoformat(),
                modified.isoformat(),
                file_mtime,
            ),
        )

        # Delete old links and tags
        self.db.execute("DELETE FROM links WHERE source_path = ?", (path,))
        self.db.execute("DELETE FROM tags WHERE note_path = ?", (path,))

        # Insert new links
        for link in links:
            self.db.execute(
                """
                INSERT INTO links (source_path, target, display_text, is_embed, block_ref)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    path,
                    link.target,
                    link.display_text,
                    1 if link.is_embed else 0,
                    link.block_ref,
                ),
            )

        # Insert new tags
        for tag in tags:
            self.db.execute("INSERT INTO tags (note_path, tag) VALUES (?, ?)", (path, tag))

    def all_notes(self) -> List[Note]:
        """Load all notes from database.

        Returns:
            List of all Note objects
        """
        cursor = self.db.execute(
            "SELECT path, title, content, created, modified FROM notes ORDER BY path"
        )

        notes = []
        for row in cursor.fetchall():
            path, title, content, created_str, modified_str = row

            # Load links for this note
            link_cursor = self.db.execute(
                """
                SELECT target, display_text, is_embed, block_ref
                FROM links
                WHERE source_path = ?
                """,
                (path,),
            )
            links = [
                Link(
                    target=link_row[0],
                    display_text=link_row[1],
                    is_embed=bool(link_row[2]),
                    block_ref=link_row[3],
                )
                for link_row in link_cursor.fetchall()
            ]

            # Load tags for this note
            tag_cursor = self.db.execute(
                "SELECT tag FROM tags WHERE note_path = ? ORDER BY tag", (path,)
            )
            tags = [tag_row[0] for tag_row in tag_cursor.fetchall()]

            # Create Note object
            notes.append(
                Note(
                    path=path,
                    title=title,
                    content=content,
                    links=links,
                    tags=tags,
                    created=datetime.fromisoformat(created_str),
                    modified=datetime.fromisoformat(modified_str),
                )
            )

        return notes

    def get_note(self, path: str) -> Optional[Note]:
        """Retrieve specific note by path.

        Args:
            path: Relative path of note in vault

        Returns:
            Note object or None if not found
        """
        cursor = self.db.execute(
            "SELECT path, title, content, created, modified FROM notes WHERE path = ?",
            (path,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        path, title, content, created_str, modified_str = row

        # Load links for this note
        link_cursor = self.db.execute(
            """
            SELECT target, display_text, is_embed, block_ref
            FROM links
            WHERE source_path = ?
            """,
            (path,),
        )
        links = [
            Link(
                target=link_row[0],
                display_text=link_row[1],
                is_embed=bool(link_row[2]),
                block_ref=link_row[3],
            )
            for link_row in link_cursor.fetchall()
        ]

        # Load tags for this note
        tag_cursor = self.db.execute(
            "SELECT tag FROM tags WHERE note_path = ? ORDER BY tag", (path,)
        )
        tags = [tag_row[0] for tag_row in tag_cursor.fetchall()]

        return Note(
            path=path,
            title=title,
            content=content,
            links=links,
            tags=tags,
            created=datetime.fromisoformat(created_str),
            modified=datetime.fromisoformat(modified_str),
        )

    def close(self) -> None:
        """Close database connection."""
        self.db.close()
