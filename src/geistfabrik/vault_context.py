"""VaultContext - Rich execution context for geists."""

import logging
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    overload,
)

import numpy as np

from .clustering_analysis import Cluster, format_cluster_label
from .config import TOTAL_DIM
from .embeddings import Session, cosine_similarity
from .models import Link, Note, link_target_forms
from .vault import Vault
from .voice_analysis import VoiceMetadata, compute_voice, compute_voice_metadata

logger = logging.getLogger(__name__)

# Markdown checkbox tasks: "- [ ] open" / "- [x] done" (also * and + bullets)
_TASK_PATTERN = re.compile(r"^\s*[-*+]\s+\[[ xX]\]", re.MULTILINE)
_COMPLETED_TASK_PATTERN = re.compile(r"^\s*[-*+]\s+\[[xX]\]", re.MULTILINE)

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


@dataclass
class ChurnResult:
    """Result of neighbour churn analysis for a single note.

    Attributes:
        churn: 1 - Jaccard(old neighbours, new neighbours), in [0, 1]
        departed: Neighbour paths present then, absent now (sorted)
        arrived: Neighbour paths absent then, present now (sorted)
    """

    churn: float
    departed: list[str]
    arrived: list[str]


def _normalise_rows(matrix: np.ndarray) -> np.ndarray:
    """Row-normalise a matrix to unit vectors, leaving zero rows as zeros.

    Args:
        matrix: (N, d) array

    Returns:
        (N, d) array with each non-zero row scaled to unit norm
    """
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    result: np.ndarray = matrix / norms
    return result


def _jaccard_churn(old: set[str], new: set[str]) -> float:
    """Compute Jaccard churn between two neighbour sets.

    churn = 1 - |old ∩ new| / |old ∪ new|, defined as 0.0 when both
    sets are empty. Symmetric, and always in [0, 1].

    Args:
        old: Historical neighbour paths
        new: Current neighbour paths

    Returns:
        Churn value in [0.0, 1.0]
    """
    union = old | new
    if not union:
        return 0.0
    return 1.0 - len(old & new) / len(union)


def _topk_neighbour_sets(
    matrix: np.ndarray, paths: list[str], k: int, block_size: int = 1024
) -> dict[str, set[str]]:
    """Compute top-k cosine neighbour path sets for every row of a matrix.

    Uses blocked matrix multiplication (block_size rows at a time) so peak
    memory stays bounded at roughly block_size × N floats, followed by
    np.argpartition for O(N) top-k selection per row. Self-similarity is
    masked out, and k is capped at N - 1.

    Args:
        matrix: (N, d) embedding matrix; row i corresponds to paths[i]
        paths: Note paths, one per matrix row
        k: Number of neighbours per note
        block_size: Rows per block (memory/speed trade-off)

    Returns:
        Dictionary mapping each path to the set of its top-k neighbour paths
    """
    n = matrix.shape[0]
    if n == 0 or k <= 0:
        return {path: set() for path in paths}

    k_eff = min(k, n - 1)
    if k_eff <= 0:
        return {path: set() for path in paths}

    normalised = _normalise_rows(matrix.astype(np.float64))

    result: dict[str, set[str]] = {}
    for start in range(0, n, block_size):
        end = min(start + block_size, n)
        sims = normalised[start:end] @ normalised.T
        # Mask self-similarity so a note is never its own neighbour
        sims[np.arange(end - start), np.arange(start, end)] = -np.inf
        topk_idx = np.argpartition(sims, -k_eff, axis=1)[:, -k_eff:]
        for offset in range(end - start):
            result[paths[start + offset]] = {paths[j] for j in topk_idx[offset]}

    return result


def _surprisal_blocked(
    embeddings: dict[str, np.ndarray], k_neighbours: int, block_size: int = 1024
) -> dict[str, float]:
    """Compute surprisal for all notes using blocked matrix operations.

    Surprisal = 1 - cosine(note, centroid of its k nearest neighbours).
    Same flop count as the naive version but runs as blocked BLAS matmuls
    rather than Python loops:

    1. E = row-normalised embedding matrix (paths in fixed sorted order)
    2. For each block of rows: S = E_block @ E.T (peak ~block_size × N)
    3. Mask self-similarity to -inf; top-k indices via np.argpartition
    4. centroid = mean of top-k rows, normalised (zero-norm guarded)
    5. surprisal = 1 - row · centroid, clipped to [0.0, 2.0]

    Args:
        embeddings: Mapping of note path to embedding vector
        k_neighbours: Number of nearest neighbours forming the centroid
        block_size: Rows per block (memory/speed trade-off)

    Returns:
        Mapping of note path to surprisal in [0.0, 2.0]; empty dict if
        fewer than k_neighbours + 1 notes are available
    """
    paths = sorted(embeddings)
    n = len(paths)
    if k_neighbours < 1 or n < k_neighbours + 1:
        return {}

    matrix = np.stack([np.asarray(embeddings[p], dtype=np.float64) for p in paths])
    normalised = _normalise_rows(matrix)

    scores: dict[str, float] = {}
    for start in range(0, n, block_size):
        end = min(start + block_size, n)
        block = normalised[start:end]
        sims = block @ normalised.T
        # Mask self-similarity so a note is never its own neighbour
        sims[np.arange(end - start), np.arange(start, end)] = -np.inf
        topk_idx = np.argpartition(sims, -k_neighbours, axis=1)[:, -k_neighbours:]

        # Centroids of top-k neighbours: (b, k, d) -> (b, d), then normalise
        centroids = normalised[topk_idx].mean(axis=1)
        centroid_norms = np.linalg.norm(centroids, axis=1, keepdims=True)
        centroid_norms = np.where(centroid_norms == 0, 1.0, centroid_norms)
        centroids = centroids / centroid_norms

        surprisal = 1.0 - np.einsum("ij,ij->i", block, centroids)
        surprisal = np.clip(surprisal, 0.0, 2.0)

        for offset in range(end - start):
            scores[paths[start + offset]] = float(surprisal[offset])

    return scores


def _surprisal_naive(embeddings: dict[str, np.ndarray], k_neighbours: int) -> dict[str, float]:
    """Readable reference implementation of surprisal (plain Python loops).

    Used by the differential test to define correctness for the blocked
    implementation (_surprisal_blocked). O(N²) Python-level work — do NOT
    use in production code.

    Args:
        embeddings: Mapping of note path to embedding vector
        k_neighbours: Number of nearest neighbours forming the centroid

    Returns:
        Mapping of note path to surprisal in [0.0, 2.0]; empty dict if
        fewer than k_neighbours + 1 notes are available
    """
    paths = sorted(embeddings)
    n = len(paths)
    if k_neighbours < 1 or n < k_neighbours + 1:
        return {}

    # Normalise each vector (zero vectors stay zero)
    normed: dict[str, np.ndarray] = {}
    for path in paths:
        vector = np.asarray(embeddings[path], dtype=np.float64)
        norm = float(np.linalg.norm(vector))
        normed[path] = vector / norm if norm > 0 else vector

    scores: dict[str, float] = {}
    for path in paths:
        # Rank all other notes by cosine similarity
        sims = []
        for other in paths:
            if other == path:
                continue
            sims.append((float(np.dot(normed[path], normed[other])), other))
        sims.sort(key=lambda pair: pair[0], reverse=True)
        top_paths = [other for _, other in sims[:k_neighbours]]

        # Centroid of the top-k neighbours, normalised (zero-norm guarded)
        centroid = np.mean([normed[other] for other in top_paths], axis=0)
        norm = float(np.linalg.norm(centroid))
        if norm > 0:
            centroid = centroid / norm

        surprisal = 1.0 - float(np.dot(normed[path], centroid))
        scores[path] = float(min(max(surprisal, 0.0), 2.0))

    return scores


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
        seed: int | None = None,
        metadata_loader: "MetadataLoader | None" = None,
        function_registry: "FunctionRegistry | None" = None,
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
        self._functions: dict[str, Callable[..., Any]] = {}
        self._function_registry = function_registry

        # Cache for notes (performance optimisation)
        self._notes_cache: list[Note] | None = None

        # Cache for metadata
        self._metadata_cache: dict[str, dict[str, Any]] = {}

        # Cache for clusters (performance optimisation - keyed by min_size)
        self._clusters_cache: dict[int, dict[int, Cluster]] = {}

        # Cache for similarity scores (performance optimisation - keyed by note path pair)
        self._similarity_cache: dict[tuple[str, str], float] = {}

        # Cache for neighbours (keyed by (note_path, count, return_scores))
        self._neighbours_cache: dict[
            tuple[str, int, bool], list[Note] | list[tuple[Note, float]]
        ] = {}

        # Cache for backlinks (performance optimisation - keyed by note_path)
        self._backlinks_cache: dict[str, list[Note]] = {}

        # Cache for outgoing_links (performance optimisation - keyed by note_path)
        self._outgoing_links_cache: dict[str, list[Note]] = {}

        # Cache for graph_neighbours (performance optimisation - keyed by note_path)
        self._graph_neighbours_cache: dict[str, list[Note]] = {}

        # Cache for read() content (OPTIMISATION #2 - session-scoped)
        self._read_cache: dict[str, str] = {}

        # Cache for surprisal scores (session-scoped - keyed by k_neighbours)
        self._surprisal_cache: dict[int, dict[str, float]] = {}

        # Cache for neighbour churn (session-scoped - keyed by (since_days, k))
        self._churn_cache: dict[tuple[int, int], dict[str, ChurnResult]] = {}

        # Cache for typed voice metadata (session-scoped - keyed by note path)
        self._voice_cache: dict[str, VoiceMetadata] = {}

        # Metadata loader for extensible metadata inference
        self._metadata_loader = metadata_loader

        # Track metadata inference errors
        self.metadata_errors: dict[str, list[str]] = {}  # note_path -> list of failed module names

        # Vector search backend (delegated from session)
        self._backend = session.get_backend()

        # Session embeddings loaded once and cached for the session
        cursor = vault.db.execute(
            """
            SELECT note_path, embedding FROM session_embeddings
            WHERE session_id = ?
            """,
            (session.session_id,),
        )
        self._embeddings: dict[str, np.ndarray] = {}
        for row in cursor.fetchall():
            note_path, embedding_bytes = row
            self._embeddings[note_path] = np.frombuffer(embedding_bytes, dtype=np.float32)

    # Direct vault access (delegated)

    def notes(self) -> list[Note]:
        """Get all notes in vault (cached).

        Performance optimisation: Notes are loaded once and cached
        for the duration of the VaultContext session.

        Returns:
            List of all notes
        """
        if self._notes_cache is None:
            self._notes_cache = self.vault.all_notes()
        return self._notes_cache

    def notes_excluding_journal(self) -> list[Note]:
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

    def get_note(self, path: str) -> Note | None:
        """Get specific note by path.

        Args:
            path: Note path

        Returns:
            Note or None if not found
        """
        return self.vault.get_note(path)

    def get_embedding(self, path: str) -> np.ndarray | None:
        """Get the embedding vector for a note by path.

        Args:
            path: Note path

        Returns:
            Embedding array or None if not found. The array is a READ-ONLY
            view over the cached buffer (np.frombuffer) shared with every
            other caller this session - in-place mutation raises ValueError
            by design. Call .copy() if you need a writable array.
        """
        return self._embeddings.get(path)

    def get_all_embeddings(self) -> dict[str, np.ndarray]:
        """Get all session embeddings as a path-to-embedding dictionary.

        Returns:
            Dictionary mapping note paths to embedding arrays. The arrays are
            READ-ONLY views shared with every other caller this session (see
            get_embedding); call .copy() before mutating.
        """
        return self._embeddings

    def resolve_link_target(self, target: str) -> Note | None:
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
        self, note: Note, count: int = 10, return_scores: Literal[False] = False
    ) -> list[Note]: ...

    @overload
    def neighbours(
        self, note: Note, count: int = 10, *, return_scores: Literal[True]
    ) -> list[tuple[Note, float]]: ...

    def neighbours(
        self, note: Note, count: int = 10, return_scores: bool = False
    ) -> list[Note] | list[tuple[Note, float]]:
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
        cache_key = (note.path, count, return_scores)

        # Check cache first
        if cache_key in self._neighbours_cache:
            return self._neighbours_cache[cache_key]

        # Get embedding for query note
        try:
            query_embedding = self._backend.get_embedding(note.path)
        except KeyError:
            return [] if not return_scores else []

        # Find similar notes (request k+1 to exclude self)
        similar = self._backend.find_similar(query_embedding, count=count + 1)

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
                if len(result) >= count:
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
        cache_key: tuple[str, str] = (sorted_paths[0], sorted_paths[1])

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

    def batch_similarity(self, notes_a: list[Note], notes_b: list[Note]) -> np.ndarray:
        """Calculate semantic similarity between two sets of notes (cache-aware).

        Computes all pairwise similarities between notes_a and notes_b using
        vectorised matrix operations. Now integrates with the session-scoped
        similarity cache for best performance in all scenarios.

        Performance characteristics:
        - 100% cache hits: O(N×M) dict lookups (~1-2ms for 100 pairs)
        - 0% cache hits: Same as before (vectorized batch computation)
        - Mixed hits: Batch compute all, then cache for subsequent calls

        OPTIMISATION #3: Use this instead of nested similarity() calls:

        Before (O(N×M) individual calls):
            for a in notes_a:
                for b in notes_b:
                    sim = vault.similarity(a, b)

        After (O(1) batch operation, cache-aware):
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

        # Phase 1: Check cache for all pairs
        result = np.zeros((len(notes_a), len(notes_b)))
        needs_computation = np.ones((len(notes_a), len(notes_b)), dtype=bool)

        for i, note_a in enumerate(notes_a):
            for j, note_b in enumerate(notes_b):
                # Create order-independent cache key (same as similarity())
                sorted_paths = sorted([note_a.path, note_b.path])
                cache_key: tuple[str, str] = (sorted_paths[0], sorted_paths[1])

                if cache_key in self._similarity_cache:
                    result[i, j] = self._similarity_cache[cache_key]
                    needs_computation[i, j] = False

        # If fully cached, return immediately (fast path)
        if not needs_computation.any():
            return result

        # Phase 2: Batch compute all pairs (existing implementation)
        # Note: We compute ALL pairs even if some cached, because vectorized
        # matrix operations are most efficient when done as single operation
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
        similarity_matrix = np.clip(similarity_matrix, 0.0, 1.0)

        # Phase 3: Populate cache for newly computed pairs
        for i in range(len(notes_a)):
            for j in range(len(notes_b)):
                if needs_computation[i, j]:
                    result[i, j] = similarity_matrix[i, j]

                    # Cache this pair for future use
                    sorted_paths = sorted([notes_a[i].path, notes_b[j].path])
                    cache_key_store: tuple[str, str] = (sorted_paths[0], sorted_paths[1])
                    self._similarity_cache[cache_key_store] = similarity_matrix[i, j]

        return result

    # Graph operations

    def backlinks(self, note: Note) -> list[Note]:
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

    def outgoing_links(self, note: Note) -> list[Note]:
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

    def orphans(self, count: int | None = None) -> list[Note]:
        """Find notes with no outgoing or incoming links.

        Builds the linked-note sets once, then set-checks each note: O(N + M).
        (The previous LEFT-JOIN formulation was O(N x M) - its OR-join on
        l2.target is not sargable, so SQLite scanned the full links index for
        every note, and the composite index added for it went unused.)

        Args:
            k: Maximum number to return. If None, return all.

        Returns:
            List of orphan notes, most recently modified first
        """
        # One pass over links: notes with outgoing links, and every link
        # target in the forms links may use (exact path, bare title, or
        # path without the .md extension - checked per-note below).
        sources = {row[0] for row in self.db.execute("SELECT DISTINCT source_path FROM links")}
        targets = {row[0] for row in self.db.execute("SELECT DISTINCT target FROM links")}

        cursor = self.db.execute("SELECT path, title FROM notes ORDER BY modified DESC")

        result: list[Note] = []
        for path, title in cursor.fetchall():
            if path in sources:
                continue
            # Canonical link-target resolution (single source of truth)
            if link_target_forms(path, title) & targets:
                continue
            note = self.get_note(path)
            if note is not None:
                result.append(note)
                if count is not None and len(result) >= count:
                    break

        return result

    def hubs(self, count: int = 10) -> list[Note]:
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
            (count,),
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

    def notes_grouped_by_creation_date(
        self, min_per_day: int = 1, exclude_journal: bool = True
    ) -> dict[str, list[Note]]:
        """Group notes by creation date.

        Provides temporal aggregation without exposing SQL implementation.
        Use this instead of direct database queries for grouping notes by date.

        Args:
            min_per_day: Minimum notes per day to include in results
            exclude_journal: If True, exclude "geist journal/" notes (default)

        Returns:
            Dictionary mapping date strings (YYYY-MM-DD) to lists of notes
            created on that date, sorted by note count descending
        """
        journal_filter = "WHERE NOT path LIKE 'geist journal/%'" if exclude_journal else ""

        cursor = self.db.execute(
            f"""
            SELECT DATE(created) as creation_date,
                   GROUP_CONCAT(path, char(31)) as note_paths
            FROM notes
            {journal_filter}
            GROUP BY DATE(created)
            HAVING COUNT(*) >= ?
            ORDER BY COUNT(*) DESC
            """,
            (min_per_day,),
        )

        result: dict[str, list[Note]] = {}
        for row in cursor.fetchall():
            date_str, paths_str = row
            if paths_str:
                paths = paths_str.split("\x1f")
                # Batch load notes for efficiency
                notes_map = self.vault.get_notes_batch(paths)
                # Preserve order and filter out None
                notes: list[Note] = []
                for p in paths:
                    note = notes_map.get(p)
                    if note is not None:
                        notes.append(note)
                if notes:
                    result[date_str] = notes

        return result

    def session_count(self) -> int:
        """Get the number of sessions recorded for this vault.

        Returns:
            Number of sessions
        """
        cursor = self.db.execute("SELECT COUNT(*) FROM sessions")
        result = cursor.fetchone()
        return result[0] if result else 0

    def session_dates_for_note(self, note: Note) -> list[str]:
        """Get session dates when a note had embeddings computed.

        Args:
            note: Note to look up

        Returns:
            List of date strings (YYYY-MM-DD) in ascending order
        """
        cursor = self.db.execute(
            """
            SELECT s.date
            FROM session_embeddings se
            JOIN sessions s ON se.session_id = s.session_id
            WHERE se.note_path = ?
            ORDER BY s.date ASC
            """,
            (note.path,),
        )
        dates: list[str] = []
        for row in cursor.fetchall():
            val = row[0]
            if hasattr(val, "strftime"):
                dates.append(val.strftime("%Y-%m-%d"))
            else:
                dates.append(str(val))
        return dates

    def session_embeddings_by_session(
        self,
    ) -> list[tuple[int, str, list[Any]]]:
        """Get embeddings grouped by session for temporal analysis.

        Returns:
            List of (session_id, date_str, embeddings) tuples
            ordered by date DESC, limited to 5 most recent sessions.
        """
        cursor = self.db.execute(
            """
            SELECT session_id, date FROM sessions
            ORDER BY date DESC
            LIMIT 5
            """
        )
        sessions = cursor.fetchall()

        result_list: list[tuple[int, str, list[Any]]] = []
        for session_id, session_date in sessions:
            emb_cursor = self.db.execute(
                """
                SELECT embedding FROM session_embeddings
                WHERE session_id = ?
                """,
                (session_id,),
            )
            embeddings = [np.frombuffer(row[0], dtype=np.float32) for row in emb_cursor.fetchall()]
            if hasattr(session_date, "strftime"):
                date_str = session_date.strftime("%Y-%m")
            else:
                date_str = str(session_date)
            result_list.append((session_id, date_str, embeddings))

        return result_list

    def persist_cluster_labels(self, assignments: dict[str, str]) -> None:
        """Record this session's cluster assignment for each note.

        Stores the label on the note's session_embeddings row so future
        sessions can compare assignments over time (the data that
        previous_cluster_label_for_note() reads and cluster_evolution_tracker
        builds on). Notes not present in `assignments` (noise/unclustered)
        keep a NULL label. Called automatically when clusters are computed.

        Args:
            assignments: Mapping of note path -> cluster label for the
                current session
        """
        if not assignments:
            return
        self.db.executemany(
            """
            UPDATE session_embeddings SET cluster_label = ?
            WHERE session_id = ? AND note_path = ?
            """,
            [(label, self.session.session_id, path) for path, label in assignments.items()],
        )
        self.db.commit()

    def previous_cluster_label_for_note(self, note: Note, session_id: int) -> str | None:
        """Get the cluster label for a note in a previous session.

        Args:
            note: Note to look up
            session_id: The session ID to check

        Returns:
            Cluster label string or None if not found
        """
        row = self.db.execute(
            """
            SELECT cluster_label
            FROM session_embeddings
            WHERE session_id = ? AND note_path = ?
            """,
            (session_id, note.path),
        ).fetchone()
        return row[0] if row and row[0] else None

    def recent_session_ids(self, count: int = 3) -> list[int]:
        """Get the most recent session IDs.

        Args:
            limit: Maximum number of session IDs to return

        Returns:
            List of session IDs ordered by date descending
        """
        cursor = self.db.execute(
            """
            SELECT session_id FROM sessions
            ORDER BY date DESC
            LIMIT ?
            """,
            (count,),
        )
        return [row[0] for row in cursor.fetchall()]

    def get_clusters(self, min_size: int = 5) -> dict[int, Cluster]:
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
            empty_result: dict[int, Cluster] = {}
            self._clusters_cache[min_size] = empty_result
            return empty_result

        from . import cluster_labeling

        # Use cached session embeddings instead of re-querying DB
        embeddings_dict = self._embeddings

        if len(embeddings_dict) < min_size * 2:  # Need at least 2 clusters worth
            empty_result_2: dict[int, Cluster] = {}
            self._clusters_cache[min_size] = empty_result_2
            return empty_result_2

        paths = list(embeddings_dict.keys())
        embeddings_array = np.array([embeddings_dict[p] for p in paths])

        # Run HDBSCAN clustering
        clusterer = HDBSCAN(min_cluster_size=min_size, min_samples=3)
        labels = clusterer.fit_predict(embeddings_array)

        # Group notes by cluster
        clusters: dict[int, list[Note]] = {}
        cluster_paths: dict[int, list[str]] = {}

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
            empty_result_3: dict[int, Cluster] = {}
            self._clusters_cache[min_size] = empty_result_3
            return empty_result_3

        # Generate labels using cluster_labeling module (single source of truth)
        labeling_method = self.vault.config.clustering.labeling_method
        n_terms = self.vault.config.clustering.n_label_terms

        if labeling_method == "keybert":
            cluster_labels_raw = cluster_labeling.label_keybert(
                paths, labels, self.db, n_terms=n_terms
            )
        else:  # Default to tfidf
            cluster_labels_raw = cluster_labeling.label_tfidf(
                paths, labels, self.db, n_terms=n_terms
            )

        # Build result with formatted labels and centroids
        result: dict[int, Cluster] = {}

        for cluster_id, notes in clusters.items():
            # Get embeddings for this cluster
            cluster_embeddings_arr = np.array(
                [embeddings_dict[path] for path in cluster_paths[cluster_id]]
            )

            # Calculate centroid (mean of embeddings)
            centroid = np.mean(cluster_embeddings_arr, axis=0)

            # Format label as phrase
            keyword_label = cluster_labels_raw.get(cluster_id, f"Cluster {cluster_id}")
            formatted_label = format_cluster_label(keyword_label)

            result[cluster_id] = Cluster(
                cluster_id=cluster_id,
                label=keyword_label,
                formatted_label=formatted_label,
                notes=notes,
                size=len(notes),
                centroid=centroid,
            )

        # Persist this session's assignments so future sessions can compare
        # cluster membership over time (cluster_evolution_tracker).
        self.persist_cluster_labels(
            {
                path: result[cluster_id].label
                for cluster_id in result
                for path in cluster_paths[cluster_id]
            }
        )

        # Cache result for this session
        self._clusters_cache[min_size] = result

        return result

    def get_cluster_representatives(
        self,
        cluster_id: int,
        count: int = 3,
        clusters: dict[int, Cluster] | None = None,
    ) -> list[Note]:
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
        centroid = cluster.centroid
        notes = cluster.notes

        # Use cached session embeddings instead of re-querying DB
        similarities = []

        for note in notes:
            note_embedding = self._embeddings.get(note.path)
            if note_embedding is not None:
                sim = cosine_similarity(centroid, note_embedding)
                similarities.append((note, sim))

        # Sort by similarity descending, return top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [note for note, _ in similarities[:count]]

    def unlinked_pairs(
        self, count: int = 10, candidate_limit: int = 200
    ) -> list[tuple[Note, Note]]:
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
            recent = self.recent_notes(count=candidate_limit // 2)
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
        return [(a, b) for a, b, _ in pairs[:count]]

    def links_between(self, a: Note, b: Note) -> list[Link]:
        """Find all links between two notes (bidirectional).

        Args:
            a: First note
            b: Second note

        Returns:
            List of links between the notes
        """

        # Canonical link-target resolution (single source of truth)
        a_forms = a.link_target_forms()
        b_forms = b.link_target_forms()

        # Check a -> b
        links_ab = [link for link in a.links if link.target in b_forms]

        # Check b -> a
        links_ba = [link for link in b.links if link.target in a_forms]

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

    def graph_neighbours(self, note: Note) -> list[Note]:
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
        if note.path in self._graph_neighbours_cache:
            return self._graph_neighbours_cache[note.path]

        neighbours = set()

        # Add outgoing link targets (now cached)
        for target in self.outgoing_links(note):
            neighbours.add(target)

        # Add incoming link sources (now cached)
        for source in self.backlinks(note):
            neighbours.add(source)

        result = list(neighbours)

        # Cache the result
        self._graph_neighbours_cache[note.path] = result
        return result

    # Temporal queries

    def old_notes(self, count: int = 10) -> list[Note]:
        """Find least recently modified notes.

        Args:
            k: Number of notes to return

        Returns:
            List of old notes, sorted by modification time ascending
        """
        cursor = self.db.execute("SELECT path FROM notes ORDER BY modified ASC LIMIT ?", (count,))

        result = []
        for row in cursor.fetchall():
            note = self.get_note(row[0])
            if note is not None:
                result.append(note)

        return result

    def recent_notes(self, count: int = 10) -> list[Note]:
        """Find most recently modified notes.

        Args:
            k: Number of notes to return

        Returns:
            List of recent notes, sorted by modification time descending
        """
        cursor = self.db.execute("SELECT path FROM notes ORDER BY modified DESC LIMIT ?", (count,))

        result = []
        for row in cursor.fetchall():
            note = self.get_note(row[0])
            if note is not None:
                result.append(note)

        return result

    # Reflective lens analysis

    def surprisal_scores(self, k_neighbours: int = 10) -> dict[str, float]:
        """Surprisal = 1 - cosine(note, centroid of its k nearest neighbours).

        How unexpected is each note given its own semantic neighbourhood?
        Values lie in [0, 2] (cosine ∈ [-1, 1]); in practice [0, 1].

        Computed for ALL notes in one vectorised pass and session-cached,
        so every geist and vault function shares the result.

        Algorithm (O(N²·d) flops, but as blocked BLAS matmuls, NOT a
        Python loop):

        1. E = row-normalised embedding matrix (paths in sorted order)
        2. For each 1024-row block B: S_B = E[B] @ E.T
        3. Top-k neighbour indices per row via np.argpartition
        4. centroid_i = normalise(mean(E[topk_i]));
           surprisal_i = 1 - E[i] · centroid_i, clipped to [0.0, 2.0]

        Args:
            k_neighbours: Number of nearest neighbours forming the centroid

        Returns:
            Mapping of note path to surprisal score; empty dict when the
            vault has fewer than k_neighbours + 1 embedded notes (surprisal
            is meaningless in a near-empty vault)
        """
        if k_neighbours in self._surprisal_cache:
            return self._surprisal_cache[k_neighbours]

        scores = _surprisal_blocked(self._embeddings, k_neighbours)
        self._surprisal_cache[k_neighbours] = scores
        return scores

    def neighbour_churn(self, since_days: int = 180, k: int = 10) -> dict[str, ChurnResult]:
        """Jaccard churn between each note's current semantic neighbours and
        its neighbours as of the nearest session at or before
        (session date - since_days).

        Graceful degradation:

        - No session that old → falls back to the OLDEST available session,
          but only if it is at least 30 days older than the current session;
          otherwise returns {} (geists then return []).
        - The historical session is never the current session itself.
        - Only notes embedded in BOTH epochs receive a ChurnResult.

        Implementation:

        1. ONE bulk SELECT loads the historical session's embeddings —
           never per-note queries
        2. Two blocked top-k passes (shared helper with surprisal_scores),
           one per epoch
        3. Set-based Jaccard per note (O(k) each):
           churn = 1 - |old ∩ new| / |old ∪ new| (0.0 if both empty)

        Session-cached per (since_days, k).

        Args:
            since_days: How far back to look for the historical session
            k: Number of neighbours per note in each epoch

        Returns:
            Mapping of note path to ChurnResult for notes present in both
            epochs; empty dict when no suitable historical session exists
        """
        cache_key = (since_days, k)
        if cache_key in self._churn_cache:
            return self._churn_cache[cache_key]

        result = self._compute_neighbour_churn(since_days, k)
        self._churn_cache[cache_key] = result
        return result

    def _compute_neighbour_churn(self, since_days: int, k: int) -> dict[str, ChurnResult]:
        """Compute neighbour churn against a historical session (uncached).

        Args:
            since_days: How far back to look for the historical session
            k: Number of neighbours per note in each epoch

        Returns:
            Mapping of note path to ChurnResult (see neighbour_churn)
        """
        current_date = self.session.date
        cutoff = (current_date - timedelta(days=since_days)).strftime("%Y-%m-%d")

        row = self.db.execute(
            """
            SELECT session_id, date FROM sessions
            WHERE date <= ?
            ORDER BY date DESC
            LIMIT 1
            """,
            (cutoff,),
        ).fetchone()

        if row is None:
            # Fallback: oldest session, but only if >= 30 days older than
            # the current session date
            row = self.db.execute(
                "SELECT session_id, date FROM sessions ORDER BY date ASC LIMIT 1"
            ).fetchone()
            if row is None:
                return {}
            min_age_cutoff = (current_date - timedelta(days=30)).strftime("%Y-%m-%d")
            if str(row[1]) > min_age_cutoff:
                return {}

        historical_session_id = int(row[0])
        # Never compare the current session against itself
        if historical_session_id == self.session.session_id:
            return {}

        # ONE bulk SELECT of the historical session's embeddings
        cursor = self.db.execute(
            """
            SELECT note_path, embedding FROM session_embeddings
            WHERE session_id = ?
            """,
            (historical_session_id,),
        )
        historical: dict[str, np.ndarray] = {}
        for note_path, embedding_bytes in cursor.fetchall():
            historical[note_path] = np.frombuffer(embedding_bytes, dtype=np.float32)

        if not historical or not self._embeddings:
            return {}

        # Top-k neighbour path sets per epoch (same blocked helper)
        old_paths = sorted(historical)
        old_matrix = np.stack([historical[p] for p in old_paths])
        old_sets = _topk_neighbour_sets(old_matrix, old_paths, k)

        new_paths = sorted(self._embeddings)
        new_matrix = np.stack([self._embeddings[p] for p in new_paths])
        new_sets = _topk_neighbour_sets(new_matrix, new_paths, k)

        # Jaccard churn for notes present in BOTH epochs
        result: dict[str, ChurnResult] = {}
        for path in sorted(old_sets.keys() & new_sets.keys()):
            old_neighbours = old_sets[path]
            new_neighbours = new_sets[path]
            result[path] = ChurnResult(
                churn=_jaccard_churn(old_neighbours, new_neighbours),
                departed=sorted(old_neighbours - new_neighbours),
                arrived=sorted(new_neighbours - old_neighbours),
            )

        return result

    # Metadata access

    def metadata(self, note: Note) -> dict[str, Any]:
        """Retrieve all inferred metadata for a note.

        Args:
            note: Note to get metadata for

        Returns:
            Dictionary of metadata properties
        """
        if note.path in self._metadata_cache:
            return self._metadata_cache[note.path]

        # Built-in metadata. "Now" is the session date, not wall-clock, so
        # --date replays stay deterministic (same date + vault = same output).
        session_now = self.session.date
        words = note.content.split()
        word_count = len(words)
        days_since_modified = max(0, (session_now - note.modified).days)
        task_count = len(_TASK_PATTERN.findall(note.content))
        completed_task_count = len(_COMPLETED_TASK_PATTERN.findall(note.content))
        metadata = {
            "word_count": word_count,
            "link_count": len(note.links),
            "tag_count": len(note.tags),
            "age_days": max(0, (session_now - note.created).days),
            "days_since_modified": days_since_modified,
            # 0 (fresh) -> 1 (stale); asymptotic: 30d=0.5, 90d=0.75, 365d~0.92.
            # Same curve as examples/metadata_inference/temporal.py, which can
            # still override these keys via enabled_modules.
            "staleness": round(1 - (1 / (1 + days_since_modified / 30)), 3),
            "has_tasks": task_count > 0,
            "task_count": task_count,
            "completed_task_count": completed_task_count,
            "lexical_diversity": (
                round(len({w.lower() for w in words}) / word_count, 3) if word_count else 0.0
            ),
            "reading_time": round(word_count / 200.0, 2),  # minutes at ~200 wpm
        }

        # Merge in linguistic voice metadata (computed lazily per note,
        # cached via the same session-scoped metadata cache). Built-in keys
        # take precedence: both layers compute a lexical_diversity, and
        # metadata_driven_discovery's thresholds are tuned to the built-in.
        for key, value in compute_voice_metadata(note.content).items():
            metadata.setdefault(key, value)

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

    def voice(self, note: Note) -> VoiceMetadata:
        """Get typed linguistic voice properties for a note.

        Returns a VoiceMetadata dataclass with typed fields for temporal
        orientation, pronoun patterns, hedging, and structural features.
        Session-cached for performance.

        Use this instead of metadata()["temporal_orientation"] etc. for
        type-safe access with IDE autocompletion and mypy checking.

        Args:
            note: Note to analyse

        Returns:
            VoiceMetadata dataclass with all voice properties
        """
        if note.path in self._voice_cache:
            return self._voice_cache[note.path]

        voice = compute_voice(note.content)
        self._voice_cache[note.path] = voice
        return voice

    # Deterministic sampling

    def sample(self, items: list[Any], count: int) -> list[Any]:
        """Deterministically sample k items.

        Args:
            items: List to sample from
            k: Number of items to sample

        Returns:
            Sample of k items (or fewer if list is smaller)
        """
        if count >= len(items):
            return list(items)

        return self.rng.sample(items, count)

    def random_notes(self, count: int = 1) -> list[Note]:
        """Sample k random notes.

        Args:
            k: Number of notes to sample

        Returns:
            Random sample of notes
        """
        notes = self.notes()
        return self.sample(notes, count)

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

        return self._functions[name](self, *args, **kwargs)

    def list_functions(self) -> list[str]:
        """List all registered function names.

        Includes functions from the attached FunctionRegistry (builtins and
        user vault functions) as well as locally registered ones. Previously
        only the local dict was consulted, so this returned [] whenever a
        registry was attached - i.e. always, in production.

        Returns:
            Sorted list of function names
        """
        names = set(self._functions.keys())
        if self._function_registry is not None:
            names.update(self._function_registry.functions.keys())
        return sorted(names)

    def get_metadata_error_summary(self) -> dict[str, int]:
        """Get summary of metadata inference errors.

        Returns:
            Dictionary mapping module names to count of notes where they failed
        """
        module_error_counts: dict[str, int] = {}
        for note_path, failed_modules in self.metadata_errors.items():
            for module_name in failed_modules:
                module_error_counts[module_name] = module_error_counts.get(module_name, 0) + 1
        return module_error_counts
