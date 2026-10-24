"""Physical source boundaries and failed discovery must survive sync and reopen."""

from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from geistfabrik.config_loader import GeistFabrikConfig
from geistfabrik.embeddings import Session
from geistfabrik.topics import TopicIndex, TopicIndexIncompleteError
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


def test_private_physical_source_cannot_leak_through_alias(tmp_path: Path) -> None:
    private = tmp_path / "Private" / "hidden.md"
    private.parent.mkdir()
    private.write_text("# Confidential acquisition\n")
    (tmp_path / "public.md").symlink_to(private)
    config = GeistFabrikConfig()
    config.filtering.exclude_paths = ["Private/"]
    config.filtering.boundary_enabled = False
    database = tmp_path / "state.db"
    with closing(Vault(tmp_path, database, config)) as vault:
        vault.sync()
        index = TopicIndex(vault.db, config.filtering.exclude_paths)
        assert index.state("public.md").status == "excluded"
        assert index.catalog() == []
        assert vault.db.execute("SELECT * FROM note_topics").fetchall() == []
    with closing(Vault(tmp_path, database, config)) as reopened:
        index = TopicIndex(reopened.db, config.filtering.exclude_paths)
        assert index.state("public.md").status == "excluded"
        assert index.paths("confidential acquisition") == []


def test_shared_prefix_and_template_boundaries(tmp_path: Path) -> None:
    for path in ("Private ideas.md", "Templates/example.md", "public.md"):
        source = tmp_path / path
        source.parent.mkdir(exist_ok=True)
        source.write_text("# Rare subject\n")
    config = GeistFabrikConfig()
    config.filtering.exclude_paths = ["Private"]
    with closing(Vault(tmp_path, config=config)) as vault:
        vault.sync()
        index = TopicIndex(vault.db, config.filtering.exclude_paths)
        assert index.paths("rare subject") == ["public.md"]


def test_discovery_failure_is_explicit_after_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import geistfabrik.vault as vault_module

    source = tmp_path / "blocked.md"
    source.write_text("# Rare subject\n")
    database = tmp_path / "state.db"
    original = vault_module.ensure_contained

    def denied(path: Path, root: Path, **kwargs: Any) -> Path:
        if path == source:
            raise PermissionError("traversal denied")
        return original(path, root, **kwargs)

    with closing(Vault(tmp_path, database)) as vault:
        vault.sync()
        monkeypatch.setattr(vault_module, "ensure_contained", denied)
        vault.sync()
        assert TopicIndex(vault.db).state("blocked.md").status == "error"
    with closing(Vault(tmp_path, database)) as reopened:
        index = TopicIndex(reopened.db)
        assert source.exists()
        assert index.state("blocked.md").status == "error"
        with pytest.raises(TopicIndexIncompleteError):
            index.catalog()
        context = VaultContext(reopened, Session(datetime(2026, 1, 15), reopened.db))
        assert context.topic_state("[[blocked]]").status == "error"


@pytest.mark.parametrize("prefix", ["./Private/", "X/../Private/"])
def test_canonical_source_prefixes_are_honored(tmp_path: Path, prefix: str) -> None:
    source = tmp_path / "Private" / "secret.md"
    source.parent.mkdir()
    source.write_text("# Protected subject\n")
    config = GeistFabrikConfig()
    config.filtering.exclude_paths = [prefix]
    with closing(Vault(tmp_path, config=config)) as vault:
        vault.sync()
        index = TopicIndex(vault.db, config.filtering.exclude_paths)
        assert index.state("Private/secret.md").status == "excluded"
        assert index.catalog() == []


def test_individual_virtual_entry_is_excluded(tmp_path: Path) -> None:
    (tmp_path / "Diary.md").write_text(
        "## 2025-01-01\n# Protected entry\n\nProtected entry.\n"
        "## 2025-01-02\n# Public entry\n\nPublic entry.\n"
    )
    config = GeistFabrikConfig()
    config.filtering.exclude_paths = ["Diary.md/2025-01-01"]
    with closing(Vault(tmp_path, config=config)) as vault:
        vault.sync()
        index = TopicIndex(vault.db, config.filtering.exclude_paths)
        assert index.state("Diary.md/2025-01-01").status == "excluded"
        assert index.paths("protected entry") == []
        assert index.paths("public entry") == ["Diary.md/2025-01-02"]


def _oversized(path: Path) -> None:
    from geistfabrik.config import MAX_NOTE_BYTES

    with path.open("wb") as handle:
        handle.seek(MAX_NOTE_BYTES)
        handle.write(b"x")


def test_new_oversized_source_during_sync_is_not_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "good.md").write_text("# Public topic\n")
    original = TopicIndex.synchronize
    created = False

    def create_after_topics(self: TopicIndex, **kwargs: Any) -> None:
        nonlocal created
        original(self, **kwargs)
        if not created:
            created = True
            _oversized(tmp_path / "late.md")

    with closing(Vault(tmp_path)) as vault:
        monkeypatch.setattr(TopicIndex, "synchronize", create_after_topics)
        vault.sync()
        index = TopicIndex(vault.db)
        assert created and index.state("late.md").status == "error"
        with pytest.raises(TopicIndexIncompleteError):
            index.catalog()


def test_oversized_alias_retarget_cannot_publish_stale_exclusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = tmp_path / "Private" / "large.bin"
    private.parent.mkdir()
    _oversized(private)
    public = tmp_path / "public-large.bin"
    _oversized(public)
    alias = tmp_path / "alias.md"
    alias.symlink_to(private)
    config = GeistFabrikConfig()
    config.filtering.exclude_paths = ["Private/"]
    original = TopicIndex.synchronize
    changed = False

    def retarget_after_topics(self: TopicIndex, **kwargs: Any) -> None:
        nonlocal changed
        original(self, **kwargs)
        if not changed:
            changed = True
            alias.unlink()
            alias.symlink_to(public)

    with closing(Vault(tmp_path, config=config)) as vault:
        monkeypatch.setattr(TopicIndex, "synchronize", retarget_after_topics)
        vault.sync()
        index = TopicIndex(vault.db, config.filtering.exclude_paths)
        assert changed and index.state("alias.md").status == "error"
        assert vault.db.execute(
            "SELECT resolved_path FROM topic_source_identity WHERE source_path='alias.md'"
        ).fetchone() == ("public-large.bin",)
        with pytest.raises(TopicIndexIncompleteError):
            index.catalog()


def test_unconfirmed_physical_provenance_cannot_validate_cached_topics(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("# Public topic\n")
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        index = TopicIndex(vault.db)
        assert index.state("note.md").status == "complete"
        vault.db.execute("DELETE FROM topic_source_identity")
        vault.db.commit()
        assert index.state("note.md").status == "pending"
        with pytest.raises(TopicIndexIncompleteError):
            index.tags("note.md")
        vault.sync()
        assert index.state("note.md").status == "complete"
        assert index.paths("public topic") == ["note.md"]
