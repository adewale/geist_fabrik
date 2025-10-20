"""Pytest configuration and shared fixtures."""

import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from geistfabrik.embeddings import EmbeddingComputer
from geistfabrik.schema import init_db


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


@pytest.fixture(scope="session")
def shared_embedding_computer() -> Generator[EmbeddingComputer, None, None]:
    """Single shared EmbeddingComputer for all tests that need direct model access.

    Note: Most embedding tests should use the shared_session_with_embeddings
    fixture instead, which includes pre-computed embeddings. This fixture is
    for tests that specifically need to test EmbeddingComputer behavior.
    """
    computer = EmbeddingComputer()
    yield computer
    computer.close()


@pytest.fixture
def test_db() -> Generator[sqlite3.Connection, None, None]:
    """Function-scoped database with cleanup.

    Use this instead of manually calling init_db() and db.close().
    Ensures cleanup happens even if test fails.
    """
    db = init_db()
    yield db
    db.close()
