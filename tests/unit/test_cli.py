"""Tests for CLI module."""

from pathlib import Path

import pytest

from geistfabrik.cli import create_parser
from geistfabrik.commands import find_vault_root
from geistfabrik.commands.invoke import InvokeCommand


def test_find_vault_root_with_obsidian_dir(tmp_path: Path) -> None:
    """Test finding vault root when .obsidian directory exists."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    obsidian_dir = vault_path / ".obsidian"
    obsidian_dir.mkdir()

    # Should find from within vault
    assert find_vault_root(vault_path) == vault_path

    # Should find from subdirectory
    subdir = vault_path / "notes" / "subdir"
    subdir.mkdir(parents=True)
    assert find_vault_root(subdir) == vault_path


def test_find_vault_root_not_found(tmp_path: Path) -> None:
    """Test finding vault root when no .obsidian directory exists."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    assert find_vault_root(empty_dir) is None


def test_find_vault_root_current_dir_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test finding vault root defaults to current directory."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    obsidian_dir = vault_path / ".obsidian"
    obsidian_dir.mkdir()

    # Change to vault directory
    monkeypatch.chdir(vault_path)

    # Should find from current directory when no path specified
    assert find_vault_root() == vault_path


def test_invoke_command_no_filter_flag(tmp_path: Path) -> None:
    """The public parser accepts --no-filter and preserves its vault argument."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    args = create_parser().parse_args(["invoke", str(vault_path), "--no-filter"])
    assert args.command == "invoke"
    assert args.vault == str(vault_path)
    assert args.no_filter is True
    assert args.full is False


def test_invoke_command_full_vs_no_filter_help_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Help exits successfully and documents the two distinct contracts."""
    with pytest.raises(SystemExit) as exc:
        create_parser().parse_args(["invoke", "--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "--full" in help_text
    assert "Show all filtered suggestions" in help_text
    assert "--no-filter" in help_text
    assert "Skip filtering pipeline" in help_text


def test_invoke_loads_both_code_and_tracery_geists(tmp_path: Path) -> None:
    """Test that invoke command loads both code and Tracery geists."""
    # Create a minimal vault
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    # Create test notes
    (vault_path / "note1.md").write_text("# Note 1\nContent")
    (vault_path / "note2.md").write_text("# Note 2\nContent")

    # Create geists directories
    geists_dir = vault_path / "_geistfabrik" / "geists"
    code_geists_dir = geists_dir / "code"
    tracery_geists_dir = geists_dir / "tracery"
    code_geists_dir.mkdir(parents=True)
    tracery_geists_dir.mkdir(parents=True)

    # Create a simple code geist
    code_geist = '''"""Test code geist."""
from geistfabrik import Suggestion

def suggest(vault):
    """Generate a test suggestion."""
    return [Suggestion(text="Code geist test", notes=[], geist_id="test_code")]
'''
    (code_geists_dir / "test_code.py").write_text(code_geist)

    # Create a simple Tracery geist
    tracery_geist = """type: geist-tracery
id: test_tracery
tracery:
  origin: "Tracery geist test"
"""
    (tracery_geists_dir / "test_tracery.yaml").write_text(tracery_geist)

    # Exercise InvokeCommand's real loading and unified execution lifecycle.
    args = create_parser().parse_args(["invoke", str(vault_path), "--date", "2025-01-15"])
    command = InvokeCommand(args)
    try:
        command_context = command.setup_command_context(vault_path)
        assert command_context is not None
        command_context.vault.sync()
        session_date = command.parse_session_date("2025-01-15")
        assert session_date is not None
        execution_context = command.setup_execution_context(command_context, session_date)
        executor, tracery_geists, _ = command._load_geists(execution_context, session_date)
        assert "test_code" in executor.geists
        assert any(geist.geist_id == "test_tracery" for geist in tracery_geists)
        assert executor.execute_geist("test_code", execution_context.vault_context)[0].text == (
            "Code geist test"
        )
        assert executor.execute_geist("test_tracery", execution_context.vault_context)[0].text == (
            "Tracery geist test"
        )
    finally:
        command._cleanup()


def test_invoke_executes_tracery_geists(tmp_path: Path) -> None:
    """Test that invoke command executes Tracery geists and generates suggestions."""
    from geistfabrik.tracery import TraceryGeistLoader
    from geistfabrik.vault import Vault

    # Create a minimal vault
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    # Create test notes
    (vault_path / "note1.md").write_text("# Note 1\nContent")

    # Create Tracery geists directory
    tracery_geists_dir = vault_path / "_geistfabrik" / "geists" / "tracery"
    tracery_geists_dir.mkdir(parents=True)

    # Create a simple Tracery geist
    tracery_geist = """type: geist-tracery
id: test_tracery
tracery:
  origin: "Test suggestion from Tracery"
"""
    (tracery_geists_dir / "test_tracery.yaml").write_text(tracery_geist)

    # Initialise vault
    vault = Vault(vault_path)
    vault.sync()

    # Load Tracery geists
    loader = TraceryGeistLoader(tracery_geists_dir, seed=12345)
    geists, newly_discovered = loader.load_all()

    assert len(geists) == 1, "Should load 1 Tracery geist"
    assert geists[0].geist_id == "test_tracery"
    assert len(newly_discovered) == 1, "Should discover 1 new geist"
    assert "test_tracery" in newly_discovered

    vault.close()
