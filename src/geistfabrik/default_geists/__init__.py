"""Default geists bundled with GeistFabrik.

This package contains the default geists that ship with GeistFabrik,
providing immediate value to users without requiring custom extensions.

The geist names and counts are computed programmatically to ensure they
always match reality. This is the single source of truth for geist lists
and counts throughout the codebase and documentation.
"""

from pathlib import Path

# Programmatically discover default geists (single source of truth)
_default_geists_dir = Path(__file__).parent

# Discover code geists (*.py files, excluding __init__.py and __pycache__)
_code_geist_files = sorted((_default_geists_dir / "code").glob("*.py"))
DEFAULT_CODE_GEISTS: list[str] = [f.stem for f in _code_geist_files if f.name != "__init__.py"]
"""Sorted list of default code geist IDs, derived from filesystem.

Computed by scanning default_geists/code/ for Python files (excluding __init__.py).
This is the single source of truth - never hardcode geist names elsewhere.
"""

CODE_GEIST_COUNT = len(DEFAULT_CODE_GEISTS)
"""Number of code-based geists (.py files) bundled with GeistFabrik."""

# Discover Tracery geists (*.yaml files)
_tracery_geist_files = sorted((_default_geists_dir / "tracery").glob("*.yaml"))
DEFAULT_TRACERY_GEISTS: list[str] = [f.stem for f in _tracery_geist_files]
"""Sorted list of default Tracery geist IDs, derived from filesystem.

Computed by scanning default_geists/tracery/ for YAML files.
This is the single source of truth - never hardcode geist names elsewhere.
"""

TRACERY_GEIST_COUNT = len(DEFAULT_TRACERY_GEISTS)
"""Number of Tracery-based geists (.yaml files) bundled with GeistFabrik."""

# Total count
TOTAL_GEIST_COUNT = CODE_GEIST_COUNT + TRACERY_GEIST_COUNT
"""Total number of default geists (code + Tracery) bundled with GeistFabrik."""

__all__ = [
    "DEFAULT_CODE_GEISTS",
    "DEFAULT_TRACERY_GEISTS",
    "CODE_GEIST_COUNT",
    "TRACERY_GEIST_COUNT",
    "TOTAL_GEIST_COUNT",
]
