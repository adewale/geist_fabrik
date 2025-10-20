#!/usr/bin/env python3
"""Check which implementation phases are complete based on acceptance criteria.

This script verifies acceptance criteria from specs/acceptance_criteria.md and reports
which phases are complete, in progress, or not started.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def parse_acceptance_criteria(file_path: Path) -> Dict[str, List[Tuple[str, str, str]]]:
    """Parse acceptance criteria from markdown file.

    Returns:
        Dict mapping phase numbers to lists of (id, status, criteria, verification_cmd) tuples
    """
    content = file_path.read_text()
    phases: Dict[str, List[Tuple[str, str, str]]] = {}

    # Match phase sections like "## Phase 0: Project Scaffolding"
    phase_pattern = r"## Phase (\d+):"
    # Match table rows like "| AC-0.1 | ⬜ | ... | `command` |"
    ac_pattern = r"\| (AC-\d+\.\d+) \| ([⬜🔄✅⚠️❌]) \| ([^|]+) \| `([^`]+)` \|"

    current_phase = None
    for line in content.split("\n"):
        phase_match = re.match(phase_pattern, line)
        if phase_match:
            current_phase = phase_match.group(1)
            phases[current_phase] = []
            continue

        if current_phase is not None:
            ac_match = re.match(ac_pattern, line)
            if ac_match:
                ac_id, status, criteria, verification = ac_match.groups()
                phases[current_phase].append((ac_id, status, criteria.strip(), verification))

    return phases


def run_verification_command(cmd: str) -> bool:
    """Run a verification command and return True if it succeeds."""
    try:
        # Handle compound commands with &&
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            timeout=30,
            cwd=Path(__file__).parent.parent,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False


def check_phase(phase_num: str, criteria: List[Tuple[str, str, str]]) -> Tuple[int, int, int]:
    """Check all criteria for a phase.

    Returns:
        Tuple of (total, passed, failed) counts
    """
    total = len(criteria)
    passed = 0
    failed = 0

    for ac_id, status, description, verification in criteria:
        # Skip if already marked as complete in the spec
        if status == "✅":
            passed += 1
            continue

        # Run verification command
        if run_verification_command(verification):
            passed += 1
        else:
            failed += 1

    return total, passed, failed


def main() -> int:
    """Check phase completion and report results."""
    # Find the acceptance criteria file
    repo_root = Path(__file__).parent.parent
    ac_file = repo_root / "specs" / "acceptance_criteria.md"

    if not ac_file.exists():
        print(f"Error: Could not find {ac_file}")
        return 1

    print("GeistFabrik Phase Completion Checker")
    print("=" * 80)
    print()

    phases = parse_acceptance_criteria(ac_file)

    if not phases:
        print("Error: No phases found in acceptance criteria")
        return 1

    overall_total = 0
    overall_passed = 0
    overall_failed = 0

    for phase_num in sorted(phases.keys(), key=int):
        criteria = phases[phase_num]
        total, passed, failed = check_phase(phase_num, criteria)

        overall_total += total
        overall_passed += passed
        overall_failed += failed

        # Determine phase status
        if passed == total:
            status_icon = "✅"
            status_text = "COMPLETE"
        elif passed > 0:
            status_icon = "🔄"
            status_text = "IN PROGRESS"
        else:
            status_icon = "⬜"
            status_text = "NOT STARTED"

        print(f"Phase {phase_num}: {status_icon} {status_text}")
        print(f"  Passed: {passed}/{total} criteria")
        if failed > 0:
            print(f"  Failed: {failed} criteria")
        print()

    print("=" * 80)
    print(f"Overall: {overall_passed}/{overall_total} criteria passed")

    if overall_passed == overall_total:
        print("🎉 All phases complete!")
        return 0
    else:
        print(f"📋 {overall_failed} criteria remaining")
        return 1


if __name__ == "__main__":
    sys.exit(main())
