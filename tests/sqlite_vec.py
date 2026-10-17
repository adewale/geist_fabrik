"""Shared native-backend capability policy for all test owners."""

import os
import platform
import sqlite3
from contextlib import closing

import pytest


def _is_loadable() -> bool:
    try:
        import sqlite_vec
    except ImportError:
        return False
    with closing(sqlite3.connect(":memory:")) as probe:
        if not hasattr(probe, "enable_load_extension"):
            return False
        try:
            probe.enable_load_extension(True)
            sqlite_vec.load(probe)
            probe.execute("SELECT vec_version()")
        except (sqlite3.OperationalError, AttributeError):
            return False
    return True


SQLITE_VEC_LOADABLE = _is_loadable()
REQUIRES_SQLITE_VEC = pytest.mark.skipif(
    not SQLITE_VEC_LOADABLE, reason="sqlite-vec extension is not loadable on this interpreter"
)

# Native availability is mandatory in Linux CI, optional on macOS builds of
# Python whose SQLite omits extension loading. Never turn Linux failures into skips.
if os.environ.get("CI") and platform.system() == "Linux" and not SQLITE_VEC_LOADABLE:
    pytest.fail(
        "sqlite-vec is required in CI (Linux) but not loadable. "
        "Run: uv pip install -e '.[vector-search]'"
    )
