"""Vector search backend abstraction for GeistFabrik.

This module provides pluggable vector similarity search backends,
allowing users to choose between in-memory and sqlite-vec implementations.
"""

import sqlite3
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

import numpy as np


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
    - Uses vec0 virtual table
    """

    def __init__(self, db: sqlite3.Connection):
        """Initialize sqlite-vec backend.

        Args:
            db: SQLite database connection

        Raises:
            RuntimeError: If sqlite-vec extension not available
        """
        self.db = db
        self.session_date: str = ""
        self.session_id: int = 0
        self._setup_vec_table()

    def _setup_vec_table(self) -> None:
        """Create vec0 virtual table if needed.

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

        # Create virtual table for vector search
        # Note: This table is temporary and repopulated each session
        self.db.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_search USING vec0(
                embedding float[387]
            )
        """)

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
            # No session found
            self.session_id = 0
            return

        self.session_id = int(row[0])

        # Clear existing vec_search data
        self.db.execute("DELETE FROM vec_search")

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
            # Insert into vec_search with path as rowid
            # Note: We use path as string for rowid mapping
            # This is a limitation - we'll need a mapping table for proper implementation
            # For now, we'll use a separate path_mapping table
            self.db.execute(
                "INSERT INTO vec_search(rowid, embedding) VALUES (?, ?)",
                (hash(path) % (2**63), embedding.tobytes()),
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
        # Note: This is a placeholder implementation
        # Full implementation requires proper path mapping
        # For now, fall back to in-memory approach
        raise NotImplementedError(
            "SqliteVecBackend is not yet fully implemented. Please use 'in-memory' backend for now."
        )

    def get_similarity(self, path_a: str, path_b: str) -> float:
        """Get similarity between two notes.

        Args:
            path_a: Path to first note
            path_b: Path to second note

        Returns:
            Cosine similarity score

        Raises:
            NotImplementedError: Not yet implemented
        """
        raise NotImplementedError(
            "SqliteVecBackend is not yet fully implemented. Please use 'in-memory' backend for now."
        )

    def get_embedding(self, path: str) -> np.ndarray:
        """Get embedding for a note.

        Args:
            path: Note path

        Returns:
            Embedding vector

        Raises:
            NotImplementedError: Not yet implemented
        """
        raise NotImplementedError(
            "SqliteVecBackend is not yet fully implemented. Please use 'in-memory' backend for now."
        )
