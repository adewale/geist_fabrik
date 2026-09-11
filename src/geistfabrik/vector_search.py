"""Vector search backend abstraction for GeistFabrik.

This module provides pluggable vector similarity search backends,
allowing users to choose between in-memory and sqlite-vec implementations.
"""

import re
import sqlite3
from abc import ABC, abstractmethod
from importlib import import_module
from itertools import count

import numpy as np
from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
    cosine_similarity as sklearn_cosine,
)

from .config import TOTAL_DIM
from .sqlite_transaction import owned_transaction

_VEC_TABLE_COUNTER = count()


class VectorSearchBackend(ABC):
    """Abstract base class for vector similarity search backends."""

    _closed: bool = False

    @property
    def closed(self) -> bool:
        """Whether this backend has released its loaded projection."""
        return self._closed

    def _ensure_open(self) -> None:
        if self.closed:
            raise RuntimeError("Vector search backend is closed")

    @abstractmethod
    def load_embeddings(self, session_date: str) -> None:
        """Load embeddings for the given session.

        Args:
            session_date: ISO date string (YYYY-MM-DD)
        """
        pass

    def close(self) -> None:
        """Release backend-specific derived state."""
        self._closed = True

    @abstractmethod
    def find_similar(self, query_embedding: np.ndarray, count: int = 10) -> list[tuple[str, float]]:
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

    This is the current implementation, now encapsulated
    in the backend interface.

    Characteristics:
    - Fast for small-medium vaults (100-1000 notes)
    - Loads all embeddings into memory
    - Pure Python, no external dependencies
    - Memory usage: ~50 bytes per dimension per note
    """

    def __init__(self, db: sqlite3.Connection):
        """Initialise in-memory backend.

        Args:
            db: SQLite database connection
        """
        self.db = db
        self.embeddings: dict[str, np.ndarray] = {}
        self.session_id: int = 0
        # Cached stacked matrix + parallel path index for vectorised search.
        # Rebuilt whenever embeddings change (see _rebuild_matrix).
        self._paths: list[str] = []
        self._matrix: np.ndarray | None = None

    def close(self) -> None:
        """Release loaded arrays; the shared database connection remains open."""
        self.embeddings = {}
        self._paths = []
        self._matrix = None
        self.session_id = 0
        super().close()

    def _rebuild_matrix(self) -> None:
        """Rebuild the cached embedding matrix and path index from self.embeddings.

        Stacking all embeddings into a single (N, dim) matrix once lets
        find_similar() compute every cosine similarity in a single vectorised
        operation instead of an O(N) Python loop of per-pair calls.
        """
        self._paths = list(self.embeddings.keys())
        if self._paths:
            self._matrix = np.vstack([self.embeddings[p] for p in self._paths])
        else:
            self._matrix = None

    def load_embeddings(self, session_date: str) -> None:
        """Load all embeddings for session into memory.

        Args:
            session_date: ISO date string (YYYY-MM-DD)
        """
        self._ensure_open()
        # Get session_id from date
        cursor = self.db.execute("SELECT session_id FROM sessions WHERE date = ?", (session_date,))
        row = cursor.fetchone()
        if row is None:
            # No session found, embeddings will be empty
            self.embeddings = {}
            self.session_id = 0
            self._rebuild_matrix()
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

        self._rebuild_matrix()

    def find_similar(self, query_embedding: np.ndarray, count: int = 10) -> list[tuple[str, float]]:
        """Find similar notes via vectorised in-memory cosine similarity.

        Computes all similarities in a single matrix operation (matching the
        semantics of embeddings.find_similar_notes), rather than looping over
        every embedding in Python. Results are sorted descending; ties preserve
        insertion order (stable sort) to keep output deterministic.

        Args:
            query_embedding: Query vector
            k: Number of results to return

        Returns:
            List of (note_path, similarity_score) tuples, sorted descending
        """
        self._ensure_open()
        # Defensive: rebuild if embeddings were mutated since the last load.
        if self._matrix is None or len(self._paths) != len(self.embeddings):
            self._rebuild_matrix()
        if self._matrix is None or count <= 0:
            return []

        scores = sklearn_cosine(query_embedding.reshape(1, -1), self._matrix)[0]
        n = scores.shape[0]
        if count >= n:
            # Full stable sort: descending by score, ties keep insertion order.
            order = np.argsort(-scores, kind="stable")
        else:
            # O(N + k log k) top-k via argpartition instead of an O(N log N)
            # full sort (this is the hottest path - every neighbours() call).
            # To keep output byte-identical to a full stable argsort prefix,
            # widen the candidate set to every score tied with the k-th
            # largest, then stable-sort just that small set.
            part = np.argpartition(-scores, count - 1)[:count]
            kth_score = scores[part].min()
            cand = np.flatnonzero(scores >= kth_score)
            order = cand[np.argsort(-scores[cand], kind="stable")][:count]
        return [(self._paths[int(i)], float(scores[int(i)])) for i in order]

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
        self._ensure_open()
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
            Embedding vector. READ-ONLY (np.frombuffer view shared by all
            callers) - mutation raises ValueError; .copy() first if needed.

        Raises:
            KeyError: If note path not found
        """
        self._ensure_open()
        if path not in self.embeddings:
            raise KeyError(f"Note not found: {path}")
        return self.embeddings[path]


class SqliteVecBackend(VectorSearchBackend):
    """Vector search using sqlite-vec extension.

    Requires: pip install sqlite-vec

    Characteristics:
    - Scales better for large vaults (5000+ notes)
    - Native SQL vector operations
    - Durable embeddings remain in session_embeddings
    - Uses an instance-private TEMP vec0 projection with persistent path mapping
    """

    def __init__(self, db: sqlite3.Connection, dim: int = TOTAL_DIM):
        """Initialise sqlite-vec backend.

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
        self._path_to_id: dict[str, int] = {}  # Cache for path -> vec_id mapping
        self._id_to_path: dict[int, str] = {}  # Cache for vec_id -> path mapping
        self._search_table = f"_geist_vec_search_{next(_VEC_TABLE_COUNTER)}"
        self._closed = False
        self._setup_vec_tables()

    def _setup_vec_tables(self) -> None:
        """Create vec0 virtual table and path mapping table.

        Raises:
            RuntimeError: If sqlite-vec extension not available
        """
        self._ensure_sqlite_vec_loaded()

        with owned_transaction(self.db, "SqliteVecBackend setup"):
            # Releases before TEMP projections stored a disposable vec0 table in
            # main. Dropping the virtual table also drops its own shadow tables.
            # Do not delete an unrelated ordinary table that shares the name.
            legacy = self.db.execute(
                "SELECT sql FROM main.sqlite_master WHERE type = 'table' AND name = 'vec_search'"
            ).fetchone()
            if legacy and re.search(
                r"^\s*CREATE\s+VIRTUAL\s+TABLE\s+vec_search\s+USING\s+vec0\s*\(\s*"
                r"embedding\s+float\[\d+\]\s+distance_metric\s*=\s*cosine\s*\)\s*$",
                legacy[0] or "",
                re.IGNORECASE | re.DOTALL,
            ):
                self.db.execute("DROP TABLE main.vec_search")

            # Create path mapping table (maps note paths to integer IDs)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS vec_path_mapping (
                    vec_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_path TEXT NOT NULL UNIQUE
                )
            """)

            # TEMP plus a per-instance name prevents one Session/backend from
            # replacing another backend's loaded projection. Durable vectors
            # remain in session_embeddings; this table is only an accelerator.
            self.db.execute(f"""
                CREATE VIRTUAL TABLE temp.{self._search_table} USING vec0(
                    embedding float[{self.dim}] distance_metric=cosine
                )
            """)

    def _ensure_sqlite_vec_loaded(self) -> None:
        """Load the known sqlite-vec package on this connection when needed."""
        try:
            self.db.execute("SELECT vec_version()").fetchone()
            return
        except sqlite3.OperationalError:
            pass

        try:
            sqlite_vec = import_module("sqlite_vec")
            load = getattr(sqlite_vec, "load")
            enable_load_extension = self.db.enable_load_extension
        except (ImportError, AttributeError) as error:
            raise RuntimeError(
                "sqlite-vec extension not available. Install with: pip install sqlite-vec"
            ) from error

        load_error: BaseException | None = None
        try:
            enable_load_extension(True)
            load(self.db)
        except (sqlite3.Error, OSError) as error:
            load_error = error
        finally:
            try:
                # Loading arbitrary extensions must not remain enabled after the
                # trusted package has initialized this connection.
                enable_load_extension(False)
            except (sqlite3.Error, AttributeError) as error:
                raise RuntimeError(
                    "sqlite-vec loaded but SQLite extension loading could not be disabled"
                ) from error

        if load_error is not None:
            raise RuntimeError(
                "sqlite-vec extension not available. Install with: pip install sqlite-vec"
            ) from load_error
        try:
            self.db.execute("SELECT vec_version()").fetchone()
        except sqlite3.OperationalError as error:
            raise RuntimeError(
                "sqlite-vec extension not available. Install with: pip install sqlite-vec"
            ) from error

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

        vec_id = self._lookup_or_create_vec_id(path)
        self._path_to_id[path] = vec_id
        self._id_to_path[vec_id] = path
        return vec_id

    def _lookup_or_create_vec_id(self, path: str) -> int:
        """Resolve durable mapping without publishing it to instance caches."""
        cursor = self.db.execute("SELECT vec_id FROM vec_path_mapping WHERE note_path = ?", (path,))
        row = cursor.fetchone()

        if row is not None:
            return int(row[0])

        # Create new mapping
        cursor = self.db.execute("INSERT INTO vec_path_mapping (note_path) VALUES (?)", (path,))
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError(f"Failed to create vec_id for path: {path}")

        return lastrowid

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
        self._ensure_open()
        path_to_id: dict[str, int] = {}
        id_to_path: dict[int, str] = {}
        with owned_transaction(self.db, "SqliteVecBackend.load_embeddings"):
            # A different writer may create/replace the session while BEGIN
            # waits. Both identity and vectors must come from the locked state.
            row = self.db.execute(
                "SELECT session_id FROM sessions WHERE date = ?", (session_date,)
            ).fetchone()
            session_id = int(row[0]) if row is not None else 0
            self.db.execute(f"DELETE FROM temp.{self._search_table}")
            if row is not None:
                cursor = self.db.execute(
                    """
                    SELECT note_path, embedding
                    FROM session_embeddings
                    WHERE session_id = ?
                    """,
                    (session_id,),
                )
                try:
                    for path, blob in cursor:
                        vec_id = self._lookup_or_create_vec_id(path)
                        self.db.execute(
                            f"INSERT INTO temp.{self._search_table}(rowid, embedding) "
                            "VALUES (?, ?)",
                            (vec_id, blob),
                        )
                        path_to_id[path] = vec_id
                        id_to_path[vec_id] = path
                finally:
                    # A traceback can keep this partially consumed statement
                    # alive; close it before rollback/cleanup need schema locks.
                    cursor.close()

        # Publish only after commit; exceptions leave the previous projection
        # and its Python-side identity/cache state together.
        self.session_date = session_date
        self.session_id = session_id
        self._path_to_id = path_to_id
        self._id_to_path = id_to_path

    def close(self) -> None:
        """Drop this backend's connection-local vector projection."""
        if self._closed:
            return
        if self.db.in_transaction:
            raise RuntimeError("SqliteVecBackend.close requires an idle SQLite connection")
        # TEMP schema teardown is connection-local and does not need the main
        # database's writer lock. Acquiring it here can make cleanup fail merely
        # because an unrelated connection is writing.
        self.db.execute(f"DROP TABLE IF EXISTS temp.{self._search_table}")
        self._path_to_id = {}
        self._id_to_path = {}
        self.session_id = 0
        self._closed = True

    def find_similar(self, query_embedding: np.ndarray, count: int = 10) -> list[tuple[str, float]]:
        """Find similar notes via sqlite-vec.

        Args:
            query_embedding: Query vector
            k: Number of results to return

        Returns:
            List of (note_path, similarity_score) tuples, sorted descending
        """
        self._ensure_open()
        # Query vec_search for similar vectors
        cursor = self.db.execute(
            f"""
            SELECT rowid, distance
            FROM temp.{self._search_table}
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (query_embedding.astype(np.float32).tobytes(), count),
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
        self._ensure_open()
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
        cursor = self.db.execute(
            f"SELECT embedding FROM temp.{self._search_table} WHERE rowid = ?", (vec_id,)
        )
        row = cursor.fetchone()

        if row is None:
            raise KeyError(f"Note not found in vec_search: {path}")

        return np.frombuffer(row[0], dtype=np.float32)
