"""Vault class for Obsidian vault management."""

import fnmatch
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config_loader import GeistFabrikConfig, load_config
from .date_collection import is_date_collection_note, split_date_collection_note
from .markdown_parser import parse_markdown
from .models import Link, Note
from .schema import init_db, migrate_schema

logger = logging.getLogger(__name__)

# Constants for vault synchronization
FLOAT_COMPARISON_TOLERANCE = 0.01  # Tolerance for file modification time comparison


class Vault:
    """Raw vault data access and SQLite sync."""

    def __init__(
        self,
        vault_path: Path | str,
        db_path: Optional[Path | str] = None,
        config: Optional[GeistFabrikConfig] = None,
    ):
        """Initialize vault.

        Args:
            vault_path: Path to Obsidian vault directory
            db_path: Path to SQLite database. If None, uses in-memory database.
            config: Optional configuration. If None, attempts to load from vault.
        """
        self.vault_path = Path(vault_path)
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault path does not exist: {vault_path}")
        if not self.vault_path.is_dir():
            raise NotADirectoryError(f"Vault path is not a directory: {vault_path}")

        # Load or use provided config
        if config is None:
            config_path = self.vault_path / ".geistfabrik" / "config.yaml"
            self.config = load_config(config_path)
        else:
            self.config = config

        # Initialize database
        if db_path is None:
            self.db = init_db(None)
        else:
            self.db = init_db(Path(db_path))

        # Migrate schema if needed
        migrate_schema(self.db)

    def _is_excluded_from_date_collection(self, rel_path: str) -> bool:
        """Check if file should be excluded from date-collection detection.

        Args:
            rel_path: Relative path from vault root

        Returns:
            True if file matches any exclude pattern
        """
        for pattern in self.config.date_collection.exclude_files:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        return False

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
            # For regular notes, check by path; for journals (virtual entries), check by source_file
            cursor = self.db.execute(
                "SELECT file_mtime FROM notes WHERE path = ? OR source_file = ? LIMIT 1",
                (rel_path, rel_path),
            )
            row = cursor.fetchone()

            if row is not None:
                db_mtime = row[0]
                if abs(db_mtime - file_mtime) < FLOAT_COMPARISON_TOLERANCE:
                    # File unchanged, skip
                    continue

            # File is new or modified, process it
            try:
                content = md_file.read_text(encoding="utf-8")
            except UnicodeDecodeError as e:
                logger.warning(f"Skipping file {rel_path} due to encoding error: {e}")
                continue
            except PermissionError as e:
                logger.warning(f"Skipping file {rel_path} due to permission denied: {e}")
                continue

            # Get file timestamps
            stat = md_file.stat()
            created = datetime.fromtimestamp(stat.st_ctime)
            modified = datetime.fromtimestamp(stat.st_mtime)

            # Check if this is a date-collection note (if enabled and not excluded)
            dc_config = self.config.date_collection
            if (
                dc_config.enabled
                and not self._is_excluded_from_date_collection(rel_path)
                and is_date_collection_note(
                    content,
                    min_sections=dc_config.min_sections,
                    date_threshold=dc_config.date_threshold,
                )
            ):
                # Delete any existing entries for this file (both regular note and virtual entries)
                # This handles the case where a regular note becomes a journal
                self.db.execute(
                    "DELETE FROM notes WHERE path = ? OR source_file = ?", (rel_path, rel_path)
                )

                # Split into virtual entries
                virtual_notes = split_date_collection_note(rel_path, content, created, modified)

                # Insert each virtual entry
                for virtual_note in virtual_notes:
                    self._update_note_from_object(virtual_note, file_mtime)

                processed_count += len(virtual_notes)
                logger.debug(f"Split {rel_path} into {len(virtual_notes)} virtual entries")
            else:
                # Regular note - parse markdown
                title, clean_content, links, tags = parse_markdown(rel_path, content)

                # Delete any virtual entries from when this might have been a journal
                # This handles the case where a journal becomes a regular note
                self.db.execute("DELETE FROM notes WHERE source_file = ?", (rel_path,))

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
        # Build set of existing paths for efficient lookup
        existing_paths = {str(f.relative_to(self.vault_path)) for f in md_files}

        # Delete regular notes (not virtual entries) that no longer exist
        # Virtual entries are managed by their source_file, not their path
        if existing_paths:
            # Build placeholders string safely (no f-string for SQL)
            placeholders = ",".join(["?"] * len(existing_paths))
            # Only delete non-virtual notes whose paths don't exist
            # Virtual entries will be cleaned up if their source_file doesn't exist
            query = "DELETE FROM notes WHERE is_virtual = 0 AND path NOT IN ({})".format(
                placeholders
            )
            self.db.execute(query, tuple(existing_paths))

            # Also delete virtual entries whose source files no longer exist
            query = "DELETE FROM notes WHERE is_virtual = 1 AND source_file NOT IN ({})".format(
                placeholders
            )
            self.db.execute(query, tuple(existing_paths))
        else:
            # No files exist, delete all notes
            self.db.execute("DELETE FROM notes")

        try:
            self.db.commit()
        except sqlite3.Error as e:
            logger.error(f"Database commit failed during sync: {e}")
            raise
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
        # Construct a Note object for regular (non-virtual) entries
        note = Note(
            path=path,
            title=title,
            content=content,
            links=links,
            tags=tags,
            created=created,
            modified=modified,
            is_virtual=False,
            source_file=None,
            entry_date=None,
        )
        # Delegate to the full update method
        self._update_note_from_object(note, file_mtime)

    def _update_note_from_object(self, note: Note, file_mtime: float) -> None:
        """Update a note from a Note object (including virtual entries).

        Args:
            note: Note object to insert/update
            file_mtime: File modification time
        """
        # Insert or replace note with virtual entry fields
        self.db.execute(
            """
            INSERT OR REPLACE INTO notes (
                path, title, content, created, modified, file_mtime,
                is_virtual, source_file, entry_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note.path,
                note.title,
                note.content,
                note.created.isoformat(),
                note.modified.isoformat(),
                file_mtime,
                1 if note.is_virtual else 0,
                note.source_file,
                note.entry_date.isoformat() if note.entry_date else None,
            ),
        )

        # Delete old links and tags
        self.db.execute("DELETE FROM links WHERE source_path = ?", (note.path,))
        self.db.execute("DELETE FROM tags WHERE note_path = ?", (note.path,))

        # Insert new links
        for link in note.links:
            self.db.execute(
                """
                INSERT INTO links (source_path, target, display_text, is_embed, block_ref)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    note.path,
                    link.target,
                    link.display_text,
                    1 if link.is_embed else 0,
                    link.block_ref,
                ),
            )

        # Insert new tags
        for tag in note.tags:
            self.db.execute("INSERT INTO tags (note_path, tag) VALUES (?, ?)", (note.path, tag))

    def _build_note_from_row(
        self,
        row: tuple[str, str, str, str, str, int, Optional[str], Optional[str]],
        links: List[Link],
        tags: List[str],
    ) -> Note:
        """Build a Note object from a database row.

        Args:
            row: Tuple of (path, title, content, created, modified,
                          is_virtual, source_file, entry_date)
            links: List of Link objects for this note
            tags: List of tag strings for this note

        Returns:
            Note object constructed from the row data
        """
        from datetime import date

        (
            path,
            title,
            content,
            created_str,
            modified_str,
            is_virtual,
            source_file,
            entry_date_str,
        ) = row

        # Parse entry_date if present
        entry_date = date.fromisoformat(entry_date_str) if entry_date_str else None

        return Note(
            path=path,
            title=title,
            content=content,
            links=links,
            tags=tags,
            created=datetime.fromisoformat(created_str),
            modified=datetime.fromisoformat(modified_str),
            is_virtual=bool(is_virtual),
            source_file=source_file,
            entry_date=entry_date,
        )

    def all_notes(self) -> List[Note]:
        """Load all notes from database.

        Returns:
            List of all Note objects (including virtual entries)
        """
        # Batch load all notes
        cursor = self.db.execute(
            """
            SELECT path, title, content, created, modified,
                   is_virtual, source_file, entry_date
            FROM notes ORDER BY path
            """
        )
        note_rows = cursor.fetchall()

        # Batch load all links and group by source_path
        link_cursor = self.db.execute(
            "SELECT source_path, target, display_text, is_embed, block_ref FROM links"
        )
        links_by_path: dict[str, List[Link]] = {}
        for link_row in link_cursor.fetchall():
            source_path = link_row[0]
            if source_path not in links_by_path:
                links_by_path[source_path] = []
            links_by_path[source_path].append(
                Link(
                    target=link_row[1],
                    display_text=link_row[2],
                    is_embed=bool(link_row[3]),
                    block_ref=link_row[4],
                )
            )

        # Batch load all tags and group by note_path
        tag_cursor = self.db.execute("SELECT note_path, tag FROM tags ORDER BY note_path, tag")
        tags_by_path: dict[str, List[str]] = {}
        for tag_row in tag_cursor.fetchall():
            note_path = tag_row[0]
            if note_path not in tags_by_path:
                tags_by_path[note_path] = []
            tags_by_path[note_path].append(tag_row[1])

        # Assemble Note objects
        notes = []
        for row in note_rows:
            path = row[0]  # Extract path for dict lookups
            note = self._build_note_from_row(
                row, links_by_path.get(path, []), tags_by_path.get(path, [])
            )
            notes.append(note)

        return notes

    def get_note(self, path: str) -> Optional[Note]:
        """Retrieve specific note by path (including virtual entries).

        Args:
            path: Relative path of note in vault (or virtual path)

        Returns:
            Note object or None if not found
        """
        cursor = self.db.execute(
            """
            SELECT path, title, content, created, modified,
                   is_virtual, source_file, entry_date
            FROM notes WHERE path = ?
            """,
            (path,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        # Load links for this note
        note_path = row[0]  # Extract path from row
        link_cursor = self.db.execute(
            """
            SELECT target, display_text, is_embed, block_ref
            FROM links
            WHERE source_path = ?
            """,
            (note_path,),
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
            "SELECT tag FROM tags WHERE note_path = ? ORDER BY tag", (note_path,)
        )
        tags = [tag_row[0] for tag_row in tag_cursor.fetchall()]

        return self._build_note_from_row(row, links, tags)

    def get_notes_batch(self, paths: List[str]) -> Dict[str, Optional[Note]]:
        """Load multiple notes efficiently in batched queries.

        Performance optimized (OP-6): Batches database queries to load N notes
        in 3 queries instead of 3×N queries. This is significantly faster when
        loading many notes (e.g., backlinks, neighbors).

        Args:
            paths: List of note paths to load

        Returns:
            Dictionary mapping paths to Note objects (or None if not found)
        """
        if not paths:
            return {}

        # Query 1: Load all notes at once
        placeholders = ",".join(["?"] * len(paths))
        cursor = self.db.execute(
            f"""SELECT path, title, content, created, modified,
                       is_virtual, source_file, entry_date
                FROM notes WHERE path IN ({placeholders})""",
            tuple(paths),
        )

        notes_data: Dict[str, Dict[str, Any]] = {}
        for row in cursor.fetchall():
            path = row[0]
            notes_data[path] = {
                "row": row,
                "links": [],
                "tags": [],
            }

        # Query 2: Load all links for these notes
        cursor = self.db.execute(
            f"""SELECT source_path, target, display_text, is_embed, block_ref
                FROM links WHERE source_path IN ({placeholders})""",
            tuple(paths),
        )

        for row in cursor.fetchall():
            source_path, target, display_text, is_embed, block_ref = row
            if source_path in notes_data:
                link = Link(
                    target=target,
                    display_text=display_text,
                    is_embed=bool(is_embed),
                    block_ref=block_ref,
                )
                notes_data[source_path]["links"].append(link)

        # Query 3: Load all tags for these notes
        cursor = self.db.execute(
            f"""SELECT note_path, tag FROM tags WHERE note_path IN ({placeholders})""",
            tuple(paths),
        )

        for row in cursor.fetchall():
            note_path, tag = row
            if note_path in notes_data:
                notes_data[note_path]["tags"].append(tag)

        # Build Note objects
        result: Dict[str, Optional[Note]] = {}
        for path in paths:
            if path in notes_data:
                data = notes_data[path]
                result[path] = self._build_note_from_row(data["row"], data["links"], data["tags"])
            else:
                result[path] = None

        return result

    def resolve_link_target(self, target: str, source_path: Optional[str] = None) -> Optional[Note]:
        """Resolve a wiki-link target to a Note.

        Wiki-links in Obsidian can reference notes by:
        - Full path with extension: "path/to/note.md"
        - Path without extension: "path/to/note"
        - Note title: "Note Title"
        - Basename: "note"
        - Date (from journal): "2025-01-15" (resolves to entry in same journal)
        - Virtual path: "Journal.md/2025-01-15"

        This method tries to resolve the target in order:
        1. As exact path match (handles virtual paths)
        2. As path with .md extension added
        3. As title match (handles virtual entry titles)
        4. As date reference (if source is a journal entry)

        Args:
            target: Link target string from wiki-link
            source_path: Optional path of the note containing the link
                         (needed for context-aware date resolution)

        Returns:
            Note object if found, None otherwise
        """
        # Strip heading/block references for resolution
        # e.g., [[Note#heading]] -> "Note", [[Note^block]] -> "Note"
        clean_target = target.split("#")[0].split("^")[0]

        # Try as exact path first (handles virtual paths like "Journal.md/2025-01-15")
        note = self.get_note(clean_target)
        if note is not None:
            return note

        # Try adding .md extension
        if not clean_target.endswith(".md"):
            note = self.get_note(f"{clean_target}.md")
            if note is not None:
                return note

        # Try looking up by title (handles virtual entry titles)
        cursor = self.db.execute(
            "SELECT path FROM notes WHERE title = ?",
            (clean_target,),
        )
        row = cursor.fetchone()
        if row is not None:
            return self.get_note(row[0])

        # Try date-based resolution if source is a virtual entry
        if source_path and "/" in source_path:
            from .date_collection import parse_date_heading

            # Source is a virtual entry, target might be a date reference
            date_obj = parse_date_heading(f"## {clean_target}")
            if date_obj is not None:
                # Extract source file from virtual path
                source_file = source_path.split("/")[0]
                # Try to find entry with this date in the same journal
                virtual_path = f"{source_file}/{date_obj.isoformat()}"
                note = self.get_note(virtual_path)
                if note is not None:
                    return note

        return None

    def close(self) -> None:
        """Close database connection."""
        self.db.close()
