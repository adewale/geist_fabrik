"""Test package version and release metadata."""

from importlib.metadata import metadata, version

from packaging.specifiers import SpecifierSet
from packaging.version import Version

import geistfabrik


def test_version_matches_installed_metadata() -> None:
    """Runtime and distribution versions share one release value."""
    parsed = Version(geistfabrik.__version__)
    assert str(parsed) == geistfabrik.__version__
    assert version("geistfabrik") == geistfabrik.__version__


def test_release_metadata_contract() -> None:
    """Core project metadata is suitable for a published wheel."""
    package_metadata = metadata("geistfabrik")
    assert package_metadata["License-Expression"] == "MIT"
    assert SpecifierSet(package_metadata["Requires-Python"]) == SpecifierSet(">=3.11,<3.13")
    project_urls = package_metadata.get_all("Project-URL")
    assert project_urls is not None
    assert "https://github.com/adewale/geist_fabrik" in project_urls[0]
    assert "ade@example.com" not in str(package_metadata)
