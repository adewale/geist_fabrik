"""Regression tests for embedding dependency and host-process contracts."""

import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_import_does_not_change_global_sklearn_configuration() -> None:
    """A library import must not weaken validation for its host process."""
    code = """
import sklearn
sklearn.set_config(assume_finite=False)
before = sklearn.get_config()["assume_finite"]
import geistfabrik.embeddings
after = sklearn.get_config()["assume_finite"]
assert before is False and after is False, (before, after)
"""
    subprocess.run([sys.executable, "-c", code], check=True, cwd=REPO, timeout=30)


def test_sentence_transformers_minimum_supports_local_only_loading() -> None:
    """Keep the declared lower bound at the first supported constructor API."""
    project = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]
    dependencies = project["dependencies"]
    assert "sentence-transformers>=3.0.0" in dependencies
