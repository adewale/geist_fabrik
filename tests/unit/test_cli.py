"""Tests for CLI module."""

from pathlib import Path

import pytest

from geistfabrik.cli import find_vault_root


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
