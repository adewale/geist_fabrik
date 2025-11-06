"""Embeddings computation for GeistFabrik."""

import os

# CRITICAL: Limit thread/process spawning for ML libraries
# These MUST be set before importing numpy, torch, or transformers
# to prevent runaway process spawning during test execution and production use
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import hashlib
import logging
import math
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
    cosine_similarity as sklearn_cosine,
)

if TYPE_CHECKING:
    from .vector_search import VectorSearchBackend

from .config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_SEMANTIC_WEIGHT,
    MODEL_NAME,
)
from .models import Note

logger = logging.getLogger(__name__)


class EmbeddingComputer:
    """Handles embedding computation using sentence-transformers."""

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        model: Optional[SentenceTransformer] = None,
    ):
        """Initialize embedding computer.

        Args:
            model_name: Name of sentence-transformers model to use
            model: Pre-initialized model (for testing/injection), if None will lazy-load
        """
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = model
        self.device: Optional[str] = None  # Will be set on first model access

    def _detect_device(self) -> str:
        """Detect best available device for model inference.

        Priority: cuda (NVIDIA GPU) > mps (Apple Silicon) > cpu

        Returns:
            Device string: "cuda", "mps", or "cpu"
        """
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            # torch not available, fall back to CPU
            pass

        return "cpu"

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the sentence-transformers model.

        Checks for bundled local model first (models/all-MiniLM-L6-v2/),
        then falls back to HuggingFace cache/download.

        Auto-detects best available device (CUDA > MPS > CPU).
        """
        if self._model is None:
            # Detect device if not already set
            if self.device is None:
                self.device = self._detect_device()
                logger.info(f"Using device: {self.device}")

            # Check for local bundled model first
            # Project root is: src/geistfabrik -> src -> project_root
            project_root = Path(__file__).parent.parent.parent
            local_model_path = project_root / "models" / self.model_name

            if local_model_path.exists():
                # Use local bundled model (offline, faster, reproducible)
                model_source = str(local_model_path)
            else:
                # Fall back to HuggingFace (auto-download to cache)
                model_source = self.model_name

            self._model = SentenceTransformer(
                model_source,
                device=self.device,  # Use detected device (cuda/mps/cpu)
            )
        return self._model

    def compute_semantic(self, text: str) -> np.ndarray:
        """Compute semantic embedding for text.

        Args:
            text: Text to embed

        Returns:
            384-dimensional semantic embedding
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding

    def compute_batch_semantic(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Compute semantic embeddings for multiple texts in batch.

        This is significantly faster than calling compute_semantic() in a loop,
        as it leverages batched matrix operations.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for encoding (default: 32)

        Returns:
            NxM numpy array where N is number of texts and M is embedding dimension (384)
        """
        if not texts:
            return np.array([])

        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=batch_size,
        )
        return embeddings

    def compute_temporal_features(self, note: Note, session_date: datetime) -> np.ndarray:
        """Compute temporal features for a note.

        Args:
            note: Note to compute features for
            session_date: Current session date

        Returns:
            3-dimensional temporal features:
            - note_age: days since note creation
            - creation_season: sin/cos encoding of creation day-of-year
            - session_season: sin/cos encoding of session day-of-year
        """
        # Note age in days
        age_days = (session_date - note.created).days
        note_age = age_days / 365.0  # Normalize to years

        # Creation season (cyclical encoding)
        creation_doy = note.created.timetuple().tm_yday
        creation_season = math.sin(2 * math.pi * creation_doy / 365.0)

        # Session season (cyclical encoding)
        session_doy = session_date.timetuple().tm_yday
        session_season = math.sin(2 * math.pi * session_doy / 365.0)

        return np.array([note_age, creation_season, session_season])

    def compute_temporal_embedding(
        self, note: Note, session_date: datetime, semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT
    ) -> np.ndarray:
        """Compute combined temporal embedding.

        Args:
            note: Note to embed
            session_date: Current session date
            semantic_weight: Weight for semantic component (0-1)

        Returns:
            387-dimensional embedding (384 semantic + 3 temporal)
        """
        # Compute semantic embedding
        semantic = self.compute_semantic(note.content)

        # Compute temporal features
        temporal = self.compute_temporal_features(note, session_date)

        # Weight and combine
        temporal_weight = 1.0 - semantic_weight
        semantic_scaled = semantic * semantic_weight
        temporal_scaled = temporal * temporal_weight

        # Concatenate
        embedding = np.concatenate([semantic_scaled, temporal_scaled])
        return embedding

    def close(self) -> None:
        """Clean up model resources."""
        if self._model is not None:
            self._model = None

    def __enter__(self) -> "EmbeddingComputer":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit."""
        self.close()

    def __del__(self) -> None:
        """Cleanup when object is garbage collected."""
        self.close()


class Session:
    """Represents a GeistFabrik session with temporal embeddings."""

    def __init__(
        self,
        date: datetime,
        db: sqlite3.Connection,
        computer: Optional[EmbeddingComputer] = None,
        backend: str = "in-memory",
    ):
        """Initialize session.

        Args:
            date: Session date
            db: Database connection
            computer: EmbeddingComputer instance (for testing/injection), if None will create new
            backend: Vector search backend to use ('in-memory' or 'sqlite-vec')
        """
        self.date = date
        self.db = db
        self.session_id = self._get_or_create_session()
        self.computer = computer if computer is not None else EmbeddingComputer()
        self._backend_type = backend
        self._backend: Optional["VectorSearchBackend"] = None

    def _get_or_create_session(self) -> int:
        """Get existing session ID or create new session.

        Returns:
            Session ID
        """
        date_str = self.date.strftime("%Y-%m-%d")

        # Check if session exists
        cursor = self.db.execute("SELECT session_id FROM sessions WHERE date = ?", (date_str,))
        row = cursor.fetchone()

        if row is not None:
            return int(row[0])

        # Create new session
        cursor = self.db.execute(
            """
            INSERT INTO sessions (date, created_at)
            VALUES (?, ?)
            """,
            (date_str, datetime.now().isoformat()),
        )
        try:
            self.db.commit()
        except sqlite3.Error as e:
            logger.error(f"Database commit failed creating session: {e}")
            raise
        session_id = cursor.lastrowid
        if session_id is None:
            raise RuntimeError("Failed to create session")
        return session_id

    def compute_vault_state_hash(self, notes: List[Note]) -> str:
        """Compute hash of vault state for change detection.

        Args:
            notes: List of all notes

        Returns:
            SHA256 hash of vault state
        """
        hasher = hashlib.sha256()
        for note in sorted(notes, key=lambda n: n.path):
            hasher.update(note.path.encode())
            hasher.update(str(note.modified).encode())
        return hasher.hexdigest()

    def _compute_content_hash(self, content: str) -> str:
        """Compute hash of note content for cache invalidation.

        Args:
            content: Note content

        Returns:
            SHA256 hash of content
        """
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cached_semantic_embedding(self, note: Note) -> Optional[np.ndarray]:
        """Get cached semantic embedding if available and valid.

        Args:
            note: Note to get embedding for

        Returns:
            Cached semantic embedding or None if not found/invalid
        """
        content_hash = self._compute_content_hash(note.content)

        cursor = self.db.execute(
            """
            SELECT embedding FROM embeddings
            WHERE note_path = ? AND model_version = ?
            """,
            (note.path, f"{MODEL_NAME}:{content_hash}"),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        # Deserialize from numpy bytes (safe, no code execution risk)
        embedding: np.ndarray = np.frombuffer(row[0], dtype=np.float32)
        return embedding

    def _cache_semantic_embedding(self, note: Note, embedding: np.ndarray) -> None:
        """Cache semantic embedding for a note.

        Args:
            note: Note to cache embedding for
            embedding: Semantic embedding to cache
        """
        content_hash = self._compute_content_hash(note.content)
        # Serialize using numpy's native format (safe, no code execution risk)
        # Store as float32 to reduce storage size (sufficient precision)
        embedding_bytes = embedding.astype(np.float32).tobytes()

        self.db.execute(
            """
            INSERT OR REPLACE INTO embeddings (note_path, embedding, model_version, computed_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                note.path,
                embedding_bytes,
                f"{MODEL_NAME}:{content_hash}",
                datetime.now().isoformat(),
            ),
        )

    def compute_embeddings(self, notes: List[Note]) -> None:
        """Compute and store session embeddings for all notes.

        Uses cached semantic embeddings when available (content unchanged),
        only recomputing temporal features each session for performance.

        Args:
            notes: List of all notes in vault
        """
        # Compute vault state hash
        vault_hash = self.compute_vault_state_hash(notes)

        # Update session with vault state
        self.db.execute(
            "UPDATE sessions SET vault_state_hash = ? WHERE session_id = ?",
            (vault_hash, self.session_id),
        )

        # Delete existing embeddings for this session (if recomputing)
        self.db.execute("DELETE FROM session_embeddings WHERE session_id = ?", (self.session_id,))

        # Separate notes into cached and uncached
        cached_notes: List[tuple[Note, np.ndarray]] = []
        uncached_notes: List[Note] = []

        for note in notes:
            cached_embedding = self._get_cached_semantic_embedding(note)
            if cached_embedding is not None:
                cached_notes.append((note, cached_embedding))
            else:
                uncached_notes.append(note)

        # Batch compute semantic embeddings for uncached notes only
        semantic_embeddings: dict[str, np.ndarray] = {}

        if uncached_notes:
            texts = [note.content for note in uncached_notes]
            computed_embeddings = self.computer.model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=DEFAULT_BATCH_SIZE,
            )

            # Cache newly computed embeddings
            for i, note in enumerate(uncached_notes):
                semantic = computed_embeddings[i]
                semantic_embeddings[note.path] = semantic
                self._cache_semantic_embedding(note, semantic)

        # Add cached embeddings to lookup dict
        for note, semantic in cached_notes:
            semantic_embeddings[note.path] = semantic

        # Compute temporal features and combine with semantic embeddings
        embedding_rows = []
        for note in notes:
            semantic = semantic_embeddings[note.path]
            temporal = self.computer.compute_temporal_features(note, self.date)

            # Weight and combine (matching compute_temporal_embedding logic)
            semantic_weight = DEFAULT_SEMANTIC_WEIGHT
            temporal_weight = 1.0 - DEFAULT_SEMANTIC_WEIGHT
            semantic_scaled = semantic * semantic_weight
            temporal_scaled = temporal * temporal_weight
            embedding = np.concatenate([semantic_scaled, temporal_scaled])

            # Serialize embedding to bytes using numpy's native format (safe)
            # Store as float32 to reduce storage size (sufficient precision for embeddings)
            embedding_bytes = embedding.astype(np.float32).tobytes()

            embedding_rows.append((self.session_id, note.path, embedding_bytes))

        # Batch insert all embeddings
        self.db.executemany(
            """
            INSERT INTO session_embeddings (session_id, note_path, embedding)
            VALUES (?, ?, ?)
            """,
            embedding_rows,
        )

        try:
            self.db.commit()
        except sqlite3.Error as e:
            logger.error(f"Database commit failed saving embeddings: {e}")
            raise

        # Log cache statistics
        total = len(notes)
        cached = len(cached_notes)
        computed = len(uncached_notes)
        cache_hit_rate = (cached / total * 100) if total > 0 else 0
        print(
            f"Embedding cache: {cached}/{total} cached ({cache_hit_rate:.1f}% hit rate), "
            f"{computed} computed"
        )

    def get_embedding(self, note_path: str) -> Optional[np.ndarray]:
        """Get embedding for a note in this session.

        Args:
            note_path: Path to note

        Returns:
            Embedding array or None if not found
        """
        cursor = self.db.execute(
            """
            SELECT embedding FROM session_embeddings
            WHERE session_id = ? AND note_path = ?
            """,
            (self.session_id, note_path),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        # Deserialize from numpy bytes (safe, no code execution risk)
        embedding: np.ndarray = np.frombuffer(row[0], dtype=np.float32)
        return embedding

    def _create_backend(self) -> "VectorSearchBackend":
        """Create vector search backend based on configuration.

        Returns:
            Initialized VectorSearchBackend

        Raises:
            ValueError: If unknown backend type specified
        """
        from .vector_search import InMemoryVectorBackend, SqliteVecBackend

        if self._backend_type == "in-memory":
            return InMemoryVectorBackend(self.db)
        elif self._backend_type == "sqlite-vec":
            return SqliteVecBackend(self.db)
        else:
            raise ValueError(f"Unknown backend type: {self._backend_type}")

    def get_backend(self) -> "VectorSearchBackend":
        """Get vector search backend for this session.

        Lazily creates and loads the backend on first access.

        Returns:
            VectorSearchBackend with embeddings loaded
        """
        if self._backend is None:
            self._backend = self._create_backend()
            # Load embeddings for this session
            session_date = self.date.strftime("%Y-%m-%d")
            self._backend.load_embeddings(session_date)

        return self._backend


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two embeddings.

    Args:
        a: First embedding
        b: Second embedding

    Returns:
        Cosine similarity (0-1)
    """
    # Handle zero vectors
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    # Use sklearn for vectorized computation
    return float(sklearn_cosine(a.reshape(1, -1), b.reshape(1, -1))[0, 0])


def find_similar_notes(
    query_embedding: np.ndarray,
    embeddings: dict[str, np.ndarray],
    k: int = 10,
    exclude_paths: Optional[set[str]] = None,
) -> List[tuple[str, float]]:
    """Find k most similar notes to query embedding.

    Args:
        query_embedding: Query embedding
        embeddings: Dictionary of note paths to embeddings
        k: Number of similar notes to return
        exclude_paths: Set of paths to exclude from results

    Returns:
        List of (note_path, similarity) tuples, sorted by similarity descending
    """
    if exclude_paths is None:
        exclude_paths = set()

    # Filter excluded paths
    filtered_paths = [p for p in embeddings.keys() if p not in exclude_paths]

    if not filtered_paths:
        return []

    # Vectorized computation: compute all similarities at once
    embedding_matrix = np.vstack([embeddings[p] for p in filtered_paths])
    similarity_scores = sklearn_cosine(query_embedding.reshape(1, -1), embedding_matrix)[0]

    # Create (path, similarity) tuples
    similarities = [
        (filtered_paths[i], float(similarity_scores[i])) for i in range(len(filtered_paths))
    ]

    # Sort by similarity descending
    similarities.sort(key=lambda x: x[1], reverse=True)

    return similarities[:k]
