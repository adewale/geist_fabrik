"""Pytest configuration and shared fixtures."""

import sqlite3
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from geistfabrik.embeddings import EmbeddingComputer, _bundled_model_path
from geistfabrik.schema import init_db
from tests.stubs import SentenceTransformerStub


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


@pytest.fixture
def preserve_model_path_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore the real resource resolver for focused loader contract tests."""
    from geistfabrik import embeddings

    monkeypatch.setattr(embeddings, "_bundled_model_path", _bundled_model_path)


@pytest.fixture(scope="session", autouse=True)
def stub_sentence_transformer_constructor(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Stub inference before module fixtures, without requiring Git LFS weights.

    The canonical fast lane excludes ``production_model``. If a run includes
    any production-model item, leave the whole session real rather than risk a
    mixed session silently using the stub.
    """
    if any(
        item.get_closest_marker("production_model") is not None for item in request.session.items
    ):
        yield
        return

    from geistfabrik import embeddings

    patcher = pytest.MonkeyPatch()
    source_model = Path(embeddings.__file__).resolve().parents[2] / "models" / embeddings.MODEL_NAME
    patcher.setattr(embeddings, "SentenceTransformer", SentenceTransformerStub)
    patcher.setattr(embeddings, "_bundled_model_path", lambda _name: source_model)
    try:
        yield
    finally:
        patcher.undo()


@pytest.fixture(scope="session")
def shared_embedding_computer() -> Generator[EmbeddingComputer, None, None]:
    """Single shared EmbeddingComputer for all tests that need direct model access.

    Note: Most embedding tests should use the shared_session_with_embeddings
    fixture instead, which includes pre-computed embeddings. This fixture is
    for tests that specifically need to test EmbeddingComputer behaviour.
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


@pytest.fixture(autouse=True)
def clear_global_registry() -> Generator[None, None, None]:
    """Reset the module-level function registry around every test.

    FunctionRegistry registers builtins into a process-global registry
    (function_registry._GLOBAL_REGISTRY), so any test that constructs a
    registry would otherwise poison the next one with DuplicateFunctionError.
    Hoisted here from ~49 per-file copies of this same fixture.
    """
    from geistfabrik.function_registry import _GLOBAL_REGISTRY

    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()
