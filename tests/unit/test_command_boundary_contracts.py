"""CLI lifecycle boundaries exercise real managed files and SQLite state."""

import json
from pathlib import Path

import pytest

from geistfabrik.cli import create_parser
from geistfabrik.commands.initialize import InitCommand
from geistfabrik.commands.stats import StatsCommand


def initialise(vault_path: Path, *flags: str) -> int:
    return InitCommand(create_parser().parse_args(["init", str(vault_path), *flags])).run()


@pytest.mark.parametrize("obsidian", [False, True])
def test_init_creates_managed_state_without_mutating_source_notes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], obsidian: bool
) -> None:
    if obsidian:
        (tmp_path / ".obsidian").mkdir()
    source = tmp_path / "source.md"
    source.write_text("# Source\nDo not modify this note.\n")
    original = source.read_bytes()
    assert initialise(tmp_path) == 0
    managed = tmp_path / "_geistfabrik"
    assert (managed / "vault.db").is_file()
    assert (managed / "config.yaml").is_file()
    assert (managed / "geists/code").is_dir()
    assert (managed / "geists/tracery").is_dir()
    assert (managed / "metadata_inference").is_dir()
    assert (managed / "vault_functions").is_dir()
    assert source.read_bytes() == original
    output = capsys.readouterr().out
    assert ("No .obsidian directory" in output) is not obsidian
    assert "Synced 1 notes" in output


def test_init_requires_force_to_replace_existing_configuration(tmp_path: Path, capsys) -> None:
    assert initialise(tmp_path) == 0
    config = tmp_path / "_geistfabrik/config.yaml"
    original = config.read_text()
    config.write_text("# User-owned configuration\n")
    assert initialise(tmp_path) == 1
    assert config.read_text() == "# User-owned configuration\n"
    assert "already exists" in capsys.readouterr().err
    assert initialise(tmp_path, "--force") == 0
    assert config.read_text() == original


@pytest.mark.parametrize("target", ["missing", "file"])
def test_init_rejects_invalid_vault_before_creating_managed_state(
    tmp_path: Path, target: str, capsys
) -> None:
    vault_path = tmp_path / target
    if target == "file":
        vault_path.write_text("not a directory")
    assert initialise(vault_path) == 1
    assert not (tmp_path / "_geistfabrik").exists()
    assert "Vault path" in capsys.readouterr().err


def test_force_init_cannot_follow_redirected_configuration(tmp_path: Path, capsys) -> None:
    vault = tmp_path / "vault"
    managed = vault / "_geistfabrik"
    managed.mkdir(parents=True)
    outside = tmp_path / "outside.yaml"
    outside.write_text("important: keep\n")
    (managed / "config.yaml").symlink_to(outside)
    assert initialise(vault, "--force") == 1
    assert outside.read_text() == "important: keep\n"
    assert not (managed / "vault.db").exists()
    assert "Error:" in capsys.readouterr().err


def test_stats_uninitialised_vault_does_not_create_database(tmp_path: Path, capsys) -> None:
    command = StatsCommand(create_parser().parse_args(["stats", str(tmp_path)]))
    assert command.run() == 1
    assert not (tmp_path / "_geistfabrik").exists()
    assert "not initialised" in capsys.readouterr().err


@pytest.mark.parametrize("output_flags", [[], ["--json"], ["--verbose", "--json"]])
def test_stats_empty_initialised_vault_is_serializable_and_closes_database(
    tmp_path: Path, capsys, output_flags: list[str]
) -> None:
    assert initialise(tmp_path) == 0
    capsys.readouterr()
    command = StatsCommand(create_parser().parse_args(["stats", str(tmp_path), *output_flags]))
    assert command.run() == 0
    assert command._vault is None
    assert command._session is None
    output = capsys.readouterr().out
    if "--json" in output_flags:
        stats = json.loads(output)
        assert stats["notes"]["total"] == 0
        assert stats["vault"]["path"] == str(tmp_path)
    else:
        assert "0" in output
        assert "Vault" in output
