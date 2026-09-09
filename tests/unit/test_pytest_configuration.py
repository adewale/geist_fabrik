"""Regression tests for the canonical pytest configuration."""

from pathlib import Path


def test_pyproject_is_canonical_pytest_configuration(pytestconfig) -> None:
    """A higher-precedence pytest.ini must not silently shadow pyproject.toml."""
    assert pytestconfig.inipath is not None
    assert Path(str(pytestconfig.inipath)).name == "pyproject.toml"


def test_required_markers_are_registered(pytestconfig) -> None:
    """Strict marker mode has declarations for every supported test lane."""
    marker_lines = pytestconfig.getini("markers")
    registered = {line.split(":", 1)[0].strip() for line in marker_lines}
    assert {
        "unit",
        "integration",
        "slow",
        "benchmark",
        "production_model",
        "artifact",
    } <= registered
