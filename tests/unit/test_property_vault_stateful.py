"""Stateful model properties for vault synchronization and SQLite storage modes."""

import os
import sqlite3
from contextlib import ExitStack, closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from geistfabrik import Vault

PATH_VALUES = (
    "alpha.md",
    "notes/beta.md",
    "notes/deep/gamma.md",
    "unicode-例.md",
)
NOTE_PATHS = st.sampled_from(PATH_VALUES)
DISTINCT_PATH_PAIRS = st.sampled_from(
    [(first, second) for first in PATH_VALUES for second in PATH_VALUES if first != second]
)
SAFE_TEXT = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs"),
        whitelist_characters=".,!?_-'",
    ),
    max_size=80,
)
NONEMPTY_SAFE_TEXT = SAFE_TEXT.map(str.strip).filter(bool)
TAG = st.from_regex(r"[a-z][a-z0-9_-]{0,10}", fullmatch=True)
LINK = st.sampled_from(["Alpha", "Beta Note", "Gamma", "Missing Note"])
FIXED_MTIME = 1_700_000_000.0
MTIME_STEP_SECONDS = 4.0
SESSION_DATE = "2000-01-01"

LinkState = tuple[str, str | None, bool, str | None]
RelationshipState = tuple[str, str, str | None, bool, str | None]


@dataclass(frozen=True)
class NoteState:
    """Independent expected state for one persisted note."""

    title: str
    content: str
    links: tuple[LinkState, ...]
    tags: tuple[str, ...]
    is_virtual: bool = False
    source_file: str | None = None
    entry_date: str | None = None


@dataclass(frozen=True)
class RegularNoteCase:
    """Generated regular Markdown plus its independently known parsed fields."""

    content: str
    state: NoteState


@dataclass(frozen=True)
class JournalEntryCase:
    """One generated date-collection entry and its expected parsed fields."""

    entry_date: date
    content: str
    links: tuple[LinkState, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class JournalCase:
    """Generated date-collection source and its independently known entries."""

    content: str
    entries: tuple[JournalEntryCase, ...]


def _link_states(targets: list[str]) -> tuple[LinkState, ...]:
    return tuple(sorted(((target, None, False, None) for target in targets), key=repr))


def _native_path(path: str) -> str:
    """Match Vault's native relative-path representation on every platform."""
    return str(Path(path))


@st.composite
def regular_notes(draw: st.DrawFn) -> RegularNoteCase:
    """Build structured notes with an independent title/link/tag oracle."""
    title = draw(NONEMPTY_SAFE_TEXT)
    body = draw(SAFE_TEXT)
    tags = draw(st.lists(TAG, max_size=3, unique=True))
    links = draw(st.lists(LINK, max_size=3, unique=True))
    references = " ".join(f"[[{target}]]" for target in links)
    tag_text = " ".join(f"#{tag}" for tag in tags)
    content = f"# {title}\n\n{body}\n\n{references}\n\n{tag_text}\n"
    return RegularNoteCase(
        content=content,
        state=NoteState(
            title=title,
            content=content,
            links=_link_states(links),
            tags=tuple(sorted(tags)),
        ),
    )


@st.composite
def journal_cases(draw: st.DrawFn) -> JournalCase:
    """Build date collections whose virtual-note state is known independently."""
    entry_dates = draw(
        st.lists(
            st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
            min_size=2,
            max_size=4,
            unique=True,
        )
    )
    entries: list[JournalEntryCase] = []
    sections: list[str] = []
    for entry_date in sorted(entry_dates):
        body = draw(NONEMPTY_SAFE_TEXT)
        tags = draw(st.lists(TAG, max_size=3, unique=True))
        links = draw(st.lists(LINK, max_size=3, unique=True))
        references = " ".join(f"[[{target}]]" for target in links)
        tag_text = " ".join(f"#{tag}" for tag in tags)
        entry_content = f"{body}\n\n{references}\n\n{tag_text}".strip()
        entries.append(
            JournalEntryCase(
                entry_date=entry_date,
                content=entry_content,
                links=_link_states(links),
                tags=tuple(sorted(tags)),
            )
        )
        sections.append(f"## {entry_date.isoformat()}\n\n{entry_content}")
    return JournalCase(
        content="# Journal\n\n" + "\n\n".join(sections) + "\n",
        entries=tuple(entries),
    )


class _VaultSyncStateMachineBase(RuleBasedStateMachine):
    """Persistent SQLite writers checked against a fresh read-only observer."""

    memory_vault: Vault
    disk_vault: Vault

    def __init__(self) -> None:
        super().__init__()
        self._resources = ExitStack()
        try:
            root = Path(self._resources.enter_context(TemporaryDirectory()))
            self.vault_path = root / "vault"
            self.vault_path.mkdir()
            self.disk_db_path = root / "vault.db"
            self.memory_vault = Vault(self.vault_path)
            self._resources.callback(self.memory_vault.close)
            self.config = self.memory_vault.config
            self.disk_vault = Vault(self.vault_path, self.disk_db_path, config=self.config)
            self._resources.callback(self._close_disk_vault)
        except BaseException:
            self._resources.close()
            raise
        self.expected_notes: dict[str, NoteState] = {}
        self.expected_semantic_paths: set[str] = set()
        self.expected_session_embedding_paths: set[str] = set()
        self._file_mtimes: dict[str, float] = {}
        self._mtime = FIXED_MTIME

    def _close_disk_vault(self) -> None:
        self.disk_vault.close()

    def _restart_disk_vault(self) -> None:
        """Exercise an explicit clean restart without resetting every transition."""
        self.disk_vault.close()
        self.disk_vault = Vault(self.vault_path, self.disk_db_path, config=self.config)

    def _open_disk_observer(self) -> sqlite3.Connection:
        """Open a passive reader that can see committed file-backed state only."""
        uri = f"{self.disk_db_path.resolve().as_uri()}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def _sync_both(self, expected_count: int) -> None:
        assert self.memory_vault.sync() == expected_count
        assert self.disk_vault.sync() == expected_count

    def _write_file(self, path: str, content: str) -> str:
        native_path = _native_path(path)
        note_path = self.vault_path / native_path
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")
        self._stamp_file(native_path)
        return native_path

    def _stamp_file(self, native_path: str) -> None:
        note_path = self.vault_path / native_path
        previous_mtime = self._file_mtimes.get(native_path)
        self._mtime += MTIME_STEP_SECONDS
        os.utime(note_path, (self._mtime, self._mtime))
        actual_mtime = note_path.stat().st_mtime
        if previous_mtime is not None:
            assert actual_mtime != previous_mtime
        self._file_mtimes[native_path] = actual_mtime

    def _remove_expected_source(self, source_file: str) -> None:
        affected_paths = [
            path
            for path, state in self.expected_notes.items()
            if path == source_file or state.source_file == source_file
        ]
        for path in affected_paths:
            self.expected_notes.pop(path)
            self.expected_semantic_paths.discard(path)
            self.expected_session_embedding_paths.discard(path)
        self._file_mtimes.pop(source_file, None)

    @staticmethod
    def _snapshot(vault: Vault) -> dict[str, NoteState]:
        return {
            note.path: NoteState(
                title=note.title,
                content=note.content,
                links=tuple(
                    sorted(
                        (
                            (link.target, link.display_text, link.is_embed, link.block_ref)
                            for link in note.links
                        ),
                        key=repr,
                    )
                ),
                tags=tuple(sorted(note.tags)),
                is_virtual=note.is_virtual,
                source_file=note.source_file,
                entry_date=note.entry_date.isoformat() if note.entry_date else None,
            )
            for note in vault.all_notes()
        }

    @staticmethod
    def _snapshot_connection(connection: sqlite3.Connection) -> dict[str, NoteState]:
        """Read persisted state directly without invoking a mutating Vault constructor."""
        links_by_path: dict[str, list[LinkState]] = {}
        for row in connection.execute(
            "SELECT source_path, target, display_text, is_embed, block_ref FROM links"
        ).fetchall():
            links_by_path.setdefault(str(row[0]), []).append(
                (str(row[1]), row[2], bool(row[3]), row[4])
            )

        tags_by_path: dict[str, list[str]] = {}
        for row in connection.execute("SELECT note_path, tag FROM tags").fetchall():
            tags_by_path.setdefault(str(row[0]), []).append(str(row[1]))

        snapshot: dict[str, NoteState] = {}
        for row in connection.execute(
            "SELECT path, title, content, is_virtual, source_file, entry_date FROM notes"
        ).fetchall():
            path = str(row[0])
            snapshot[path] = NoteState(
                title=str(row[1]),
                content=str(row[2]),
                links=tuple(sorted(links_by_path.get(path, []), key=repr)),
                tags=tuple(sorted(tags_by_path.get(path, []))),
                is_virtual=bool(row[3]),
                source_file=row[4],
                entry_date=row[5],
            )
        return snapshot

    @staticmethod
    def _relationship_snapshot(
        connection: sqlite3.Connection,
    ) -> tuple[tuple[RelationshipState, ...], tuple[tuple[str, str], ...]]:
        links = tuple(
            sorted(
                (
                    (str(row[0]), str(row[1]), row[2], bool(row[3]), row[4])
                    for row in connection.execute(
                        "SELECT source_path, target, display_text, is_embed, block_ref FROM links"
                    ).fetchall()
                ),
                key=repr,
            )
        )
        tags = tuple(
            sorted(
                (str(row[0]), str(row[1]))
                for row in connection.execute("SELECT note_path, tag FROM tags").fetchall()
            )
        )
        return links, tags

    def _expected_relationships(
        self,
    ) -> tuple[tuple[RelationshipState, ...], tuple[tuple[str, str], ...]]:
        links: list[RelationshipState] = []
        tags: list[tuple[str, str]] = []
        for path, state in self.expected_notes.items():
            links.extend((path, *link) for link in state.links)
            tags.extend((path, tag) for tag in state.tags)
        return tuple(sorted(links, key=repr)), tuple(sorted(tags))

    @staticmethod
    def _dependent_paths(connection: sqlite3.Connection) -> tuple[set[str], set[str]]:
        embeddings = {
            str(row[0]) for row in connection.execute("SELECT note_path FROM embeddings").fetchall()
        }
        session_embeddings = {
            str(row[0])
            for row in connection.execute("SELECT note_path FROM session_embeddings").fetchall()
        }
        return embeddings, session_embeddings

    def _assert_connection_matches_model(self, connection: sqlite3.Connection) -> None:
        assert self._snapshot_connection(connection) == self.expected_notes
        assert self._relationship_snapshot(connection) == self._expected_relationships()
        assert self._dependent_paths(connection) == (
            self.expected_semantic_paths,
            self.expected_session_embedding_paths,
        )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    def _assert_vault_matches_model(self, vault: Vault) -> None:
        assert self._snapshot(vault) == self.expected_notes
        self._assert_connection_matches_model(vault.db)
        foreign_keys = vault.db.execute("PRAGMA foreign_keys").fetchone()
        assert foreign_keys is not None and foreign_keys[0] == 1

    @staticmethod
    def _insert_dependent_rows(vault: Vault, path: str) -> None:
        vault.db.execute(
            "INSERT OR IGNORE INTO sessions (date, vault_state_hash, created_at) "
            "VALUES (?, NULL, ?)",
            (SESSION_DATE, SESSION_DATE),
        )
        session = vault.db.execute(
            "SELECT session_id FROM sessions WHERE date = ?", (SESSION_DATE,)
        ).fetchone()
        assert session is not None
        vault.db.execute(
            "INSERT OR REPLACE INTO embeddings "
            "(note_path, embedding, model_version, computed_at) VALUES (?, ?, ?, ?)",
            (path, b"stateful-test", "stateful-test", SESSION_DATE),
        )
        vault.db.execute(
            "INSERT OR REPLACE INTO session_embeddings "
            "(session_id, note_path, embedding, cluster_label) VALUES (?, ?, ?, NULL)",
            (session[0], path, b"stateful-test"),
        )
        vault.db.commit()

    @precondition(lambda self: bool(self.expected_notes))
    @rule()
    def seed_dependent_rows(self) -> None:
        """Seed rows whose cascaded cleanup must survive generated transitions."""
        path = sorted(self.expected_notes)[0]
        self._insert_dependent_rows(self.memory_vault, path)
        self._insert_dependent_rows(self.disk_vault, path)
        self.expected_semantic_paths.add(path)
        self.expected_session_embedding_paths.add(path)

    @rule()
    def repeat_sync(self) -> None:
        """A quiescent sync reports no work in either storage mode."""
        self._sync_both(0)

    @rule()
    def restart_disk_writer(self) -> None:
        """A deliberate clean restart preserves the committed model state."""
        self._restart_disk_vault()

    @invariant()
    def stores_match_the_independent_model(self) -> None:
        self._assert_vault_matches_model(self.memory_vault)
        self._assert_vault_matches_model(self.disk_vault)
        with closing(self._open_disk_observer()) as observer:
            self._assert_connection_matches_model(observer)

    def teardown(self) -> None:
        self._resources.close()


class RegularVaultSyncStateMachine(_VaultSyncStateMachineBase):
    """Exercise regular notes, batching, renames, updates, and deletions."""

    @rule(path=NOTE_PATHS, note=regular_notes())
    def create_or_update_note(self, path: str, note: RegularNoteCase) -> None:
        native_path = self._write_file(path, note.content)
        self.expected_notes[native_path] = note.state
        self.expected_semantic_paths.discard(native_path)
        self._sync_both(1)

    @rule(path=NOTE_PATHS)
    def delete_note(self, path: str) -> None:
        native_path = _native_path(path)
        note_path = self.vault_path / native_path
        if note_path.exists():
            note_path.unlink()
        self.expected_notes.pop(native_path, None)
        self.expected_semantic_paths.discard(native_path)
        self.expected_session_embedding_paths.discard(native_path)
        self._file_mtimes.pop(native_path, None)
        self._sync_both(0)

    @rule(paths=DISTINCT_PATH_PAIRS, first=regular_notes(), second=regular_notes())
    def batch_update_notes(
        self,
        paths: tuple[str, str],
        first: RegularNoteCase,
        second: RegularNoteCase,
    ) -> None:
        first_path = self._write_file(paths[0], first.content)
        second_path = self._write_file(paths[1], second.content)
        self.expected_notes[first_path] = first.state
        self.expected_notes[second_path] = second.state
        self.expected_semantic_paths.difference_update((first_path, second_path))
        self._sync_both(2)

    @precondition(lambda self: bool(self.expected_notes))
    @rule(destination=NOTE_PATHS)
    def rename_note(self, destination: str) -> None:
        source_path = sorted(self.expected_notes)[0]
        destination_path = _native_path(destination)
        if source_path == destination_path:
            self._sync_both(0)
            return

        source_file = self.vault_path / source_path
        destination_file = self.vault_path / destination_path
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.replace(destination_file)
        source_state = self.expected_notes.pop(source_path)
        self.expected_notes.pop(destination_path, None)
        self.expected_notes[destination_path] = source_state
        self.expected_semantic_paths.difference_update((source_path, destination_path))
        self.expected_session_embedding_paths.discard(source_path)
        self._file_mtimes.pop(destination_path, None)
        self._file_mtimes.pop(source_path, None)
        self._stamp_file(destination_path)
        self._sync_both(1)


JOURNAL_PATH = _native_path("journals/history.md")


class DateCollectionVaultSyncStateMachine(_VaultSyncStateMachineBase):
    """Exercise virtual notes and regular/date-collection transitions."""

    def _replace_journal_model(self, journal: JournalCase) -> None:
        old_paths = {
            path
            for path, state in self.expected_notes.items()
            if path == JOURNAL_PATH or state.source_file == JOURNAL_PATH
        }
        new_paths = {
            f"{JOURNAL_PATH}/{entry.entry_date.isoformat()}" for entry in journal.entries
        }
        for stale_path in old_paths - new_paths:
            self.expected_notes.pop(stale_path)
            self.expected_semantic_paths.discard(stale_path)
            self.expected_session_embedding_paths.discard(stale_path)
        for entry in journal.entries:
            entry_date = entry.entry_date.isoformat()
            virtual_path = f"{JOURNAL_PATH}/{entry_date}"
            self.expected_notes[virtual_path] = NoteState(
                title=entry_date,
                content=entry.content,
                links=entry.links,
                tags=entry.tags,
                is_virtual=True,
                source_file=JOURNAL_PATH,
                entry_date=entry_date,
            )
            self.expected_semantic_paths.discard(virtual_path)

    @rule(journal=journal_cases())
    def create_or_update_journal(self, journal: JournalCase) -> None:
        self._replace_journal_model(journal)
        self._write_file(JOURNAL_PATH, journal.content)
        self._sync_both(len(journal.entries))

    @rule(note=regular_notes())
    def convert_journal_to_regular(self, note: RegularNoteCase) -> None:
        virtual_paths = {
            path
            for path, state in self.expected_notes.items()
            if state.source_file == JOURNAL_PATH
        }
        for virtual_path in virtual_paths:
            self.expected_notes.pop(virtual_path)
            self.expected_semantic_paths.discard(virtual_path)
            self.expected_session_embedding_paths.discard(virtual_path)
        self.expected_notes[JOURNAL_PATH] = note.state
        self.expected_semantic_paths.discard(JOURNAL_PATH)
        self._write_file(JOURNAL_PATH, note.content)
        self._sync_both(1)

    @rule()
    def delete_journal_source(self) -> None:
        journal_path = self.vault_path / JOURNAL_PATH
        if journal_path.exists():
            journal_path.unlink()
        self._remove_expected_source(JOURNAL_PATH)
        self._sync_both(0)


TestRegularVaultSyncStateMachine = RegularVaultSyncStateMachine.TestCase
TestRegularVaultSyncStateMachine.settings = settings(
    max_examples=30,
    stateful_step_count=25,
    deadline=None,
)

TestDateCollectionVaultSyncStateMachine = DateCollectionVaultSyncStateMachine.TestCase
TestDateCollectionVaultSyncStateMachine.settings = settings(
    max_examples=30,
    stateful_step_count=25,
    deadline=None,
)
