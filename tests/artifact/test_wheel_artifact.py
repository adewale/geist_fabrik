"""Structural release-artifact contract tests.

Run through ``scripts/test_wheel.sh``; these tests deliberately inspect built
archives rather than the editable checkout.
"""

import hashlib
import os
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path
from typing import Protocol

import pytest

from geistfabrik.default_geists import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS

pytestmark = pytest.mark.artifact

MODEL_PREFIX = "geistfabrik/model_data/all-MiniLM-L6-v2/"
REQUIRED_MODEL_FILES = {
    "1_Pooling/config.json",
    "LICENSE.apache-2.0",
    "NOTICE",
    "README.md",
    "config.json",
    "config_sentence_transformers.json",
    "model.safetensors",
    "modules.json",
    "sentence_bert_config.json",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
}
ARTIFACT_SIZE_LIMIT = 95_000_000
EXPECTED_MODEL_HASHES = {
    "model.safetensors": "1377e9af0ca0b016a9f2aa584d6fc71ab3ea6804fae21ef9fb1416e2944057ac",
    "tokenizer.json": "4084ce5afffa730ba5697e3e81ec5707e14b13ad1bace0cc43bb0bdb411cfdcf",
}


class _BinaryReader(Protocol):
    def read(self, size: int = -1, /) -> bytes: ...


def _sha256(handle: _BinaryReader) -> str:
    digest = hashlib.sha256()
    while chunk := handle.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(environment_name: str) -> Path:
    value = os.environ.get(environment_name)
    if not value:
        pytest.fail(
            f"{environment_name} is supplied by scripts/test_wheel.sh; "
            "run that script for the required artifact gate"
        )
    path = Path(value).resolve()
    assert path.is_file(), path
    return path


def test_wheel_contents_and_size() -> None:
    """The wheel contains materialized model, geist, typing, and license data."""
    wheel = _artifact_path("GEISTFABRIK_WHEEL")
    assert wheel.stat().st_size < ARTIFACT_SIZE_LIMIT

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert {MODEL_PREFIX + name for name in REQUIRED_MODEL_FILES} <= names
        weights_name = MODEL_PREFIX + "model.safetensors"
        assert archive.getinfo(weights_name).file_size > 1_000
        with archive.open(weights_name) as weights_file:
            assert not weights_file.read(64).startswith(
                b"version https://git-lfs.github.com/spec/v1"
            )
        for filename, expected_hash in EXPECTED_MODEL_HASHES.items():
            with archive.open(MODEL_PREFIX + filename) as model_file:
                assert _sha256(model_file) == expected_hash
        assert "geistfabrik/py.typed" in names
        assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
        assert {
            f"geistfabrik/default_geists/code/{name}.py" for name in DEFAULT_CODE_GEISTS
        } <= names
        assert {
            f"geistfabrik/default_geists/tracery/{name}.yaml" for name in DEFAULT_TRACERY_GEISTS
        } <= names


def test_wheel_metadata_and_entry_points() -> None:
    """Published metadata and both console entry points are present."""
    wheel = _artifact_path("GEISTFABRIK_WHEEL")
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        entry_points_name = next(
            name for name in archive.namelist() if name.endswith(".dist-info/entry_points.txt")
        )
        package_metadata = BytesParser().parsebytes(archive.read(metadata_name))
        entry_points = archive.read(entry_points_name).decode()

    assert package_metadata["License-Expression"] == "MIT"
    assert package_metadata["Requires-Python"] in {">=3.11,<3.13", "<3.13,>=3.11"}
    project_urls = package_metadata.get_all("Project-URL") or []
    assert any("Homepage, https://github.com/adewale/geist_fabrik" in url for url in project_urls)
    assert any(
        "Issues, https://github.com/adewale/geist_fabrik/issues" in url for url in project_urls
    )
    assert "ade@example.com" not in str(package_metadata)
    assert "geistfabrik = geistfabrik.cli:main" in entry_points
    assert "gf = geistfabrik.cli:main" in entry_points


def test_sdist_retains_wheel_inputs_and_size() -> None:
    """A wheel rebuilt from the source release retains the model snapshot."""
    sdist = _artifact_path("GEISTFABRIK_SDIST")
    assert sdist.stat().st_size < ARTIFACT_SIZE_LIMIT
    with tarfile.open(sdist, "r:gz") as archive:
        names = archive.getnames()
        assert any(name.endswith("/src/geistfabrik/model_data/__init__.py") for name in names)
        for filename, expected_hash in EXPECTED_MODEL_HASHES.items():
            member_name = next(
                name for name in names if name.endswith(f"/models/all-MiniLM-L6-v2/{filename}")
            )
            model_file = archive.extractfile(member_name)
            assert model_file is not None
            with model_file:
                assert _sha256(model_file) == expected_hash
