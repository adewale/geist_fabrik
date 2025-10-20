"""Test package version and basic imports."""

import geistfabrik


def test_version() -> None:
    """Test that version is defined and follows semantic versioning."""
    assert hasattr(geistfabrik, "__version__")
    assert isinstance(geistfabrik.__version__, str)
    assert len(geistfabrik.__version__.split(".")) == 3
