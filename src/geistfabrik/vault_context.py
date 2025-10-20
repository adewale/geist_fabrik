"""VaultContext - Rich execution context for geists."""

import random
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from .embeddings import Session, cosine_similarity, find_similar_notes
from .models import Link, Note
from .vault import Vault


class VaultContext:
    """Rich execution context for geists.

    This class wraps a Vault with intelligence and utilities, providing
    semantic search, graph operations, metadata access, and deterministic
    randomness. This is what geists actually receive.
    """

    def __init__(
        self,
        vault: Vault,
        session: Session,
        seed: Optional[int] = None,
    ):
        """Initialize vault context.

        Args:
            vault: Vault instance
            session: Session with embeddings computed
            seed: Random seed for deterministic operations. If None, use date-based seed.
        """
        self.vault = vault
        self.session = session
        self.db = vault.db

        # Deterministic randomness
        if seed is None:
            # Use session date as seed for determinism
            seed = int(session.date.strftime("%Y%m%d"))
        self.rng = random.Random(seed)

        # Function registry (for extensibility)
        self._functions: Dict[str, Callable[..., Any]] = {}

        # Cache for metadata
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}

        # Cache for embeddings (loaded from session)
        self._embeddings = session.get_all_embeddings()

    # Direct vault access (delegated)

    def notes(self) -> List[Note]:
        """Get all notes in vault.

        Returns:
            List of all notes
        """
        return self.vault.all_notes()

    def get_note(self, path: str) -> Optional[Note]:
        """Get specific note by path.

        Args:
            path: Note path

        Returns:
            Note or None if not found
        """
        return self.vault.get_note(path)

    def read(self, note: Note) -> str:
        """Read note content.

        Args:
            note: Note to read

        Returns:
            Note content
        """
        return note.content

    # Semantic search

    def neighbors(self, note: Note, k: int = 10) -> List[Note]:
        """Find k semantically similar notes.

        Args:
            note: Query note
            k: Number of neighbors to return

        Returns:
            List of similar notes, sorted by similarity descending
        """
        # Get embedding for query note
        query_embedding = self._embeddings.get(note.path)
        if query_embedding is None:
            return []

        # Find similar notes
        similar = find_similar_notes(
            query_embedding, self._embeddings, k=k + 1, exclude_paths={note.path}
        )

        # Convert paths to notes
        result = []
        for path, _ in similar[:k]:
            similar_note = self.get_note(path)
            if similar_note is not None:
                result.append(similar_note)

        return result

    def similarity(self, a: Note, b: Note) -> float:
        """Calculate semantic similarity between two notes.

        Args:
            a: First note
            b: Second note

        Returns:
            Cosine similarity (0-1)
        """
        embedding_a = self._embeddings.get(a.path)
        embedding_b = self._embeddings.get(b.path)

        if embedding_a is None or embedding_b is None:
            return 0.0

        return cosine_similarity(embedding_a, embedding_b)

    # Graph operations

    def backlinks(self, note: Note) -> List[Note]:
        """Find notes that link to this note.

        Args:
            note: Target note

        Returns:
            List of notes with links to target
        """
        # Need to match target as: path, path without extension, or title
        path_without_ext = note.path.rsplit(".", 1)[0] if "." in note.path else note.path

        cursor = self.db.execute(
            """
            SELECT DISTINCT source_path FROM links
            WHERE target = ? OR target = ? OR target = ?
            """,
            (note.path, path_without_ext, note.title),
        )

        result = []
        for row in cursor.fetchall():
            source = self.get_note(row[0])
            if source is not None:
                result.append(source)

        return result

    def orphans(self, k: Optional[int] = None) -> List[Note]:
        """Find notes with no outgoing or incoming links.

        Args:
            k: Maximum number to return. If None, return all.

        Returns:
            List of orphan notes
        """
        cursor = self.db.execute(
            """
            SELECT path FROM notes
            WHERE path NOT IN (SELECT source_path FROM links)
            AND path NOT IN (SELECT DISTINCT target FROM links
                           WHERE target LIKE '%.md')
            ORDER BY modified DESC
            """
        )

        result = []
        for row in cursor.fetchall():
            note = self.get_note(row[0])
            if note is not None:
                result.append(note)
                if k is not None and len(result) >= k:
                    break

        return result

    def hubs(self, k: int = 10) -> List[Note]:
        """Find most-linked-to notes.

        Args:
            k: Number of hubs to return

        Returns:
            List of hub notes, sorted by link count descending
        """
        cursor = self.db.execute(
            """
            SELECT target, COUNT(*) as link_count
            FROM links
            WHERE target LIKE '%.md'
            GROUP BY target
            ORDER BY link_count DESC
            LIMIT ?
            """,
            (k,),
        )

        result = []
        for row in cursor.fetchall():
            target_path = row[0]
            note = self.get_note(target_path)
            if note is not None:
                result.append(note)

        return result

    def unlinked_pairs(self, k: int = 10) -> List[Tuple[Note, Note]]:
        """Find semantically similar note pairs with no links between them.

        Args:
            k: Number of pairs to return

        Returns:
            List of (note_a, note_b) tuples
        """
        notes = self.notes()
        pairs = []

        # Find similar pairs without links
        for i, note_a in enumerate(notes):
            embedding_a = self._embeddings.get(note_a.path)
            if embedding_a is None:
                continue

            for note_b in notes[i + 1 :]:
                embedding_b = self._embeddings.get(note_b.path)
                if embedding_b is None:
                    continue

                # Check if there's a link between them
                if self.links_between(note_a, note_b):
                    continue

                # Compute similarity
                sim = cosine_similarity(embedding_a, embedding_b)
                pairs.append((note_a, note_b, sim))

        # Sort by similarity and take top k
        pairs.sort(key=lambda x: x[2], reverse=True)
        return [(a, b) for a, b, _ in pairs[:k]]

    def links_between(self, a: Note, b: Note) -> List[Link]:
        """Find all links between two notes (bidirectional).

        Args:
            a: First note
            b: Second note

        Returns:
            List of links between the notes
        """

        # Helper to check if a link target matches a note
        def link_matches_note(link_target: str, note: Note) -> bool:
            path_without_ext = note.path.rsplit(".", 1)[0] if "." in note.path else note.path
            return link_target in (note.path, path_without_ext, note.title)

        # Check a -> b
        links_ab = [link for link in a.links if link_matches_note(link.target, b)]

        # Check b -> a
        links_ba = [link for link in b.links if link_matches_note(link.target, a)]

        return links_ab + links_ba

    # Temporal queries

    def old_notes(self, k: int = 10) -> List[Note]:
        """Find least recently modified notes.

        Args:
            k: Number of notes to return

        Returns:
            List of old notes, sorted by modification time ascending
        """
        cursor = self.db.execute("SELECT path FROM notes ORDER BY modified ASC LIMIT ?", (k,))

        result = []
        for row in cursor.fetchall():
            note = self.get_note(row[0])
            if note is not None:
                result.append(note)

        return result

    def recent_notes(self, k: int = 10) -> List[Note]:
        """Find most recently modified notes.

        Args:
            k: Number of notes to return

        Returns:
            List of recent notes, sorted by modification time descending
        """
        cursor = self.db.execute("SELECT path FROM notes ORDER BY modified DESC LIMIT ?", (k,))

        result = []
        for row in cursor.fetchall():
            note = self.get_note(row[0])
            if note is not None:
                result.append(note)

        return result

    # Metadata access

    def metadata(self, note: Note) -> Dict[str, Any]:
        """Retrieve all inferred metadata for a note.

        Args:
            note: Note to get metadata for

        Returns:
            Dictionary of metadata properties
        """
        if note.path in self._metadata_cache:
            return self._metadata_cache[note.path]

        # For now, return basic metadata
        # Metadata inference system will be added in Phase 2C
        metadata = {
            "word_count": len(note.content.split()),
            "link_count": len(note.links),
            "tag_count": len(note.tags),
            "age_days": (datetime.now() - note.created).days,
        }

        self._metadata_cache[note.path] = metadata
        return metadata

    # Deterministic sampling

    def sample(self, items: List[Any], k: int) -> List[Any]:
        """Deterministically sample k items.

        Args:
            items: List to sample from
            k: Number of items to sample

        Returns:
            Sample of k items (or fewer if list is smaller)
        """
        if k >= len(items):
            return list(items)

        return self.rng.sample(items, k)

    def random_notes(self, k: int = 1) -> List[Note]:
        """Sample k random notes.

        Args:
            k: Number of notes to sample

        Returns:
            Random sample of notes
        """
        notes = self.notes()
        return self.sample(notes, k)

    # Function registry

    def register_function(self, name: str, func: Callable[..., Any]) -> None:
        """Register a vault function.

        Args:
            name: Function name
            func: Callable function
        """
        self._functions[name] = func

    def call_function(self, name: str, **kwargs: Any) -> Any:
        """Call registered vault function.

        Args:
            name: Function name
            **kwargs: Function arguments

        Returns:
            Function result

        Raises:
            KeyError: If function not found
        """
        if name not in self._functions:
            raise KeyError(f"Function '{name}' not registered")

        return self._functions[name](self, **kwargs)

    def list_functions(self) -> List[str]:
        """List all registered function names.

        Returns:
            List of function names
        """
        return list(self._functions.keys())
