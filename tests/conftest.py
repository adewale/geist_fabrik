"""Pytest configuration and shared fixtures."""

import hashlib
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Generator, List, Union, cast

import numpy as np
import pytest

from geistfabrik.config import SEMANTIC_DIM
from geistfabrik.embeddings import EmbeddingComputer
from geistfabrik.schema import init_db


class SentenceTransformerStub:
    """Stub for SentenceTransformer that generates deterministic embeddings.

    This stub allows tests to run without downloading the real model from HuggingFace.
    It generates embeddings based on text content hash for deterministic results.
    """

    def __init__(self, model_name: str, device: str = "cpu"):
        """Initialise stub.

        Args:
            model_name: Model name (ignored, for compatibility)
            device: Device (ignored, for compatibility)
        """
        self.model_name = model_name
        self.device = device

    def encode(
        self,
        sentences: Union[str, List[str]],
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
        batch_size: int = 32,
        **kwargs: Any,
    ) -> np.ndarray:
        """Generate deterministic embeddings from text.

        Args:
            sentences: Single text or list of texts
            convert_to_numpy: Always returns numpy array
            show_progress_bar: Ignored
            batch_size: Ignored
            **kwargs: Ignored

        Returns:
            Numpy array of shape (n, 384) for multiple texts or (384,) for single text
        """
        is_single = isinstance(sentences, str)
        if is_single:
            texts: List[str] = [cast(str, sentences)]
        else:
            texts = cast(List[str], sentences)

        embeddings: List[np.ndarray] = []
        for text in texts:
            # Generate deterministic embedding from text hash
            # Use SHA256 to get bytes, then convert to float values
            text_hash = hashlib.sha256(text.encode()).digest()

            # Generate SEMANTIC_DIM (384) dimensional vector
            # Repeat hash bytes to fill dimensions
            num_repeats = (SEMANTIC_DIM + len(text_hash) - 1) // len(text_hash)
            extended = (text_hash * num_repeats)[:SEMANTIC_DIM]

            # Convert bytes to normalised float values [-1, 1]
            embedding = np.array([b / 128.0 - 1.0 for b in extended], dtype=np.float32)

            # Normalise to unit vector (like real sentence-transformers)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            embeddings.append(embedding)

        result = np.array(embeddings, dtype=np.float32)
        return result[0] if is_single else result


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


def pytest_configure(config: Any) -> None:
    """Pytest plugin hook to configure tests before they run.

    This replaces SentenceTransformer with our stub ONLY when running unit tests
    (with -m "not slow"). Integration tests (marked as slow) use the real model.
    """
    import sys
    import types

    # Check if we're skipping slow tests (unit test mode)
    markexpr = config.getoption("-m", default="")

    # Only inject stub if we're explicitly filtering out slow tests with -m "not slow"
    # This ensures integration tests (marked as @pytest.mark.slow) use the real model
    # When running all tests (no -m flag), integration tests should get real model
    should_use_stub = "not slow" in markexpr

    if not should_use_stub:
        # Either running integration tests or running all tests - use real model
        return

    # Create a fake sentence_transformers module
    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = SentenceTransformerStub  # type: ignore[attr-defined]

    # Replace in sys.modules so imports get our stub
    sys.modules["sentence_transformers"] = fake_module

    # Also patch the EmbeddingComputer class to use our stub
    # This is needed because embeddings.py may have already imported SentenceTransformer
    from geistfabrik import embeddings

    def patched_init(
        self: Any,
        model_name: str = embeddings.MODEL_NAME,
        model: Any = None,
    ) -> None:
        """Patched init that uses stub instead of real SentenceTransformer.

        Args:
            model_name: Name of model (used for stub creation)
            model: Pre-initialised model (if provided, uses this instead of creating stub)
        """
        self.model_name = model_name
        self._model = model  # Use provided model or None (will be lazy-loaded)

    def patched_model_property(self: Any) -> Any:
        """Patched model property that returns stub or injected model."""
        if self._model is None:
            self._model = SentenceTransformerStub(self.model_name, device="cpu")
        return self._model

    # Replace the methods
    embeddings.EmbeddingComputer.__init__ = patched_init  # type: ignore[method-assign]
    embeddings.EmbeddingComputer.model = property(patched_model_property)  # type: ignore[assignment]


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
