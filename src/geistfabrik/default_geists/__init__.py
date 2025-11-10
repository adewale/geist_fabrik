"""Default geists bundled with GeistFabrik.

This package contains the default geists that ship with GeistFabrik,
providing immediate value to users without requiring custom extensions.

The geist counts are computed programmatically to ensure they always match
reality. This is the single source of truth for geist counts throughout
the codebase and documentation.
"""

from pathlib import Path

# Programmatically count default geists (single source of truth)
_default_geists_dir = Path(__file__).parent

# Count code geists (*.py files, excluding __init__.py and __pycache__)
_code_geist_files = list((_default_geists_dir / "code").glob("*.py"))
CODE_GEIST_COUNT = len([f for f in _code_geist_files if f.name != "__init__.py"])
"""Number of code-based geists (.py files) bundled with GeistFabrik.

This count is computed programmatically by scanning the default_geists/code/
directory for Python files (excluding __init__.py).

Use this constant instead of hardcoding geist counts in code or documentation.
Automated tests verify that documentation stays synchronised with this count.
"""

# Count Tracery geists (*.yaml files)
_tracery_geist_files = list((_default_geists_dir / "tracery").glob("*.yaml"))
TRACERY_GEIST_COUNT = len(_tracery_geist_files)
"""Number of Tracery-based geists (.yaml files) bundled with GeistFabrik.

This count is computed programmatically by scanning the default_geists/tracery/
directory for YAML files.

Use this constant instead of hardcoding geist counts in code or documentation.
Automated tests verify that documentation stays synchronised with this count.
"""

# Total count
TOTAL_GEIST_COUNT = CODE_GEIST_COUNT + TRACERY_GEIST_COUNT
"""Total number of default geists (code + Tracery) bundled with GeistFabrik.

This is simply CODE_GEIST_COUNT + TRACERY_GEIST_COUNT, computed programmatically
to ensure it always matches reality.

Use this constant instead of hardcoding geist counts in code or documentation.
Automated tests verify that documentation stays synchronised with this count.
"""

__all__ = ["CODE_GEIST_COUNT", "TRACERY_GEIST_COUNT", "TOTAL_GEIST_COUNT"]
