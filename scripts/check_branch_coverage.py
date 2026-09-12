#!/usr/bin/env python3
"""Enforce a true branch-only coverage threshold from a coverage.py data file."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Protocol

import coverage


class BranchCoverage(Protocol):
    """Subset of coverage.Coverage used by the branch gate."""

    def measured_files(self) -> Iterable[str]: ...

    def branch_stats(self, morf: str) -> Mapping[int, tuple[int, int]]: ...


def branch_totals(source: BranchCoverage) -> tuple[int, int]:
    """Return covered and total branch destinations across measured files."""
    covered = 0
    total = 0
    for filename in source.measured_files():
        for destinations, taken in source.branch_stats(filename).values():
            total += destinations
            covered += taken
    return covered, total


def files_under_root(files: Iterable[str], source_root: Path) -> tuple[str, ...]:
    """Exclude dynamically loaded user plugins outside the project source tree."""
    resolved_root = source_root.resolve()
    return tuple(
        filename
        for filename in files
        if Path(filename).resolve().is_relative_to(resolved_root)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum", type=float, required=True, help="minimum branch percentage")
    parser.add_argument("--data-file", type=Path, default=Path(".coverage"))
    parser.add_argument("--source-root", type=Path, default=Path("src/geistfabrik"))
    args = parser.parse_args()

    cov = coverage.Coverage(data_file=str(args.data_file))
    cov.load()
    data = cov.get_data()
    measured_files = files_under_root(data.measured_files(), args.source_root)
    covered, total = branch_totals(_CoverageAdapter(cov, measured_files))
    if total == 0:
        print("Branch coverage gate failed: no branch data was measured")
        return 1

    percentage = covered * 100.0 / total
    print(f"Branch coverage: {covered}/{total} ({percentage:.2f}%), required {args.minimum:.2f}%")
    return 0 if percentage >= args.minimum else 1


class _CoverageAdapter:
    """Expose measured data and analysis through the gate protocol."""

    def __init__(self, cov: coverage.Coverage, files: Iterable[str]) -> None:
        self._coverage = cov
        self._files = tuple(files)

    def measured_files(self) -> Iterable[str]:
        return self._files

    def branch_stats(self, morf: str) -> Mapping[int, tuple[int, int]]:
        return self._coverage.branch_stats(morf)


if __name__ == "__main__":
    raise SystemExit(main())
