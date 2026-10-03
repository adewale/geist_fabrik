#!/usr/bin/env python3
"""Render a pytest JUnit XML report as a Markdown table for a CI job summary.

Used by .github/workflows/scheduled-tiers.yml. It only reports: pass/fail is
decided by the pytest step's exit code, never by this script.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET  # nosec B405 - parses our own pytest output
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaseResult:
    """One test case from a JUnit report."""

    name: str
    outcome: str
    seconds: float


def read_cases(report: Path) -> list[CaseResult]:
    """Return every test case in a pytest JUnit XML report."""
    root = ET.parse(report).getroot()  # nosec B314 - trusted, locally generated file
    cases = []
    for case in root.iter("testcase"):
        outcome = "passed"
        for child, label in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
            if case.find(child) is not None:
                outcome = label
                break
        name = f"{case.get('classname', '')}::{case.get('name', '')}"
        cases.append(CaseResult(name, outcome, float(case.get("time", "0") or 0)))
    return cases


def render(title: str, cases: list[CaseResult]) -> str:
    """Markdown summary: outcome counts, then every case slowest first."""
    counts: dict[str, int] = {}
    for case in cases:
        counts[case.outcome] = counts.get(case.outcome, 0) + 1
    tally = ", ".join(f"{n} {outcome}" for outcome, n in sorted(counts.items())) or "no tests"
    lines = [f"### {title}", "", tally, "", "| Test | Outcome | Seconds |", "|---|---|---:|"]
    for case in sorted(cases, key=lambda c: c.seconds, reverse=True):
        lines.append(f"| `{case.name}` | {case.outcome} | {case.seconds:.2f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--title", default=None)
    args = parser.parse_args(argv)
    if not args.report.is_file():
        print(f"### {args.report.name}\n\nNo JUnit report was produced.")
        return 1
    print(render(args.title or args.report.stem, read_cases(args.report)), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
