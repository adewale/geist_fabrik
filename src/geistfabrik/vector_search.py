"""Vector search backend abstraction for GeistFabrik.

This module provides pluggable vector similarity search backends,
allowing users to choose between in-memory and sqlite-vec implementations.
"""

import sqlite3
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

import numpy as np

from .config import TOTAL_DIM


class VectorSearchBackend(ABC):
    """Abstract base class for vector similarity search backends."""

    @abstractmethod
    def load_embeddings(self, session_date: str) -> None:
        """Load embeddings for the given session.

        Args:
            session_date: ISO date string (YYYY-MM-DD)
        """
        pass

    @abstractmethod
    def find_similar(self, query_embedding: np.ndarray, k: int = 10) -> List[Tuple[str, float]]:
        """Find k most similar notes to query embedding.

        Args:
            query_embedding: Query vector (384 or 387 dimensions)
            k: Number of results to return

        Returns:
            List of (note_path, similarity_score) tuples, sorted descending
        """
        pass

    @abstractmethod
    def get_similarity(self, path_a: str, path_b: str) -> float:
        """Get similarity score between two notes.

        Args:
            path_a: Path to first note
            path_b: Path to second note

        Returns:
            Cosine similarity score (0.0 to 1.0)

        Raises:
            KeyError: If either note path not found
        """
        pass

    @abstractmethod
    def get_embedding(self, path: str) -> np.ndarray:
        """Get embedding vector for a note.

        Args:
            path: Note path

        Returns:
            Embedding vector

        Raises:
            KeyError: If note path not found
        """
        pass


class InMemoryVectorBackend(VectorSearchBackend):
    """In-memory vector search using Python cosine similarity.

    This is the current implementation (v0.9.0), now encapsulated
    in the backend interface.

    Characteristics:
    - Fast for small-medium vaults (100-1000 notes)
    - Loads all embeddings into memory
    - Pure Python, no external dependencies
    - Memory usage: ~50 bytes per dimension per note
    """

    def __init__(self, db: sqlite3.Connection):
        """Initialize in-memory backend.

        Args:
            db: SQLite database connection
        """
        self.db = db
        self.embeddings: Dict[str, np.ndarray] = {}
        self.session_id: int = 0

    def load_embeddings(self, session_date: str) -> None:
        """Load all embeddings for session into memory.

        Args:
            session_date: ISO date string (YYYY-MM-DD)
        """
        # Get session_id from date
        cursor = self.db.execute("SELECT session_id FROM sessions WHERE date = ?", (session_date,))
        row = cursor.fetchone()
        if row is None:
            # No session found, embeddings will be empty
            self.embeddings = {}
            self.session_id = 0
            return

        self.session_id = int(row[0])

        # Load embeddings for this session
        cursor = self.db.execute(
            """
            SELECT note_path, embedding
            FROM session_embeddings
            WHERE session_id = ?
            """,
            (self.session_id,),
        )

        self.embeddings = {}
        for row in cursor:
            path, blob = row
            embedding = np.frombuffer(blob, dtype=np.float32)
            self.embeddings[path] = embedding

    def find_similar(self, query_embedding: np.ndarray, k: int = 10) -> List[Tuple[str, float]]:
        """Find similar notes via in-memory cosine similarity.

        Args:
            query_embedding: Query vector
            k: Number of results to return

        Returns:
            List of (note_path, similarity_score) tuples, sorted descending
        """
        from .embeddings import cosine_similarity

        similarities = [
            (path, cosine_similarity(query_embedding, emb)) for path, emb in self.embeddings.items()
        ]

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]

    def get_similarity(self, path_a: str, path_b: str) -> float:
        """Compute similarity between two notes.

        Args:
            path_a: Path to first note
            path_b: Path to second note

        Returns:
            Cosine similarity score

        Raises:
            KeyError: If either note path not found
        """
        from .embeddings import cosine_similarity

        if path_a not in self.embeddings:
            raise KeyError(f"Note not found: {path_a}")
        if path_b not in self.embeddings:
            raise KeyError(f"Note not found: {path_b}")

        emb_a = self.embeddings[path_a]
        emb_b = self.embeddings[path_b]
        return cosine_similarity(emb_a, emb_b)

    def get_embedding(self, path: str) -> np.ndarray:
        """Get embedding for a note.

        Args:
            path: Note path

        Returns:
            Embedding vector

        Raises:
            KeyError: If note path not found
        """
        if path not in self.embeddings:
            raise KeyError(f"Note not found: {path}")
        return self.embeddings[path]


class SqliteVecBackend(VectorSearchBackend):
    """Vector search using sqlite-vec extension.

    Requires: pip install sqlite-vec

    Characteristics:
    - Scales better for large vaults (5000+ notes)
    - Native SQL vector operations
    - Disk-based with intelligent caching
    - Uses vec0 virtual table with path mapping
    """

    def __init__(self, db: sqlite3.Connection, dim: int = TOTAL_DIM):
        """Initialize sqlite-vec backend.

        Args:
            db: SQLite database connection
            dim: Embedding dimension (default: TOTAL_DIM for temporal embeddings)

        Raises:
            RuntimeError: If sqlite-vec extension not available
        """
        self.db = db
        self.dim = dim
        self.session_date: str = ""
        self.session_id: int = 0
        self._path_to_id: Dict[str, int] = {}  # Cache for path -> vec_id mapping
        self._id_to_path: Dict[int, str] = {}  # Cache for vec_id -> path mapping
        self._setup_vec_tables()

    def _setup_vec_tables(self) -> None:
        """Create vec0 virtual table and path mapping table.

        Raises:
            RuntimeError: If sqlite-vec extension not available
        """
        # Check if sqlite-vec is available
        try:
            self.db.execute("SELECT vec_version()")
        except sqlite3.OperationalError:
            raise RuntimeError(
                "sqlite-vec extension not available. Install with: pip install sqlite-vec"
            )

        # Create path mapping table (maps note paths to integer IDs)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS vec_path_mapping (
                vec_id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_path TEXT NOT NULL UNIQUE
            )
        """)

        # Create virtual table for vector search with cosine distance
        # rowid corresponds to vec_id from vec_path_mapping
        self.db.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_search USING vec0(
                embedding float[{self.dim}] distance_metric=cosine
            )
        """)

        self.db.commit()

    def _get_or_create_vec_id(self, path: str) -> int:
        """Get or create a vec_id for a note path.

        Args:
            path: Note path

        Returns:
            Integer ID for use as vec_search rowid
        """
        # Check cache first
        if path in self._path_to_id:
            return self._path_to_id[path]

        # Check database
        cursor = self.db.execute("SELECT vec_id FROM vec_path_mapping WHERE note_path = ?", (path,))
        row = cursor.fetchone()

        if row is not None:
            vec_id = int(row[0])
            self._path_to_id[path] = vec_id
            self._id_to_path[vec_id] = path
            return vec_id

        # Create new mapping
        cursor = self.db.execute("INSERT INTO vec_path_mapping (note_path) VALUES (?)", (path,))
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError(f"Failed to create vec_id for path: {path}")

        vec_id = lastrowid
        self._path_to_id[path] = vec_id
        self._id_to_path[vec_id] = path
        return vec_id

    def _get_path_from_vec_id(self, vec_id: int) -> str:
        """Get note path from vec_id.

        Args:
            vec_id: Vector ID

        Returns:
            Note path

        Raises:
            KeyError: If vec_id not found
        """
        # Check cache first
        if vec_id in self._id_to_path:
            return self._id_to_path[vec_id]

        # Check database
        cursor = self.db.execute(
            "SELECT note_path FROM vec_path_mapping WHERE vec_id = ?", (vec_id,)
        )
        row = cursor.fetchone()

        if row is None:
            raise KeyError(f"vec_id not found: {vec_id}")

        path = str(row[0])
        self._path_to_id[path] = vec_id
        self._id_to_path[vec_id] = path
        return path

    def load_embeddings(self, session_date: str) -> None:
        """Load embeddings into vec0 virtual table.

        Args:
            session_date: ISO date string (YYYY-MM-DD)
        """
        self.session_date = session_date

        # Get session_id from date
        cursor = self.db.execute("SELECT session_id FROM sessions WHERE date = ?", (session_date,))
        row = cursor.fetchone()
        if row is None:
            # No session found, clear caches
            self.session_id = 0
            self._path_to_id = {}
            self._id_to_path = {}
            return

        self.session_id = int(row[0])

        # Clear existing vec_search data and caches
        self.db.execute("DELETE FROM vec_search")
        self._path_to_id = {}
        self._id_to_path = {}

        # Load from session_embeddings into vec_search
        cursor = self.db.execute(
            """
            SELECT note_path, embedding
            FROM session_embeddings
            WHERE session_id = ?
            """,
            (self.session_id,),
        )

        for path, blob in cursor:
            embedding = np.frombuffer(blob, dtype=np.float32)
            vec_id = self._get_or_create_vec_id(path)

            # Insert into vec_search using vec_id as rowid
            self.db.execute(
                "INSERT INTO vec_search(rowid, embedding) VALUES (?, ?)",
                (vec_id, embedding.tobytes()),
            )

        self.db.commit()

    def find_similar(self, query_embedding: np.ndarray, k: int = 10) -> List[Tuple[str, float]]:
        """Find similar notes via sqlite-vec.

        Args:
            query_embedding: Query vector
            k: Number of results to return

        Returns:
            List of (note_path, similarity_score) tuples, sorted descending
        """
        # Query vec_search for similar vectors
        cursor = self.db.execute(
            """
            SELECT rowid, distance
            FROM vec_search
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (query_embedding.astype(np.float32).tobytes(), k),
        )

        results = []
        for row in cursor:
            vec_id = int(row[0])
            distance = float(row[1])

            # Convert distance to similarity (cosine distance -> cosine similarity)
            # sqlite-vec returns cosine distance (1 - cosine_similarity)
            similarity = 1.0 - distance

            # Get path from vec_id
            try:
                path = self._get_path_from_vec_id(vec_id)
                results.append((path, similarity))
            except KeyError:
                # vec_id not found in mapping (shouldn't happen, but be defensive)
                continue

        return results

    def get_similarity(self, path_a: str, path_b: str) -> float:
        """Get similarity between two notes.

        Args:
            path_a: Path to first note
            path_b: Path to second note

        Returns:
            Cosine similarity score

        Raises:
            KeyError: If either note path not found
        """
        # Get embeddings for both notes
        emb_a = self.get_embedding(path_a)
        emb_b = self.get_embedding(path_b)

        # Compute cosine similarity
        from .embeddings import cosine_similarity

        return cosine_similarity(emb_a, emb_b)

    def get_embedding(self, path: str) -> np.ndarray:
        """Get embedding for a note.

        Args:
            path: Note path

        Returns:
            Embedding vector

        Raises:
            KeyError: If note path not found
        """
        # Get vec_id for path
        if path not in self._path_to_id:
            # Try to load from database
            cursor = self.db.execute(
                "SELECT vec_id FROM vec_path_mapping WHERE note_path = ?", (path,)
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(f"Note not found: {path}")
            vec_id = int(row[0])
            self._path_to_id[path] = vec_id
            self._id_to_path[vec_id] = path
        else:
            vec_id = self._path_to_id[path]

        # Get embedding from vec_search
        cursor = self.db.execute("SELECT embedding FROM vec_search WHERE rowid = ?", (vec_id,))
        row = cursor.fetchone()

        if row is None:
            raise KeyError(f"Note not found in vec_search: {path}")

        return np.frombuffer(row[0], dtype=np.float32)
