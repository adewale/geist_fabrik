"""Configuration loader for GeistFabrik.

This module handles loading and saving vault configuration from config.yaml.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml

# List of all default geists (for reference and validation)
DEFAULT_CODE_GEISTS = [
    "anachronism_detector",
    "antithesis_generator",
    "assumption_challenger",
    "blind_spot_detector",
    "bridge_builder",
    "bridge_hunter",
    "cluster_mirror",
    "columbo",
    "complexity_mismatch",
    "concept_cluster",
    "concept_drift",
    "congruence_mirror",
    "convergent_evolution",
    "creative_collision",
    "density_inversion",
    "dialectic_triad",
    "divergent_evolution",
    "hermeneutic_instability",
    "hidden_hub",
    "island_hopper",
    "link_density_analyser",
    "metadata_driven_discovery",
    "method_scrambler",
    "on_this_day",
    "pattern_finder",
    "question_generator",
    "recent_focus",
    "scale_shifter",
    "seasonal_patterns",
    "seasonal_revisit",
    "session_drift",
    "structure_diversity_checker",
    "stub_expander",
    "task_archaeology",
    "temporal_clustering",
    "temporal_drift",
    "temporal_mirror",
    "vocabulary_expansion",
]

DEFAULT_TRACERY_GEISTS = [
    "contradictor",
    "hub_explorer",
    "note_combinations",
    "orphan_connector",
    "perspective_shifter",
    "random_prompts",
    "semantic_neighbours",
    "transformation_suggester",
    "what_if",
]


@dataclass
class DateCollectionConfig:
    """Configuration for date-collection notes."""

    enabled: bool = True
    exclude_files: List[str] = field(default_factory=list)
    min_sections: int = 2
    date_threshold: float = 0.5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DateCollectionConfig":
        """Create config from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            exclude_files=data.get("exclude_files", []),
            min_sections=data.get("min_sections", 2),
            date_threshold=data.get("date_threshold", 0.5),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "enabled": self.enabled,
            "exclude_files": self.exclude_files,
            "min_sections": self.min_sections,
            "date_threshold": self.date_threshold,
        }


@dataclass
class VectorSearchConfig:
    """Configuration for vector search backend."""

    backend: str = "in-memory"
    backend_settings: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VectorSearchConfig":
        """Create config from dictionary."""
        return cls(
            backend=data.get("backend", "in-memory"),
            backend_settings=data.get("backends", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        result: Dict[str, Any] = {
            "backend": self.backend,
        }
        if self.backend_settings:
            result["backends"] = self.backend_settings
        return result


@dataclass
class GeistFabrikConfig:
    """GeistFabrik configuration."""

    enabled_modules: List[str] = field(default_factory=list)
    default_geists: Dict[str, bool] = field(default_factory=dict)
    date_collection: DateCollectionConfig = field(default_factory=DateCollectionConfig)
    vector_search: VectorSearchConfig = field(default_factory=VectorSearchConfig)

    def is_geist_enabled(self, geist_id: str) -> bool:
        """Check if a geist is enabled.

        Args:
            geist_id: ID of the geist to check

        Returns:
            True if enabled (defaults to True if not specified)
        """
        return self.default_geists.get(geist_id, True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeistFabrikConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            GeistFabrikConfig instance
        """
        date_collection_data = data.get("date_collection", {})
        vector_search_data = data.get("vector_search", {})
        return cls(
            enabled_modules=data.get("enabled_modules", []),
            default_geists=data.get("default_geists", {}),
            date_collection=DateCollectionConfig.from_dict(date_collection_data),
            vector_search=VectorSearchConfig.from_dict(vector_search_data),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Configuration dictionary
        """
        return {
            "enabled_modules": self.enabled_modules,
            "default_geists": self.default_geists,
            "date_collection": self.date_collection.to_dict(),
            "vector_search": self.vector_search.to_dict(),
        }


def load_config(config_path: Path) -> GeistFabrikConfig:
    """Load configuration from config.yaml.

    Args:
        config_path: Path to config.yaml file

    Returns:
        GeistFabrikConfig instance (with defaults if file doesn't exist)
    """
    if not config_path.exists():
        return GeistFabrikConfig()

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            if data is None:
                return GeistFabrikConfig()
            return GeistFabrikConfig.from_dict(data)
    except Exception:
        # If loading fails, return default config
        return GeistFabrikConfig()


def save_config(config: GeistFabrikConfig, config_path: Path) -> None:
    """Save configuration to config.yaml.

    Args:
        config: Configuration to save
        config_path: Path to config.yaml file
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.safe_dump(config.to_dict(), f, default_flow_style=False, sort_keys=False)


def generate_default_config() -> str:
    """Generate default config.yaml content with all default geists listed.

    Returns:
        YAML string with default configuration
    """
    lines = [
        "# GeistFabrik Configuration",
        "",
        "# Default Geists",
        "# --------------",
        "# Default geists are enabled by default.",
        "# Set to false to disable specific geists.",
        "",
        "default_geists:",
        "  # Code geists",
    ]

    for geist in DEFAULT_CODE_GEISTS:
        lines.append(f"  {geist}: true")

    lines.append("")
    lines.append("  # Tracery geists")

    for geist in DEFAULT_TRACERY_GEISTS:
        lines.append(f"  {geist}: true")

    lines.append("")
    lines.append("# Enabled Modules")
    lines.append("# ---------------")
    lines.append("# List of metadata inference and vault function modules to enable")
    lines.append("# If empty or not specified, all modules are enabled")
    lines.append("enabled_modules: []")
    lines.append("")
    lines.append("# Date-Collection Notes")
    lines.append("# ---------------------")
    lines.append("# Configuration for journal files with multiple date-based entries")
    lines.append("date_collection:")
    lines.append("  enabled: true           # Enable date-collection detection and splitting")
    lines.append("  min_sections: 2         # Minimum H2 headings required for detection")
    lines.append("  date_threshold: 0.5     # Minimum fraction of H2s that must be dates")
    lines.append("  exclude_files: []       # Glob patterns to exclude (e.g., 'Templates/*.md')")
    lines.append("")
    lines.append("# Vector Search Backend")
    lines.append("# ---------------------")
    lines.append("# Configuration for vector similarity search")
    lines.append("vector_search:")
    lines.append("  backend: in-memory      # Options: 'in-memory' | 'sqlite-vec'")
    lines.append("  # backends:             # Backend-specific settings (optional)")
    lines.append("  #   sqlite_vec:")
    lines.append("  #     cache_size_mb: 100")
    lines.append("")

    return "\n".join(lines)
