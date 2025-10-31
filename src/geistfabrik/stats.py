"""Statistics and vault health checking for GeistFabrik.

This module provides comprehensive vault statistics including:
- Basic counts (notes, tags, links)
- Graph structure metrics (orphans, hubs, density)
- Semantic metrics (clusters, diversity, intrinsic dimensionality)
- Temporal analysis (drift rates, evolving concepts)
- Configuration status
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Optional dependencies for advanced metrics
try:
    from sklearn.cluster import HDBSCAN  # type: ignore[import-untyped]
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]
    from sklearn.metrics import silhouette_score  # type: ignore[import-untyped]

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from skdim.id import TwoNN  # type: ignore

    HAS_SKDIM = True
except ImportError:
    HAS_SKDIM = False

try:
    from vendi_score import vendi  # type: ignore

    HAS_VENDI = True
except ImportError:
    HAS_VENDI = False


class StatsCollector:
    """Collects statistics from a GeistFabrik vault."""

    def __init__(self, vault: Any, config: Any, history_days: int = 30):
        """Initialize stats collector.

        Args:
            vault: Vault instance
            config: Configuration object
            history_days: Days of session history to analyze
        """
        self.vault = vault
        self.config = config
        self.history_days = history_days
        self.db = vault.db

        # Collected stats
        self.stats: Dict[str, Any] = {}
        self._collect_basic_stats()

    def _collect_basic_stats(self) -> None:
        """Collect basic statistics from database."""
        # Vault overview
        db_path = Path(self.db.execute("PRAGMA database_list").fetchone()[2])
        self.stats["vault"] = {
            "path": str(self.vault.vault_path),
            "database_size_mb": db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0,
            "last_sync": self._get_last_sync(),
            "config_path": str(self.vault.vault_path / "_geistfabrik" / "config.yaml"),
            "vector_backend": self.config.vector_search.backend,
        }

        # Note statistics
        self.stats["notes"] = self._collect_note_stats()

        # Tag statistics
        self.stats["tags"] = self._collect_tag_stats()

        # Link statistics
        self.stats["links"] = self._collect_link_stats()

        # Graph structure
        self.stats["graph"] = self._collect_graph_stats()

        # Session history
        self.stats["sessions"] = self._collect_session_stats()

        # Geist configuration
        self.stats["geists"] = self._collect_geist_stats()

    def _get_last_sync(self) -> str:
        """Get timestamp of last vault sync."""
        cursor = self.db.execute("SELECT MAX(file_mtime) FROM notes")
        row = cursor.fetchone()
        if row and row[0]:
            return datetime.fromtimestamp(row[0]).isoformat()
        return "Unknown"

    def _collect_note_stats(self) -> Dict[str, Any]:
        """Collect note-level statistics."""
        # Total notes
        total = self.db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]

        # Regular vs virtual
        regular = self.db.execute("SELECT COUNT(*) FROM notes WHERE is_virtual = 0").fetchone()[0]
        virtual = self.db.execute("SELECT COUNT(*) FROM notes WHERE is_virtual = 1").fetchone()[0]

        # Virtual note sources
        cursor = self.db.execute(
            """
            SELECT source_file, COUNT(*)
            FROM notes
            WHERE is_virtual = 1
            GROUP BY source_file
            """
        )
        virtual_sources = {row[0]: row[1] for row in cursor.fetchall() if row[0]}

        # Note ages
        cursor = self.db.execute(
            """
            SELECT
                AVG(julianday('now') - julianday(created)) as avg_age,
                MAX(modified) as most_recent,
                MIN(created) as oldest
            FROM notes
            """
        )
        row = cursor.fetchone()
        avg_age = row[0] if row[0] else 0
        most_recent = row[1] if row[1] else "Unknown"
        oldest = row[2] if row[2] else "Unknown"

        return {
            "total": total,
            "regular": regular,
            "virtual": virtual,
            "virtual_pct": (virtual / total * 100) if total > 0 else 0,
            "virtual_sources": virtual_sources,
            "average_age_days": round(avg_age, 1),
            "most_recent": most_recent,
            "oldest": oldest,
        }

    def _collect_tag_stats(self) -> Dict[str, Any]:
        """Collect tag statistics."""
        # Unique tags
        unique = self.db.execute("SELECT COUNT(DISTINCT tag) FROM tags").fetchone()[0]

        # Total tag instances
        total = self.db.execute("SELECT COUNT(*) FROM tags").fetchone()[0]

        # Average tags per note
        note_count = self.stats["notes"]["total"]
        avg_per_note = total / note_count if note_count > 0 else 0

        # Top tags
        cursor = self.db.execute(
            """
            SELECT tag, COUNT(*) as cnt
            FROM tags
            GROUP BY tag
            ORDER BY cnt DESC
            LIMIT 10
            """
        )
        top_tags = [{"tag": row[0], "count": row[1]} for row in cursor.fetchall()]

        return {
            "unique": unique,
            "total_instances": total,
            "average_per_note": round(avg_per_note, 2),
            "top_tags": top_tags,
        }

    def _collect_link_stats(self) -> Dict[str, Any]:
        """Collect link statistics."""
        # Total links
        total = self.db.execute("SELECT COUNT(*) FROM links").fetchone()[0]

        # Average links per note
        note_count = self.stats["notes"]["total"]
        avg_per_note = total / note_count if note_count > 0 else 0

        # Bidirectional links (links where reverse link exists)
        cursor = self.db.execute(
            """
            SELECT COUNT(DISTINCT l1.source_path || '|' || l1.target)
            FROM links l1
            INNER JOIN links l2
                ON l1.source_path = l2.target
                AND l1.target = l2.source_path
            """
        )
        bidirectional = cursor.fetchone()[0]
        bidirectional_pct = (bidirectional / total * 100) if total > 0 else 0

        return {
            "total": total,
            "average_per_note": round(avg_per_note, 1),
            "bidirectional": bidirectional,
            "bidirectional_pct": round(bidirectional_pct, 1),
        }

    def _collect_graph_stats(self) -> Dict[str, Any]:
        """Collect graph structure statistics."""
        note_count = self.stats["notes"]["total"]

        # Orphans: notes with no incoming or outgoing links
        cursor = self.db.execute(
            """
            SELECT COUNT(*)
            FROM notes
            WHERE path NOT IN (SELECT DISTINCT source_path FROM links)
              AND path NOT IN (SELECT DISTINCT target FROM links)
            """
        )
        orphans = cursor.fetchone()[0]
        orphan_pct = (orphans / note_count * 100) if note_count > 0 else 0

        # Hubs: notes with >= 10 connections (outgoing)
        cursor = self.db.execute(
            """
            SELECT source_path
            FROM links
            GROUP BY source_path
            HAVING COUNT(*) >= 10
            """
        )
        hubs = len(cursor.fetchall())

        # Graph density
        possible_links = note_count * (note_count - 1)
        actual_links = self.stats["links"]["total"]
        density = actual_links / possible_links if possible_links > 0 else 0

        # Largest connected component (simplified: notes with at least one link)
        cursor = self.db.execute(
            """
            SELECT COUNT(DISTINCT path)
            FROM notes
            WHERE path IN (SELECT DISTINCT source_path FROM links)
               OR path IN (SELECT DISTINCT target FROM links)
            """
        )
        largest_component = cursor.fetchone()[0]
        largest_component_pct = (largest_component / note_count * 100) if note_count > 0 else 0

        return {
            "orphans": orphans,
            "orphan_pct": round(orphan_pct, 1),
            "hubs": hubs,
            "density": round(density, 4),
            "largest_component_size": largest_component,
            "largest_component_pct": round(largest_component_pct, 1),
        }

    def _collect_session_stats(self) -> Dict[str, Any]:
        """Collect session history statistics."""
        # Total sessions
        total = self.db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]

        if total == 0:
            return {
                "total": 0,
                "date_range": [],
                "average_interval_days": 0,
                "total_suggestions": 0,
                "average_suggestions_per_session": 0,
                "recent_sessions": [],
            }

        # Date range
        cursor = self.db.execute("SELECT MIN(date), MAX(date) FROM sessions")
        row = cursor.fetchone()
        date_range = [row[0], row[1]]

        # Average interval
        if total > 1:
            first_date = datetime.fromisoformat(date_range[0])
            last_date = datetime.fromisoformat(date_range[1])
            total_days = (last_date - first_date).days
            avg_interval = total_days / (total - 1)
        else:
            avg_interval = 0

        # Total suggestions
        cursor = self.db.execute("SELECT COUNT(*) FROM session_suggestions")
        total_suggestions = cursor.fetchone()[0]

        # Average suggestions per session
        avg_suggestions = total_suggestions / total if total > 0 else 0

        # Recent sessions
        cursor = self.db.execute(
            """
            SELECT
                ss.session_date,
                COUNT(*) as suggestion_count,
                COUNT(DISTINCT ss.geist_id) as active_geists
            FROM session_suggestions ss
            GROUP BY ss.session_date
            ORDER BY ss.session_date DESC
            LIMIT 5
            """
        )
        recent_sessions = [
            {"date": row[0], "suggestions": row[1], "active_geists": row[2]}
            for row in cursor.fetchall()
        ]

        return {
            "total": total,
            "date_range": date_range,
            "average_interval_days": round(avg_interval, 1),
            "total_suggestions": total_suggestions,
            "average_suggestions_per_session": round(avg_suggestions, 1),
            "recent_sessions": recent_sessions,
        }

    def _collect_geist_stats(self) -> Dict[str, Any]:
        """Collect geist configuration statistics."""
        # Count default geists
        from geistfabrik.config_loader import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS

        default_code_count = len(DEFAULT_CODE_GEISTS)
        default_tracery_count = len(DEFAULT_TRACERY_GEISTS)

        # Count custom geists
        custom_code_dir = self.vault.vault_path / "_geistfabrik" / "geists" / "code"
        custom_tracery_dir = self.vault.vault_path / "_geistfabrik" / "geists" / "tracery"

        custom_code_count = (
            len(list(custom_code_dir.glob("*.py"))) if custom_code_dir.exists() else 0
        )
        custom_tracery_count = (
            len(list(custom_tracery_dir.glob("*.yaml"))) if custom_tracery_dir.exists() else 0
        )

        # Count enabled/disabled from config
        enabled_count = sum(1 for v in self.config.default_geists.values() if v)
        disabled_count = len(self.config.default_geists) - enabled_count

        # Find disabled geists
        disabled_geists = [k for k, v in self.config.default_geists.items() if not v]

        return {
            "code_total": default_code_count,
            "code_enabled": enabled_count,  # Simplified: assume all enabled are code
            "code_disabled": disabled_count,
            "tracery_total": default_tracery_count,
            "tracery_enabled": default_tracery_count,  # Tracery geists always enabled
            "custom_code": custom_code_count,
            "custom_tracery": custom_tracery_count,
            "total_enabled": (
                enabled_count + default_tracery_count + custom_code_count + custom_tracery_count
            ),
            "disabled_geists": disabled_geists,
        }

    def get_top_linked_notes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top linked notes with incoming and outgoing counts.

        Args:
            limit: Maximum number of notes to return

        Returns:
            List of dicts with path, title, outgoing, incoming, total
        """
        # Get outgoing link counts
        cursor = self.db.execute(
            """
            SELECT n.path, n.title, COUNT(l.target) as outgoing
            FROM notes n
            LEFT JOIN links l ON n.path = l.source_path
            GROUP BY n.path
            """
        )
        outgoing_counts = {row[0]: {"title": row[1], "outgoing": row[2]} for row in cursor}

        # Get incoming link counts
        cursor = self.db.execute(
            """
            SELECT target, COUNT(*) as incoming
            FROM links
            GROUP BY target
            """
        )
        incoming_counts = {row[0]: row[1] for row in cursor}

        # Combine and calculate total
        all_notes = []
        for path, data in outgoing_counts.items():
            incoming = incoming_counts.get(path, 0)
            outgoing = data["outgoing"]
            total = incoming + outgoing

            all_notes.append(
                {
                    "path": path,
                    "title": data["title"],
                    "outgoing": outgoing,
                    "incoming": incoming,
                    "total": total,
                }
            )

        # Sort by total and return top N
        all_notes.sort(key=lambda x: x["total"], reverse=True)
        return all_notes[:limit]

    def get_orphan_notes(self) -> List[Dict[str, str]]:
        """Get list of orphan notes (no links in or out).

        Returns:
            List of dicts with path and title
        """
        cursor = self.db.execute(
            """
            SELECT path, title
            FROM notes
            WHERE path NOT IN (SELECT DISTINCT source_path FROM links)
              AND path NOT IN (SELECT DISTINCT target FROM links)
            ORDER BY title
            """
        )
        return [{"path": row[0], "title": row[1]} for row in cursor.fetchall()]

    def get_hub_notes(self, min_connections: int = 10) -> List[Dict[str, Any]]:
        """Get hub notes with high connection counts.

        Args:
            min_connections: Minimum total connections to qualify as hub

        Returns:
            List of dicts with path, title, total connections
        """
        top_notes = self.get_top_linked_notes(limit=100)
        return [note for note in top_notes if note["total"] >= min_connections]

    def has_embeddings(self) -> bool:
        """Check if embeddings exist for any session."""
        cursor = self.db.execute("SELECT COUNT(*) FROM session_embeddings LIMIT 1")
        row = cursor.fetchone()
        return row[0] > 0 if row else False

    def get_latest_embeddings(self) -> Optional[Tuple[str, np.ndarray, List[str]]]:
        """Get embeddings from most recent session.

        Returns:
            Tuple of (session_date, embeddings_array, note_paths) or None if no embeddings
        """
        if not self.has_embeddings():
            return None

        # Get most recent session with embeddings
        cursor = self.db.execute(
            """
            SELECT DISTINCT s.date
            FROM sessions s
            INNER JOIN session_embeddings se ON s.session_id = se.session_id
            ORDER BY s.date DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            return None

        session_date = row[0]

        # Get embeddings for this session
        cursor = self.db.execute(
            """
            SELECT se.note_path, se.embedding
            FROM session_embeddings se
            INNER JOIN sessions s ON se.session_id = s.session_id
            WHERE s.date = ?
            ORDER BY se.note_path
            """,
            (session_date,),
        )

        embeddings_list = []
        paths = []
        for row in cursor.fetchall():
            path, blob = row
            embedding = np.frombuffer(blob, dtype=np.float32)
            embeddings_list.append(embedding)
            paths.append(path)

        if not embeddings_list:
            return None

        embeddings = np.vstack(embeddings_list)
        return session_date, embeddings, paths

    def get_temporal_drift(
        self, current_date: str, days_back: int = 30
    ) -> Optional[Dict[str, Any]]:
        """Analyze temporal drift between current and historical embeddings.

        Args:
            current_date: Current session date (YYYY-MM-DD)
            days_back: How many days back to compare (default: 30)

        Returns:
            Dictionary with drift analysis or None if not enough data
        """
        from datetime import timedelta

        from scipy.linalg import orthogonal_procrustes  # type: ignore[import-untyped]

        # Get current embeddings
        current = self.get_latest_embeddings()
        if not current:
            return None

        curr_date, curr_emb, curr_paths = current

        # Find a past session approximately days_back ago
        try:
            target_date = (
                datetime.fromisoformat(curr_date) - timedelta(days=days_back)
            ).isoformat()[:10]
        except Exception:
            return None

        # Get closest past session
        cursor = self.db.execute(
            """
            SELECT s.date
            FROM sessions s
            WHERE s.date < ? AND EXISTS (
                SELECT 1 FROM session_embeddings se WHERE se.session_id = s.session_id
            )
            ORDER BY s.date DESC
            LIMIT 1
            """,
            (target_date,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        past_date = row[0]

        # Get past embeddings
        cursor = self.db.execute(
            """
            SELECT se.note_path, se.embedding
            FROM session_embeddings se
            INNER JOIN sessions s ON se.session_id = s.session_id
            WHERE s.date = ?
            ORDER BY se.note_path
            """,
            (past_date,),
        )

        past_emb_dict = {}
        for row in cursor.fetchall():
            path, blob = row
            embedding = np.frombuffer(blob, dtype=np.float32)
            past_emb_dict[path] = embedding

        # Find common notes
        common_paths = [p for p in curr_paths if p in past_emb_dict]
        if len(common_paths) < 5:
            return None  # Not enough overlap

        # Build aligned embedding matrices
        curr_aligned = np.vstack([curr_emb[curr_paths.index(p)] for p in common_paths])
        past_aligned = np.vstack([past_emb_dict[p] for p in common_paths])

        # Align past embeddings to current via Procrustes
        try:
            rotation_matrix, _ = orthogonal_procrustes(past_aligned, curr_aligned)
            past_rotated = past_aligned @ rotation_matrix
        except Exception:
            # Procrustes can fail
            past_rotated = past_aligned

        # Compute drift per note (1 - cosine similarity)
        from geistfabrik.embeddings import cosine_similarity

        drift_scores = []
        for i in range(len(common_paths)):
            sim = cosine_similarity(past_rotated[i], curr_aligned[i])
            drift = 1.0 - sim
            drift_scores.append((common_paths[i], drift))

        # Sort by drift
        drift_scores.sort(key=lambda x: x[1], reverse=True)

        # Compute statistics
        drifts = [d for _, d in drift_scores]
        avg_drift = float(np.mean(drifts))

        # Compare to previous period (if available) to detect acceleration
        drift_trend = "stable"
        try:
            earlier_date = (
                datetime.fromisoformat(past_date) - timedelta(days=days_back)
            ).isoformat()[:10]
            cursor = self.db.execute(
                """
                SELECT s.date
                FROM sessions s
                WHERE s.date < ? AND EXISTS (
                    SELECT 1 FROM session_embeddings se WHERE se.session_id = s.session_id
                )
                ORDER BY s.date DESC
                LIMIT 1
                """,
                (earlier_date,),
            )
            row = cursor.fetchone()
            if row:
                # Simplified: just check if current avg_drift is higher
                # Full implementation would compute drift for past period too
                drift_trend = "accelerating" if avg_drift > 0.2 else "stable"
        except Exception:
            pass

        return {
            "current_date": curr_date,
            "comparison_date": past_date,
            "days_elapsed": (
                datetime.fromisoformat(curr_date) - datetime.fromisoformat(past_date)
            ).days,
            "notes_compared": len(common_paths),
            "average_drift": round(avg_drift, 3),
            "drift_trend": drift_trend,
            "high_drift_notes": [
                {"title": path.replace(".md", ""), "drift": round(d, 2)}
                for path, d in drift_scores[:5]
            ],
            "stable_notes": [
                {"title": path.replace(".md", ""), "drift": round(d, 2)}
                for path, d in drift_scores[-5:]
            ],
        }

    def add_embedding_metrics(self, metrics: Dict[str, Any]) -> None:
        """Add computed embedding metrics to stats."""
        self.stats["embeddings"] = metrics

    def add_temporal_analysis(self, temporal: Dict[str, Any]) -> None:
        """Add temporal drift analysis to stats."""
        self.stats["temporal"] = temporal

    def add_verbose_details(self) -> None:
        """Add verbose details to stats for detailed output."""
        # Top linked notes
        self.stats["top_linked_notes"] = self.get_top_linked_notes(limit=10)

        # Orphan notes list
        self.stats["orphan_notes"] = self.get_orphan_notes()

        # Hub notes list
        self.stats["hub_notes"] = self.get_hub_notes(min_connections=10)


class EmbeddingMetricsComputer:
    """Computes advanced embedding-based metrics."""

    def __init__(self, db: sqlite3.Connection):
        """Initialize metrics computer.

        Args:
            db: SQLite database connection
        """
        self.db = db

    def compute_metrics(
        self,
        session_date: str,
        embeddings: np.ndarray,
        paths: List[str],
        force_recompute: bool = False,
    ) -> Dict[str, Any]:
        """Compute and cache embedding metrics.

        Args:
            session_date: Session date (YYYY-MM-DD)
            embeddings: Embedding matrix (n_notes, dim)
            paths: Note paths corresponding to embeddings
            force_recompute: Force recomputation even if cached

        Returns:
            Dictionary of computed metrics
        """
        # Check cache first
        if not force_recompute:
            cached = self._load_cached_metrics(session_date)
            if cached:
                # Always include dimension and n_notes from current embeddings
                # (these are not cached because they can change)
                cached["n_notes"] = len(embeddings)
                cached["dimension"] = embeddings.shape[1]
                cached["session_date"] = session_date
                return cached

        # Compute metrics
        metrics: Dict[str, Any] = {
            "session_date": session_date,
            "n_notes": len(embeddings),
            "dimension": embeddings.shape[1],
        }

        # Basic metrics (always available)
        metrics.update(self._compute_basic_metrics(embeddings))

        # Advanced metrics (require sklearn)
        if HAS_SKLEARN:
            metrics.update(self._compute_clustering_metrics(embeddings, paths))
        else:
            metrics["clustering_available"] = False

        # Cache results
        self._cache_metrics(session_date, metrics)

        return metrics

    def _load_cached_metrics(self, session_date: str) -> Optional[Dict[str, Any]]:
        """Load cached metrics from database."""
        cursor = self.db.execute(
            "SELECT * FROM embedding_metrics WHERE session_date = ?", (session_date,)
        )
        row = cursor.fetchone()

        if not row:
            return None

        # Convert row to dict
        columns = [desc[0] for desc in cursor.description]
        cached = dict(zip(columns, row))

        # Parse cluster_labels JSON and convert string keys back to int
        if cached.get("cluster_labels"):
            cluster_labels_raw = json.loads(cached["cluster_labels"])
            # JSON converts int keys to strings, convert them back
            cached["cluster_labels"] = {int(k): v for k, v in cluster_labels_raw.items()}

        # Ensure integer fields are actually integers (SQLite sometimes returns blobs)
        for key in ["n_clusters", "n_gaps"]:
            if key in cached and cached[key] is not None:
                try:
                    # Handle both regular ints and blobs (numpy int serialization)
                    if isinstance(cached[key], bytes):
                        # Blob from numpy int - use struct to unpack
                        import struct

                        cached[key] = struct.unpack("<q", cached[key])[0]  # little-endian int64
                    else:
                        cached[key] = int(cached[key])
                except (TypeError, ValueError, struct.error):
                    # If conversion fails, set to None rather than keeping invalid data
                    cached[key] = None

        return cached

    def _cache_metrics(self, session_date: str, metrics: Dict[str, Any]) -> None:
        """Cache computed metrics to database."""
        # Serialize cluster_labels to JSON (keys already converted to Python int)
        cluster_labels_json = json.dumps(metrics.get("cluster_labels", {}))

        # Convert numpy types to Python types for SQLite
        def to_python_type(val: Any) -> Any:
            if val is None:
                return None
            if isinstance(val, (np.integer, np.int64, np.int32)):
                return int(val)
            if isinstance(val, (np.floating, np.float64, np.float32)):
                return float(val)
            return val

        self.db.execute(
            """
            INSERT OR REPLACE INTO embedding_metrics
            (session_date, intrinsic_dim, vendi_score, shannon_entropy,
             silhouette_score, n_clusters, n_gaps, cluster_labels, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_date,
                to_python_type(metrics.get("intrinsic_dim")),
                to_python_type(metrics.get("vendi_score")),
                to_python_type(metrics.get("shannon_entropy")),
                to_python_type(metrics.get("silhouette_score")),
                to_python_type(metrics.get("n_clusters")),
                to_python_type(metrics.get("n_gaps")),
                cluster_labels_json,
                datetime.now().isoformat(),
            ),
        )
        self.db.commit()

    def _compute_basic_metrics(self, embeddings: np.ndarray) -> Dict[str, Any]:
        """Compute basic metrics that don't require external libraries."""
        metrics = {}

        # Intrinsic dimensionality (if available)
        if HAS_SKDIM and len(embeddings) >= 10:
            try:
                id_estimator = TwoNN()
                intrinsic_dim = id_estimator.fit_transform(embeddings)
                metrics["intrinsic_dim"] = round(float(intrinsic_dim), 1)
            except Exception:
                # TwoNN can fail on some data distributions
                pass

        # Vendi Score (if available)
        if HAS_VENDI and len(embeddings) >= 2:
            try:
                from sklearn.metrics.pairwise import (  # type: ignore[import-untyped]
                    cosine_similarity as sklearn_cosine,
                )

                # Compute similarity matrix for Vendi Score
                similarity_matrix = sklearn_cosine(embeddings)
                vendi_score_value = vendi.score_K(similarity_matrix)
                metrics["vendi_score"] = round(float(vendi_score_value), 1)
            except Exception:
                # Vendi computation can fail
                pass

        # IsoScore: measure of embedding space uniformity
        # Based on variance in the eigenvalues of the covariance matrix
        if len(embeddings) >= 10:
            try:
                # Compute covariance matrix
                cov_matrix = np.cov(embeddings.T)
                eigenvalues = np.linalg.eigvalsh(cov_matrix)
                eigenvalues = eigenvalues[eigenvalues > 1e-10]  # Filter near-zero

                if len(eigenvalues) > 0:
                    # IsoScore: normalize eigenvalues and compute entropy
                    eigenvalues_norm = eigenvalues / eigenvalues.sum()
                    entropy = -np.sum(eigenvalues_norm * np.log(eigenvalues_norm + 1e-10))
                    max_entropy = np.log(len(eigenvalues))
                    isoscore = entropy / max_entropy if max_entropy > 0 else 0
                    metrics["isoscore"] = round(float(isoscore), 2)
            except Exception:
                # Eigenvalue computation can fail
                pass

        # Basic similarity statistics
        from geistfabrik.embeddings import cosine_similarity

        # Sample for efficiency if large
        if len(embeddings) > 1000:
            indices = np.random.choice(len(embeddings), 1000, replace=False)
            sample_embeddings = embeddings[indices]
        else:
            sample_embeddings = embeddings

        # Compute similarity matrix
        similarities = []
        for i in range(len(sample_embeddings)):
            for j in range(i + 1, len(sample_embeddings)):
                sim = cosine_similarity(sample_embeddings[i], sample_embeddings[j])
                similarities.append(sim)

        if similarities:
            metrics["avg_similarity"] = float(np.mean(similarities))
            metrics["std_similarity"] = float(np.std(similarities))

        return metrics

    def _compute_clustering_metrics(
        self, embeddings: np.ndarray, paths: List[str]
    ) -> Dict[str, Any]:
        """Compute clustering-based metrics (requires sklearn)."""
        metrics: Dict[str, Any] = {}

        # Run HDBSCAN clustering
        clusterer = HDBSCAN(min_cluster_size=5, min_samples=3)
        labels = clusterer.fit_predict(embeddings)

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = np.sum(labels == -1)

        metrics["n_clusters"] = n_clusters
        metrics["n_gaps"] = n_noise
        metrics["gap_pct"] = round(n_noise / len(labels) * 100, 1) if len(labels) > 0 else 0

        # Silhouette score (only if we have clusters)
        if n_clusters > 1:
            # Filter out noise points for silhouette calculation
            mask = labels != -1
            if np.sum(mask) > 1:
                silhouette = silhouette_score(embeddings[mask], labels[mask])
                metrics["silhouette_score"] = round(float(silhouette), 3)

        # Shannon entropy of cluster distribution
        if n_clusters > 0:
            cluster_counts = np.bincount(labels[labels >= 0])
            cluster_dist = cluster_counts / cluster_counts.sum()
            shannon = -np.sum(cluster_dist * np.log2(cluster_dist + 1e-10))
            metrics["shannon_entropy"] = round(float(shannon), 2)

        # Label clusters using c-TF-IDF
        if n_clusters > 0:
            cluster_labels = self._label_clusters_tfidf(paths, labels)
            # Convert numpy.int64 keys to Python int for JSON serialization
            metrics["cluster_labels"] = {int(k): v for k, v in cluster_labels.items()}

        return metrics

    def _label_clusters_tfidf(
        self, paths: List[str], labels: np.ndarray, n_terms: int = 4
    ) -> Dict[int, str]:
        """Generate cluster labels using c-TF-IDF.

        Args:
            paths: Note paths
            labels: Cluster labels
            n_terms: Number of terms to use in label

        Returns:
            Dictionary mapping cluster_id to label string
        """
        cluster_labels = {}

        # Load note titles/content for each cluster
        clusters: Dict[int, List[str]] = {}
        for i, label in enumerate(labels):
            if label == -1:
                continue
            if label not in clusters:
                clusters[label] = []

            # Get note title from path
            path = paths[i]
            cursor = self.db.execute("SELECT title, content FROM notes WHERE path = ?", (path,))
            row = cursor.fetchone()
            if row:
                title, content = row
                # Use title + first 200 chars of content
                text = f"{title} {content[:200]}"
                clusters[label].append(text)

        if not clusters:
            return {}

        # Concatenate all text per cluster
        cluster_texts = {cid: " ".join(texts) for cid, texts in clusters.items()}

        # Compute TF-IDF
        vectorizer = TfidfVectorizer(max_features=100, stop_words="english", ngram_range=(1, 2))

        try:
            tfidf_matrix = vectorizer.fit_transform(cluster_texts.values())
            feature_names = vectorizer.get_feature_names_out()

            # Extract top terms per cluster
            for i, cluster_id in enumerate(cluster_texts.keys()):
                cluster_vector = tfidf_matrix[i].toarray()[0]
                top_indices = cluster_vector.argsort()[-n_terms:][::-1]
                top_terms = [feature_names[idx] for idx in top_indices]
                cluster_labels[cluster_id] = ", ".join(top_terms)
        except Exception:
            # If TF-IDF fails, use simple fallback
            for cluster_id in clusters.keys():
                cluster_labels[cluster_id] = f"Cluster {cluster_id}"

        return cluster_labels


class StatsFormatter:
    """Formats statistics for output."""

    def __init__(
        self, stats: Dict[str, Any], recommendations: List[Dict[str, Any]], verbose: bool = False
    ):
        """Initialize formatter.

        Args:
            stats: Collected statistics
            recommendations: Generated recommendations
            verbose: Include detailed output
        """
        self.stats = stats
        self.recommendations = recommendations
        self.verbose = verbose

    def format_text(self) -> str:
        """Format stats as human-readable text."""
        lines = []

        # Header
        lines.append("=" * 70)
        lines.append("GeistFabrik Vault Statistics")
        lines.append("=" * 70)

        # Vault overview
        vault = self.stats["vault"]
        lines.append(f"Vault: {vault['path']}")
        lines.append(f"Database: {vault['database_size_mb']:.2f} MB")
        lines.append(f"Last sync: {vault['last_sync']}")
        lines.append("")

        # Note statistics
        lines.append("Notes:")
        notes = self.stats["notes"]
        lines.append(f"  Total: {notes['total']} notes")
        lines.append(f"  Regular: {notes['regular']} ({100 - notes['virtual_pct']:.1f}%)")
        lines.append(f"  Virtual: {notes['virtual']} ({notes['virtual_pct']:.1f}%)")
        if notes["virtual_sources"]:
            lines.append(f"    From {len(notes['virtual_sources'])} date-collection files")
        lines.append(f"  Average age: {notes['average_age_days']:.0f} days")
        lines.append(f"  Most recent: {notes['most_recent']}")
        lines.append(f"  Oldest: {notes['oldest']}")

        # Verbose: Virtual notes by source
        if self.verbose and notes.get("virtual_sources"):
            lines.append("")
            lines.append("  Virtual Notes by Source:")
            for source, count in notes["virtual_sources"].items():
                lines.append(f"    {source} → {count} virtual entries")

        lines.append("")

        # Tag statistics
        lines.append("Tags:")
        tags = self.stats["tags"]
        lines.append(f"  Unique tags: {tags['unique']}")
        lines.append(f"  Total instances: {tags['total_instances']}")
        lines.append(f"  Average per note: {tags['average_per_note']:.2f}")
        if tags["top_tags"]:
            top_3 = tags["top_tags"][:3]
            tag_str = ", ".join([f"{t['tag']} ({t['count']})" for t in top_3])
            lines.append(f"  Most used: {tag_str}")

        # Verbose: Full tag distribution
        if self.verbose and tags.get("top_tags"):
            lines.append("")
            lines.append("  Tag Distribution:")
            for tag_info in tags["top_tags"]:
                pct = (
                    tag_info["count"] / self.stats["notes"]["total"] * 100
                    if self.stats["notes"]["total"] > 0
                    else 0
                )
                lines.append(f"    {tag_info['tag']}: {tag_info['count']} notes ({pct:.1f}%)")

        lines.append("")

        # Link statistics
        lines.append("Links:")
        links = self.stats["links"]
        lines.append(f"  Total: {links['total']}")
        lines.append(f"  Average per note: {links['average_per_note']:.1f}")
        lines.append(
            f"  Bidirectional: {links['bidirectional']} ({links['bidirectional_pct']:.1f}%)"
        )
        lines.append("")

        # Graph structure
        lines.append("Graph Structure:")
        graph = self.stats["graph"]
        lines.append(f"  Orphans: {graph['orphans']} ({graph['orphan_pct']:.1f}%)")
        lines.append(f"  Hubs (≥10 links): {graph['hubs']}")
        lines.append(f"  Density: {graph['density']:.4f}")
        lines.append(
            f"  Largest component: {graph['largest_component_size']} "
            f"({graph['largest_component_pct']:.1f}%)"
        )

        # Verbose: Top linked notes
        if self.verbose and "top_linked_notes" in self.stats:
            lines.append("")
            lines.append("  Top 10 Most Linked Notes:")
            for note in self.stats["top_linked_notes"]:
                lines.append(
                    f"    [[{note['title']}]] - "
                    f"{note['outgoing']} out, {note['incoming']} in ({note['total']} total)"
                )

        # Verbose: Orphan notes
        if self.verbose and "orphan_notes" in self.stats:
            orphans = self.stats["orphan_notes"]
            if orphans:
                lines.append("")
                lines.append(f"  Orphan Notes ({len(orphans)} total):")
                # Show first 10
                for note in orphans[:10]:
                    lines.append(f"    [[{note['title']}]]")
                if len(orphans) > 10:
                    lines.append(f"    ... and {len(orphans) - 10} more")

        # Verbose: Hub notes
        if self.verbose and "hub_notes" in self.stats:
            hubs = self.stats["hub_notes"]
            if hubs:
                lines.append("")
                lines.append("  Hub Notes (≥10 connections):")
                for note in hubs:
                    lines.append(f"    [[{note['title']}]] ({note['total']} connections)")

        lines.append("")

        # Embedding metrics (if available)
        if "embeddings" in self.stats:
            lines.append("Semantic Structure:")
            emb = self.stats["embeddings"]
            lines.append(f"  Dimension: {emb.get('dimension', 'N/A')}")
            if emb.get("n_clusters") is not None:
                lines.append(f"  Clusters detected: {emb['n_clusters']}")
            if emb.get("silhouette_score") is not None:
                lines.append(f"  Clustering quality: {emb['silhouette_score']:.2f}")
            if emb.get("shannon_entropy") is not None:
                lines.append(f"  Shannon entropy: {emb['shannon_entropy']:.2f} bits")
            if emb.get("n_gaps") is not None:
                lines.append(f"  Notes in gaps: {emb['n_gaps']} ({emb.get('gap_pct', 0):.1f}%)")

            if self.verbose and emb.get("cluster_labels"):
                lines.append("")
                lines.append("  Detected Clusters:")
                for cid, label in emb["cluster_labels"].items():
                    lines.append(f"    {cid}. {label}")

            lines.append("")

        # Session history
        sessions = self.stats["sessions"]
        if sessions["total"] > 0:
            lines.append("Sessions:")
            lines.append(f"  Total: {sessions['total']}")
            if sessions["date_range"]:
                lines.append(
                    f"  Date range: {sessions['date_range'][0]} to {sessions['date_range'][1]}"
                )
            lines.append(f"  Average interval: {sessions['average_interval_days']:.1f} days")
            lines.append(f"  Total suggestions: {sessions['total_suggestions']}")
            lines.append(
                f"  Average per session: {sessions['average_suggestions_per_session']:.1f}"
            )

            if sessions["recent_sessions"] and self.verbose:
                lines.append("")
                lines.append("  Recent sessions:")
                for s in sessions["recent_sessions"][:5]:
                    lines.append(
                        f"    {s['date']}: {s['suggestions']} suggestions "
                        f"({s['active_geists']} geists)"
                    )

            lines.append("")

        # Temporal drift analysis (if available)
        if "temporal" in self.stats:
            lines.append("Temporal Analysis:")
            temporal = self.stats["temporal"]
            lines.append(
                f"  Comparing: {temporal['current_date']} vs {temporal['comparison_date']}"
            )
            lines.append(f"  Days elapsed: {temporal['days_elapsed']}")
            lines.append(f"  Notes compared: {temporal['notes_compared']}")
            lines.append(f"  Average drift: {temporal['average_drift']:.3f}")
            lines.append(f"  Trend: {temporal['drift_trend']}")

            if self.verbose and temporal.get("high_drift_notes"):
                lines.append("")
                lines.append("  High-drift notes (evolving concepts):")
                for note in temporal["high_drift_notes"]:
                    lines.append(f"    [[{note['title']}]] - drift: {note['drift']:.2f}")

                lines.append("")
                lines.append("  Stable notes (unchanging meaning):")
                for note in temporal["stable_notes"]:
                    lines.append(f"    [[{note['title']}]] - drift: {note['drift']:.2f}")

            lines.append("")

        # Geist configuration
        lines.append("Geists:")
        geists = self.stats["geists"]
        lines.append(f"  Code geists: {geists['code_total']} ({geists['code_enabled']} enabled)")
        lines.append(
            f"  Tracery geists: {geists['tracery_total']} ({geists['tracery_enabled']} enabled)"
        )
        if geists["custom_code"] > 0 or geists["custom_tracery"] > 0:
            lines.append(f"  Custom geists: {geists['custom_code'] + geists['custom_tracery']}")
        lines.append(f"  Total enabled: {geists['total_enabled']}")

        if geists["disabled_geists"]:
            lines.append("")
            lines.append("  Disabled geists:")
            for gid in geists["disabled_geists"][:5]:
                lines.append(f"    - {gid}")

        lines.append("")

        # Recommendations
        if self.recommendations:
            lines.append("Recommendations:")
            lines.append("")
            for rec in self.recommendations:
                severity = rec["severity"]
                icon = "⚠" if severity == "warning" else "✓"
                lines.append(f"  {icon} {rec['type'].title()}")
                lines.append(f"    {rec['message']}")
                if rec.get("action"):
                    lines.append(f"    → {rec['action']}")
                lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)

    def format_json(self) -> str:
        """Format stats as JSON."""

        def convert_numpy(obj: Any) -> Any:
            """Convert numpy types to Python types for JSON serialization."""
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                # Convert both keys and values to handle numpy types in dictionary keys
                return {
                    (int(k) if isinstance(k, np.integer) else k): convert_numpy(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [convert_numpy(item) for item in obj]
            else:
                return obj

        output = {
            "vault": convert_numpy(self.stats["vault"]),
            "notes": convert_numpy(self.stats["notes"]),
            "tags": convert_numpy(self.stats["tags"]),
            "links": convert_numpy(self.stats["links"]),
            "graph": convert_numpy(self.stats["graph"]),
            "sessions": convert_numpy(self.stats["sessions"]),
            "geists": convert_numpy(self.stats["geists"]),
            "recommendations": convert_numpy(self.recommendations),
        }

        if "embeddings" in self.stats:
            output["embeddings"] = convert_numpy(self.stats["embeddings"])

        if "temporal" in self.stats:
            output["temporal"] = convert_numpy(self.stats["temporal"])

        return json.dumps(output, indent=2)


def generate_recommendations(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate recommendations based on statistics.

    Args:
        stats: Collected statistics

    Returns:
        List of recommendation dictionaries
    """
    recommendations = []

    # Backend recommendation
    notes = stats["notes"]["total"]
    backend = stats.get("vault", {}).get("vector_backend", "in-memory")

    if notes > 1000 and backend == "in-memory":
        recommendations.append(
            {
                "type": "performance",
                "severity": "warning",
                "message": f"Consider sqlite-vec backend for {notes} notes (5-6x faster queries)",
                "action": 'uv pip install -e ".[vector-search]" && update config.yaml',
            }
        )

    # Orphan alert
    graph = stats["graph"]
    if graph["orphan_pct"] > 10:
        recommendations.append(
            {
                "type": "structure",
                "severity": "warning",
                "message": (
                    f"{graph['orphans']} orphan notes ({graph['orphan_pct']:.1f}%) could be linked"
                ),
                "action": "geistfabrik invoke --geist orphan_connector",
            }
        )

    # Gap alert (if embeddings available)
    if "embeddings" in stats:
        emb = stats["embeddings"]
        if emb.get("gap_pct", 0) > 5:
            recommendations.append(
                {
                    "type": "structure",
                    "severity": "warning",
                    "message": f"{emb['n_gaps']} notes in semantic gaps (potential bridges)",
                    "action": "geistfabrik invoke --geist bridge_builder",
                }
            )

        # Diversity alerts
        vendi_score = emb.get("vendi_score")
        if vendi_score and vendi_score < notes * 0.3:
            recommendations.append(
                {
                    "type": "diversity",
                    "severity": "info",
                    "message": (
                        f"Low conceptual diversity (Vendi Score: {vendi_score:.1f}). "
                        "Consider exploring new topics."
                    ),
                    "action": "Review your reading/research sources for diversity",
                }
            )

        # Shannon entropy alert
        shannon = emb.get("shannon_entropy")
        if shannon and shannon < 1.5:
            recommendations.append(
                {
                    "type": "diversity",
                    "severity": "info",
                    "message": (
                        f"Notes are heavily concentrated in few clusters "
                        f"(entropy: {shannon:.2f}). Consider diversifying."
                    ),
                    "action": "Explore topics outside your main clusters",
                }
            )

    # Temporal drift alerts
    if "temporal" in stats:
        temporal = stats["temporal"]
        avg_drift = temporal.get("average_drift", 0)

        if avg_drift > 0.5:
            recommendations.append(
                {
                    "type": "temporal",
                    "severity": "warning",
                    "message": (
                        f"High semantic drift detected ({avg_drift:.2f}). "
                        "Many notes changing meaning rapidly."
                    ),
                    "action": "Review high-drift notes to ensure they remain coherent",
                }
            )
        elif avg_drift < 0.05:
            recommendations.append(
                {
                    "type": "temporal",
                    "severity": "info",
                    "message": (
                        f"Very low semantic drift ({avg_drift:.2f}). Vault may be stagnating."
                    ),
                    "action": "Consider revisiting and expanding older notes",
                }
            )

    # Disabled geist alert
    geists = stats["geists"]
    if geists["code_disabled"] > 0:
        recommendations.append(
            {
                "type": "configuration",
                "severity": "info",
                "message": f"{geists['code_disabled']} geists disabled in configuration",
                "action": "Review config.yaml to enable or test individually",
            }
        )

    # All clear if no recommendations
    if not recommendations:
        rec: Dict[str, Optional[str]] = {
            "type": "health",
            "severity": "success",
            "message": "All checks passed - vault structure is healthy",
            "action": None,
        }
        recommendations.append(rec)  # type: ignore[arg-type]

    return recommendations
