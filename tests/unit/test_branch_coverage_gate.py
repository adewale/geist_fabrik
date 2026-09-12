"""Tests for the branch-only coverage gate."""

import tomllib
from pathlib import Path
from typing import cast

from scripts.check_branch_coverage import BranchCoverage, branch_totals, files_under_root


class _FakeCoverage:
    def measured_files(self) -> tuple[str, ...]:
        return ("complete.py", "partial.py")

    def branch_stats(self, morf: str) -> dict[int, tuple[int, int]]:
        if morf == "complete.py":
            return {1: (60, 30)}
        return {1: (40, 10)}


def test_branch_totals_do_not_include_statement_coverage() -> None:
    """A statement-heavy report cannot conceal branch coverage below the gate."""
    source = cast(BranchCoverage, _FakeCoverage())
    assert branch_totals(source) == (40, 100)


def test_coverage_script_is_repository_local() -> None:
    assert Path("scripts/check_branch_coverage.py").is_file()


def test_dynamic_plugins_outside_source_root_are_not_counted(tmp_path: Path) -> None:
    source_root = tmp_path / "src/geistfabrik"
    source_root.mkdir(parents=True)
    project_file = source_root / "vault.py"
    plugin_file = tmp_path / "pytest-tmp/geistfabrik.user_geists.plugin.py"
    assert files_under_root([str(project_file), str(plugin_file)], source_root) == (
        str(project_file),
    )


def test_branch_stats_api_has_an_explicit_compatible_dependency() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())
    assert "coverage[toml]>=7.7" in project["dependency-groups"]["dev"]
