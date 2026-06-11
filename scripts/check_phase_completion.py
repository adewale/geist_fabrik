#!/usr/bin/env python3
"""Verify acceptance criteria from specs/acceptance_criteria.md by RUNNING them.

Root-cause history (see LESSONS_LEARNED.md "Specified But Never Built:
Self-Attesting Status Is Not Verification"):
the previous version of this script trusted the spec's own status emoji
(``if status == "✅": passed += 1``) and used a rigid regex that *silently
dropped* 95 of 231 criteria whose verification cell carried a trailing
annotation or was prose. "All criteria pass" could therefore be true while
41% of them were never looked at. That is exactly how the spec drifted away
from the code without anyone noticing.

This version is **verify, never trust**:

* Every ``AC-x.y`` row is parsed. A row that cannot be classified is a hard
  error, not a silent skip.
* The spec's status emoji is ignored for pass/fail. A criterion passes iff its
  verification command is run and exits 0.
* Each criterion is either:
    - **AUTO** — its Verification cell *starts with* a backtick-wrapped command
      (optionally followed by a human annotation). The command is executed.
    - **MANUAL** — anything else (prose like "Verify X manually", or a criterion
      that needs human judgement / a platform we can't run here). MANUAL
      criteria are reported and counted but do not fail the gate.
* The gate (exit code) fails if **any AUTO criterion fails** or **any row is
  unparseable** or **a MANUAL cell contains an un-wrapped command** (a command
  written as prose would otherwise masquerade as "manual" and never run).

Usage:
    python scripts/check_phase_completion.py            # gate (CI/validate.sh)
    python scripts/check_phase_completion.py --verbose  # per-criterion detail
    python scripts/check_phase_completion.py --list      # classify only, no run
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AC_FILE = REPO_ROOT / "specs" / "acceptance_criteria.md"

# Per-command wall-clock budget. File-level pytest runs are the slow case.
COMMAND_TIMEOUT = 180

AC_ROW = re.compile(r"^\|\s*(AC-\d+\.\d+)\s*\|")
PHASE_HEADER = re.compile(r"^## Phase (\d+):")
# A backtick-wrapped span anywhere in a cell.
BACKTICK_SPAN = re.compile(r"`([^`]+)`")
# Heuristic: prose that actually hides a runnable command (so it doesn't slip
# through as "manual" and never get verified). Deliberately narrow to avoid
# false positives on cells that merely *mention* tests.
COMMAND_SMELL = re.compile(r"(?:\buv run\b|::test_|^\s*pytest\b)")

# The project's canonical way to run the suite (see scripts/validate.sh and
# .github/workflows/test.yml): the "not slow" marker swaps in the
# SentenceTransformerStub (tests/conftest.py::pytest_configure) so tests run
# fast and offline, without the real sentence-transformers/torch stack. The AC
# table predates the stub and lists bare ``uv run pytest …`` commands, so we
# normalise them to the canonical invocation here rather than repeating the
# marker in ~150 spec cells.
PYTEST_INVOCATION = re.compile(r"\buv run pytest\b")
STD_MARKER = '-m "not slow and not benchmark"'
BRACE_TOKEN = re.compile(r"(\S*)\{([^{}]+)\}(\S*)")


def expand_braces(cmd: str) -> str:
    """Expand ``a{x,y}b`` -> ``ax by`` (shell-independent; /bin/sh may be dash).

    The AC table uses brace lists to name sibling test nodes, e.g.
    ``test_sync_{modified_file,no_changes}``. Only single, non-nested braces
    occur, so one pass per token is enough.
    """
    while True:
        m = BRACE_TOKEN.search(cmd)
        if not m:
            return cmd
        prefix, options, suffix = m.group(1), m.group(2), m.group(3)
        expanded = " ".join(f"{prefix}{opt.strip()}{suffix}" for opt in options.split(","))
        cmd = cmd[: m.start()] + expanded + cmd[m.end() :]


def normalize_command(cmd: str) -> str:
    """Run pytest commands the way the project actually runs them.

    For ``uv run pytest`` commands: expand brace node-lists and, unless the
    command already pins markers, append the canonical ``not slow``/``not
    benchmark`` filter that activates the embedding stub. Non-pytest commands
    are returned unchanged.
    """
    if not PYTEST_INVOCATION.search(cmd):
        return cmd
    cmd = expand_braces(cmd)
    if " -m " not in cmd:
        cmd = f"{cmd} {STD_MARKER}"
    return cmd


TARGET = re.compile(r"^tests/[\w/]+\.py(::[\w-]+)?$")


def pytest_targets(cmd: str) -> list[str]:
    """The ``tests/…`` file/node targets named by a pytest command (braces expanded)."""
    return [tok for tok in expand_braces(cmd).split() if TARGET.match(tok)]


@dataclass(frozen=True)
class Criterion:
    ac_id: str
    phase: str
    description: str
    raw_verification: str
    is_auto: bool
    command: str | None  # set iff is_auto
    manual_reason: str | None  # set iff not is_auto


def parse_criteria(text: str) -> tuple[list[Criterion], list[str]]:
    """Parse every AC row. Returns (criteria, parse_errors).

    A parse error is a row that looks like an AC row but does not have the
    four expected ``| id | status | criteria | verification |`` columns, or a
    MANUAL cell that contains an un-wrapped command. Parse errors fail the gate
    so the spec can never again silently swallow a criterion.
    """
    criteria: list[Criterion] = []
    errors: list[str] = []
    phase = "?"

    for lineno, line in enumerate(text.splitlines(), start=1):
        header = PHASE_HEADER.match(line)
        if header:
            phase = header.group(1)
            continue

        if not AC_ROW.match(line):
            continue

        # Every AC row in this file is a clean 4-column table row (5 pipes).
        cells = [c.strip() for c in line.split("|")]
        # cells[0] and cells[-1] are the empty outer edges.
        if len(cells) != 6:
            errors.append(
                f"line {lineno}: {cells[1] if len(cells) > 1 else line!r} "
                f"has {len(cells) - 2} columns, expected 4"
            )
            continue

        ac_id, _status, description, verification = cells[1], cells[2], cells[3], cells[4]

        if verification.startswith("`"):
            spans = BACKTICK_SPAN.findall(verification)
            command = spans[0] if spans else None
            if not command:
                errors.append(f"{ac_id}: cell starts with backtick but no command found")
                continue
            criteria.append(Criterion(ac_id, phase, description, verification, True, command, None))
        else:
            # MANUAL. Guard against a command smuggled in as prose.
            if COMMAND_SMELL.search(verification):
                errors.append(
                    f"{ac_id}: verification looks like a command but is not "
                    f"backtick-wrapped (so it would never run): {verification!r}"
                )
                continue
            reason = verification
            if reason.lower().startswith("manual"):
                reason = reason.split(":", 1)[-1].strip() or reason
            criteria.append(Criterion(ac_id, phase, description, verification, False, None, reason))

    return criteria, errors


_run_cache: dict[str, tuple[bool, str]] = {}


def run_command(cmd: str) -> tuple[bool, str]:
    """Run a verification command; return (passed, short_detail).

    Results are memoised by command string. Many criteria in a phase verify the
    same test module (e.g. all of Phase 8 -> test_metadata_system.py), so after
    coarsening they normalise to an identical command; without this cache the
    same file would be run a dozen times.
    """
    if cmd in _run_cache:
        return _run_cache[cmd]
    try:
        result = subprocess.run(  # noqa: S602 - trusted, repo-local spec commands
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            cwd=REPO_ROOT,
        )
    except subprocess.TimeoutExpired:
        outcome = (False, f"timed out after {COMMAND_TIMEOUT}s")
    except OSError as exc:
        outcome = (False, f"could not launch: {exc}")
    else:
        if result.returncode == 0:
            outcome = (True, "")
        else:
            tail = (result.stderr or result.stdout or "").strip().splitlines()
            detail = tail[-1] if tail else f"exit {result.returncode}"
            outcome = (False, f"exit {result.returncode}: {detail[:160]}")
    _run_cache[cmd] = outcome
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verbose", action="store_true", help="print every criterion's classification/result"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="classify criteria but do not run commands (fast triage)",
    )
    args = parser.parse_args()

    if not AC_FILE.exists():
        print(f"Error: {AC_FILE} not found")
        return 2

    criteria, errors = parse_criteria(AC_FILE.read_text())

    if not criteria:
        print("Error: no acceptance criteria parsed")
        return 2

    auto = [c for c in criteria if c.is_auto]
    manual = [c for c in criteria if not c.is_auto]

    print("GeistFabrik Acceptance-Criteria Verifier")
    print("=" * 80)
    print(f"Parsed {len(criteria)} criteria: {len(auto)} AUTO, {len(manual)} MANUAL")
    if errors:
        print(f"{len(errors)} PARSE ERROR(S) — these fail the gate:")
        for err in errors:
            print(f"  ✗ {err}")
    print()

    if args.list:
        for c in criteria:
            if c.is_auto:
                kind = f"AUTO  {normalize_command(c.command or '')}"
            else:
                kind = f"MANUAL  ({c.manual_reason})"
            print(f"  {c.ac_id:<10} {kind}")
        return 0 if not errors else 1

    pytest_acs = [c for c in auto if PYTEST_INVOCATION.search(c.command or "")]
    other_acs = [c for c in auto if not PYTEST_INVOCATION.search(c.command or "")]

    failures: list[tuple[Criterion, str]] = []

    # Run every pytest target in ONE process. conftest imports the embedding
    # stack (~5s) once per process, so spawning ~60 separate pytest runs would
    # cost minutes; batching pays that once, exactly like scripts/validate.sh. A
    # renamed/removed target still fails the batch (pytest exits non-zero on an
    # unmatched node), so drift is still caught. Only on a red batch do we re-run
    # each criterion to attribute the failure.
    targets: list[str] = []
    files = {t for c in pytest_acs for t in pytest_targets(c.command or "") if "::" not in t}
    for c in pytest_acs:
        for t in pytest_targets(c.command or ""):
            keep = t if "::" not in t else (t if t.split("::")[0] not in files else None)
            if keep and keep not in targets:
                targets.append(keep)

    if pytest_acs:
        batch = f"uv run pytest {' '.join(targets)} {STD_MARKER} --no-cov -q -p no:cacheprovider"
        batch_ok, batch_detail = run_command(batch)
        if batch_ok:
            if args.verbose:
                print(f"  ✓ {'batch':<12} {len(pytest_acs)} pytest criteria via 1 run")
        else:
            print(f"  ✗ pytest batch failed ({batch_detail}); attributing per-criterion…")
            for c in pytest_acs:
                passed, detail = run_command(normalize_command(c.command or ""))
                if not passed:
                    failures.append((c, detail))
                    print(f"  ✗ {c.ac_id:<10} AUTO   {normalize_command(c.command or '')}")
                    print(f"      {detail}")

    for c in other_acs:
        command = normalize_command(c.command or "")
        passed, detail = run_command(command)
        if passed:
            if args.verbose:
                print(f"  ✓ {c.ac_id:<10} AUTO   {command}")
        else:
            failures.append((c, detail))
            print(f"  ✗ {c.ac_id:<10} AUTO   {command}")
            print(f"      {detail}")

    if args.verbose:
        for c in manual:
            print(f"  · {c.ac_id:<10} MANUAL {c.manual_reason}")

    print()
    print("=" * 80)
    print(
        f"AUTO: {len(auto) - len(failures)}/{len(auto)} passed   "
        f"MANUAL (not auto-verifiable): {len(manual)}   "
        f"PARSE ERRORS: {len(errors)}"
    )

    if failures or errors:
        print()
        if failures:
            print(f"✗ {len(failures)} AUTO criteria FAILED:")
            for c, detail in failures:
                print(f"    {c.ac_id}: {detail}")
        if errors:
            print(f"✗ {len(errors)} rows could not be parsed (silent-drop guard).")
        print()
        print("Gate FAILED. Fix the criterion or its verification command, or — if the")
        print("criterion is genuinely not machine-verifiable — reword its Verification")
        print("cell as prose (it will be reported as MANUAL).")
        return 1

    print(f"✓ All {len(auto)} AUTO criteria pass. {len(manual)} criteria are MANUAL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
