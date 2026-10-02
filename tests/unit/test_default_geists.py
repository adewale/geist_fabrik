"""Tests for default geists functionality."""

import tempfile
from pathlib import Path

from geistfabrik import (
    GeistFabrikConfig,
    default_geists,
    generate_default_config,
    load_config,
    save_config,
)
from geistfabrik.default_geists import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS
from geistfabrik.geist_executor import GeistExecutor
from geistfabrik.tracery import TraceryGeistLoader


def test_config_default_values():
    """Test that config defaults all geists to enabled."""
    config = GeistFabrikConfig()

    # All geists should default to enabled
    assert config.is_geist_enabled("blind_spot_detector") is True
    assert config.is_geist_enabled("contradictor") is True
    assert config.is_geist_enabled("unknown_geist") is True  # Unknown defaults to True


def test_config_with_disabled_geists():
    """Test that disabled geists are properly respected."""
    config = GeistFabrikConfig(
        default_geists={
            "blind_spot_detector": False,
            "contradictor": True,
        }
    )

    assert config.is_geist_enabled("blind_spot_detector") is False
    assert config.is_geist_enabled("contradictor") is True
    assert config.is_geist_enabled("on_this_day") is True  # Not specified, defaults to True


def test_config_from_dict():
    """Test creating config from dictionary."""
    data = {
        "enabled_modules": ["test_module"],
        "default_geists": {
            "blind_spot_detector": False,
        },
    }

    config = GeistFabrikConfig.from_dict(data)

    assert config.enabled_modules == ["test_module"]
    assert config.is_geist_enabled("blind_spot_detector") is False
    assert config.is_geist_enabled("contradictor") is True


def test_config_to_dict():
    """Test converting config to dictionary."""
    config = GeistFabrikConfig(
        enabled_modules=["test_module"],
        default_geists={"blind_spot_detector": False},
    )

    data = config.to_dict()

    assert data["enabled_modules"] == ["test_module"]
    assert data["default_geists"] == {"blind_spot_detector": False}


def test_load_config_nonexistent():
    """Test loading config when file doesn't exist returns default config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"
        config = load_config(config_path)

        assert isinstance(config, GeistFabrikConfig)
        assert config.enabled_modules == []
        assert config.default_geists == {}


def test_save_and_load_config():
    """Test saving and loading config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.yaml"

        # Create and save config
        original_config = GeistFabrikConfig(
            enabled_modules=["module1", "module2"],
            default_geists={
                "blind_spot_detector": False,
                "contradictor": True,
            },
        )
        save_config(original_config, config_path)

        # Load config
        loaded_config = load_config(config_path)

        assert loaded_config.enabled_modules == ["module1", "module2"]
        assert loaded_config.is_geist_enabled("blind_spot_detector") is False
        assert loaded_config.is_geist_enabled("contradictor") is True


def test_generate_default_config():
    """Test generating default config content."""
    content = generate_default_config()

    assert "default_geists:" in content
    assert "enabled_modules:" in content

    # Check that all default code geists are listed
    for geist in DEFAULT_CODE_GEISTS:
        assert f"{geist}: true" in content

    # Check that all default Tracery geists are listed
    for geist in DEFAULT_TRACERY_GEISTS:
        assert f"{geist}: true" in content


def test_default_geist_directories_load_exactly_the_default_lists(tmp_path: Path) -> None:
    """The ids the production loaders load from the bundled dirs are the DEFAULT_* lists.

    DEFAULT_CODE_GEISTS / DEFAULT_TRACERY_GEISTS are filename globs. This
    checks them against what actually loads: every code module imports and
    exports suggest(), every YAML parses with an id equal to its filename
    stem, nothing fails to load, and neither set is empty.
    """
    bundled = Path(default_geists.__file__).parent
    no_custom_geists = tmp_path / "no-custom-geists"

    executor = GeistExecutor(no_custom_geists, default_geists_dir=bundled / "code")
    executor.load_geists()
    loader = TraceryGeistLoader(no_custom_geists, seed=1, default_geists_dir=bundled / "tracery")
    tracery_geists, _ = loader.load_all()

    assert executor.execution_log == [], "code geists failed to load"
    assert loader.load_errors == [], "Tracery geists failed to load"
    assert sorted(executor.geists) == DEFAULT_CODE_GEISTS
    assert sorted(g.geist_id for g in tracery_geists) == DEFAULT_TRACERY_GEISTS
    assert DEFAULT_CODE_GEISTS and DEFAULT_TRACERY_GEISTS


def test_default_geist_lists():
    """Spot-check well-known default geists and the lists' sorted order."""
    assert "blind_spot_detector" in DEFAULT_CODE_GEISTS
    assert "temporal_drift" in DEFAULT_CODE_GEISTS
    assert "this_time_last_year" in DEFAULT_CODE_GEISTS
    assert "columbo" in DEFAULT_CODE_GEISTS

    assert "contradictor" in DEFAULT_TRACERY_GEISTS
    assert "hub_explorer" in DEFAULT_TRACERY_GEISTS
    assert "what_if" in DEFAULT_TRACERY_GEISTS

    # Lists should be sorted (filesystem-derived, sorted by name)
    assert DEFAULT_CODE_GEISTS == sorted(DEFAULT_CODE_GEISTS)
    assert DEFAULT_TRACERY_GEISTS == sorted(DEFAULT_TRACERY_GEISTS)
