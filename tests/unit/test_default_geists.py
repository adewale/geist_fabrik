"""Tests for default geists functionality."""

import tempfile
from pathlib import Path

from geistfabrik import GeistFabrikConfig, generate_default_config, load_config, save_config
from geistfabrik.config_loader import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS


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


def test_default_geist_lists():
    """Test that default geist lists are complete."""
    # Should have 38 code geists
    assert len(DEFAULT_CODE_GEISTS) == 38
    # Spot check a few key geists
    assert "blind_spot_detector" in DEFAULT_CODE_GEISTS
    assert "temporal_drift" in DEFAULT_CODE_GEISTS
    assert "temporal_mirror" in DEFAULT_CODE_GEISTS
    assert "columbo" in DEFAULT_CODE_GEISTS
    assert "on_this_day" in DEFAULT_CODE_GEISTS

    # Should have 9 Tracery geists
    assert len(DEFAULT_TRACERY_GEISTS) == 9
    assert "contradictor" in DEFAULT_TRACERY_GEISTS
    assert "hub_explorer" in DEFAULT_TRACERY_GEISTS
    assert "transformation_suggester" in DEFAULT_TRACERY_GEISTS
    assert "what_if" in DEFAULT_TRACERY_GEISTS


def test_default_geists_exist():
    """Test that default geist files actually exist."""
    package_dir = Path(__file__).parent.parent.parent / "src" / "geistfabrik"
    default_code_dir = package_dir / "default_geists" / "code"
    default_tracery_dir = package_dir / "default_geists" / "tracery"

    # Check code geists
    for geist_id in DEFAULT_CODE_GEISTS:
        geist_file = default_code_dir / f"{geist_id}.py"
        assert geist_file.exists(), f"Default code geist {geist_id}.py not found"

    # Check Tracery geists
    for geist_id in DEFAULT_TRACERY_GEISTS:
        geist_file = default_tracery_dir / f"{geist_id}.yaml"
        assert geist_file.exists(), f"Default Tracery geist {geist_id}.yaml not found"
