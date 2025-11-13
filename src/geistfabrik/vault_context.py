"""VaultContext - Rich execution context for geists."""

import logging
import random
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    overload,
)

import numpy as np

from .config import TOTAL_DIM
from .embeddings import Session, cosine_similarity
from .models import Link, Note
from .vault import Vault

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .function_registry import FunctionRegistry
    from .metadata_system import MetadataLoader


def _clip_similarity(score: float) -> float:
    """Clip similarity score to valid [0, 1] range.

    Handles floating-point precision errors that can cause scores slightly
    outside the valid range due to numpy/sklearn version differences.

    Args:
        score: Raw similarity score

    Returns:
        Clipped score in [0.0, 1.0] range
    """
    return max(0.0, min(1.0, score))


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
        """Initialise vault context.

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

        # Cache for notes (performance optimisation)
        self._notes_cache: Optional[List[Note]] = None

        # Cache for metadata
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}

        # Cache for clusters (performance optimisation - keyed by min_size)
        self._clusters_cache: Dict[int, Dict[int, Dict[str, Any]]] = {}

        # Cache for similarity scores (performance optimisation - keyed by note path pair)
        self._similarity_cache: Dict[Tuple[str, str], float] = {}

        # Cache for neighbours (performance optimisation - keyed by (note_path, k))
        self._neighbours_cache: Dict[
            Tuple[str, int, bool], Union[List[Note], List[Tuple[Note, float]]]
        ] = {}

        # Cache for backlinks (performance optimisation - keyed by note_path)
        self._backlinks_cache: Dict[str, List[Note]] = {}

        # Cache for outgoing_links (performance optimisation - keyed by note_path)
        self._outgoing_links_cache: Dict[str, List[Note]] = {}

        # Cache for graph_neighbors (performance optimisation - keyed by note_path)
        self._graph_neighbors_cache: Dict[str, List[Note]] = {}

        # Cache for read() content (OPTIMISATION #2 - session-scoped)
        self._read_cache: Dict[str, str] = {}

        # Metadata loader for extensible metadata inference
        self._metadata_loader = metadata_loader

        # Track metadata inference errors
        self.metadata_errors: Dict[str, List[str]] = {}  # note_path -> list of failed module names

        # Vector search backend (delegated from session)
        self._backend = session.get_backend()

        # Keep backward-compatible embeddings dict for compatibility
        # (Some code may still access self._embeddings directly)
        cursor = vault.db.execute(
            """
            SELECT note_path, embedding FROM session_embeddings
            WHERE session_id = ?
            """,
            (session.session_id,),
        )
        self._embeddings = {}
        for row in cursor.fetchall():
            note_path, embedding_bytes = row
            self._embeddings[note_path] = np.frombuffer(embedding_bytes, dtype=np.float32)

    # Direct vault access (delegated)

    def notes(self) -> List[Note]:
        """Get all notes in vault (cached).

        Performance optimisation: Notes are loaded once and cached
        for the duration of the VaultContext session.

        Returns:
            List of all notes
        """
        if self._notes_cache is None:
            self._notes_cache = self.vault.all_notes()
        return self._notes_cache

    def notes_excluding_journal(self) -> List[Note]:
        """Get all notes except geist journal entries.

        Convenience method for geists that analyze vault history.
        Geist journal notes are ephemeral session output and should
        typically be excluded from historical analysis to avoid:
        - Circular references (analyzing system output as user notes)
        - Statistical skew (session notes have different characteristics)
        - False patterns (journal structure is predictable)

        When to use:
        - Analyzing vault history or temporal patterns
        - Computing statistical distributions
        - Tracking note evolution over time
        - Building cohort analysis

        When NOT to use:
        - Point-in-time content analysis (pattern extraction)
        - Semantic similarity queries (no risk of circular reference)
        - Single-note operations

        Returns:
            List of notes excluding those in "geist journal/" directory
        """
        return [n for n in self.notes() if not n.path.startswith("geist journal/")]

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
        # Check cache first (OPTIMISATION #2 - session-scoped)
        if note.path in self._read_cache:
            return self._read_cache[note.path]

        # Get content and cache it
        content = note.content
        self._read_cache[note.path] = content
        return content

    # Semantic search

    @overload
    def neighbours(
        self, note: Note, k: int = 10, return_scores: Literal[False] = False
    ) -> List[Note]: ...

    @overload
    def neighbours(
        self, note: Note, k: int = 10, *, return_scores: Literal[True]
    ) -> List[Tuple[Note, float]]: ...

    def neighbours(
        self, note: Note, k: int = 10, return_scores: bool = False
    ) -> Union[List[Note], List[Tuple[Note, float]]]:
        """Find k semantically similar notes, optionally with similarity scores.

        Uses session-scoped caching for performance. Many geists query neighbours
        for the same notes (e.g., hub notes, recently modified notes), so caching
        eliminates redundant vector searches across all geists in a session.

        Performance: return_scores=True avoids recomputing similarities that were
        already computed during the neighbour search (OP-9).

        Args:
            note: Query note
            k: Number of neighbours to return
            return_scores: If True, return (Note, score) tuples; if False, just Notes

        Returns:
            List of similar notes, or list of (note, score) tuples, sorted by
            similarity descending
        """
        # Create cache key (note path + k parameter + return_scores flag)
        cache_key = (note.path, k, return_scores)

        # Check cache first
        if cache_key in self._neighbours_cache:
            return self._neighbours_cache[cache_key]

        # Get embedding for query note
        try:
            query_embedding = self._backend.get_embedding(note.path)
        except KeyError:
            return [] if not return_scores else []

        # Find similar notes (request k+1 to exclude self)
        similar = self._backend.find_similar(query_embedding, k=k + 1)

        # Convert paths to notes using batch loading (OP-6)
        # Collect paths first (excluding self)
        paths_to_load = []
        path_score_map = {}
        for path, score in similar:
            if path != note.path:
                paths_to_load.append(path)
                # Clip score to [0, 1] range (handle floating-point precision errors)
                path_score_map[path] = _clip_similarity(score)

        # Batch load all notes at once
        notes_map = self.vault.get_notes_batch(paths_to_load)

        # Build results in order, preserving similarity ranking
        result = []
        result_with_scores = []
        for path in paths_to_load:
            similar_note = notes_map.get(path)
            if similar_note is not None:
                result.append(similar_note)
                result_with_scores.append((similar_note, path_score_map[path]))
                if len(result) >= k:
                    break

        # Cache and return based on return_scores flag
        if return_scores:
            self._neighbours_cache[cache_key] = result_with_scores
            return result_with_scores
        else:
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
            # Clip to [0, 1] range (handle floating-point precision errors)
            similarity_score = _clip_similarity(similarity_score)
        except KeyError:
            similarity_score = 0.0

        self._similarity_cache[cache_key] = similarity_score
        return similarity_score

    def batch_similarity(self, notes_a: List[Note], notes_b: List[Note]) -> np.ndarray:
        """Calculate semantic similarity between two sets of notes (vectorised).

        Computes all pairwise similarities between notes_a and notes_b using
        vectorised matrix operations for 10-100× speedup compared to nested loops.

        OPTIMISATION #3: Use this instead of nested similarity() calls:

        Before (O(N×M) individual calls):
            for a in notes_a:
                for b in notes_b:
                    sim = vault.similarity(a, b)

        After (O(1) batch operation):
            similarities = vault.batch_similarity(notes_a, notes_b)
            # similarities[i, j] = similarity between notes_a[i] and notes_b[j]

        Args:
            notes_a: First set of notes
            notes_b: Second set of notes

        Returns:
            Matrix of shape (len(notes_a), len(notes_b)) where element [i, j]
            is the cosine similarity between notes_a[i] and notes_b[j]
        """
        if not notes_a or not notes_b:
            return np.array([]).reshape(0, 0)

        # Get embeddings for all notes
        embeddings_a = []
        embeddings_b = []

        for note in notes_a:
            try:
                emb = self._backend.get_embedding(note.path)
                embeddings_a.append(emb)
            except KeyError:
                # Note not found, use zero vector
                embeddings_a.append(np.zeros(TOTAL_DIM))  # 384 + 3 temporal features

        for note in notes_b:
            try:
                emb = self._backend.get_embedding(note.path)
                embeddings_b.append(emb)
            except KeyError:
                # Note not found, use zero vector
                embeddings_b.append(np.zeros(TOTAL_DIM))

        # Stack into matrices: (n, d) and (m, d)
        matrix_a = np.stack(embeddings_a)  # shape: (len(notes_a), 387)
        matrix_b = np.stack(embeddings_b)  # shape: (len(notes_b), 387)

        # Normalise rows to unit vectors for cosine similarity
        # ||a|| = sqrt(sum(a^2)) for each row
        norms_a = np.linalg.norm(matrix_a, axis=1, keepdims=True)
        norms_b = np.linalg.norm(matrix_b, axis=1, keepdims=True)

        # Avoid division by zero
        norms_a = np.where(norms_a == 0, 1, norms_a)
        norms_b = np.where(norms_b == 0, 1, norms_b)

        matrix_a_normalised = matrix_a / norms_a
        matrix_b_normalised = matrix_b / norms_b

        # Compute cosine similarity matrix: A @ B.T
        # Result shape: (len(notes_a), len(notes_b))
        similarity_matrix = matrix_a_normalised @ matrix_b_normalised.T

        # Clip to [0, 1] range (numerical errors can cause slight overshoot)
        clipped: np.ndarray = np.clip(similarity_matrix, 0.0, 1.0)

        return clipped

    # Graph operations

    def backlinks(self, note: Note) -> List[Note]:
        """Find notes that link to this note (cached).

        Uses session-scoped caching for performance. Many geists query backlinks
        for the same notes (e.g., hub notes, recently modified notes), so caching
        eliminates redundant database queries across all geists in a session.

        Args:
            note: Target note

        Returns:
            List of notes with links to target
        """
        # Check cache first
        if note.path in self._backlinks_cache:
            return self._backlinks_cache[note.path]

        # Need to match target as: path, path without extension, or title
        path_without_ext = note.path.rsplit(".", 1)[0] if "." in note.path else note.path

        cursor = self.db.execute(
            """
            SELECT DISTINCT source_path FROM links
            WHERE target = ? OR target = ? OR target = ?
            """,
            (note.path, path_without_ext, note.title),
        )

        # Collect all source paths, then batch load (OP-6)
        source_paths = [row[0] for row in cursor.fetchall()]
        notes_map = self.vault.get_notes_batch(source_paths)

        # Build result list, preserving order
        result = []
        for path in source_paths:
            source = notes_map.get(path)
            if source is not None:
                result.append(source)

        # Cache the result
        self._backlinks_cache[note.path] = result
        return result

    def outgoing_links(self, note: Note) -> List[Note]:
        """Find notes that this note links to (cached outgoing links).

        Symmetric counterpart to backlinks(). Returns resolved Note objects
        for all outgoing links from this note.

        Uses session-scoped caching for performance. Link resolution requires
        multiple database queries per link, and many geists traverse the graph
        repeatedly, so caching eliminates redundant resolution work.

        Args:
            note: Source note

        Returns:
            List of notes that this note links to
        """
        # Check cache first
        if note.path in self._outgoing_links_cache:
            return self._outgoing_links_cache[note.path]

        result = []
        for link in note.links:
            target = self.resolve_link_target(link.target)
            if target is not None:
                result.append(target)

        # Cache the result
        self._outgoing_links_cache[note.path] = result
        return result

    def orphans(self, k: Optional[int] = None) -> List[Note]:
        """Find notes with no outgoing or incoming links.

        Performance optimised with LEFT JOINs instead of NOT IN subqueries.

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
        """Find most-linked-to notes using optimised SQL query.

        Performance optimised (OP-8): Uses JOIN to resolve link targets in SQL
        rather than fetching k×3 candidates and resolving in Python. This is
        15-25% faster and eliminates redundant database queries.

        Args:
            k: Number of hubs to return

        Returns:
            List of hub notes, sorted by link count descending
        """
        cursor = self.db.execute(
            """
            SELECT n.path, COUNT(DISTINCT l.source_path) as link_count
            FROM links l
            JOIN notes n ON (
                n.path = l.target
                OR n.path = l.target || '.md'
                OR n.title = l.target
            )
            GROUP BY n.path
            ORDER BY link_count DESC
            LIMIT ?
            """,
            (k,),
        )

        # Collect all paths, then batch load (OP-6)
        hub_paths = [row[0] for row in cursor.fetchall()]
        notes_map = self.vault.get_notes_batch(hub_paths)

        # Build result list, preserving order
        result = []
        for path in hub_paths:
            note = notes_map.get(path)
            if note is not None:
                result.append(note)

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
        cursor = self.vault.db.execute(
            """
            SELECT note_path, embedding FROM session_embeddings
            WHERE session_id = ?
            """,
            (self.session.session_id,),
        )
        embeddings_dict = {}
        for row in cursor.fetchall():
            note_path, embedding_bytes = row
            embeddings_dict[note_path] = np.frombuffer(embedding_bytes, dtype=np.float32)

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

        metrics_computer = EmbeddingMetricsComputer(self.db, self.vault.config)

        # Choose labelling method based on config
        labeling_method = self.vault.config.clustering.labeling_method
        n_terms = self.vault.config.clustering.n_label_terms

        if labeling_method == "keybert":
            cluster_labels_raw = metrics_computer._label_clusters_keybert(
                paths, labels, n_terms=n_terms
            )
        else:  # Default to tfidf
            cluster_labels_raw = metrics_computer._label_clusters_tfidf(
                paths, labels, n_terms=n_terms
            )

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
        cursor = self.vault.db.execute(
            """
            SELECT note_path, embedding FROM session_embeddings
            WHERE session_id = ?
            """,
            (self.session.session_id,),
        )
        embeddings_dict = {}
        for row in cursor.fetchall():
            note_path, embedding_bytes = row
            embeddings_dict[note_path] = np.frombuffer(embedding_bytes, dtype=np.float32)

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

        Performance optimised: Uses vectorised numpy matrix multiplication to compute
        all pairwise similarities at once, rather than nested loops. This is 10-50x
        faster than the loop-based approach, especially for large vaults.

        Args:
            k: Number of pairs to return
            candidate_limit: Maximum number of notes to consider (to avoid O(n²) on large vaults)

        Returns:
            List of (note_a, note_b) tuples sorted by similarity
        """
        all_notes = self.notes()

        # Optimise for large vaults by limiting candidate set
        if len(all_notes) > candidate_limit:
            # Sample a diverse set: recent notes + random notes
            recent = self.recent_notes(k=candidate_limit // 2)
            # Use set for O(1) membership check instead of O(N) list membership
            recent_set = set(recent)
            remaining = [n for n in all_notes if n not in recent_set]
            random_notes = self.sample(remaining, min(candidate_limit // 2, len(remaining)))
            notes = recent + random_notes
        else:
            notes = all_notes

        # Build valid notes + embeddings arrays
        valid_notes = []
        embeddings_list = []

        for note in notes:
            embedding = self._embeddings.get(note.path)
            if embedding is not None:
                valid_notes.append(note)
                embeddings_list.append(embedding)

        if len(valid_notes) < 2:
            return []

        # Vectorised: Compute all pairwise similarities at once
        embeddings_matrix = np.array(embeddings_list)

        # Matrix multiplication: X @ X^T gives all dot products
        similarity_matrix = np.dot(embeddings_matrix, embeddings_matrix.T)

        # Normalise to get cosine similarities
        norms = np.linalg.norm(embeddings_matrix, axis=1)
        similarity_matrix = similarity_matrix / np.outer(norms, norms)

        # Extract high-similarity pairs (upper triangle only, threshold > 0.5)
        pairs = []
        n = len(valid_notes)

        for i in range(n):
            for j in range(i + 1, n):
                sim = similarity_matrix[i, j]

                # Early threshold filter
                if sim <= 0.5:
                    continue

                note_a, note_b = valid_notes[i], valid_notes[j]

                # Check if linked (this is now the main bottleneck)
                if self.links_between(note_a, note_b):
                    continue

                pairs.append((note_a, note_b, sim))

        # Sort by similarity descending, return top k
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
        """Get all notes connected to this note by links (cached, bidirectional).

        Returns notes that:
        - This note links to (outgoing links)
        - Link to this note (incoming links / backlinks)

        Uses session-scoped caching for performance. Now that backlinks() and
        outgoing_links() are cached, this method benefits from their caching
        and adds its own layer to avoid recomputing the union.

        Args:
            note: Query note

        Returns:
            List of connected notes (no duplicates)
        """
        # Check cache first
        if note.path in self._graph_neighbors_cache:
            return self._graph_neighbors_cache[note.path]

        neighbours = set()

        # Add outgoing link targets (now cached)
        for target in self.outgoing_links(note):
            neighbours.add(target)

        # Add incoming link sources (now cached)
        for source in self.backlinks(note):
            neighbours.add(source)

        result = list(neighbours)

        # Cache the result
        self._graph_neighbors_cache[note.path] = result
        return result

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
