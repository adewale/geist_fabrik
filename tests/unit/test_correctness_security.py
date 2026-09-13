"""Regression tests for the correctness/security hardening tranche."""

import errno
import hashlib
import os
import signal
import sqlite3
import subprocess
import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, TypeAlias, cast

import pytest

from geistfabrik.bounded_yaml import MAX_YAML_BYTES, BoundedYAMLError, load_bounded_yaml
from geistfabrik.cli import create_parser
from geistfabrik.commands.base import ExecutionContext
from geistfabrik.commands.batch_runner import TestAllCommand as GeistTestAllCommand
from geistfabrik.commands.invoke import InvokeCommand
from geistfabrik.commands.runner import TestCommand as GeistTestCommand
from geistfabrik.config import (
    MAX_GEIST_TIMEOUT,
    MAX_NOTE_BYTES,
    MAX_NOTE_LINKS,
    MAX_SESSION_SUGGESTIONS,
    MAX_TRACERY_COUNT,
    MAX_TRACERY_RULE_BYTES,
)
from geistfabrik.config_loader import ConfigError, GeistFabrikConfig, load_config
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.geist_executor import GeistExecutor, GeistTimeoutError, _alarm_timeout
from geistfabrik.geist_status import GeistStatusStore
from geistfabrik.journal_writer import JournalWriter
from geistfabrik.markdown_parser import MarkdownLimitError, extract_links, parse_frontmatter
from geistfabrik.metadata_system import MetadataLoader
from geistfabrik.models import Suggestion
from geistfabrik.path_safety import PathSafetyError
from geistfabrik.schema import SCHEMA_VERSION, get_schema_version, init_db
from geistfabrik.tracery import (
    TraceryEngine,
    TraceryExecutionError,
    TraceryGeist,
    TraceryGeistLoader,
    TraceryLimitError,
)
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext

SqlValue: TypeAlias = str | bytes | int | float | None
SqlParameters: TypeAlias = Sequence[SqlValue] | Mapping[str, SqlValue]


def _legacy_db(path: Path, version: int) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE notes (
            path TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
            created TEXT NOT NULL, modified TEXT NOT NULL, file_mtime REAL NOT NULL,
            is_virtual INTEGER DEFAULT 0, source_file TEXT, entry_date TEXT
        );
        CREATE TABLE links (
            source_path TEXT NOT NULL, target TEXT NOT NULL, display_text TEXT,
            is_embed INTEGER NOT NULL DEFAULT 0, block_ref TEXT
        );
        CREATE TABLE session_embeddings (
            session_id INTEGER NOT NULL, note_path TEXT NOT NULL, embedding BLOB NOT NULL,
            PRIMARY KEY (session_id, note_path)
        );
        INSERT INTO notes VALUES (
            'sentinel.md', 'Sentinel', 'keep me', '2025-01-01', '2025-01-01',
            1.0, 0, NULL, NULL
        );
        """
    )
    if version >= 7:
        db.execute("ALTER TABLE session_embeddings ADD COLUMN cluster_label TEXT")
    db.execute(f"PRAGMA user_version = {version}")
    db.commit()
    db.close()


@pytest.mark.parametrize("version", [6, 7])
def test_file_backed_legacy_database_migrates_via_vault(tmp_path: Path, version: int) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    db_path = vault_path / "legacy.db"
    _legacy_db(db_path, version)

    vault = Vault(vault_path, db_path)
    assert get_schema_version(vault.db) == SCHEMA_VERSION
    assert vault.db.execute("SELECT content FROM notes WHERE path='sentinel.md'").fetchone() == (
        "keep me",
    )
    columns = {row[1] for row in vault.db.execute("PRAGMA table_info(session_embeddings)")}
    assert "cluster_label" in columns
    assert vault.db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='geist_status'"
    ).fetchone()
    vault.close()


def test_prematurely_stamped_v8_repairs_missing_additive_column(tmp_path: Path) -> None:
    db_path = tmp_path / "premature-v8.db"
    _legacy_db(db_path, 6)
    db = sqlite3.connect(db_path)
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    db.commit()
    db.close()

    repaired = init_db(db_path)
    columns = {row[1] for row in repaired.execute("PRAGMA table_info(session_embeddings)")}
    assert "cluster_label" in columns
    assert get_schema_version(repaired) == SCHEMA_VERSION
    repaired.close()


def test_malformed_supported_schema_rolls_back_entire_upgrade(tmp_path: Path) -> None:
    db_path = tmp_path / "malformed.db"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE notes (path TEXT PRIMARY KEY)")
    db.execute("PRAGMA user_version = 7")
    db.commit()
    db.close()

    with pytest.raises(sqlite3.OperationalError, match="modified"):
        init_db(db_path)

    check = sqlite3.connect(db_path)
    assert get_schema_version(check) == 7
    assert check.execute("PRAGMA table_info(notes)").fetchall() == [(0, "path", "TEXT", 0, None, 1)]
    assert (
        check.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='geist_status'"
        ).fetchone()
        is None
    )
    check.close()


def test_future_database_is_rejected_without_mutation(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    db_path = vault_path / "future.db"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE sentinel (value TEXT)")
    db.execute("INSERT INTO sentinel VALUES ('keep')")
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    db.commit()
    db.close()

    with pytest.raises(RuntimeError, match="newer"):
        Vault(vault_path, db_path)
    check = sqlite3.connect(db_path)
    assert get_schema_version(check) == SCHEMA_VERSION + 1
    assert check.execute("SELECT value FROM sentinel").fetchone() == ("keep",)


@pytest.mark.parametrize(
    "yaml_text,key",
    [
        ("geist_execution:\n  timeout: 0\n", "geist_execution.timeout"),
        (f"geist_execution:\n  timeout: {MAX_GEIST_TIMEOUT + 1}\n", "geist_execution.timeout"),
        ("geist_execution:\n  max_failures: true\n", "geist_execution.max_failures"),
        ("session:\n  default_suggestions: -1\n", "session.default_suggestions"),
        ("geist_execution: []\n", "geist_execution"),
        ("enabled_modules: {}\n", "enabled_modules"),
        ("default_geists: []\n", "default_geists"),
        ("default_geists:\n  unsafe: 1\n", "default_geists"),
        ('date_collection:\n  enabled: "false"\n', "date_collection.enabled"),
        ("date_collection:\n  exclude_files: '*.md'\n", "date_collection.exclude_files"),
        ("date_collection:\n  min_sections: 0\n", "date_collection.min_sections"),
        ("date_collection:\n  date_threshold: 1.1\n", "date_collection.date_threshold"),
        ("vector_search:\n  backend: external\n", "vector_search.backend"),
        ("vector_search:\n  backends: []\n", "backends"),
        ("clustering:\n  labeling_method: magic\n", "clustering.labeling_method"),
        ("clustering:\n  min_cluster_size: 1\n", "clustering.min_cluster_size"),
        ("clustering:\n  n_label_terms: 0\n", "clustering.n_label_terms"),
        ("session_embedding_retention: -1\n", "session_embedding_retention"),
        ("filtering:\n  boundary: []\n", "filtering.boundary"),
        ("filtering:\n  boundary:\n    exclude_paths: Private/\n", "exclude_paths"),
        ("filtering:\n  novelty:\n    window_days: -1\n", "window_days"),
        ("filtering:\n  novelty:\n    threshold: true\n", "threshold"),
        (
            "filtering:\n  quality:\n    min_length: 100\n    max_length: 10\n",
            "min_length",
        ),
        ("unknown_security_key: true\n", "unknown_security_key"),
        ("- not-a-mapping\n", "configuration root"),
    ],
)
def test_invalid_config_fails_closed(tmp_path: Path, yaml_text: str, key: str) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(yaml_text)
    with pytest.raises(ConfigError, match=key):
        load_config(path)


@pytest.mark.parametrize(
    "argv",
    [
        ["invoke", "/tmp", "--timeout", "0"],
        ["invoke", "/tmp", "--count", "1001"],
        ["test", "g", "/tmp", "--timeout", "3601"],
        ["test-all", "/tmp", "--timeout", "-1"],
    ],
)
def test_cli_rejects_unbounded_integers(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        create_parser().parse_args(argv)
    assert exc.value.code == 2


def test_command_rejects_malformed_config_before_database_or_plugin_import(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    managed = vault_path / "_geistfabrik"
    plugin_dir = managed / "metadata_inference"
    plugin_dir.mkdir(parents=True)
    marker = tmp_path / "plugin-executed"
    (plugin_dir / "unsafe.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "def infer(note, vault): return {}\n"
    )
    (managed / "config.yaml").write_text("enabled_modules: {}\n")
    (vault_path / "note.md").write_text("# Note\n")
    args = create_parser().parse_args(["invoke", str(vault_path), "--write"])

    assert InvokeCommand(args).run() == 1
    assert not marker.exists()
    assert not (managed / "vault.db").exists()
    assert not (vault_path / "geist journal").exists()


def test_validate_rejects_malformed_config_before_importing_code_geist(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    code_dir = vault_path / "_geistfabrik" / "geists" / "code"
    code_dir.mkdir(parents=True)
    marker = tmp_path / "validate-imported"
    (code_dir / "unsafe.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "def suggest(vault): return []\n"
    )
    (vault_path / "_geistfabrik" / "config.yaml").write_text("enabled_modules: {}\n")
    args = create_parser().parse_args(["validate", str(vault_path), "--geist", "unsafe"])

    from geistfabrik.commands.validate import ValidateCommand

    assert ValidateCommand(args).run() == 1
    assert not marker.exists()
    assert not (vault_path / "_geistfabrik" / "vault.db").exists()


@pytest.mark.parametrize("geist_id", ["../outside", "nested/escape", "bad.yaml"])
def test_validate_rejects_non_filename_geist_id(tmp_path: Path, geist_id: str) -> None:
    vault_path = tmp_path / "vault"
    managed = vault_path / "_geistfabrik"
    (managed / "geists" / "code").mkdir(parents=True)
    (managed / "geists" / "tracery").mkdir(parents=True)
    (managed / "config.yaml").write_text("enabled_modules: []\n")
    args = create_parser().parse_args(["validate", str(vault_path), "--geist", geist_id])
    from geistfabrik.commands.validate import ValidateCommand

    assert ValidateCommand(args).run() == 1
    assert not (managed / "vault.db").exists()


def test_validate_rejects_leaf_code_symlink_before_import(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    managed = vault_path / "_geistfabrik"
    code_dir = managed / "geists" / "code"
    (managed / "geists" / "tracery").mkdir(parents=True)
    code_dir.mkdir(parents=True)
    (managed / "config.yaml").write_text("enabled_modules: []\n")
    marker = tmp_path / "executed"
    outside = tmp_path / "outside.py"
    outside.write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('yes')\n"
        "def suggest(vault): return []\n"
    )
    try:
        (code_dir / "linked.py").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    args = create_parser().parse_args(["validate", str(vault_path), "--geist", "linked"])
    from geistfabrik.commands.validate import ValidateCommand

    assert ValidateCommand(args).run() == 1
    assert not marker.exists()


def test_canonical_config_is_used_by_direct_vault(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    config_dir = vault_path / "_geistfabrik"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text("date_collection:\n  enabled: false\n")
    (vault_path / "Journal.md").write_text("## 2025-01-01\nOne\n## 2025-01-02\nTwo\n")
    vault = Vault(vault_path)
    vault.sync()
    notes = vault.all_notes()
    assert len(notes) == 1
    assert notes[0].is_virtual is False


def _suggestion(text: str) -> Suggestion:
    return Suggestion(text=text, notes=[], geist_id="test")


def test_journal_recovery_hash_is_canonical_at_one_thousand_rows(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    writer = JournalWriter(vault_path, vault.db)
    date = datetime(2025, 1, 2)
    suggestions = [_suggestion(f"suggestion {index}") for index in range(1000)]
    path = writer.write_session(date, suggestions)
    assert writer._database_state_hash("2025-01-02") == writer._expected_state_hash(
        date, suggestions
    )

    content = path.read_bytes()
    writer._write_pending_record(
        path,
        had_old_file=True,
        expected_database_hash=writer._expected_state_hash(date, suggestions),
        expected_file_hash=hashlib.sha256(content).hexdigest(),
        old_file_hash=hashlib.sha256(content).hexdigest(),
    )
    JournalWriter(vault_path, vault.db)
    assert not list((vault_path / "geist journal").glob(".*.pending"))


def test_journal_rejects_malformed_suggestion_fields(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    malformed = Suggestion(text=cast(Any, 123), notes=[], geist_id="bad")
    with pytest.raises(TypeError, match="text must be a string"):
        JournalWriter(vault_path, vault.db).write_session(datetime(2025, 1, 2), [malformed])
    assert not (vault_path / "geist journal").exists()


def test_journal_rejects_more_than_session_limit(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    suggestions = [
        _suggestion(f"suggestion {index}") for index in range(MAX_SESSION_SUGGESTIONS + 1)
    ]
    with pytest.raises(ValueError, match="session has more than"):
        JournalWriter(vault_path, vault.db).write_session(datetime(2025, 1, 2), suggestions)
    assert not (vault_path / "geist journal").exists()


def test_journal_force_replacement_exactly_mirrors_database(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    writer = JournalWriter(vault_path, vault.db)
    date = datetime(2025, 1, 2)
    path = writer.write_session(date, [_suggestion("old one"), _suggestion("old two")])
    writer.write_session(date, [_suggestion("new")], overwrite=True)
    assert "new" in path.read_text() and "old one" not in path.read_text()
    assert vault.db.execute(
        "SELECT suggestion_text FROM session_suggestions WHERE session_date='2025-01-02'"
    ).fetchall() == [("new",)]


def test_journal_exclusive_create_refuses_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    writer = JournalWriter(vault_path, vault.db)
    date = datetime(2025, 1, 2)
    real_link = __import__("os").link

    def race_link(
        source: str | Path,
        destination: str | Path,
        **kwargs: Any,
    ) -> None:
        destination_fd = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=cast(int | None, kwargs.get("dst_dir_fd")),
        )
        os.write(destination_fd, b"raced")
        os.close(destination_fd)
        real_link(source, destination, **kwargs)

    monkeypatch.setattr("geistfabrik.journal_writer.os.link", race_link)
    with pytest.raises(FileExistsError):
        writer.write_session(date, [_suggestion("new")])
    path = vault_path / "geist journal" / "2025-01-02.md"
    assert path.read_text() == "raced"
    assert vault.db.execute("SELECT * FROM session_suggestions").fetchall() == []


def test_journal_force_preserves_edit_made_after_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    writer = JournalWriter(vault_path, vault.db)
    path = writer.write_session(date, [_suggestion("old")])
    original = writer._replace_suggestion_rows

    def edit_after_database_update(date_str: str, suggestions: list[Suggestion]) -> None:
        original(date_str, suggestions)
        path.write_text("concurrent user edit")

    monkeypatch.setattr(writer, "_replace_suggestion_rows", edit_after_database_update)
    with pytest.raises(RuntimeError, match="changed during write"):
        writer.write_session(date, [_suggestion("new")], overwrite=True)

    assert path.read_text() == "concurrent user edit"
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]
    assert not list(writer.journal_dir.glob(".*.pending"))
    assert not list(writer.journal_dir.glob(".*.previous"))


def test_journal_force_preserves_edit_at_install_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    writer = JournalWriter(vault_path, vault.db)
    path = writer.write_session(date, [_suggestion("old")])
    original = writer._install_staged_file

    def edit_at_install(*args: Any, **kwargs: Any) -> None:
        path.write_text("last-moment user edit")
        original(*args, **kwargs)

    monkeypatch.setattr(writer, "_install_staged_file", edit_at_install)
    with pytest.raises(RuntimeError, match="immediately before replacement"):
        writer.write_session(date, [_suggestion("new")], overwrite=True)

    assert path.read_text() == "last-moment user edit"
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]


def test_journal_exclusive_create_falls_back_when_hardlinks_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)

    def unsupported_link(*args: Any, **kwargs: Any) -> None:
        raise OSError(errno.ENOTSUP, "hard links unsupported")

    monkeypatch.setattr("geistfabrik.journal_writer.os.link", unsupported_link)
    path = JournalWriter(vault_path, vault.db).write_session(
        datetime(2025, 1, 2), [_suggestion("fallback")]
    )
    assert "fallback" in path.read_text()
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("fallback",)
    ]


def test_journal_directory_swap_rolls_back_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.name == "nt":
        pytest.skip("descriptor-relative directory identity is POSIX-only")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    writer = JournalWriter(vault_path, vault.db)
    original_install = writer._install_staged_file
    moved = tmp_path / "moved-journal"

    def swap_after_install(*args: Any, **kwargs: Any) -> None:
        original_install(*args, **kwargs)
        writer.journal_dir.rename(moved)
        writer.journal_dir.mkdir()

    monkeypatch.setattr(writer, "_install_staged_file", swap_after_install)
    with pytest.raises(PathSafetyError, match="identity changed"):
        writer.write_session(datetime(2025, 1, 2), [_suggestion("never commit")])
    assert vault.db.execute("SELECT * FROM session_suggestions").fetchall() == []
    assert list(moved.iterdir()) == []
    assert list(writer.journal_dir.iterdir()) == []


def test_journal_directory_swap_before_pending_cleans_original_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.name == "nt":
        pytest.skip("descriptor-relative directory identity is POSIX-only")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    writer = JournalWriter(vault_path, vault.db)
    writer.write_session(date, [_suggestion("old")])
    original = writer._write_pending_record
    moved = tmp_path / "moved-before-pending"

    def swap_then_write(*args: Any, **kwargs: Any) -> tuple[Path, Path]:
        writer.journal_dir.rename(moved)
        writer.journal_dir.mkdir()
        return original(*args, **kwargs)

    monkeypatch.setattr(writer, "_write_pending_record", swap_then_write)
    with pytest.raises(PathSafetyError, match="identity changed"):
        writer.write_session(date, [_suggestion("new")], overwrite=True)

    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]
    assert [path.name for path in moved.iterdir()] == ["2025-01-02.md"]
    assert list(writer.journal_dir.iterdir()) == []


def test_journal_swap_during_final_fsync_prevents_commit_and_cleans_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.name == "nt":
        pytest.skip("descriptor-relative directory identity is POSIX-only")
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    writer = JournalWriter(vault_path, vault.db)
    original_fsync = writer._fsync_journal
    moved = tmp_path / "moved-during-fsync"

    def swap_after_generated_file(descriptor: int | None) -> None:
        original_fsync(descriptor)
        session = writer._read_sibling(writer.journal_dir / "2025-01-02.md", descriptor)
        if session is not None and b"never commit" in session and not moved.exists():
            writer.journal_dir.rename(moved)
            writer.journal_dir.mkdir()

    monkeypatch.setattr(writer, "_fsync_journal", swap_after_generated_file)
    with pytest.raises(PathSafetyError, match="identity changed"):
        writer.write_session(datetime(2025, 1, 2), [_suggestion("never commit")])

    assert vault.db.execute("SELECT * FROM session_suggestions").fetchall() == []
    assert list(moved.iterdir()) == []
    assert list(writer.journal_dir.iterdir()) == []


def test_journal_database_failure_restores_old_file_and_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    writer = JournalWriter(vault_path, vault.db)
    date = datetime(2025, 1, 2)
    path = writer.write_session(date, [_suggestion("old")])
    old_bytes = path.read_bytes()

    original = writer._replace_suggestion_rows

    def fail_after_replace(date_str: str, suggestions: list[Suggestion]) -> None:
        original(date_str, suggestions)
        raise sqlite3.OperationalError("injected")

    monkeypatch.setattr(writer, "_replace_suggestion_rows", fail_after_replace)
    with pytest.raises(sqlite3.OperationalError):
        writer.write_session(date, [_suggestion("new")], overwrite=True)
    assert path.read_bytes() == old_bytes
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]


def test_invoke_force_delegates_overwrite_and_preserves_state_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    path = JournalWriter(vault_path, vault.db).write_session(date, [_suggestion("old")])
    old_bytes = path.read_bytes()

    original = JournalWriter._replace_suggestion_rows

    def fail_after_replace(
        writer: JournalWriter, date_str: str, suggestions: list[Suggestion]
    ) -> None:
        assert path.exists(), "InvokeCommand must not pre-unlink the existing journal"
        original(writer, date_str, suggestions)
        raise sqlite3.OperationalError("injected")

    monkeypatch.setattr(JournalWriter, "_replace_suggestion_rows", fail_after_replace)
    args = create_parser().parse_args(
        ["invoke", str(vault_path), "--write", "--force", "--date", "2025-01-02"]
    )
    command = InvokeCommand(args)

    context = object.__new__(ExecutionContext)
    context.vault_path = vault_path
    context.vault = vault
    assert command._write_journal(context, date, [_suggestion("new")]) is False
    assert path.read_bytes() == old_bytes
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]


def test_journal_rejects_outer_transaction_without_file_change(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()
    path = journal_dir / "2025-01-02.md"
    path.write_bytes(b"existing journal")
    vault.db.execute(
        """
        INSERT INTO session_suggestions
        (session_date, geist_id, suggestion_text, block_id, created_at)
        VALUES ('2025-01-01', 'outer', 'pending', '^pending', 'now')
        """
    )
    assert vault.db.in_transaction
    before = {item.name: item.read_bytes() for item in journal_dir.iterdir()}

    with pytest.raises(RuntimeError, match="idle SQLite connection"):
        JournalWriter(vault_path, vault.db).write_session(
            datetime(2025, 1, 2), [_suggestion("new")], overwrite=True
        )

    assert vault.db.in_transaction
    assert {item.name: item.read_bytes() for item in journal_dir.iterdir()} == before
    vault.db.rollback()


def test_journal_commit_failure_restores_replaced_file(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    normal_writer = JournalWriter(vault_path, vault.db)
    path = normal_writer.write_session(date, [_suggestion("old")])
    old_bytes = path.read_bytes()

    class FailingCommitConnection:
        def __init__(self, db: sqlite3.Connection):
            self.db = db
            self.failed = False

        @property
        def in_transaction(self) -> bool:
            return self.db.in_transaction

        def execute(self, sql: str, parameters: SqlParameters = ()) -> sqlite3.Cursor:
            return self.db.execute(sql, parameters)

        def executemany(self, sql: str, rows: Iterable[SqlParameters]) -> sqlite3.Cursor:
            return self.db.executemany(sql, rows)

        def commit(self) -> None:
            if not self.failed:
                self.failed = True
                raise sqlite3.OperationalError("injected commit failure")
            self.db.commit()

        def rollback(self) -> None:
            self.db.rollback()

    failing_db = cast(sqlite3.Connection, FailingCommitConnection(vault.db))
    writer = JournalWriter(vault_path, failing_db)
    with pytest.raises(sqlite3.OperationalError):
        writer.write_session(date, [_suggestion("new")], overwrite=True)
    assert path.read_bytes() == old_bytes
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]


def test_journal_missing_backup_preserves_generated_file_and_recovery_record(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    path = JournalWriter(vault_path, vault.db).write_session(date, [_suggestion("old")])

    class MissingBackupCommitConnection:
        def __init__(self, db: sqlite3.Connection):
            self.db = db

        @property
        def in_transaction(self) -> bool:
            return self.db.in_transaction

        def execute(self, sql: str, parameters: SqlParameters = ()) -> sqlite3.Cursor:
            return self.db.execute(sql, parameters)

        def executemany(self, sql: str, rows: Iterable[SqlParameters]) -> sqlite3.Cursor:
            return self.db.executemany(sql, rows)

        def commit(self) -> None:
            next((vault_path / "geist journal").glob(".*.previous")).unlink()
            raise sqlite3.OperationalError("injected commit failure")

        def rollback(self) -> None:
            self.db.rollback()

    failing_db = cast(sqlite3.Connection, MissingBackupCommitConnection(vault.db))
    with pytest.raises(RuntimeError, match="backup is unavailable"):
        JournalWriter(vault_path, failing_db).write_session(
            date, [_suggestion("new")], overwrite=True
        )

    assert "new" in path.read_text()
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]
    assert list((vault_path / "geist journal").glob(".*.pending"))


def test_journal_corrupt_backup_preserves_generated_file_and_recovery_record(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    path = JournalWriter(vault_path, vault.db).write_session(date, [_suggestion("old")])

    class CorruptBackupCommitConnection:
        def __init__(self, db: sqlite3.Connection):
            self.db = db

        @property
        def in_transaction(self) -> bool:
            return self.db.in_transaction

        def execute(self, sql: str, parameters: SqlParameters = ()) -> sqlite3.Cursor:
            return self.db.execute(sql, parameters)

        def executemany(self, sql: str, rows: Iterable[SqlParameters]) -> sqlite3.Cursor:
            return self.db.executemany(sql, rows)

        def commit(self) -> None:
            next((vault_path / "geist journal").glob(".*.previous")).write_bytes(b"corrupt")
            raise sqlite3.OperationalError("injected commit failure")

        def rollback(self) -> None:
            self.db.rollback()

    failing_db = cast(sqlite3.Connection, CorruptBackupCommitConnection(vault.db))
    with pytest.raises(RuntimeError, match="backup is corrupt"):
        JournalWriter(vault_path, failing_db).write_session(
            date, [_suggestion("new")], overwrite=True
        )

    assert "new" in path.read_text()
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]
    assert list((vault_path / "geist journal").glob(".*.pending"))


def test_journal_empty_reservation_is_recovered_after_process_death(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    writer = JournalWriter(vault_path, vault.db)
    path = writer._safe_session_path(date, create_dir=True)
    suggestions = [_suggestion("generated")]
    content = writer._format_session_note(date, suggestions, "default").encode()
    writer._write_pending_record(
        path,
        had_old_file=False,
        expected_database_hash=writer._expected_state_hash(date, suggestions),
        expected_file_hash=hashlib.sha256(content).hexdigest(),
        old_file_hash=None,
    )
    path.touch()

    JournalWriter(vault_path, vault.db)
    assert not path.exists()
    assert list(writer.journal_dir.iterdir()) == []


def test_journal_immediate_rollback_preserves_concurrent_user_edit(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    path = JournalWriter(vault_path, vault.db).write_session(date, [_suggestion("old")])

    class EditingFailCommitConnection:
        def __init__(self, db: sqlite3.Connection):
            self.db = db

        @property
        def in_transaction(self) -> bool:
            return self.db.in_transaction

        def execute(self, sql: str, parameters: SqlParameters = ()) -> sqlite3.Cursor:
            return self.db.execute(sql, parameters)

        def executemany(self, sql: str, rows: Iterable[SqlParameters]) -> sqlite3.Cursor:
            return self.db.executemany(sql, rows)

        def commit(self) -> None:
            path.write_text("concurrent user edit")
            raise sqlite3.OperationalError("injected commit failure")

        def rollback(self) -> None:
            self.db.rollback()

    editing_db = cast(sqlite3.Connection, EditingFailCommitConnection(vault.db))
    with pytest.raises(RuntimeError, match="rollback conflict"):
        JournalWriter(vault_path, editing_db).write_session(
            date, [_suggestion("new")], overwrite=True
        )
    assert path.read_text() == "concurrent user edit"
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]
    assert list((vault_path / "geist journal").glob(".*.pending"))


def test_journal_keyboard_interrupt_restores_file_and_database(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    path = JournalWriter(vault_path, vault.db).write_session(date, [_suggestion("old")])
    old_bytes = path.read_bytes()

    class InterruptingCommitConnection:
        def __init__(self, db: sqlite3.Connection):
            self.db = db

        @property
        def in_transaction(self) -> bool:
            return self.db.in_transaction

        def execute(self, sql: str, parameters: SqlParameters = ()) -> sqlite3.Cursor:
            return self.db.execute(sql, parameters)

        def executemany(self, sql: str, rows: Iterable[SqlParameters]) -> sqlite3.Cursor:
            return self.db.executemany(sql, rows)

        def commit(self) -> None:
            raise KeyboardInterrupt

        def rollback(self) -> None:
            self.db.rollback()

    interrupting_db = cast(sqlite3.Connection, InterruptingCommitConnection(vault.db))
    with pytest.raises(KeyboardInterrupt):
        JournalWriter(vault_path, interrupting_db).write_session(
            date, [_suggestion("new")], overwrite=True
        )
    assert path.read_bytes() == old_bytes
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]


def test_journal_post_commit_interrupt_preserves_commit_and_later_user_edit(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    path = JournalWriter(vault_path, vault.db).write_session(date, [_suggestion("old")])

    class PostCommitInterruptConnection:
        def __init__(self, db: sqlite3.Connection):
            self.db = db

        @property
        def in_transaction(self) -> bool:
            return self.db.in_transaction

        def execute(self, sql: str, parameters: SqlParameters = ()) -> sqlite3.Cursor:
            return self.db.execute(sql, parameters)

        def executemany(self, sql: str, rows: Iterable[SqlParameters]) -> sqlite3.Cursor:
            return self.db.executemany(sql, rows)

        def commit(self) -> None:
            self.db.commit()
            raise KeyboardInterrupt

        def rollback(self) -> None:
            self.db.rollback()

    post_commit_db = cast(sqlite3.Connection, PostCommitInterruptConnection(vault.db))
    with pytest.raises(KeyboardInterrupt):
        JournalWriter(vault_path, post_commit_db).write_session(
            date, [_suggestion("new")], overwrite=True
        )
    assert "new" in path.read_text()
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("new",)
    ]
    assert list((vault_path / "geist journal").glob(".*.pending"))

    path.write_text("user edit after committed write")
    JournalWriter(vault_path, vault.db)
    assert path.read_text() == "user edit after committed write"
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("new",)
    ]
    assert not list((vault_path / "geist journal").glob(".*.pending"))


def test_journal_restores_before_releasing_database_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    db_path = tmp_path / "journal.db"
    setup_vault = Vault(vault_path, db_path)
    date = datetime(2025, 1, 2)
    JournalWriter(vault_path, setup_vault.db).write_session(date, [_suggestion("old")])
    setup_vault.close()

    first_db = sqlite3.connect(db_path, timeout=5, check_same_thread=False)
    second_db = sqlite3.connect(db_path, timeout=5, check_same_thread=False)

    class FailingCommitConnection:
        def __init__(self, db: sqlite3.Connection):
            self.db = db

        @property
        def in_transaction(self) -> bool:
            return self.db.in_transaction

        def execute(self, sql: str, parameters: SqlParameters = ()) -> sqlite3.Cursor:
            return self.db.execute(sql, parameters)

        def executemany(self, sql: str, rows: Iterable[SqlParameters]) -> sqlite3.Cursor:
            return self.db.executemany(sql, rows)

        def commit(self) -> None:
            raise sqlite3.OperationalError("injected commit failure")

        def rollback(self) -> None:
            self.db.rollback()

    restoring = threading.Event()
    permit_restore = threading.Event()
    second_started = threading.Event()
    second_finished = threading.Event()
    real_replace = os.replace

    def blocking_restore(
        source: str | Path,
        destination: str | Path,
        **kwargs: Any,
    ) -> None:
        if Path(source).name.endswith(".previous"):
            restoring.set()
            assert permit_restore.wait(2)
        real_replace(source, destination, **kwargs)

    monkeypatch.setattr("geistfabrik.journal_writer.os.replace", blocking_restore)
    first_error: list[BaseException] = []
    second_error: list[BaseException] = []

    def first_write() -> None:
        try:
            failing_db = cast(sqlite3.Connection, FailingCommitConnection(first_db))
            JournalWriter(vault_path, failing_db).write_session(
                date, [_suggestion("first")], overwrite=True
            )
        except BaseException as exc:
            first_error.append(exc)

    def second_write() -> None:
        second_started.set()
        try:
            JournalWriter(vault_path, second_db).write_session(
                date, [_suggestion("second")], overwrite=True
            )
        except BaseException as exc:
            second_error.append(exc)
        finally:
            second_finished.set()

    first_thread = threading.Thread(target=first_write)
    second_thread = threading.Thread(target=second_write)
    first_thread.start()
    assert restoring.wait(2)
    second_thread.start()
    assert second_started.wait(2)
    assert not second_finished.wait(0.1), "second writer must wait for restore and rollback"
    permit_restore.set()
    first_thread.join(2)
    second_thread.join(2)

    assert len(first_error) == 1 and isinstance(first_error[0], sqlite3.OperationalError)
    assert second_error == []
    assert (vault_path / "geist journal" / "2025-01-02.md").read_text().find("second") >= 0
    assert second_db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("second",)
    ]
    first_db.close()
    second_db.close()


def test_journal_recovers_process_death_marker(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    writer = JournalWriter(vault_path, vault.db)
    path = writer.write_session(date, [_suggestion("old")])
    old_bytes = path.read_bytes()
    new_suggestions = [_suggestion("new")]
    new_content = writer._format_session_note(date, new_suggestions, "default").encode()
    _, backup_path = writer._pending_paths(path)
    writer._atomic_write(backup_path, old_bytes, ".test-backup")
    writer._write_pending_record(
        path,
        had_old_file=True,
        expected_database_hash=writer._expected_state_hash(date, new_suggestions),
        expected_file_hash=hashlib.sha256(new_content).hexdigest(),
        old_file_hash=hashlib.sha256(old_bytes).hexdigest(),
    )
    path.write_bytes(new_content)

    JournalWriter(vault_path, vault.db)
    assert path.read_bytes() == old_bytes
    assert vault.db.execute("SELECT suggestion_text FROM session_suggestions").fetchall() == [
        ("old",)
    ]
    assert not any((vault_path / "geist journal").glob("*.pending"))


def test_journal_recovery_preserves_conflicting_user_edit(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    vault = Vault(vault_path)
    date = datetime(2025, 1, 2)
    writer = JournalWriter(vault_path, vault.db)
    path = writer.write_session(date, [_suggestion("old")])
    old_bytes = path.read_bytes()
    new_suggestions = [_suggestion("new")]
    new_content = writer._format_session_note(date, new_suggestions, "default").encode()
    _, backup_path = writer._pending_paths(path)
    writer._atomic_write(backup_path, old_bytes, ".test-backup")
    writer._write_pending_record(
        path,
        had_old_file=True,
        expected_database_hash=writer._expected_state_hash(date, new_suggestions),
        expected_file_hash=hashlib.sha256(new_content).hexdigest(),
        old_file_hash=hashlib.sha256(old_bytes).hexdigest(),
    )
    path.write_text("conflicting user edit")

    with pytest.raises(RuntimeError, match="recovery conflict"):
        JournalWriter(vault_path, vault.db)
    assert path.read_text() == "conflicting user edit"
    assert list((vault_path / "geist journal").glob(".*.pending"))


def test_journal_rejects_escaping_directory_symlink(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    outside = tmp_path / "outside"
    vault_path.mkdir()
    outside.mkdir()
    try:
        (vault_path / "geist journal").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    vault = Vault(vault_path)
    with pytest.raises(PathSafetyError):
        JournalWriter(vault_path, vault.db).write_session(datetime(2025, 1, 2), [])
    assert list(outside.iterdir()) == []


def test_package_smoke_rejects_destructive_workspace_root() -> None:
    result = subprocess.run(
        ["./scripts/test_wheel.sh"],
        env={**os.environ, "PACKAGE_SMOKE_WORKDIR": "/"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Unsafe PACKAGE_SMOKE_WORKDIR" in result.stderr


def test_dense_markdown_link_limit_accepts_boundary_and_rejects_next() -> None:
    at_limit = " ".join(f"[[n{index}]]" for index in range(MAX_NOTE_LINKS))
    assert len(extract_links(at_limit)) == MAX_NOTE_LINKS
    with pytest.raises(MarkdownLimitError, match="links"):
        extract_links(at_limit + " [[overflow]]")


def test_vault_skips_structurally_dense_markdown_and_removes_stale_row(
    tmp_path: Path,
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    note_path = vault_path / "dense.md"
    note_path.write_text("# Dense\nordinary")
    vault = Vault(vault_path)
    assert vault.sync() == 1
    note_path.write_text(" ".join("[[x]]" for _ in range(MAX_NOTE_LINKS + 1)))
    os.utime(note_path, (note_path.stat().st_atime, note_path.stat().st_mtime + 2))
    assert vault.sync() == 0
    assert vault.all_notes() == []


def test_unchanged_sync_resolves_each_note_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    for index in range(20):
        (vault_path / f"note-{index}.md").write_text(f"# Note {index}\n")
    vault = Vault(vault_path)
    vault.sync()

    from geistfabrik import vault as vault_module

    real_ensure = vault_module.ensure_contained
    note_checks = 0

    def counting_ensure(candidate: Path, root: Path, **kwargs: Any) -> Path:
        nonlocal note_checks
        if candidate.suffix == ".md":
            note_checks += 1
        return real_ensure(candidate, root, **kwargs)

    monkeypatch.setattr(vault_module, "ensure_contained", counting_ensure)
    assert vault.sync() == 0
    assert note_checks == 20


def test_vault_skips_oversized_markdown(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    with (vault_path / "huge.md").open("wb") as handle:
        handle.seek(MAX_NOTE_BYTES)
        handle.write(b"x")
    vault = Vault(vault_path)
    assert vault.sync() == 0
    assert vault.all_notes() == []


def test_vault_skips_external_markdown_symlink(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    outside = tmp_path / "secret.md"
    outside.write_text("secret")
    try:
        (vault_path / "escape.md").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    vault = Vault(vault_path)
    assert vault.sync() == 0
    assert vault.all_notes() == []


def _symlink_external_file(root: Path, suffix: str, content: str) -> tuple[Path, Path]:
    root.mkdir(parents=True)
    outside = root.parent / f"outside{suffix}"
    marker = root.parent / f"executed-{suffix.removeprefix('.')}"
    outside.write_text(content.replace("MARKER", repr(str(marker))))
    (root / f"escaped{suffix}").symlink_to(outside)
    return marker, outside


def test_code_geist_loader_rejects_external_file_symlink(tmp_path: Path) -> None:
    root = tmp_path / "code"
    marker, _ = _symlink_external_file(
        root,
        ".py",
        "from pathlib import Path\n"
        "Path(MARKER).write_text('executed')\n"
        "def suggest(vault): return []\n",
    )
    executor = GeistExecutor(root)
    executor.load_geists()
    assert "escaped" not in executor.geists
    assert not marker.exists()
    assert executor.get_execution_log()[0]["status"] == "load_error"


def test_metadata_loader_rejects_external_file_symlink(tmp_path: Path) -> None:
    root = tmp_path / "metadata"
    marker, _ = _symlink_external_file(
        root,
        ".py",
        "from pathlib import Path\n"
        "Path(MARKER).write_text('executed')\n"
        "def infer(note, vault): return {}\n",
    )
    loader = MetadataLoader(root)
    loader.load_modules()
    assert loader.modules == {}
    assert not marker.exists()


def test_vault_function_loader_rejects_external_file_symlink(tmp_path: Path) -> None:
    root = tmp_path / "functions"
    marker, _ = _symlink_external_file(
        root,
        ".py",
        "from pathlib import Path\nPath(MARKER).write_text('executed')\n",
    )
    registry = FunctionRegistry(root)
    registry.load_modules()
    assert not marker.exists()


def test_tracery_loader_rejects_external_file_symlink(tmp_path: Path) -> None:
    root = tmp_path / "tracery"
    marker, outside = _symlink_external_file(
        root,
        ".yaml",
        "type: geist-tracery\nid: escaped\ntracery:\n  origin: external\n",
    )
    loader = TraceryGeistLoader(root)
    geists, _ = loader.load_all()
    assert geists == []
    assert not marker.exists()
    assert outside.read_text().endswith("origin: external\n")


@pytest.mark.parametrize("loader_kind", ["metadata", "function", "validator"])
def test_trusted_plugin_imports_have_supported_deadline(tmp_path: Path, loader_kind: str) -> None:
    if not hasattr(signal, "SIGALRM"):
        pytest.skip("SIGALRM unavailable")
    root = tmp_path / loader_kind
    root.mkdir()
    plugin = root / "hang.py"
    plugin.write_text("import time\ntime.sleep(10)\ndef suggest(vault): return []\n")
    started = time.monotonic()
    if loader_kind == "metadata":
        plugin.write_text("import time\ntime.sleep(10)\ndef infer(note, vault): return {}\n")
        loader = MetadataLoader(root, timeout=1)
        loader.load_modules()
        assert loader.modules == {}
    elif loader_kind == "function":
        registry = FunctionRegistry(root, timeout=1)
        registry.load_modules()
        assert "hang" not in registry.functions
    else:
        from geistfabrik.validator import GeistValidator

        result = GeistValidator(timeout=1).validate_code_geist(plugin, root=root)
        assert result.passed is False
        assert "timed out" in result.issues[0].message
    assert time.monotonic() - started < 2


def test_invoke_preserves_interleaved_config_order_and_tracery_typing(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    executor = GeistExecutor(tmp_path)

    def result(geist_id: str) -> list[Suggestion]:
        calls.append(geist_id)
        return [Suggestion(text=f"from {geist_id}", notes=[], geist_id=geist_id)]

    executor.register_geist("code", tmp_path / "code.py", lambda _ctx: result("code"))
    executor.register_geist("tracery", tmp_path / "tracery.yaml", lambda _ctx: result("tracery"))
    tracery = TraceryGeist("tracery", {"origin": ["unused"]})
    config = GeistFabrikConfig(default_geists={"tracery": True, "code": True})
    context = object.__new__(ExecutionContext)
    context.vault_context = cast(VaultContext, object())
    context.config = config
    args = create_parser().parse_args(["invoke", str(tmp_path)])
    command = InvokeCommand(args)

    results = command._execute_geists(context, executor, [tracery])

    assert results is not None
    assert calls == ["tracery", "code"]
    assert list(results.tracery_results) == ["tracery"]
    assert list(results.code_results) == ["code"]
    assert [item.geist_id for item in results.all_suggestions] == ["tracery", "code"]

    selected_args = create_parser().parse_args(["invoke", str(tmp_path), "--geist", "tracery"])
    selected = InvokeCommand(selected_args)._execute_geists(context, executor, [tracery])
    assert selected is not None
    assert list(selected.tracery_results) == ["tracery"]
    assert selected.code_results == {}


def test_invoke_caps_aggregate_suggestions_in_config_order(tmp_path: Path) -> None:
    command = InvokeCommand(create_parser().parse_args(["invoke", str(tmp_path)]))
    first = [Suggestion(str(i), [], "first") for i in range(600)]
    second = [Suggestion(str(i), [], "second") for i in range(600)]
    config = GeistFabrikConfig(default_geists={"first": True, "second": True})
    collected = command._collect_suggestions_in_order(
        {"first": first, "second": second}, {}, config
    )
    assert len(collected) == MAX_SESSION_SUGGESTIONS
    assert [item.geist_id for item in collected[:600]] == ["first"] * 600
    assert [item.geist_id for item in collected[600:]] == ["second"] * 400


def test_registered_tracery_callable_uses_persistent_failure_lifecycle(tmp_path: Path) -> None:
    db = init_db(None)
    store = GeistStatusStore(db)
    executor = GeistExecutor(tmp_path, timeout=5, max_failures=1, status_store=store)

    def broken(context: VaultContext) -> list[Suggestion]:
        raise TraceryExecutionError("broken grammar")

    executor.register_geist("tracery", tmp_path / "tracery.yaml", broken)
    executor.load_status()
    context = cast(VaultContext, object())  # Broken geist raises before context use.
    executor.execute_geist("tracery", context)
    assert store.load()["tracery"].disabled is True
    assert executor.get_execution_log()[0]["error_type"] == "exception"


def test_executor_restores_prior_alarm_state(tmp_path: Path) -> None:
    if not hasattr(signal, "SIGALRM"):
        pytest.skip("SIGALRM unavailable")
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)

    def prior_handler(signum: int, frame: object) -> None:
        return None

    try:
        signal.signal(signal.SIGALRM, prior_handler)
        signal.setitimer(signal.ITIMER_REAL, 30.0)
        executor = GeistExecutor(tmp_path, timeout=2)
        executor.register_geist("ok", tmp_path / "ok.py", lambda context: [])
        context = cast(VaultContext, object())  # Registered lambda does not read it.
        executor.execute_geist("ok", context)
        assert signal.getsignal(signal.SIGALRM) is prior_handler
        remaining, _ = signal.getitimer(signal.ITIMER_REAL)
        assert 20 < remaining <= 30
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def test_executor_does_not_delay_sooner_host_alarm() -> None:
    if not hasattr(signal, "SIGALRM"):
        pytest.skip("SIGALRM unavailable")
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    calls = 0

    def host_handler(signum: int, frame: object) -> None:
        nonlocal calls
        calls += 1

    try:
        signal.signal(signal.SIGALRM, host_handler)
        signal.setitimer(signal.ITIMER_REAL, 0.02, 0.02)
        with _alarm_timeout(1):
            time.sleep(0.20)
        _, interval = signal.getitimer(signal.ITIMER_REAL)
        assert calls >= 2
        assert interval == pytest.approx(0.02, abs=0.01)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def test_host_handler_can_cancel_its_periodic_alarm() -> None:
    if not hasattr(signal, "SIGALRM"):
        pytest.skip("SIGALRM unavailable")
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    delivered = False

    def host_handler(signum: int, frame: object) -> None:
        nonlocal delivered
        delivered = True
        signal.setitimer(signal.ITIMER_REAL, 0.0)

    try:
        signal.signal(signal.SIGALRM, host_handler)
        signal.setitimer(signal.ITIMER_REAL, 0.02, 0.02)
        with _alarm_timeout(2):
            delivery_deadline = time.monotonic() + 1.0
            while not delivered and time.monotonic() < delivery_deadline:
                time.sleep(0.01)
            delivered_in_time = delivered
        remaining, interval = signal.getitimer(signal.ITIMER_REAL)
        assert delivered_in_time
        assert remaining == 0.0
        assert interval == 0.0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def test_periodic_host_alarm_does_not_disable_geist_deadline() -> None:
    if not hasattr(signal, "SIGALRM"):
        pytest.skip("SIGALRM unavailable")
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    calls = 0

    def host_handler(signum: int, frame: object) -> None:
        nonlocal calls
        calls += 1

    try:
        signal.signal(signal.SIGALRM, host_handler)
        signal.setitimer(signal.ITIMER_REAL, 0.02, 0.02)
        with pytest.raises(GeistTimeoutError, match="timed out"):
            with _alarm_timeout(1):
                time.sleep(2)
        assert calls >= 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def test_nested_alarm_timeout_uses_earliest_deadline() -> None:
    if not hasattr(signal, "SIGALRM"):
        pytest.skip("SIGALRM unavailable")
    started = time.monotonic()
    with pytest.raises(GeistTimeoutError, match="timed out"):
        with _alarm_timeout(3), _alarm_timeout(1):
            time.sleep(2)
    assert time.monotonic() - started < 2


@pytest.mark.parametrize("count", [0, -1, True, "2", MAX_TRACERY_COUNT + 1])
def test_tracery_count_is_strictly_bounded(tmp_path: Path, count: object) -> None:
    path = tmp_path / "g.yaml"
    yaml_count = f'"{count}"' if isinstance(count, str) else str(count).lower()
    path.write_text(f"type: geist-tracery\nid: g\ncount: {yaml_count}\ntracery:\n  origin: hi\n")
    with pytest.raises(ValueError, match="count"):
        TraceryGeist.from_yaml(path)


@pytest.mark.parametrize("count", [1, MAX_TRACERY_COUNT])
def test_tracery_valid_count_boundaries_are_preserved(tmp_path: Path, count: int) -> None:
    path = tmp_path / "g.yaml"
    path.write_text(f"type: geist-tracery\nid: g\ncount: {count}\ntracery:\n  origin: hi\n")
    geist = TraceryGeist.from_yaml(path)
    assert geist.count == count
    context = cast(VaultContext, object())  # Grammar has no vault function calls.
    assert len(geist.suggest(context)) == count


def test_bounded_yaml_rejects_aliases(tmp_path: Path) -> None:
    path = tmp_path / "alias.yaml"
    path.write_text("base: &base [one]\ncopy: *base\n")
    with pytest.raises(BoundedYAMLError, match="aliases"):
        load_bounded_yaml(path)


def test_bounded_yaml_rejects_oversized_input(tmp_path: Path) -> None:
    path = tmp_path / "large.yaml"
    path.write_bytes(b"x" * (MAX_YAML_BYTES + 1))
    with pytest.raises(BoundedYAMLError, match="exceeds"):
        load_bounded_yaml(path)


def test_markdown_frontmatter_uses_bounded_yaml() -> None:
    aliased = "---\nbase: &base [one]\ncopy: *base\n---\nbody\n"
    frontmatter, content = parse_frontmatter(aliased)
    assert frontmatter is None
    assert content == aliased

    oversized = "---\ntitle: " + ("x" * (MAX_YAML_BYTES + 1)) + "\n---\nbody\n"
    frontmatter, content = parse_frontmatter(oversized)
    assert frontmatter is None
    assert content == oversized


def _prepare_command_vault(tmp_path: Path) -> tuple[Path, Path, Path]:
    vault_path = tmp_path / "vault"
    code_dir = vault_path / "_geistfabrik" / "geists" / "code"
    tracery_dir = vault_path / "_geistfabrik" / "geists" / "tracery"
    code_dir.mkdir(parents=True)
    tracery_dir.mkdir(parents=True)
    (vault_path / "_geistfabrik" / "config.yaml").write_text(
        "geist_execution:\n  max_failures: 1\n"
    )
    vault = Vault(vault_path, vault_path / "_geistfabrik" / "vault.db")
    vault.close()
    return vault_path, code_dir, tracery_dir


@pytest.mark.parametrize("command_name", ["test", "test-all"])
def test_diagnostic_invalid_date_has_no_database_or_plugin_side_effect(
    tmp_path: Path, command_name: str
) -> None:
    vault_path = tmp_path / "vault"
    plugin_dir = vault_path / "_geistfabrik" / "metadata_inference"
    plugin_dir.mkdir(parents=True)
    (vault_path / "_geistfabrik" / "config.yaml").write_text("enabled_modules: []\n")
    marker = tmp_path / "imported"
    (plugin_dir / "plugin.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('yes')\n"
        "def infer(note, vault): return {}\n"
    )
    argv = (
        ["test", "anything", str(vault_path), "--date", "not-a-date"]
        if command_name == "test"
        else ["test-all", str(vault_path), "--date", "not-a-date"]
    )
    args = create_parser().parse_args(argv)
    command = GeistTestCommand(args) if command_name == "test" else GeistTestAllCommand(args)
    assert command.run() == 1
    assert not marker.exists()
    assert not (vault_path / "_geistfabrik" / "vault.db").exists()
    assert not (vault_path / "geist journal").exists()


def test_test_command_recovers_disabled_geist_and_retries_failures(tmp_path: Path) -> None:
    vault_path, code_dir, _ = _prepare_command_vault(tmp_path)
    geist_path = code_dir / "recover.py"
    geist_path.write_text(
        "from geistfabrik import Suggestion\n"
        "def suggest(vault):\n"
        "    return [Suggestion(text='fixed', notes=[], geist_id='recover')]\n"
    )
    db_path = vault_path / "_geistfabrik" / "vault.db"
    db = sqlite3.connect(db_path)
    GeistStatusStore(db).record_failure("recover", "old failure", max_failures=1)
    db.close()

    args = create_parser().parse_args(["test", "recover", str(vault_path), "--date", "2025-01-02"])
    assert GeistTestCommand(args).run() == 0
    check = sqlite3.connect(db_path)
    assert GeistStatusStore(check).load()["recover"].disabled is False
    assert GeistStatusStore(check).load()["recover"].failure_count == 0
    check.close()


def test_test_all_executes_and_recovers_disabled_geists(tmp_path: Path) -> None:
    db = init_db(None)
    store = GeistStatusStore(db)
    executor = GeistExecutor(tmp_path, max_failures=1, status_store=store)
    executor.register_geist("recover", tmp_path / "recover.py", lambda context: [])
    store.record_failure("recover", "old", max_failures=1)
    executor.load_status()
    assert executor.geists["recover"].is_enabled is False

    args = create_parser().parse_args(["test-all", str(tmp_path)])
    command = GeistTestAllCommand(args)
    context = object.__new__(ExecutionContext)
    context.vault_context = cast(VaultContext, object())
    results = command._test_all_geists(executor, context)

    assert results["recover"].status == "success"
    assert store.load()["recover"].disabled is False


def test_actual_tracery_yaml_failure_is_recorded_through_test_command(tmp_path: Path) -> None:
    vault_path, _, tracery_dir = _prepare_command_vault(tmp_path)
    (tracery_dir / "hostile.yaml").write_text(
        "type: geist-tracery\nid: hostile\ntracery:\n  origin: '$vault.missing()'\n"
    )
    args = create_parser().parse_args(["test", "hostile", str(vault_path), "--date", "2025-01-02"])
    assert GeistTestCommand(args).run() == 1

    db = sqlite3.connect(vault_path / "_geistfabrik" / "vault.db")
    status = GeistStatusStore(db).load()["hostile"]
    assert status.failure_count == 1
    assert status.disabled is True
    assert "missing" in (status.last_error or "")
    db.close()


def test_tracery_expansion_amplification_is_rejected_incrementally() -> None:
    engine = TraceryEngine({"origin": ["#large#" * 1_000], "large": ["x" * MAX_TRACERY_RULE_BYTES]})
    engine.begin_invocation(5)
    with pytest.raises(TraceryLimitError, match="output exceeds"):
        engine.expand("#origin#")


def test_tracery_rejects_oversized_preprocessed_vault_item() -> None:
    geist = TraceryGeist("g", {"origin": ["#x#"], "x": ["$vault.large()"]})

    class Context:
        def call_function(self, name: str, *args: object) -> list[str]:
            assert name == "large"
            return ["x" * (MAX_TRACERY_RULE_BYTES + 1)]

    with pytest.raises(TraceryLimitError, match="Preprocessed"):
        geist.suggest(cast(VaultContext, Context()))


def test_tracery_preprocessing_failure_is_typed_and_transactional(tmp_path: Path) -> None:
    geist = TraceryGeist("g", {"origin": ["#x#"], "x": ["$vault.missing()"]})
    original = {key: list(value) for key, value in geist.engine.grammar.items()}

    class Context:
        def call_function(self, name: str, *args: object) -> object:
            raise KeyError(name)

    context = cast(VaultContext, Context())
    with pytest.raises(TraceryExecutionError):
        geist.suggest(context)
    assert geist.engine.grammar == original
