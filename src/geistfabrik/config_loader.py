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
    "columbo",
    "complexity_mismatch",
    "concept_cluster",
    "concept_drift",
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
class GeistFabrikConfig:
    """GeistFabrik configuration."""

    enabled_modules: List[str] = field(default_factory=list)
    default_geists: Dict[str, bool] = field(default_factory=dict)

    def is_geist_enabled(self, geist_id: str) -> bool:
        """Check if a geist is enabled.

        Args:
            geist_id: ID of the geist to check

        Returns:
            True if enabled (defaults to True if not specified)
        """
        return self.default_geists.get(geist_id, True)

    def is_default_geist_enabled(self, geist_id: str) -> bool:
        """Check if a default geist is enabled.

        Deprecated: Use is_geist_enabled() instead. Kept for backward compatibility.

        Args:
            geist_id: ID of the geist to check

        Returns:
            True if enabled (defaults to True if not specified)
        """
        return self.is_geist_enabled(geist_id)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeistFabrikConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            GeistFabrikConfig instance
        """
        return cls(
            enabled_modules=data.get("enabled_modules", []),
            default_geists=data.get("default_geists", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Configuration dictionary
        """
        return {
            "enabled_modules": self.enabled_modules,
            "default_geists": self.default_geists,
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

    return "\n".join(lines)
