"""Configuration loader for GeistFabrik.

This module handles loading and saving vault configuration from config.yaml.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .bounded_yaml import BoundedYAMLError, load_bounded_yaml
from .config import (
    DEFAULT_GEIST_TIMEOUT,
    DEFAULT_MAX_GEIST_FAILURES,
    DEFAULT_MAX_SUGGESTION_LENGTH,
    DEFAULT_MIN_SUGGESTION_LENGTH,
    DEFAULT_NOVELTY_WINDOW_DAYS,
    DEFAULT_SESSION_EMBEDDING_RETENTION,
    DEFAULT_SIMILARITY_THRESHOLD,
    MAX_GEIST_TIMEOUT,
    MAX_MAX_GEIST_FAILURES,
    MAX_SESSION_SUGGESTIONS,
    MIN_GEIST_TIMEOUT,
    MIN_MAX_GEIST_FAILURES,
    MIN_SESSION_SUGGESTIONS,
    get_default_filter_config,
)
from .default_geists import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS

logger = logging.getLogger(__name__)


class ConfigError(ValueError):
    """Raised when an existing configuration file is invalid."""


def _mapping(data: Any, key: str) -> dict[str, Any]:
    if not isinstance(data, dict) or any(not isinstance(item, str) for item in data):
        raise ConfigError(f"{key} must be a mapping with string keys")
    return data


def _reject_unknown(data: dict[str, Any], allowed: set[str], key: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ConfigError(f"{key} contains unknown key(s): {', '.join(unknown)}")


def _bounded_int(data: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    value = data.get(key.rsplit(".", 1)[-1], default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{key} must be an integer in [{minimum}, {maximum}]")
    if not minimum <= value <= maximum:
        raise ConfigError(f"{key} must be in [{minimum}, {maximum}], got {value}")
    return int(value)


def _bounded_float(
    data: dict[str, Any], key: str, default: float, minimum: float, maximum: float
) -> float:
    value = data.get(key.rsplit(".", 1)[-1], default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{key} must be a number in [{minimum}, {maximum}]")
    result = float(value)
    if not minimum <= result <= maximum:
        raise ConfigError(f"{key} must be in [{minimum}, {maximum}], got {value}")
    return result


def _strict_bool(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key.rsplit(".", 1)[-1], default)
    if not isinstance(value, bool):
        raise ConfigError(f"{key} must be a boolean")
    return value


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key.rsplit(".", 1)[-1], [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConfigError(f"{key} must be a list of strings")
    return value


def _enum_string(data: dict[str, Any], key: str, default: str, allowed: set[str]) -> str:
    value = data.get(key.rsplit(".", 1)[-1], default)
    if not isinstance(value, str) or value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ConfigError(f"{key} must be one of: {choices}")
    return value


@dataclass
class DateCollectionConfig:
    """Configuration for date-collection notes."""

    enabled: bool = True
    exclude_files: list[str] = field(default_factory=list)
    min_sections: int = 2
    date_threshold: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DateCollectionConfig":
        """Create config from a fully validated dictionary."""
        _reject_unknown(
            data,
            {"enabled", "exclude_files", "min_sections", "date_threshold"},
            "date_collection",
        )
        return cls(
            enabled=_strict_bool(data, "date_collection.enabled", True),
            exclude_files=_string_list(data, "date_collection.exclude_files"),
            min_sections=_bounded_int(data, "date_collection.min_sections", 2, 1, 100_000),
            date_threshold=_bounded_float(data, "date_collection.date_threshold", 0.5, 0.0, 1.0),
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
        """Create config from a fully validated dictionary."""
        _reject_unknown(
            data,
            {"labeling_method", "min_cluster_size", "n_label_terms"},
            "clustering",
        )
        return cls(
            labeling_method=_enum_string(
                data, "clustering.labeling_method", "keybert", {"keybert", "tfidf"}
            ),
            min_cluster_size=_bounded_int(data, "clustering.min_cluster_size", 5, 2, 100_000),
            n_label_terms=_bounded_int(data, "clustering.n_label_terms", 4, 1, 100),
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
    """Configuration for the selected vector search backend.

    ``backend_settings`` retains the documented legacy ``backends`` mapping
    for round-trip compatibility. These settings are reserved and currently
    ignored, but their historical shapes remain strictly validated.
    """

    backend: str = "in-memory"
    backend_settings: dict[str, dict[str, int | str | bool]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VectorSearchConfig":
        """Create config from a fully validated dictionary."""
        _reject_unknown(data, {"backend", "backends"}, "vector_search")
        raw_backends = _mapping(data.get("backends", {}), "vector_search.backends")
        _reject_unknown(raw_backends, {"in_memory", "sqlite_vec"}, "vector_search.backends")
        backend_settings: dict[str, dict[str, int | str | bool]] = {}
        if "in_memory" in raw_backends:
            in_memory = _mapping(raw_backends["in_memory"], "vector_search.backends.in_memory")
            _reject_unknown(in_memory, {"lazy_load"}, "vector_search.backends.in_memory")
            settings: dict[str, int | str | bool] = {}
            if "lazy_load" in in_memory:
                settings["lazy_load"] = _strict_bool(
                    in_memory, "vector_search.backends.in_memory.lazy_load", False
                )
            backend_settings["in_memory"] = settings
        if "sqlite_vec" in raw_backends:
            sqlite_vec = _mapping(raw_backends["sqlite_vec"], "vector_search.backends.sqlite_vec")
            _reject_unknown(
                sqlite_vec,
                {"index_type", "cache_size_mb"},
                "vector_search.backends.sqlite_vec",
            )
            settings = {}
            if "index_type" in sqlite_vec:
                settings["index_type"] = _enum_string(
                    sqlite_vec,
                    "vector_search.backends.sqlite_vec.index_type",
                    "flat",
                    {"flat", "hnsw", "ivf"},
                )
            if "cache_size_mb" in sqlite_vec:
                settings["cache_size_mb"] = _bounded_int(
                    sqlite_vec,
                    "vector_search.backends.sqlite_vec.cache_size_mb",
                    100,
                    1,
                    1_048_576,
                )
            backend_settings["sqlite_vec"] = settings
        return cls(
            backend=_enum_string(
                data, "vector_search.backend", "in-memory", {"in-memory", "sqlite-vec"}
            ),
            backend_settings=backend_settings,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary, retaining compatible legacy settings."""
        result: dict[str, Any] = {"backend": self.backend}
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
        """Create config from a fully validated dictionary."""
        _reject_unknown(data, {"timeout", "max_failures"}, "geist_execution")
        return cls(
            timeout=_bounded_int(
                data,
                "geist_execution.timeout",
                DEFAULT_GEIST_TIMEOUT,
                MIN_GEIST_TIMEOUT,
                MAX_GEIST_TIMEOUT,
            ),
            max_failures=_bounded_int(
                data,
                "geist_execution.max_failures",
                DEFAULT_MAX_GEIST_FAILURES,
                MIN_MAX_GEIST_FAILURES,
                MAX_MAX_GEIST_FAILURES,
            ),
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
        """Create config from the nested YAML shape after exact validation."""
        _reject_unknown(data, {"boundary", "novelty", "diversity", "quality"}, "filtering")
        boundary = _mapping(data.get("boundary", {}), "filtering.boundary")
        novelty = _mapping(data.get("novelty", {}), "filtering.novelty")
        diversity = _mapping(data.get("diversity", {}), "filtering.diversity")
        quality = _mapping(data.get("quality", {}), "filtering.quality")
        _reject_unknown(boundary, {"exclude_paths"}, "filtering.boundary")
        _reject_unknown(novelty, {"window_days", "threshold"}, "filtering.novelty")
        _reject_unknown(diversity, {"threshold"}, "filtering.diversity")
        _reject_unknown(quality, {"min_length", "max_length"}, "filtering.quality")
        minimum_length = _bounded_int(
            quality,
            "filtering.quality.min_length",
            DEFAULT_MIN_SUGGESTION_LENGTH,
            0,
            1_000_000,
        )
        maximum_length = _bounded_int(
            quality,
            "filtering.quality.max_length",
            DEFAULT_MAX_SUGGESTION_LENGTH,
            1,
            1_000_000,
        )
        if minimum_length > maximum_length:
            raise ConfigError(
                "filtering.quality.min_length must not exceed filtering.quality.max_length"
            )
        return cls(
            exclude_paths=_string_list(boundary, "filtering.boundary.exclude_paths"),
            novelty_window_days=_bounded_int(
                novelty,
                "filtering.novelty.window_days",
                DEFAULT_NOVELTY_WINDOW_DAYS,
                0,
                100_000,
            ),
            novelty_threshold=_bounded_float(
                novelty,
                "filtering.novelty.threshold",
                DEFAULT_SIMILARITY_THRESHOLD,
                0.0,
                1.0,
            ),
            diversity_threshold=_bounded_float(
                diversity,
                "filtering.diversity.threshold",
                DEFAULT_SIMILARITY_THRESHOLD,
                0.0,
                1.0,
            ),
            quality_min_length=minimum_length,
            quality_max_length=maximum_length,
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
        """Create config from a fully validated dictionary."""
        _reject_unknown(data, {"default_suggestions"}, "session")
        return cls(
            default_suggestions=_bounded_int(
                data,
                "session.default_suggestions",
                5,
                MIN_SESSION_SUGGESTIONS,
                MAX_SESSION_SUGGESTIONS,
            )
        )

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
        _reject_unknown(data, set(KNOWN_CONFIG_KEYS), "configuration root")
        date_collection_data = _mapping(data.get("date_collection", {}), "date_collection")
        vector_search_data = _mapping(data.get("vector_search", {}), "vector_search")
        clustering_data = _mapping(data.get("clustering", {}), "clustering")
        geist_execution_data = _mapping(data.get("geist_execution", {}), "geist_execution")
        filtering_data = _mapping(data.get("filtering", {}), "filtering")
        session_data = _mapping(data.get("session", {}), "session")
        enabled_modules = _string_list(data, "enabled_modules")
        raw_defaults = _mapping(data.get("default_geists", {}), "default_geists")
        default_geists: dict[str, bool] = {}
        for geist_id, enabled in raw_defaults.items():
            if not isinstance(enabled, bool):
                raise ConfigError("default_geists values must be booleans")
            default_geists[geist_id] = enabled
        return cls(
            enabled_modules=enabled_modules,
            default_geists=default_geists,
            date_collection=DateCollectionConfig.from_dict(date_collection_data),
            vector_search=VectorSearchConfig.from_dict(vector_search_data),
            clustering=ClusterConfig.from_dict(clustering_data),
            session_embedding_retention=_bounded_int(
                data,
                "session_embedding_retention",
                DEFAULT_SESSION_EMBEDDING_RETENTION,
                0,
                100_000,
            ),
            geist_execution=GeistExecutionConfig.from_dict(geist_execution_data),
            filtering=FilteringConfig.from_dict(filtering_data),
            session=SessionConfig.from_dict(session_data),
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
        data = load_bounded_yaml(config_path)
        if data is None:
            return GeistFabrikConfig()
        root = _mapping(data, "configuration root")
        return GeistFabrikConfig.from_dict(root)
    except (BoundedYAMLError, ConfigError, TypeError, KeyError) as exc:
        raise ConfigError(f"Invalid configuration {config_path}: {exc}") from exc


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
        "# Unknown keys and malformed values are rejected before side effects.",
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
    lines.append("")
    lines.append("# Geist Execution (availability limits; Python plugins are trusted code)")
    lines.append("geist_execution:")
    lines.append(
        f"  timeout: {DEFAULT_GEIST_TIMEOUT}       # "
        f"{MIN_GEIST_TIMEOUT}..{MAX_GEIST_TIMEOUT} seconds"
    )
    lines.append(
        f"  max_failures: {DEFAULT_MAX_GEIST_FAILURES}    # "
        f"{MIN_MAX_GEIST_FAILURES}..{MAX_MAX_GEIST_FAILURES}, persisted"
    )
    lines.append("")
    lines.append("# Session Output")
    lines.append("session:")
    lines.append(
        f"  default_suggestions: 5  # {MIN_SESSION_SUGGESTIONS}..{MAX_SESSION_SUGGESTIONS}"
    )
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
