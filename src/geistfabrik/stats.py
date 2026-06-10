"""Statistics and vault health checking for GeistFabrik.

This module provides comprehensive vault statistics including:
- Basic counts (notes, tags, links)
- Graph structure metrics (orphans, hubs, density)
- Semantic metrics (clusters, diversity, intrinsic dimensionality)
- Temporal analysis (drift rates, evolving concepts)
- Configuration status
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class StatsCollector:
    """Collects statistics from a GeistFabrik vault."""

    def __init__(self, vault: Any, config: Any, history_days: int = 30):
        """Initialise stats collector.

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
        # Optimised with LEFT JOIN instead of NOT IN subqueries (5-10x faster)
        cursor = self.db.execute(
            """
            SELECT COUNT(*)
            FROM notes n
            LEFT JOIN links l1 ON l1.source_path = n.path
            LEFT JOIN links l2 ON (
                l2.target = n.path
                OR l2.target = n.title
                OR l2.target || '.md' = n.path
            )
            WHERE l1.source_path IS NULL
              AND l2.target IS NULL
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
        from geistfabrik.default_geists import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS

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
            SELECT n.path, n.title
            FROM notes n
            LEFT JOIN links l1 ON l1.source_path = n.path
            LEFT JOIN links l2 ON (
                l2.target = n.path
                OR l2.target = n.title
                OR l2.target || '.md' = n.path
            )
            WHERE l1.source_path IS NULL
              AND l2.target IS NULL
            ORDER BY n.title
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
            logger.debug(
                "Failed to parse date for drift comparison",
                exc_info=True,
            )
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
        # Use dict lookup instead of list.index() for O(N) instead of O(N²)
        path_to_idx = {p: i for i, p in enumerate(curr_paths)}
        curr_aligned = np.vstack([curr_emb[path_to_idx[p]] for p in common_paths])
        past_aligned = np.vstack([past_emb_dict[p] for p in common_paths])

        # Align past embeddings to current via Procrustes
        try:
            rotation_matrix, _ = orthogonal_procrustes(past_aligned, curr_aligned)
            past_rotated = past_aligned @ rotation_matrix
        except Exception:
            # Procrustes can fail
            logger.debug("Procrustes alignment failed", exc_info=True)
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
            logger.debug("Failed to compute drift trend", exc_info=True)

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
