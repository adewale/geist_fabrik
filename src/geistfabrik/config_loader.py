"""Configuration loader for GeistFabrik.

This module handles loading and saving vault configuration from config.yaml.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import (
    DEFAULT_GEIST_TIMEOUT,
    DEFAULT_MAX_GEIST_FAILURES,
    DEFAULT_MAX_SUGGESTION_LENGTH,
    DEFAULT_MIN_SUGGESTION_LENGTH,
    DEFAULT_NOVELTY_WINDOW_DAYS,
    DEFAULT_SESSION_EMBEDDING_RETENTION,
    DEFAULT_SIMILARITY_THRESHOLD,
    get_default_filter_config,
)
from .default_geists import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS

logger = logging.getLogger(__name__)


@dataclass
class DateCollectionConfig:
    """Configuration for date-collection notes."""

    enabled: bool = True
    exclude_files: list[str] = field(default_factory=list)
    min_sections: int = 2
    date_threshold: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DateCollectionConfig":
        """Create config from dictionary."""
        return cls(
            enabled=data.get("enabled", True),
            exclude_files=data.get("exclude_files", []),
            min_sections=data.get("min_sections", 2),
            date_threshold=data.get("date_threshold", 0.5),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "enabled": self.enabled,
            "exclude_files": self.exclude_files,
            "min_sections": self.min_sections,
            "date_threshold": self.date_threshold,
        }


@dataclass
class ClusterConfig:
    """Configuration for clustering and cluster labelling."""

    labeling_method: str = "keybert"  # "keybert" or "tfidf"
    min_cluster_size: int = 5
    n_label_terms: int = 4

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClusterConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            ClusterConfig instance
        """
        return cls(
            labeling_method=data.get("labeling_method", "keybert"),
            min_cluster_size=data.get("min_cluster_size", 5),
            n_label_terms=data.get("n_label_terms", 4),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Configuration dictionary
        """
        return {
            "labeling_method": self.labeling_method,
            "min_cluster_size": self.min_cluster_size,
            "n_label_terms": self.n_label_terms,
        }


@dataclass
class VectorSearchConfig:
    """Configuration for vector search backend."""

    backend: str = "in-memory"
    backend_settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VectorSearchConfig":
        """Create config from dictionary."""
        return cls(
            backend=data.get("backend", "in-memory"),
            backend_settings=data.get("backends", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        result: dict[str, Any] = {
            "backend": self.backend,
        }
        if self.backend_settings:
            result["backends"] = self.backend_settings
        return result


@dataclass
class GeistExecutionConfig:
    """Configuration for geist execution (spec: geist_execution section)."""

    timeout: int = DEFAULT_GEIST_TIMEOUT
    max_failures: int = DEFAULT_MAX_GEIST_FAILURES

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeistExecutionConfig":
        """Create config from dictionary."""
        return cls(
            timeout=data.get("timeout", DEFAULT_GEIST_TIMEOUT),
            max_failures=data.get("max_failures", DEFAULT_MAX_GEIST_FAILURES),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {"timeout": self.timeout, "max_failures": self.max_failures}


@dataclass
class FilteringConfig:
    """Configuration for the suggestion filtering pipeline.

    Mirrors the spec's filtering schema. exclude_paths lists folder prefixes
    (e.g. "Private/") whose notes must never be referenced by suggestions -
    the boundary filter drops any suggestion that mentions them.
    """

    exclude_paths: list[str] = field(default_factory=list)
    novelty_window_days: int = DEFAULT_NOVELTY_WINDOW_DAYS
    novelty_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    diversity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    quality_min_length: int = DEFAULT_MIN_SUGGESTION_LENGTH
    quality_max_length: int = DEFAULT_MAX_SUGGESTION_LENGTH

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FilteringConfig":
        """Create config from the nested YAML shape."""
        boundary = data.get("boundary", {})
        novelty = data.get("novelty", {})
        diversity = data.get("diversity", {})
        quality = data.get("quality", {})
        return cls(
            exclude_paths=boundary.get("exclude_paths", []),
            novelty_window_days=novelty.get("window_days", DEFAULT_NOVELTY_WINDOW_DAYS),
            novelty_threshold=novelty.get("threshold", DEFAULT_SIMILARITY_THRESHOLD),
            diversity_threshold=diversity.get("threshold", DEFAULT_SIMILARITY_THRESHOLD),
            quality_min_length=quality.get("min_length", DEFAULT_MIN_SUGGESTION_LENGTH),
            quality_max_length=quality.get("max_length", DEFAULT_MAX_SUGGESTION_LENGTH),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to the nested YAML shape."""
        return {
            "boundary": {"exclude_paths": self.exclude_paths},
            "novelty": {
                "window_days": self.novelty_window_days,
                "threshold": self.novelty_threshold,
            },
            "diversity": {"threshold": self.diversity_threshold},
            "quality": {
                "min_length": self.quality_min_length,
                "max_length": self.quality_max_length,
            },
        }

    def to_filter_config(self) -> dict[str, Any]:
        """Produce the SuggestionFilter config dict (defaults overlaid)."""
        cfg = get_default_filter_config()
        cfg["boundary"]["exclude_paths"] = list(self.exclude_paths)
        cfg["novelty"]["window_days"] = self.novelty_window_days
        cfg["novelty"]["threshold"] = self.novelty_threshold
        cfg["diversity"]["threshold"] = self.diversity_threshold
        cfg["quality"]["min_length"] = self.quality_min_length
        cfg["quality"]["max_length"] = self.quality_max_length
        return cfg


@dataclass
class SessionConfig:
    """Configuration for session output (spec: session section)."""

    default_suggestions: int = 5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionConfig":
        """Create config from dictionary."""
        return cls(default_suggestions=data.get("default_suggestions", 5))

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {"default_suggestions": self.default_suggestions}


@dataclass
class GeistFabrikConfig:
    """GeistFabrik configuration."""

    enabled_modules: list[str] = field(default_factory=list)
    default_geists: dict[str, bool] = field(default_factory=dict)
    date_collection: DateCollectionConfig = field(default_factory=DateCollectionConfig)
    vector_search: VectorSearchConfig = field(default_factory=VectorSearchConfig)
    clustering: ClusterConfig = field(default_factory=ClusterConfig)
    session_embedding_retention: int = DEFAULT_SESSION_EMBEDDING_RETENTION
    geist_execution: GeistExecutionConfig = field(default_factory=GeistExecutionConfig)
    filtering: FilteringConfig = field(default_factory=FilteringConfig)
    session: SessionConfig = field(default_factory=SessionConfig)

    def is_geist_enabled(self, geist_id: str) -> bool:
        """Check if a geist is enabled.

        Args:
            geist_id: ID of the geist to check

        Returns:
            True if enabled (defaults to True if not specified)
        """
        return self.default_geists.get(geist_id, True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GeistFabrikConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            GeistFabrikConfig instance
        """
        date_collection_data = data.get("date_collection", {})
        vector_search_data = data.get("vector_search", {})
        clustering_data = data.get("clustering", {})
        return cls(
            enabled_modules=data.get("enabled_modules", []),
            default_geists=data.get("default_geists", {}),
            date_collection=DateCollectionConfig.from_dict(date_collection_data),
            vector_search=VectorSearchConfig.from_dict(vector_search_data),
            clustering=ClusterConfig.from_dict(clustering_data),
            session_embedding_retention=data.get(
                "session_embedding_retention", DEFAULT_SESSION_EMBEDDING_RETENTION
            ),
            geist_execution=GeistExecutionConfig.from_dict(data.get("geist_execution", {})),
            filtering=FilteringConfig.from_dict(data.get("filtering", {})),
            session=SessionConfig.from_dict(data.get("session", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary.

        Returns:
            Configuration dictionary
        """
        return {
            "enabled_modules": self.enabled_modules,
            "default_geists": self.default_geists,
            "date_collection": self.date_collection.to_dict(),
            "vector_search": self.vector_search.to_dict(),
            "clustering": self.clustering.to_dict(),
            "session_embedding_retention": self.session_embedding_retention,
            "geist_execution": self.geist_execution.to_dict(),
            "filtering": self.filtering.to_dict(),
            "session": self.session.to_dict(),
        }


# Top-level config.yaml keys GeistFabrikConfig understands. A typo or a
# spec'd-but-unwired key surfaces as a warning instead of silently doing
# nothing (the failure mode behind several "specified but not built" gaps).
KNOWN_CONFIG_KEYS = frozenset(
    {
        "enabled_modules",
        "default_geists",
        "date_collection",
        "vector_search",
        "clustering",
        "session_embedding_retention",
        "geist_execution",
        "filtering",
        "session",
    }
)


def _warn_unknown_keys(data: dict[str, Any], config_path: Path) -> None:
    """Warn about top-level config keys that GeistFabrik does not consume."""
    if not isinstance(data, dict):
        return
    unknown = sorted(set(data) - KNOWN_CONFIG_KEYS)
    if unknown:
        logger.warning(
            "Ignoring unknown config key(s) in %s: %s",
            config_path,
            ", ".join(unknown),
        )


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
        with open(config_path) as f:
            data = yaml.safe_load(f)
            if data is None:
                return GeistFabrikConfig()
            _warn_unknown_keys(data, config_path)
            return GeistFabrikConfig.from_dict(data)
    except Exception as e:
        # If loading fails, return default config
        logger.warning(f"Failed to load config: {e}")
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
    lines.append("# Storage")
    lines.append("# -------")
    lines.append("# Bound database growth by pruning temporal embeddings for old sessions.")
    lines.append(
        f"session_embedding_retention: {DEFAULT_SESSION_EMBEDDING_RETENTION}"
        "  # Recent sessions to keep embeddings for; 0 = keep all"
    )
    lines.append("")

    return "\n".join(lines)
