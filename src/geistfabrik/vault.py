"""Vault class for Obsidian vault management."""

import fnmatch
import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import MAX_NOTE_BYTES
from .config_loader import GeistFabrikConfig, load_config
from .date_collection import is_date_collection_note, split_date_collection_note
from .markdown_parser import MarkdownLimitError, parse_markdown
from .models import Link, Note, NoteLinkIndex
from .path_safety import PathSafetyError, ensure_contained
from .schema import init_db
from .sqlite_transaction import owned_transaction

logger = logging.getLogger(__name__)

_SYNC_SNAPSHOT_ATTEMPTS = 3


class VaultSyncConflictError(RuntimeError):
    """Raised when the filesystem cannot provide a stable sync snapshot."""


class _VaultSnapshotChangedError(RuntimeError):
    """Internal retry signal for a filesystem change during synchronization."""


class Vault:
    """Raw vault data access and SQLite sync."""

    def __init__(
        self,
        vault_path: Path | str,
        db_path: Path | str | None = None,
        config: GeistFabrikConfig | None = None,
    ):
        """Initialise vault.

        Args:
            vault_path: Path to Obsidian vault directory
            db_path: Path to SQLite database. If None, uses in-memory database.
            config: Optional configuration. If None, attempts to load from vault.
        """
        self.vault_path = Path(vault_path).resolve()
        if not self.vault_path.exists():
            raise FileNotFoundError(f"Vault path does not exist: {vault_path}")
        if not self.vault_path.is_dir():
            raise NotADirectoryError(f"Vault path is not a directory: {vault_path}")

        # Load or use provided config
        if config is None:
            config_path = self.vault_path / "_geistfabrik" / "config.yaml"
            ensure_contained(config_path, self.vault_path, reject_symlinks=True)
            self.config = load_config(config_path)
        else:
            self.config = config

        # Initialise database
        if db_path is None:
            self.db = init_db(None)
        else:
            db_path_obj = Path(db_path)
            is_new_db = not db_path_obj.exists()
            self.db = init_db(db_path_obj)
            if is_new_db and db_path_obj.exists():
                os.chmod(db_path_obj, 0o600)

        # init_db performs ordered migrations for existing databases.
        self._link_index: NoteLinkIndex | None = None
        self._link_index_version: tuple[int, int] | None = None

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
        """Incrementally update the database as one exception-atomic unit.

        Returns:
            Number of notes processed (new or modified)
        """
        # The SQLite writer lock serialises synchronizers, but it cannot freeze
        # an editor's filesystem writes. Discover only after taking the lock,
        # then validate the complete source snapshot again before committing
        # destructive reconciliation. A changed snapshot rolls back every
        # database mutation from the attempt and is retried from scratch.
        for attempt in range(_SYNC_SNAPSHOT_ATTEMPTS):
            try:
                with owned_transaction(self.db, "Vault.sync"):
                    md_files = self._discover_markdown_files()
                    processed_count = self._sync_discovered_files(md_files)
                    if not self._snapshot_is_current(md_files):
                        raise _VaultSnapshotChangedError
                    self._delete_missing_notes(md_files)
                    return processed_count
            except _VaultSnapshotChangedError:
                if attempt + 1 == _SYNC_SNAPSHOT_ATTEMPTS:
                    raise VaultSyncConflictError(
                        "Vault files changed repeatedly during synchronization; retry "
                        "after filesystem activity settles"
                    ) from None

        raise AssertionError("unreachable")

    def _snapshot_is_current(self, md_files: list[tuple[Path, Path, os.stat_result]]) -> bool:
        """Revalidate the complete eligible source set without resolving known paths twice."""
        expected = {
            str(candidate.relative_to(self.vault_path)): (resolved, stat)
            for candidate, resolved, stat in md_files
        }
        current_candidates = {
            str(candidate.relative_to(self.vault_path)): candidate
            for candidate in self.vault_path.rglob("*.md")
        }
        if not expected.keys() <= current_candidates.keys():
            return False

        for rel_path, (expected_resolved, expected_stat) in expected.items():
            try:
                current_resolved = current_candidates[rel_path].resolve(strict=True)
                current_stat = current_resolved.stat()
            except (OSError, RuntimeError):
                return False
            # The original resolved target was already proven contained. Exact
            # equality detects a symlink retarget without trusting it again.
            if current_resolved != expected_resolved:
                return False
            if self._stat_signature(current_stat) != self._stat_signature(expected_stat):
                return False

        # Newly observed paths must be classified with the normal containment
        # and size rules. Ineligible files do not belong to the mirrored set;
        # any new eligible source invalidates this attempt.
        for rel_path in current_candidates.keys() - expected.keys():
            candidate = current_candidates[rel_path]
            try:
                resolved = ensure_contained(candidate, self.vault_path, must_exist=True)
                stat = resolved.stat()
            except (PathSafetyError, FileNotFoundError, OSError):
                continue
            if resolved.is_file() and stat.st_size <= MAX_NOTE_BYTES:
                return False
        return True

    def _discover_markdown_files(self) -> list[tuple[Path, Path, os.stat_result]]:
        """Resolve bounded Markdown sources without touching SQLite state."""
        md_files: list[tuple[Path, Path, os.stat_result]] = []
        for candidate in self.vault_path.rglob("*.md"):
            rel_path = str(candidate.relative_to(self.vault_path))
            try:
                resolved = ensure_contained(candidate, self.vault_path, must_exist=True)
                stat = resolved.stat()
            except (PathSafetyError, FileNotFoundError, OSError) as exc:
                logger.warning("Skipping unsafe note %s: %s", rel_path, exc)
                continue
            if not resolved.is_file():
                continue
            if stat.st_size > MAX_NOTE_BYTES:
                logger.warning(
                    "Skipping oversized note %s (%d bytes; limit %d)",
                    rel_path,
                    stat.st_size,
                    MAX_NOTE_BYTES,
                )
                continue
            md_files.append((candidate, resolved, stat))
        return md_files

    def _sync_discovered_files(self, md_files: list[tuple[Path, Path, os.stat_result]]) -> int:
        """Reconcile already-resolved sources inside the owned transaction."""
        processed_count = 0
        for md_file, resolved_file, initial_stat in md_files:
            rel_path = str(md_file.relative_to(self.vault_path))
            file_mtime = initial_stat.st_mtime

            # Check if file needs to be processed
            # For regular notes, check by path; for journals (virtual entries), check by source_file
            source_fingerprint = self._source_fingerprint(initial_stat)
            cursor = self.db.execute(
                "SELECT source_fingerprint FROM notes WHERE path = ? OR source_file = ? LIMIT 1",
                (rel_path, rel_path),
            )
            row = cursor.fetchone()

            if row is not None and row[0] == source_fingerprint:
                # Exact stat identity is unchanged. Legacy rows have NULL and
                # are refreshed once; same-mtime edits change ctime/inode/size.
                continue

            # File is new or modified, process it
            try:
                with resolved_file.open("rb") as handle:
                    raw_content = handle.read(MAX_NOTE_BYTES + 1)
                if len(raw_content) > MAX_NOTE_BYTES:
                    logger.warning(
                        "Skipping note %s because it grew beyond the size limit", rel_path
                    )
                    continue
                content = raw_content.decode("utf-8")
            except FileNotFoundError:
                continue
            except UnicodeDecodeError as e:
                logger.warning(f"Skipping file {rel_path} due to encoding error: {e}")
                continue
            except PermissionError as e:
                logger.warning(f"Skipping file {rel_path} due to permission denied: {e}")
                continue

            # Get file timestamps (file may have been deleted after read_text)
            try:
                stat = resolved_file.stat()
            except FileNotFoundError:
                raise _VaultSnapshotChangedError from None
            if self._stat_signature(stat) != self._stat_signature(initial_stat):
                raise _VaultSnapshotChangedError
            created = datetime.fromtimestamp(stat.st_ctime)
            modified = datetime.fromtimestamp(stat.st_mtime)

            # Check if this is a date-collection note (if enabled and not excluded)
            dc_config = self.config.date_collection
            try:
                is_collection = (
                    dc_config.enabled
                    and not self._is_excluded_from_date_collection(rel_path)
                    and is_date_collection_note(
                        content,
                        min_sections=dc_config.min_sections,
                        date_threshold=dc_config.date_threshold,
                    )
                )
            except MarkdownLimitError as exc:
                logger.warning("Skipping structurally dense note %s: %s", rel_path, exc)
                self.db.execute(
                    "DELETE FROM notes WHERE path = ? OR source_file = ?",
                    (rel_path, rel_path),
                )
                continue

            if is_collection:
                # Parse before changing existing rows. Stable virtual paths are
                # updated in place so their historical session embeddings survive;
                # only entries that disappeared from the source are deleted.
                try:
                    virtual_notes = split_date_collection_note(rel_path, content, created, modified)
                except MarkdownLimitError as exc:
                    logger.warning("Skipping structurally dense note %s: %s", rel_path, exc)
                    continue

                self._replace_virtual_notes(rel_path, virtual_notes, file_mtime, source_fingerprint)
                processed_count += len(virtual_notes)
                logger.debug(f"Split {rel_path} into {len(virtual_notes)} virtual entries")
            else:
                # Regular note - parse markdown
                try:
                    title, clean_content, links, tags = parse_markdown(rel_path, content)
                except MarkdownLimitError as exc:
                    logger.warning("Skipping structurally dense note %s: %s", rel_path, exc)
                    self.db.execute(
                        "DELETE FROM notes WHERE path = ? OR source_file = ?",
                        (rel_path, rel_path),
                    )
                    continue

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
                    source_fingerprint,
                    links,
                    tags,
                )

                processed_count += 1

        return processed_count

    @staticmethod
    def _stat_signature(stat: os.stat_result) -> tuple[int, int, int, int, int]:
        """Return the fields that identify the bytes observed during a scan."""
        return (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )

    def _source_fingerprint(self, stat: os.stat_result) -> str:
        """Key parsed rows by source identity, parser revision, and settings.

        Reclassification must occur even when only date-collection settings
        change. The revision also refreshes persisted links that older parsers
        stored without journal anchors; no schema migration is needed.
        """
        settings = json.dumps(self.config.date_collection.to_dict(), sort_keys=True)
        config_digest = hashlib.sha256(settings.encode()).hexdigest()
        stat_key = ":".join(str(value) for value in self._stat_signature(stat))
        return f"parser-v2:{config_digest}:{stat_key}"

    def _delete_missing_notes(self, md_files: list[tuple[Path, Path, os.stat_result]]) -> None:
        """Delete notes absent from the validated, writer-owned filesystem view."""
        existing_paths = {
            str(candidate.relative_to(self.vault_path)) for candidate, _resolved, _stat in md_files
        }

        # Delete regular notes (not virtual entries) that no longer exist.
        # Virtual entries are managed by their source_file, not their path.
        if existing_paths:
            # Stage existing paths in a temp table instead of binding one SQL
            # variable per file: a "NOT IN (?,?,...)" placeholder list hits
            # SQLite's variable limit (SQLITE_MAX_VARIABLE_NUMBER, as low as
            # 999 on older builds) - a hard failure for vaults beyond it.
            self.db.execute(
                "CREATE TEMP TABLE IF NOT EXISTS _existing_paths (path TEXT PRIMARY KEY)"
            )
            self.db.execute("DELETE FROM _existing_paths")
            self.db.executemany(
                "INSERT OR IGNORE INTO _existing_paths (path) VALUES (?)",
                ((p,) for p in existing_paths),
            )

            # Only delete non-virtual notes whose paths don't exist;
            # virtual entries are cleaned up via their source_file.
            self.db.execute(
                "DELETE FROM notes WHERE is_virtual = 0 "
                "AND path NOT IN (SELECT path FROM _existing_paths)"
            )
            self.db.execute(
                "DELETE FROM notes WHERE is_virtual = 1 "
                "AND source_file NOT IN (SELECT path FROM _existing_paths)"
            )
            self.db.execute("DELETE FROM _existing_paths")
        else:
            # No files exist, delete all notes
            self.db.execute("DELETE FROM notes")

    def _replace_virtual_notes(
        self,
        source_file: str,
        virtual_notes: list[Note],
        file_mtime: float,
        source_fingerprint: str,
    ) -> None:
        """Update a date collection while preserving history for stable paths."""
        existing_paths = {
            str(row[0])
            for row in self.db.execute(
                "SELECT path FROM notes WHERE source_file = ?", (source_file,)
            ).fetchall()
        }
        new_paths = {note.path for note in virtual_notes}

        # A regular note and its virtual entries represent different identities.
        self.db.execute("DELETE FROM notes WHERE path = ? AND is_virtual = 0", (source_file,))
        stale_paths = existing_paths - new_paths
        if stale_paths:
            self.db.executemany(
                "DELETE FROM notes WHERE path = ?",
                ((path,) for path in stale_paths),
            )
        for virtual_note in virtual_notes:
            self._update_note_from_object(virtual_note, file_mtime, source_fingerprint)

    def _update_note(
        self,
        path: str,
        title: str,
        content: str,
        created: datetime,
        modified: datetime,
        file_mtime: float,
        source_fingerprint: str,
        links: list[Link],
        tags: list[str],
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
        self._update_note_from_object(note, file_mtime, source_fingerprint)

    def _update_note_from_object(
        self, note: Note, file_mtime: float, source_fingerprint: str
    ) -> None:
        """Update a note from a Note object (including virtual entries).

        Args:
            note: Note object to insert/update
            file_mtime: File modification time
        """
        # Semantic embeddings are a cache of current content and must be
        # invalidated on a processed update. Session embeddings are historical
        # records and deliberately survive same-path updates.
        self.db.execute("DELETE FROM embeddings WHERE note_path = ?", (note.path,))
        self.db.execute(
            """
            INSERT INTO notes (
                path, title, content, created, modified, file_mtime,
                source_fingerprint, is_virtual, source_file, entry_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                created = excluded.created,
                modified = excluded.modified,
                file_mtime = excluded.file_mtime,
                source_fingerprint = excluded.source_fingerprint,
                is_virtual = excluded.is_virtual,
                source_file = excluded.source_file,
                entry_date = excluded.entry_date
            """,
            (
                note.path,
                note.title,
                note.content,
                note.created.isoformat(),
                note.modified.isoformat(),
                file_mtime,
                source_fingerprint,
                1 if note.is_virtual else 0,
                note.source_file,
                note.entry_date.isoformat() if note.entry_date else None,
            ),
        )

        # Delete old links and tags
        self.db.execute("DELETE FROM links WHERE source_path = ?", (note.path,))
        self.db.execute("DELETE FROM tags WHERE note_path = ?", (note.path,))

        # Insert new links using batch executemany
        if note.links:
            link_rows = (
                (
                    note.path,
                    link.target,
                    link.display_text,
                    1 if link.is_embed else 0,
                    link.block_ref,
                )
                for link in note.links
            )
            self.db.executemany(
                """
                INSERT INTO links (source_path, target, display_text, is_embed, block_ref)
                VALUES (?, ?, ?, ?, ?)
                """,
                link_rows,
            )

        # Insert new tags using batch executemany
        if note.tags:
            tag_rows = ((note.path, tag) for tag in note.tags)
            self.db.executemany(
                "INSERT INTO tags (note_path, tag) VALUES (?, ?)",
                tag_rows,
            )

    def _build_note_from_row(
        self,
        row: tuple[str, str, str, str, str, int, str | None, str | None],
        links: list[Link],
        tags: list[str],
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

    def all_notes(self) -> list[Note]:
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
        links_by_path: dict[str, list[Link]] = {}
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
        tags_by_path: dict[str, list[str]] = {}
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

    def get_note(self, path: str) -> Note | None:
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

    def get_notes_batch(self, paths: list[str]) -> dict[str, Note | None]:
        """Load multiple notes efficiently in batched queries.

        Performance optimised (OP-6): Batches database queries to load N notes
        in 3 queries instead of 3×N queries. This is significantly faster when
        loading many notes (e.g., backlinks, neighbours).

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

        notes_data: dict[str, dict[str, Any]] = {}
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
        result: dict[str, Note | None] = {}
        for path in paths:
            if path in notes_data:
                data = notes_data[path]
                result[path] = self._build_note_from_row(data["row"], data["links"], data["tags"])
            else:
                result[path] = None

        return result

    def link_index(self) -> NoteLinkIndex:
        """Return the canonical resolver, refreshing after local/external writes."""
        if self.db.in_transaction:
            # A resolver built from uncommitted rows must not outlive a rollback:
            # SQLite's total_changes is not decremented, so the normal cache key
            # cannot distinguish that transition.
            return NoteLinkIndex(
                self.db.execute(
                    "SELECT path, title, is_virtual, source_file, entry_date FROM notes"
                )
            )
        version = (self.db.total_changes, int(self.db.execute("PRAGMA data_version").fetchone()[0]))
        if self._link_index is None or version != self._link_index_version:
            self._link_index = NoteLinkIndex(
                self.db.execute(
                    "SELECT path, title, is_virtual, source_file, entry_date FROM notes"
                )
            )
            self._link_index_version = version
        return self._link_index

    def resolve_link_target(self, target: str, source_path: str | None = None) -> Note | None:
        """Resolve paths, aliases, and journal anchors using their source context.

        Ambiguous titles/basenames are unresolved unless the source directory
        or journal identifies a unique target. See NoteLinkIndex for precedence.
        """
        path = self.link_index().resolve(target, source_path)
        return self.get_note(path) if path is not None else None

    def close(self) -> None:
        """Close database connection."""
        self.db.close()
