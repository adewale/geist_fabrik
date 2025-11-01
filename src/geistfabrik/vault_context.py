"""VaultContext - Rich execution context for geists."""

import logging
import random
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .embeddings import Session, cosine_similarity
from .models import Link, Note
from .vault import Vault

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .function_registry import FunctionRegistry
    from .metadata_system import MetadataLoader


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
        metadata_loader: Optional["MetadataLoader"] = None,
        function_registry: Optional["FunctionRegistry"] = None,
    ):
        """Initialize vault context.

        Args:
            vault: Vault instance
            session: Session with embeddings computed
            seed: Random seed for deterministic operations. If None, use date-based seed.
            metadata_loader: Optional metadata inference loader
            function_registry: Optional function registry for vault functions
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
        self._function_registry = function_registry

        # Cache for notes (performance optimization)
        self._notes_cache: Optional[List[Note]] = None

        # Cache for metadata
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}

        # Cache for clusters (performance optimization - keyed by min_size)
        self._clusters_cache: Dict[int, Dict[int, Dict[str, Any]]] = {}

        # Cache for similarity scores (performance optimization - keyed by note path pair)
        self._similarity_cache: Dict[Tuple[str, str], float] = {}

        # Cache for neighbours (performance optimization - keyed by (note_path, k))
        self._neighbours_cache: Dict[Tuple[str, int], List[Note]] = {}

        # Metadata loader for extensible metadata inference
        self._metadata_loader = metadata_loader

        # Track metadata inference errors
        self.metadata_errors: Dict[str, List[str]] = {}  # note_path -> list of failed module names

        # Vector search backend (delegated from session)
        self._backend = session.get_backend()

        # Keep backward-compatible embeddings dict for compatibility
        # (Some code may still access self._embeddings directly)
        self._embeddings = session.get_all_embeddings()

    # Direct vault access (delegated)

    def notes(self) -> List[Note]:
        """Get all notes in vault (cached).

        Performance optimization: Notes are loaded once and cached
        for the duration of the VaultContext session.

        Returns:
            List of all notes
        """
        if self._notes_cache is None:
            self._notes_cache = self.vault.all_notes()
        return self._notes_cache

    def get_note(self, path: str) -> Optional[Note]:
        """Get specific note by path.

        Args:
            path: Note path

        Returns:
            Note or None if not found
        """
        return self.vault.get_note(path)

    def resolve_link_target(self, target: str) -> Optional[Note]:
        """Resolve a wiki-link target to a Note.

        Tries multiple resolution strategies:
        1. Exact path match
        2. Path with .md extension
        3. Lookup by note title

        Args:
            target: Link target (path or title)

        Returns:
            Note or None if not found
        """
        return self.vault.resolve_link_target(target)

    def read(self, note: Note) -> str:
        """Read note content.

        Args:
            note: Note to read

        Returns:
            Note content
        """
        return note.content

    # Semantic search

    def neighbours(self, note: Note, k: int = 10) -> List[Note]:
        """Find k semantically similar notes.

        Uses session-scoped caching for performance. Many geists query neighbours
        for the same notes (e.g., hub notes, recently modified notes), so caching
        eliminates redundant vector searches across all geists in a session.

        Args:
            note: Query note
            k: Number of neighbours to return

        Returns:
            List of similar notes, sorted by similarity descending
        """
        # Create cache key (note path + k parameter)
        cache_key = (note.path, k)

        # Check cache first
        if cache_key in self._neighbours_cache:
            return self._neighbours_cache[cache_key]

        # Get embedding for query note
        try:
            query_embedding = self._backend.get_embedding(note.path)
        except KeyError:
            return []

        # Find similar notes (request k+1 to exclude self)
        similar = self._backend.find_similar(query_embedding, k=k + 1)

        # Convert paths to notes, excluding the query note
        result = []
        for path, _ in similar:
            if path == note.path:
                continue  # Skip self
            similar_note = self.get_note(path)
            if similar_note is not None:
                result.append(similar_note)
                if len(result) >= k:
                    break

        # Cache the result
        self._neighbours_cache[cache_key] = result
        return result

    def similarity(self, a: Note, b: Note) -> float:
        """Calculate semantic similarity between two notes.

        Uses session-scoped caching for performance. Multiple geists often
        compute similarity for the same pairs (e.g., linked notes), so caching
        eliminates redundant computation across all geists in a session.

        Args:
            a: First note
            b: Second note

        Returns:
            Cosine similarity (0-1)
        """
        # Create order-independent cache key (similarity is symmetric)
        sorted_paths = sorted([a.path, b.path])
        cache_key: Tuple[str, str] = (sorted_paths[0], sorted_paths[1])

        # Check cache first
        if cache_key in self._similarity_cache:
            return self._similarity_cache[cache_key]

        # Compute and cache
        try:
            similarity_score = self._backend.get_similarity(a.path, b.path)
        except KeyError:
            similarity_score = 0.0

        self._similarity_cache[cache_key] = similarity_score
        return similarity_score

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

    def outgoing_links(self, note: Note) -> List[Note]:
        """Find notes that this note links to (outgoing links).

        Symmetric counterpart to backlinks(). Returns resolved Note objects
        for all outgoing links from this note.

        Args:
            note: Source note

        Returns:
            List of notes that this note links to
        """
        result = []
        for link in note.links:
            target = self.resolve_link_target(link.target)
            if target is not None:
                result.append(target)
        return result

    def orphans(self, k: Optional[int] = None) -> List[Note]:
        """Find notes with no outgoing or incoming links.

        Performance optimized with LEFT JOINs instead of NOT IN subqueries.

        Args:
            k: Maximum number to return. If None, return all.

        Returns:
            List of orphan notes
        """
        cursor = self.db.execute(
            """
            SELECT n.path
            FROM notes n
            LEFT JOIN links l1 ON l1.source_path = n.path
            LEFT JOIN links l2 ON (
                l2.target = n.path
                OR l2.target = n.title
                OR l2.target || '.md' = n.path
            )
            WHERE l1.source_path IS NULL
              AND l2.target IS NULL
            ORDER BY n.modified DESC
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
            GROUP BY target
            ORDER BY link_count DESC
            LIMIT ?
            """,
            (k * 3,),  # Get more candidates since some may not resolve
        )

        result = []
        for row in cursor.fetchall():
            target = row[0]
            # Resolve the link target to an actual note
            note = self.vault.resolve_link_target(target)
            if note is not None:
                result.append(note)
                if len(result) >= k:
                    break

        return result

    def get_clusters(self, min_size: int = 5) -> Dict[int, Dict[str, Any]]:
        """Get cluster assignments and labels for current session.

        Uses HDBSCAN clustering on embeddings, then generates labels via
        c-TF-IDF with MMR diversity filtering. Returns cluster information
        including formatted labels and member notes.

        Results are cached per session by min_size parameter for performance.

        Args:
            min_size: Minimum notes required to form a cluster

        Returns:
            Dictionary mapping cluster_id to cluster info:
            {
                cluster_id: {
                    "label": "keyword, list, here",
                    "formatted_label": "Notes about keyword, list, and here",
                    "notes": [Note, ...],
                    "size": int,
                    "centroid": np.ndarray,
                }
            }
        """
        # Check cache first (session-scoped caching)
        if min_size in self._clusters_cache:
            return self._clusters_cache[min_size]

        # Import optional dependency
        try:
            from sklearn.cluster import HDBSCAN  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("sklearn not available, clustering disabled")
            empty_result: Dict[int, Dict[str, Any]] = {}
            self._clusters_cache[min_size] = empty_result
            return empty_result

        # Get all embeddings and paths for current session
        embeddings_dict = self.session.get_all_embeddings()
        if len(embeddings_dict) < min_size * 2:  # Need at least 2 clusters worth
            empty_result_2: Dict[int, Dict[str, Any]] = {}
            self._clusters_cache[min_size] = empty_result_2
            return empty_result_2

        paths = list(embeddings_dict.keys())
        embeddings_array = np.array([embeddings_dict[p] for p in paths])

        # Run HDBSCAN clustering
        clusterer = HDBSCAN(min_cluster_size=min_size, min_samples=3)
        labels = clusterer.fit_predict(embeddings_array)

        # Group notes by cluster
        clusters: Dict[int, List[Note]] = {}
        cluster_paths: Dict[int, List[str]] = {}

        for i, label in enumerate(labels):
            if label == -1:  # Noise points
                continue
            if label not in clusters:
                clusters[label] = []
                cluster_paths[label] = []

            note = self.get_note(paths[i])
            if note:
                clusters[label].append(note)
                cluster_paths[label].append(paths[i])

        if not clusters:
            empty_result_3: Dict[int, Dict[str, Any]] = {}
            self._clusters_cache[min_size] = empty_result_3
            return empty_result_3

        # Generate labels using stats module
        from .stats import EmbeddingMetricsComputer

        metrics_computer = EmbeddingMetricsComputer(self.db)
        cluster_labels_raw = metrics_computer._label_clusters_tfidf(paths, labels, n_terms=4)

        # Build result with formatted labels and centroids
        result: Dict[int, Dict[str, Any]] = {}

        for cluster_id, notes in clusters.items():
            # Get embeddings for this cluster
            cluster_embeddings = np.array(
                [embeddings_dict[path] for path in cluster_paths[cluster_id]]
            )

            # Calculate centroid (mean of embeddings)
            centroid = np.mean(cluster_embeddings, axis=0)

            # Format label as phrase
            keyword_label = cluster_labels_raw.get(cluster_id, f"Cluster {cluster_id}")
            formatted_label = self._format_cluster_label(keyword_label)

            result[cluster_id] = {
                "label": keyword_label,
                "formatted_label": formatted_label,
                "notes": notes,
                "size": len(notes),
                "centroid": centroid,
            }

        # Cache result for this session
        self._clusters_cache[min_size] = result

        return result

    def _format_cluster_label(self, keyword_label: str) -> str:
        """Format keyword list as readable phrase.

        Args:
            keyword_label: Comma-separated keywords

        Returns:
            Formatted phrase template
        """
        terms = [t.strip() for t in keyword_label.split(",")]

        if len(terms) == 1:
            return f"Notes about {terms[0]}"
        elif len(terms) == 2:
            return f"Notes about {terms[0]} and {terms[1]}"
        else:
            # Oxford comma for 3+ terms
            return f"Notes about {', '.join(terms[:-1])}, and {terms[-1]}"

    def get_cluster_representatives(
        self,
        cluster_id: int,
        k: int = 3,
        clusters: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> List[Note]:
        """Get most representative notes for a cluster.

        Finds notes closest to the cluster centroid, which are the most
        "typical" or "central" notes in the cluster.

        Args:
            cluster_id: Cluster ID from get_clusters()
            k: Number of representative notes to return
            clusters: Optional pre-computed clusters dict from get_clusters().
                     If not provided, will call get_clusters() internally.
                     Passing this avoids redundant clustering.

        Returns:
            List of k notes closest to cluster centroid
        """
        if clusters is None:
            clusters = self.get_clusters()

        if cluster_id not in clusters:
            return []

        cluster = clusters[cluster_id]
        centroid = cluster["centroid"]
        notes = cluster["notes"]

        # Calculate similarity to centroid for each note
        embeddings_dict = self.session.get_all_embeddings()
        similarities = []

        for note in notes:
            note_embedding = embeddings_dict.get(note.path)
            if note_embedding is not None:
                sim = cosine_similarity(centroid, note_embedding)
                similarities.append((note, sim))

        # Sort by similarity descending, return top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [note for note, _ in similarities[:k]]

    def unlinked_pairs(self, k: int = 10, candidate_limit: int = 200) -> List[Tuple[Note, Note]]:
        """Find semantically similar note pairs with no links between them.

        Performance optimization: For large vaults (>1000 notes), this limits the
        search space to avoid O(n²) complexity. Use candidate_limit to balance
        between performance and coverage.

        Args:
            k: Number of pairs to return
            candidate_limit: Maximum number of notes to consider (to avoid O(n²) on large vaults)

        Returns:
            List of (note_a, note_b) tuples sorted by similarity
        """
        all_notes = self.notes()

        # Optimize for large vaults by limiting candidate set
        if len(all_notes) > candidate_limit:
            # Sample a diverse set: recent notes + random notes
            recent = self.recent_notes(k=candidate_limit // 2)
            remaining = [n for n in all_notes if n not in recent]
            random_notes = self.sample(remaining, min(candidate_limit // 2, len(remaining)))
            notes = recent + random_notes
        else:
            notes = all_notes

        pairs = []

        # Find similar pairs without links (optimized with early stopping)
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

                # Only keep high-similarity pairs (>0.5 threshold)
                if sim > 0.5:
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

    def has_link(self, a: Note, b: Note) -> bool:
        """Check if there's a direct link between two notes (bidirectional).

        Returns True if a links to b OR b links to a.

        Args:
            a: First note
            b: Second note

        Returns:
            True if notes are linked, False otherwise
        """
        return len(self.links_between(a, b)) > 0

    def graph_neighbors(self, note: Note) -> List[Note]:
        """Get all notes connected to this note by links (bidirectional).

        Returns notes that:
        - This note links to (outgoing links)
        - Link to this note (incoming links / backlinks)

        Args:
            note: Query note

        Returns:
            List of connected notes (no duplicates)
        """
        neighbors = set()

        # Add outgoing link targets
        for link in note.links:
            target = self.resolve_link_target(link.target)
            if target is not None:
                neighbors.add(target)

        # Add incoming link sources (backlinks)
        for source in self.backlinks(note):
            neighbors.add(source)

        return list(neighbors)

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

        # Start with basic built-in metadata
        metadata = {
            "word_count": len(note.content.split()),
            "link_count": len(note.links),
            "tag_count": len(note.tags),
            "age_days": (datetime.now() - note.created).days,
        }

        # Run metadata inference modules if available
        if self._metadata_loader is not None:
            try:
                inferred, failed_modules = self._metadata_loader.infer_all(note, self)
                metadata.update(inferred)

                # Track failed modules for this note
                if failed_modules:
                    self.metadata_errors[note.path] = failed_modules
            except Exception as e:
                # Log error but don't fail - metadata inference is optional
                logger.error(
                    f"Error inferring metadata for {note.path}: {e}",
                    exc_info=True,
                    extra={"note_path": note.path},
                )

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
        if self._function_registry is not None:
            self._function_registry.register(name, func)
        else:
            self._functions[name] = func

    def call_function(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Call registered vault function.

        Args:
            name: Function name
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            KeyError: If function not found
        """
        # Try function registry first
        if self._function_registry is not None:
            if self._function_registry.has_function(name):
                return self._function_registry.call(name, self, *args, **kwargs)

        # Fall back to local functions dict
        if name not in self._functions:
            raise KeyError(f"Function '{name}' not registered")

        return self._functions[name](self, **kwargs)

    def list_functions(self) -> List[str]:
        """List all registered function names.

        Returns:
            List of function names
        """
        return list(self._functions.keys())

    def get_metadata_error_summary(self) -> Dict[str, int]:
        """Get summary of metadata inference errors.

        Returns:
            Dictionary mapping module names to count of notes where they failed
        """
        module_error_counts: Dict[str, int] = {}
        for note_path, failed_modules in self.metadata_errors.items():
            for module_name in failed_modules:
                module_error_counts[module_name] = module_error_counts.get(module_name, 0) + 1
        return module_error_counts
