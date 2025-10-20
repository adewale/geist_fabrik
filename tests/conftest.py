"""Pytest configuration and shared fixtures."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_vault(temp_dir: Path) -> Path:
    """Create a sample Obsidian vault structure for testing."""
    vault_path = temp_dir / "test_vault"
    vault_path.mkdir()

    # Create some sample markdown files
    (vault_path / "note1.md").write_text(
        "---\ntitle: Note 1\ntags: [test]\n---\n\n# Note 1\n\nThis is a test note."
    )
    (vault_path / "note2.md").write_text("# Note 2\n\nThis links to [[note1]].")

    return vault_path
