"""AST scanner for tests that cannot fail.

The suite once passed for months while it could not fail: assertions sat in
loops over empty geist output, caps were asserted on output already below
them, and some tests asserted nothing. This scanner flags those shapes
statically, cheaply and deterministically. ``tests/unit/test_suite_hygiene.py``
runs it over the whole tree and holds the reasoned allowlist.

Rules (each returns the rule code below):

* ``no-assert`` - a test with no ``assert``, no ``pytest.raises/warns/fail``,
  no ``raise AssertionError``, no checked subprocess (``check=True``,
  ``check_call``, ``check_output``), and no call to an assertion helper (any
  callee whose name starts with ``assert``, or a function defined in the same
  module that itself asserts). Fixtures named ``test_*`` are not tests.
* ``always-true`` - an assert that holds for every input: ``assert True`` (or
  any truthy constant), ``len(x) >= 0``, ``0 <= len(x)``, ``len(x) > -1`` (also
  for ``abs``).
* ``loop-only`` - every assertion in the test sits inside a ``for`` loop (or an
  ``all(...)`` generator) over an iterable whose source text names suggestions
  or results, so empty output passes vacuously.
* ``isinstance-list-only`` - the test's only assertion is
  ``assert isinstance(x, list)``.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

NO_ASSERT = "no-assert"
ALWAYS_TRUE = "always-true"
LOOP_ONLY = "loop-only"
ISINSTANCE_LIST_ONLY = "isinstance-list-only"

RULES = (NO_ASSERT, ALWAYS_TRUE, LOOP_ONLY, ISINSTANCE_LIST_ONLY)

_OUTPUT_NAME = re.compile(r"suggest|result", re.IGNORECASE)
_PYTEST_ASSERTING = {"raises", "warns", "fail", "deprecated_call"}
_NON_NEGATIVE_CALLS = {"len", "abs"}


@dataclass(frozen=True)
class Violation:
    test_id: str  # e.g. tests/unit/test_x.py::TestY::test_z
    rule: str
    line: int
    detail: str


def _callee_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_pytest_asserting(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _PYTEST_ASSERTING
        and isinstance(func.value, ast.Name)
        and func.value.id == "pytest"
    )


def _is_checked_subprocess(call: ast.Call) -> bool:
    """``subprocess.check_call/check_output`` or ``run(..., check=True)`` raise on failure."""
    name = _callee_name(call)
    if name in {"check_call", "check_output"}:
        return True
    return name == "run" and any(
        kw.arg == "check" and isinstance(kw.value, ast.Constant) and kw.value.value is True
        for kw in call.keywords
    )


def _is_fixture(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in func.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", "")
        if name == "fixture":
            return True
    return False


def _is_assertion_error_raise(node: ast.Raise) -> bool:
    exc = node.exc
    if isinstance(exc, ast.Call):
        exc = exc.func
    return isinstance(exc, ast.Name) and exc.id == "AssertionError"


class _AssertionFinder:
    """Locate assertion nodes in a function body, given module-local helpers."""

    def __init__(self, asserting_helpers: set[str]) -> None:
        self.asserting_helpers = asserting_helpers

    def is_assertion(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Raise):
            return _is_assertion_error_raise(node)
        if isinstance(node, ast.Call):
            if _is_pytest_asserting(node) or _is_checked_subprocess(node):
                return True
            name = _callee_name(node)
            if name is None:
                return False
            return name.startswith("assert") or (
                isinstance(node.func, ast.Name) and name in self.asserting_helpers
            )
        return False

    def assertions(self, body: list[ast.stmt]) -> list[ast.AST]:
        found: list[ast.AST] = []
        for stmt in body:
            for node in ast.walk(stmt):
                if self.is_assertion(node):
                    found.append(node)
        return found


def _asserting_helpers(tree: ast.Module) -> set[str]:
    """Module-level non-test functions that (transitively) assert."""
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("test")
    }
    helpers: set[str] = set()
    changed = True
    while changed:
        changed = False
        finder = _AssertionFinder(helpers)
        for name, func in functions.items():
            if name not in helpers and finder.assertions(func.body):
                helpers.add(name)
                changed = True
    return helpers


def _is_always_true(test: ast.expr) -> bool:
    if isinstance(test, ast.Constant):
        return bool(test.value)
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1):
        return False
    left, op, right = test.left, test.ops[0], test.comparators[0]

    def non_negative_call(node: ast.expr) -> bool:
        return isinstance(node, ast.Call) and _callee_name(node) in _NON_NEGATIVE_CALLS

    def number(node: ast.expr) -> float | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float))
        ):
            return -float(node.operand.value)
        return None

    if non_negative_call(left):
        bound = number(right)
        if bound is not None:
            return (isinstance(op, ast.GtE) and bound <= 0) or (
                isinstance(op, ast.Gt) and bound < 0
            )
    if non_negative_call(right):
        bound = number(left)
        if bound is not None:
            return (isinstance(op, ast.LtE) and bound <= 0) or (
                isinstance(op, ast.Lt) and bound < 0
            )
    return False


def _names_output(node: ast.AST, source: str) -> bool:
    text = ast.get_source_segment(source, node) or ""
    return bool(_OUTPUT_NAME.search(text))


def _output_loop_ranges(func: ast.AST, source: str) -> list[ast.AST]:
    """``for`` loops and ``all(<genexp>)`` calls that iterate over output."""
    loops: list[ast.AST] = []
    for node in ast.walk(func):
        if isinstance(node, (ast.For, ast.AsyncFor)) and _names_output(node.iter, source):
            loops.append(node)
        elif (
            isinstance(node, ast.Call)
            and _callee_name(node) == "all"
            and len(node.args) == 1
            and isinstance(node.args[0], (ast.GeneratorExp, ast.ListComp))
            and any(_names_output(gen.iter, source) for gen in node.args[0].generators)
        ):
            loops.append(node)
    return loops


def _inside(node: ast.AST, containers: list[ast.AST]) -> bool:
    for container in containers:
        if node is container:
            continue
        for child in ast.walk(container):
            if child is node:
                return True
    return False


def _loop_bound(node: ast.AST, loops: list[ast.AST]) -> bool:
    """True if the assertion only runs per item, or is ``assert all(<over output>)``."""
    if isinstance(node, ast.Assert) and any(node.test is loop for loop in loops):
        return True
    return _inside(node, loops)


def _is_isinstance_list(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assert) or not isinstance(node.test, ast.Call):
        return False
    call = node.test
    return (
        isinstance(call.func, ast.Name)
        and call.func.id == "isinstance"
        and len(call.args) == 2
        and isinstance(call.args[1], ast.Name)
        and call.args[1].id == "list"
    )


def _test_functions(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    tests: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")
            and not _is_fixture(node)
        ):
            tests.append((node.name, node))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for item in node.body:
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name.startswith("test")
                    and not _is_fixture(item)
                ):
                    tests.append((f"{node.name}::{item.name}", item))
    return tests


def scan_source(source: str, path: str) -> list[Violation]:
    """Return every violation in one test module's source."""
    tree = ast.parse(source)
    finder = _AssertionFinder(_asserting_helpers(tree))
    violations: list[Violation] = []
    for name, func in _test_functions(tree):
        test_id = f"{path}::{name}"
        assertions = finder.assertions(func.body)
        if not assertions:
            violations.append(Violation(test_id, NO_ASSERT, func.lineno, "asserts nothing"))
            continue
        for node in assertions:
            if isinstance(node, ast.Assert) and _is_always_true(node.test):
                text = ast.get_source_segment(source, node) or "assert ..."
                violations.append(Violation(test_id, ALWAYS_TRUE, node.lineno, text))
        loops = _output_loop_ranges(func, source)
        if loops and all(_loop_bound(node, loops) for node in assertions):
            violations.append(
                Violation(
                    test_id,
                    LOOP_ONLY,
                    func.lineno,
                    "every assertion is inside a loop over output that may be empty",
                )
            )
        if len(assertions) == 1 and _is_isinstance_list(assertions[0]):
            violations.append(
                Violation(
                    test_id,
                    ISINSTANCE_LIST_ONLY,
                    func.lineno,
                    "only asserts isinstance(..., list)",
                )
            )
    return violations


def scan_tree(root: Path, repo_root: Path) -> list[Violation]:
    """Scan every ``test_*.py`` under ``root``; ids are relative to ``repo_root``."""
    violations: list[Violation] = []
    for path in sorted(root.rglob("test_*.py")):
        relative = path.relative_to(repo_root).as_posix()
        violations.extend(scan_source(path.read_text(encoding="utf-8"), relative))
    return violations


def collect_test_ids(root: Path, repo_root: Path) -> set[str]:
    """Every test id the scanner considers, for allowlist staleness checks."""
    ids: set[str] = set()
    for path in sorted(root.rglob("test_*.py")):
        relative = path.relative_to(repo_root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        ids.update(f"{relative}::{name}" for name, _ in _test_functions(tree))
    return ids
