"""Property-based tests for configuration round-trip invariants."""

from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.config_loader import (
    ClusterConfig,
    DateCollectionConfig,
    GeistFabrikConfig,
    VectorSearchConfig,
)

# --- Strategies ---

date_collection_dicts = st.fixed_dictionaries(
    {
        "enabled": st.booleans(),
        "exclude_files": st.lists(st.text(min_size=1, max_size=30), max_size=5),
        "min_sections": st.integers(min_value=1, max_value=100),
        "date_threshold": st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        ),
    }
)

cluster_config_dicts = st.fixed_dictionaries(
    {
        "labeling_method": st.sampled_from(["keybert", "tfidf"]),
        "min_cluster_size": st.integers(min_value=2, max_value=100),
        "n_label_terms": st.integers(min_value=1, max_value=20),
    }
)

vector_search_dicts = st.fixed_dictionaries(
    {
        "backend": st.sampled_from(["in-memory", "sqlite-vec"]),
        "backends": st.just({}),
    }
)

full_config_dicts = st.fixed_dictionaries(
    {
        "enabled_modules": st.lists(st.text(min_size=1, max_size=20), max_size=5),
        "default_geists": st.dictionaries(
            st.text(min_size=1, max_size=30), st.booleans(), max_size=10
        ),
        "date_collection": date_collection_dicts,
        "vector_search": vector_search_dicts,
        "clustering": cluster_config_dicts,
    }
)


# --- DateCollectionConfig ---


@given(date_collection_dicts)
def test_date_collection_roundtrip(d: dict) -> None:
    """from_dict(to_dict(from_dict(d))) == from_dict(d)."""
    config = DateCollectionConfig.from_dict(d)
    roundtripped = DateCollectionConfig.from_dict(config.to_dict())
    assert config == roundtripped


@given(date_collection_dicts)
def test_date_collection_dict_roundtrip(d: dict) -> None:
    """to_dict(from_dict(d)) == d for complete dicts."""
    config = DateCollectionConfig.from_dict(d)
    assert config.to_dict() == d


@given(st.fixed_dictionaries({}, optional={"enabled": st.booleans()}))
def test_date_collection_defaults_on_missing_keys(d: dict) -> None:
    """Missing keys should use defaults, not crash."""
    config = DateCollectionConfig.from_dict(d)
    assert isinstance(config.enabled, bool)
    assert isinstance(config.min_sections, int)
    assert isinstance(config.date_threshold, float)
    assert isinstance(config.exclude_files, list)


# --- ClusterConfig ---


@given(cluster_config_dicts)
def test_cluster_config_roundtrip(d: dict) -> None:
    """from_dict(to_dict(from_dict(d))) == from_dict(d)."""
    config = ClusterConfig.from_dict(d)
    roundtripped = ClusterConfig.from_dict(config.to_dict())
    assert config == roundtripped


@given(cluster_config_dicts)
def test_cluster_config_dict_roundtrip(d: dict) -> None:
    """to_dict(from_dict(d)) == d."""
    config = ClusterConfig.from_dict(d)
    assert config.to_dict() == d


# --- VectorSearchConfig ---


@given(vector_search_dicts)
def test_vector_search_roundtrip(d: dict) -> None:
    """Round-trip preserves identity."""
    config = VectorSearchConfig.from_dict(d)
    roundtripped = VectorSearchConfig.from_dict(config.to_dict())
    assert config == roundtripped


# --- GeistFabrikConfig ---


@given(full_config_dicts)
@settings(max_examples=50)
def test_full_config_roundtrip(d: dict) -> None:
    """Full config survives from_dict -> to_dict -> from_dict."""
    config = GeistFabrikConfig.from_dict(d)
    roundtripped = GeistFabrikConfig.from_dict(config.to_dict())
    assert config == roundtripped


@given(full_config_dicts)
@settings(max_examples=50)
def test_full_config_dict_roundtrip(d: dict) -> None:
    """to_dict(from_dict(d)) == d for complete dicts."""
    config = GeistFabrikConfig.from_dict(d)
    result = config.to_dict()
    assert result["enabled_modules"] == d["enabled_modules"]
    assert result["default_geists"] == d["default_geists"]
    assert result["clustering"] == d["clustering"]


def test_empty_dict_uses_all_defaults() -> None:
    """from_dict({}) should produce valid config with all defaults."""
    config = GeistFabrikConfig.from_dict({})
    assert config.enabled_modules == []
    assert config.default_geists == {}
    assert config.date_collection.enabled is True
    assert config.vector_search.backend == "in-memory"
    assert config.clustering.labeling_method == "keybert"


@given(st.text(min_size=1, max_size=50))
def test_is_geist_enabled_defaults_true(geist_id: str) -> None:
    """Unknown geist IDs should default to enabled."""
    config = GeistFabrikConfig()
    assert config.is_geist_enabled(geist_id) is True


@given(st.text(min_size=1, max_size=50), st.booleans())
def test_is_geist_enabled_respects_setting(geist_id: str, enabled: bool) -> None:
    """Explicit settings should be respected."""
    config = GeistFabrikConfig(default_geists={geist_id: enabled})
    assert config.is_geist_enabled(geist_id) is enabled
