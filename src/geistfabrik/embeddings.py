"""Embeddings computation for GeistFabrik."""

import hashlib
import math
import pickle
import sqlite3
from datetime import datetime
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from .models import Note

# Model configuration
MODEL_NAME = "all-MiniLM-L6-v2"
SEMANTIC_DIM = 384  # Dimension of semantic embeddings
TEMPORAL_DIM = 3  # Dimension of temporal features
TOTAL_DIM = SEMANTIC_DIM + TEMPORAL_DIM  # 387 total


class EmbeddingComputer:
    """Handles embedding computation using sentence-transformers."""

    def __init__(self, model_name: str = MODEL_NAME):
        """Initialize embedding computer.

        Args:
            model_name: Name of sentence-transformers model to use
        """
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
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
        self, note: Note, session_date: datetime, semantic_weight: float = 0.9
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


class Session:
    """Represents a GeistFabrik session with temporal embeddings."""

    def __init__(self, date: datetime, db: sqlite3.Connection):
        """Initialize session.

        Args:
            date: Session date
            db: Database connection
        """
        self.date = date
        self.db = db
        self.session_id = self._get_or_create_session()
        self.computer = EmbeddingComputer()

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
        self.db.commit()
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

    def compute_embeddings(self, notes: List[Note]) -> None:
        """Compute and store session embeddings for all notes.

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

        # Batch compute semantic embeddings for all notes
        texts = [note.content for note in notes]
        semantic_embeddings = self.computer.model.encode(
            texts, convert_to_numpy=True, show_progress_bar=False
        )

        # Compute temporal features and combine with semantic embeddings
        embedding_rows = []
        for i, note in enumerate(notes):
            semantic = semantic_embeddings[i]
            temporal = self.computer.compute_temporal_features(note, self.date)

            # Weight and combine (matching compute_temporal_embedding logic)
            semantic_weight = 0.9
            temporal_weight = 0.1
            semantic_scaled = semantic * semantic_weight
            temporal_scaled = temporal * temporal_weight
            embedding = np.concatenate([semantic_scaled, temporal_scaled])

            # Serialize embedding to bytes
            embedding_bytes = pickle.dumps(embedding)

            embedding_rows.append((self.session_id, note.path, embedding_bytes))

        # Batch insert all embeddings
        self.db.executemany(
            """
            INSERT INTO session_embeddings (session_id, note_path, embedding)
            VALUES (?, ?, ?)
            """,
            embedding_rows,
        )

        self.db.commit()

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

        embedding: np.ndarray = pickle.loads(row[0])
        return embedding

    def get_all_embeddings(self) -> dict[str, np.ndarray]:
        """Get all embeddings for this session.

        Returns:
            Dictionary mapping note paths to embeddings
        """
        cursor = self.db.execute(
            """
            SELECT note_path, embedding FROM session_embeddings
            WHERE session_id = ?
            """,
            (self.session_id,),
        )

        embeddings = {}
        for row in cursor.fetchall():
            note_path, embedding_bytes = row
            embeddings[note_path] = pickle.loads(embedding_bytes)

        return embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two embeddings.

    Args:
        a: First embedding
        b: Second embedding

    Returns:
        Cosine similarity (0-1)
    """
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot_product / (norm_a * norm_b))


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

    similarities = []
    for note_path, embedding in embeddings.items():
        if note_path in exclude_paths:
            continue

        similarity = cosine_similarity(query_embedding, embedding)
        similarities.append((note_path, similarity))

    # Sort by similarity descending
    similarities.sort(key=lambda x: x[1], reverse=True)

    return similarities[:k]
