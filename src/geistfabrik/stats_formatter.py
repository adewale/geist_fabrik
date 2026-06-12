"""Statistics formatting and recommendations for GeistFabrik.

Extracted from stats.py to reduce module size. Handles text and JSON
output formatting for vault statistics, plus recommendation generation.
"""

import json
from typing import Any

import numpy as np

from .stats import VaultStats


class StatsFormatter:
    """Formats statistics for output."""

    def __init__(
        self, stats: VaultStats, recommendations: list[dict[str, Any]], verbose: bool = False
    ):
        """Initialise formatter.

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


def generate_recommendations(stats: VaultStats) -> list[dict[str, Any]]:
    """Generate recommendations based on statistics.

    Args:
        stats: Collected statistics

    Returns:
        List of recommendation dictionaries
    """
    recommendations: list[dict[str, Any]] = []

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
        rec: dict[str, str | None] = {
            "type": "health",
            "severity": "success",
            "message": "All checks passed - vault structure is healthy",
            "action": None,
        }
        recommendations.append(rec)

    return recommendations
