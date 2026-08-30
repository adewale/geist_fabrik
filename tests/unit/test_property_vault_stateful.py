"""Stateful differential properties for vault synchronization."""

import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from geistfabrik import Vault

NOTE_PATHS = st.sampled_from(
    [
        "alpha.md",
        "notes/beta.md",
        "notes/deep/gamma.md",
        "unicode-例.md",
    ]
)
SAFE_TEXT = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs"),
        whitelist_characters=".,!?_-'",
    ),
    max_size=80,
)
TAG = st.from_regex(r"[a-z][a-z0-9_-]{0,10}", fullmatch=True)
LINK = st.sampled_from(["Alpha", "Beta Note", "Gamma", "Missing Note"])


@st.composite
def markdown_notes(draw: st.DrawFn) -> str:
    """Build parseable Obsidian notes instead of feeding undifferentiated text."""
    title = draw(SAFE_TEXT.map(str.strip).filter(bool))
    body = draw(SAFE_TEXT)
    tags = draw(st.lists(TAG, max_size=3, unique=True))
    links = draw(st.lists(LINK, max_size=3, unique=True))
    references = " ".join(f"[[{target}]]" for target in links)
    tag_text = " ".join(f"#{tag}" for tag in tags)
    return f"# {title}\n\n{body}\n\n{references}\n\n{tag_text}\n"


class VaultSyncStateMachine(RuleBasedStateMachine):
    """Compare two persistence modes with a filesystem-content model."""

    def __init__(self) -> None:
        super().__init__()
        self._temporary = TemporaryDirectory()
        root = Path(self._temporary.name)
        self.vault_path = root / "vault"
        self.vault_path.mkdir()
        self.memory_vault = Vault(self.vault_path, ":memory:")
        self.disk_vault = Vault(self.vault_path, root / "vault.db")
        self.expected_content: dict[str, str] = {}
        self._mtime = time.time() + 10

    def _sync_both(self) -> None:
        self.memory_vault.sync()
        self.disk_vault.sync()

    @staticmethod
    def _snapshot(vault: Vault) -> dict[str, tuple[object, ...]]:
        return {
            note.path: (
                note.title,
                note.content,
                tuple(note.links),
                tuple(note.tags),
                note.is_virtual,
                note.source_file,
            )
            for note in vault.all_notes()
        }

    @rule(path=NOTE_PATHS, content=markdown_notes())
    def create_or_update_note(self, path: str, content: str) -> None:
        note_path = self.vault_path / path
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")
        self._mtime += 1
        os.utime(note_path, (self._mtime, self._mtime))
        self.expected_content[path] = content
        self._sync_both()

    @rule(path=NOTE_PATHS)
    def delete_note(self, path: str) -> None:
        note_path = self.vault_path / path
        if note_path.exists():
            note_path.unlink()
        self.expected_content.pop(path, None)
        self._sync_both()

    @rule()
    def repeat_sync(self) -> None:
        """A quiescent sync is idempotent in both persistence modes."""
        assert self.memory_vault.sync() == 0
        assert self.disk_vault.sync() == 0

    @invariant()
    def stores_match_the_filesystem_model(self) -> None:
        memory = self._snapshot(self.memory_vault)
        disk = self._snapshot(self.disk_vault)
        assert memory == disk
        assert {path: row[1] for path, row in memory.items()} == self.expected_content

    def teardown(self) -> None:
        self.memory_vault.close()
        self.disk_vault.close()
        self._temporary.cleanup()


TestVaultSyncStateMachine = VaultSyncStateMachine.TestCase
TestVaultSyncStateMachine.settings = settings(
    max_examples=30,
    stateful_step_count=25,
    deadline=None,
)
