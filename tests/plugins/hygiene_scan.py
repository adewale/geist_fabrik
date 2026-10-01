"""AST scanner for tests that cannot fail.

The suite once passed for months while it could not fail: assertions sat in
loops over empty geist output, caps were asserted on output already below
them, and some tests asserted nothing. This scanner flags those shapes
statically, cheaply and deterministically. ``tests/unit/test_suite_hygiene.py``
runs it over the whole tree and holds the reasoned allowlist.

Only code that runs as part of the test body counts: nested ``def``s, lambdas
and classes are not walked, except that a call from the test body to a nested
function that itself asserts counts as an assertion (as does a call to a
module-level helper that asserts). Test classes are scanned at any depth.

Rules (each returns the rule code below):

* ``no-assert`` - a test with no ``assert``, no ``pytest.raises/warns/fail``,
  no ``raise AssertionError``, no checked subprocess (``check=True``,
  ``check_call``, ``check_output``), and no call to an assertion helper (a
  callee named ``assert_*`` or ``assertX...`` such as ``assertEqual``, or a
  module-level or nested function that itself asserts). Fixtures named
  ``test_*`` are not tests.
* ``always-true`` - an assertion that holds for every input: ``assert True``
  (or any truthy constant), ``len(x) >= 0``, ``0 <= len(x)``, ``len(x) > -1``
  (also for ``abs``), ``self.assertTrue(<truthy constant>)``.
* ``loop-only`` - every assertion that could prove anything passes vacuously
  when the output is empty: it sits inside a ``for`` loop over output or inside
  ``if <output>:``, or it is ``assert all(... for s in <output>)`` or
  ``assert not any(... for s in <output>)``. "Output" is an iterable whose
  source text names suggestions or results, or a name assigned from a
  ``.suggest(...)`` call. An outside assertion that an empty output also
  satisfies (``isinstance(x, list)``, ``len(x) <= N``, an always-true assert)
  does not count as a guard.
* ``isinstance-list-only`` - the test's only assertion is
  ``assert isinstance(x, list)``.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

NO_ASSERT = "no-assert"
ALWAYS_TRUE = "always-true"
LOOP_ONLY = "loop-only"
ISINSTANCE_LIST_ONLY = "isinstance-list-only"

RULES = (NO_ASSERT, ALWAYS_TRUE, LOOP_ONLY, ISINSTANCE_LIST_ONLY)

_OUTPUT_NAME = re.compile(r"suggest|result", re.IGNORECASE)
# ``assert_called_once_with``, ``assert_valid_suggestions``, ``assertEqual``;
# not ``assertions_disabled``.
_ASSERT_HELPER = re.compile(r"^assert(?:_|[A-Z])")
_PYTEST_ASSERTING = {"raises", "warns", "fail", "deprecated_call"}
_NON_NEGATIVE_CALLS = {"len", "abs"}
_NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


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


def _walk_body(nodes: Iterable[ast.AST]) -> list[ast.AST]:
    """Every node that runs as part of ``nodes``, without entering nested scopes.

    A nested ``def``/lambda/class is returned itself (so callers can find it)
    but its body is not: an assertion there runs only if something calls it.
    """
    found: list[ast.AST] = []
    stack: list[ast.AST] = list(reversed(list(nodes)))
    while stack:
        node = stack.pop()
        found.append(node)
        if not isinstance(node, _NESTED_SCOPES):
            stack.extend(reversed(list(ast.iter_child_nodes(node))))
    return found


class _AssertionFinder:
    """Locate assertion nodes in a function body, given module-local helpers."""

    def __init__(self, asserting_helpers: set[str]) -> None:
        self.asserting_helpers = asserting_helpers

    def is_assertion(self, node: ast.AST, local_helpers: set[str]) -> bool:
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
            if _ASSERT_HELPER.match(name):
                return True
            return isinstance(node.func, ast.Name) and (
                name in self.asserting_helpers or name in local_helpers
            )
        return False

    def assertions(self, body: list[ast.stmt]) -> list[ast.AST]:
        nodes = _walk_body(body)
        # A nested function that asserts counts only where the body calls it.
        nested = {
            node.name: node
            for node in nodes
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        local_helpers: set[str] = set()
        changed = True
        while changed:
            changed = False
            for name, func in nested.items():
                if name not in local_helpers and any(
                    self.is_assertion(n, local_helpers) for n in _walk_body(func.body)
                ):
                    local_helpers.add(name)
                    changed = True
        return [node for node in nodes if self.is_assertion(node, local_helpers)]


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


def _is_always_true_assertion(node: ast.AST) -> bool:
    if isinstance(node, ast.Assert):
        return _is_always_true(node.test)
    if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
        name = _callee_name(node)
        value = bool(node.args[0].value)
        return (name == "assertTrue" and value) or (name == "assertFalse" and not value)
    return False


def _is_isinstance_list(node: ast.AST) -> bool:
    """``assert isinstance(x, list)`` or ``self.assertIsInstance(x, list)``."""
    if isinstance(node, ast.Assert) and isinstance(node.test, ast.Call):
        call, expected = node.test, "isinstance"
    elif isinstance(node, ast.Call):
        call, expected = node, "assertIsInstance"
    else:
        return False
    return (
        _callee_name(call) == expected
        and len(call.args) == 2
        and isinstance(call.args[1], ast.Name)
        and call.args[1].id == "list"
    )


def _proves_nothing_about_size(node: ast.AST) -> bool:
    """An assertion an empty output also satisfies, so it is no non-empty guard."""
    if _is_always_true_assertion(node) or _is_isinstance_list(node):
        return True
    if not (isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare)):
        return False
    test = node.test
    if len(test.ops) != 1:
        return False
    left, op, right = test.left, test.ops[0], test.comparators[0]

    def is_len(expr: ast.expr) -> bool:
        return isinstance(expr, ast.Call) and _callee_name(expr) == "len"

    if is_len(left) and isinstance(op, (ast.Lt, ast.LtE)):
        return True
    return is_len(right) and isinstance(op, (ast.Gt, ast.GtE))


def _fails_unconditionally(node: ast.AST) -> bool:
    """``pytest.fail(...)``, ``raise AssertionError``, ``assert False``."""
    if isinstance(node, ast.Raise):
        return True
    if isinstance(node, ast.Assert):
        return isinstance(node.test, ast.Constant) and not node.test.value
    return (
        isinstance(node, ast.Call) and _is_pytest_asserting(node) and _callee_name(node) == "fail"
    )


def _output_names(body: list[ast.stmt]) -> set[str]:
    """Names the test assigns from a ``.suggest(...)`` call, whatever they are called."""
    names: set[str] = set()
    for node in _walk_body(body):
        if isinstance(node, ast.Assign):
            targets, value = list(node.targets), node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if any(
            isinstance(call, ast.Call) and _callee_name(call) == "suggest"
            for call in ast.walk(value)
        ):
            for target in targets:
                names.update(leaf.id for leaf in ast.walk(target) if isinstance(leaf, ast.Name))
    return names


class _EmptyOutput:
    """Find assertions that pass vacuously when a test's output is empty."""

    def __init__(self, body: list[ast.stmt], source: str) -> None:
        self.source = source
        self.names = _output_names(body)
        # Statement groups that run only when the output is non-empty.
        loops: list[ast.stmt] = []
        branches: list[ast.stmt] = []
        for node in _walk_body(body):
            if isinstance(node, (ast.For, ast.AsyncFor)) and self.names_output(node.iter):
                loops.append(node)
            elif isinstance(node, ast.If):
                if self._non_empty_test(node.test):
                    branches.extend(node.body)
                elif (
                    isinstance(node.test, ast.UnaryOp)
                    and isinstance(node.test.op, ast.Not)
                    and self._non_empty_test(node.test.operand)
                ):
                    branches.extend(node.orelse)
        self._in_loop = {id(child) for child in _walk_body(loops)}
        self._in_branch = {id(child) for child in _walk_body(branches)}

    def names_output(self, node: ast.AST) -> bool:
        if _OUTPUT_NAME.search(ast.get_source_segment(self.source, node) or ""):
            return True
        return any(isinstance(leaf, ast.Name) and leaf.id in self.names for leaf in ast.walk(node))

    def _non_empty_test(self, test: ast.expr) -> bool:
        """``if out:``, ``if len(out):``, ``if len(out) > 0:`` and the like."""
        if isinstance(test, (ast.Name, ast.Attribute, ast.Subscript)):
            return self.names_output(test)
        if isinstance(test, ast.Call) and _callee_name(test) == "len":
            return self.names_output(test)
        if (
            isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.left, ast.Call)
            and _callee_name(test.left) == "len"
            and isinstance(test.ops[0], (ast.Gt, ast.GtE, ast.NotEq))
        ):
            return self.names_output(test.left)
        return False

    def _quantifies_output(self, node: ast.expr, quantifier: str) -> bool:
        return (
            isinstance(node, ast.Call)
            and _callee_name(node) == quantifier
            and len(node.args) == 1
            and isinstance(node.args[0], (ast.GeneratorExp, ast.ListComp))
            and any(self.names_output(gen.iter) for gen in node.args[0].generators)
        )

    def vacuous(self, node: ast.AST) -> bool:
        if id(node) in self._in_loop:
            return True
        if id(node) in self._in_branch:
            # ``if out: pytest.fail(...)`` is a real check that ``out`` is empty;
            # only a check that is merely skipped on empty output is vacuous.
            return not _fails_unconditionally(node)
        if not isinstance(node, ast.Assert):
            return False
        test = node.test
        if self._quantifies_output(test, "all"):
            return True
        return (
            isinstance(test, ast.UnaryOp)
            and isinstance(test.op, ast.Not)
            and self._quantifies_output(test.operand, "any")
        )


def _test_functions(
    body: list[ast.stmt], prefix: str = ""
) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Test functions and methods, including those of nested ``Test*`` classes."""
    tests: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for node in body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test")
            and not _is_fixture(node)
        ):
            tests.append((f"{prefix}{node.name}", node))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            tests.extend(_test_functions(node.body, f"{prefix}{node.name}::"))
    return tests


def scan_source(source: str, path: str) -> list[Violation]:
    """Return every violation in one test module's source."""
    tree = ast.parse(source)
    finder = _AssertionFinder(_asserting_helpers(tree))
    violations: list[Violation] = []
    for name, func in _test_functions(tree.body):
        test_id = f"{path}::{name}"
        assertions = finder.assertions(func.body)
        if not assertions:
            violations.append(Violation(test_id, NO_ASSERT, func.lineno, "asserts nothing"))
            continue
        for node in assertions:
            if isinstance(node, (ast.Assert, ast.Call)) and _is_always_true_assertion(node):
                text = ast.get_source_segment(source, node) or "assert ..."
                violations.append(Violation(test_id, ALWAYS_TRUE, node.lineno, text))
        empty = _EmptyOutput(func.body, source)
        vacuous = [node for node in assertions if empty.vacuous(node)]
        if vacuous and all(
            node in vacuous or _proves_nothing_about_size(node) for node in assertions
        ):
            violations.append(
                Violation(
                    test_id,
                    LOOP_ONLY,
                    func.lineno,
                    "every assertion passes vacuously on empty output (inside a loop "
                    "or `if` over it, or all()/not any() over it)",
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
        ids.update(f"{relative}::{name}" for name, _ in _test_functions(tree.body))
    return ids


def stale_entries(
    allowlist: Iterable[tuple[str, str]],
    violations: Iterable[tuple[str, str]],
    existing: Iterable[str],
) -> list[str]:
    """Allowlisted ``(test id, rule)`` pairs that no longer violate, each with why."""
    violating, present = set(violations), set(existing)
    return [
        f"{test_id} [{rule}]: " + ("test no longer exists" if test_id not in present else "fixed")
        for test_id, rule in allowlist
        if (test_id, rule) not in violating
    ]
