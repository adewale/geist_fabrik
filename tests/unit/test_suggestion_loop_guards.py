"""Meta-test: a loop over geist output must not be a test's only oracle.

LESSONS_LEARNED.md "A Test That Cannot Fail Is Worse Than No Test" and Iron
Rule 2 of tests/unit/GEIST_TESTING_TEMPLATE.md: assertions that live only
inside ``for s in suggestions:`` pass vacuously when the geist returns ``[]``.
That is how about seven default geists stayed dead behind green tests until
2026-06-10 (7736927). The template states the rule; this module enforces it.

A loop (or an ``assert all(... for s in suggestions)``) over a suggestions
list must be preceded, in the same test function, by a non-empty assertion on
that list, for example ``assert suggestions``, ``assert len(suggestions) >= 1``
or ``assert_valid_suggestions(suggestions, ...)`` (which asserts non-empty
unless called with ``min_count=0``). Tests about emptiness should assert
``== []`` and need no loop.

Files that predate the rule are listed in KNOWN_UNGUARDED_LOOPS. That
baseline is a ratchet: a file may not gain unguarded loops, and when a file's
count drops the baseline must be lowered in the same change, so it only ever
goes down.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = REPO_ROOT / "tests"

# Unguarded loops that predate this meta-test, per file (repository-relative).
# Ratchet: lower a number (or delete the entry) when you fix loops; never raise
# one. tests/integration/test_example_geists.py is deliberately absent: it was
# ported to assert_valid_suggestions when this guard was introduced.
KNOWN_UNGUARDED_LOOPS: dict[str, int] = {
    "tests/integration/test_phase3b_regression.py": 1,
    "tests/integration/test_virtual_notes_regression.py": 1,
    "tests/unit/test_bridge_hunter.py": 2,
    "tests/unit/test_creative_collision.py": 1,
    "tests/unit/test_density_inversion.py": 2,
    "tests/unit/test_hidden_hub.py": 3,
    "tests/unit/test_method_scrambler.py": 1,
    "tests/unit/test_reflective_geists.py": 1,
    "tests/unit/test_tracery_empty_data.py": 1,
}

# Identifiers that hold a geist's output list (suggestions, suggestions_1,
# all_suggestions, results.all_suggestions, ...).
_OUTPUT_NAME = re.compile(r"suggestions")
# Wrappers that are empty exactly when their suggestions arguments are empty.
_TRANSPARENT_WRAPPERS = frozenset({"enumerate", "zip", "sorted", "list", "reversed", "tuple"})

Position = tuple[int, int]


@dataclass(frozen=True)
class UnguardedLoop:
    """A loop over suggestions with no preceding non-empty assertion."""

    path: str
    function: str
    line: int
    iterable: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} in {self.function}(): loop over {self.iterable}"


def _output_refs(node: ast.expr) -> list[str]:
    """Return the suggestions expressions a loop iterable is empty with."""
    if isinstance(node, ast.Name) and _OUTPUT_NAME.search(node.id):
        return [node.id]
    if isinstance(node, ast.Attribute) and _OUTPUT_NAME.search(node.attr):
        return [ast.unparse(node)]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _TRANSPARENT_WRAPPERS
    ):
        refs: list[str] = []
        for arg in node.args:
            refs.extend(_output_refs(arg))
        return refs
    return []


def _int_constant(node: ast.expr) -> int | None:
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    return None


def _len_of(node: ast.expr) -> str | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "len"
        and len(node.args) == 1
    ):
        return ast.unparse(node.args[0])
    return None


def _is_empty_literal(node: ast.expr) -> bool:
    return isinstance(node, (ast.List, ast.Tuple)) and not node.elts


def _comparison_facts(
    left: ast.expr, op: ast.cmpop, right: ast.expr
) -> tuple[set[str], set[tuple[str, str]]]:
    """Non-empty facts and equalities implied by one ``left op right`` link."""
    guarded: set[str] = set()
    equal: set[tuple[str, str]] = set()
    left_len, right_len = _len_of(left), _len_of(right)
    left_k, right_k = _int_constant(left), _int_constant(right)

    if left_len is not None and right_k is not None:
        if (
            (isinstance(op, ast.Gt) and right_k >= 0)
            or (isinstance(op, (ast.GtE, ast.Eq)) and right_k >= 1)
            or (isinstance(op, ast.NotEq) and right_k == 0)
        ):
            guarded.add(left_len)
    if right_len is not None and left_k is not None:
        if (
            (isinstance(op, ast.Lt) and left_k >= 0)
            or (isinstance(op, (ast.LtE, ast.Eq)) and left_k >= 1)
            or (isinstance(op, ast.NotEq) and left_k == 0)
        ):
            guarded.add(right_len)
    if isinstance(op, ast.NotEq):
        if _is_empty_literal(right):
            guarded.add(ast.unparse(left))
        if _is_empty_literal(left):
            guarded.add(ast.unparse(right))
    if isinstance(op, ast.Eq):
        if left_len is not None and right_len is not None:
            equal.add((left_len, right_len))
        elif isinstance(left, (ast.Name, ast.Attribute)) and isinstance(
            right, (ast.Name, ast.Attribute)
        ):
            equal.add((ast.unparse(left), ast.unparse(right)))
    return guarded, equal


def _assertion_facts(test: ast.expr) -> tuple[set[str], set[tuple[str, str]]]:
    """Facts that hold after ``assert test`` succeeds."""
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        guarded: set[str] = set()
        equal: set[tuple[str, str]] = set()
        for value in test.values:
            g, e = _assertion_facts(value)
            guarded |= g
            equal |= e
        return guarded, equal
    if isinstance(test, (ast.Name, ast.Attribute)):
        return {ast.unparse(test)}, set()
    length = _len_of(test)
    if length is not None:
        return {length}, set()
    if isinstance(test, ast.Compare):
        guarded, equal = set(), set()
        operands = [test.left, *test.comparators]
        for op, (left, right) in zip(test.ops, zip(operands, operands[1:])):
            g, e = _comparison_facts(left, op, right)
            guarded |= g
            equal |= e
        return guarded, equal
    return set(), set()


def _is_failure(stmt: ast.stmt) -> bool:
    if isinstance(stmt, ast.Raise):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
        func = stmt.value.func
        return isinstance(func, ast.Attribute) and func.attr == "fail"
    return False


def _emptiness_test(test: ast.expr) -> str | None:
    """``X`` for ``if not X:`` or ``if len(X) == 0:``."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return ast.unparse(test.operand)
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        op, bound = test.ops[0], _int_constant(test.comparators[0])
        if (isinstance(op, ast.Eq) and bound == 0) or (isinstance(op, ast.Lt) and bound == 1):
            return _len_of(test.left)
    return None


def _helper_guard(call: ast.Call) -> str | None:
    """``X`` for ``assert_valid_suggestions(X, ...)`` unless min_count may be 0."""
    func = call.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    if name != "assert_valid_suggestions" or not call.args:
        return None
    for keyword in call.keywords:
        if keyword.arg == "min_count":
            count = _int_constant(keyword.value)
            if count is None or count < 1:
                return None
    return ast.unparse(call.args[0])


def _position(node: ast.AST) -> Position:
    return (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))


def _unguarded_loops_in(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[int, str]]:
    facts: list[tuple[Position, set[str], set[tuple[str, str]]]] = []
    loops: list[tuple[Position, list[str]]] = []

    for node in ast.walk(function):
        if isinstance(node, ast.Assert):
            # A fact holds from the end of the expression that establishes it;
            # the operands of ``assert a and b`` are established left to right.
            parts = (
                node.test.values
                if isinstance(node.test, ast.BoolOp) and isinstance(node.test.op, ast.And)
                else [node.test]
            )
            for part in parts:
                guarded, equal = _assertion_facts(part)
                end = (part.end_lineno or part.lineno, part.end_col_offset or 0)
                facts.append((end, guarded, equal))
            for call in ast.walk(node.test):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "all"
                ):
                    for gen in call.args:
                        if isinstance(gen, (ast.GeneratorExp, ast.ListComp)):
                            for comp in gen.generators:
                                refs = _output_refs(comp.iter)
                                if refs:
                                    loops.append((_position(gen), refs))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            refs = _output_refs(node.iter)
            if refs:
                loops.append((_position(node), refs))
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            guarded_name = _helper_guard(node.value)
            if guarded_name is not None:
                end = (node.end_lineno or node.lineno, node.end_col_offset or 0)
                facts.append((end, {guarded_name}, set()))
        elif isinstance(node, ast.If):
            checked = _emptiness_test(node.test)
            if checked is not None and node.body and _is_failure(node.body[0]):
                facts.append((_position(node), {checked}, set()))

    unguarded: list[tuple[int, str]] = []
    for loop_pos, refs in loops:
        guarded: set[str] = set()
        equal: set[tuple[str, str]] = set()
        for fact_pos, g, e in facts:
            if fact_pos <= loop_pos:
                guarded |= g
                equal |= e
        changed = True
        while changed:
            changed = False
            for a, b in equal:
                if (a in guarded) != (b in guarded):
                    guarded |= {a, b}
                    changed = True
        # zip(a, b) is non-empty only when every argument is.
        missing = [ref for ref in refs if ref not in guarded]
        if missing:
            unguarded.append((loop_pos[0], ", ".join(refs)))
    return unguarded


def find_unguarded_loops(source: str, path: str = "<string>") -> list[UnguardedLoop]:
    """Every loop over suggestions in a test function lacking a prior non-empty assert."""
    tree = ast.parse(source)
    found: list[UnguardedLoop] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            for line, iterable in _unguarded_loops_in(node):
                found.append(UnguardedLoop(path, node.name, line, iterable))
    return sorted(found, key=lambda loop: loop.line)


def _scan_test_tree() -> dict[str, list[UnguardedLoop]]:
    by_file: dict[str, list[UnguardedLoop]] = {}
    for test_file in sorted(TESTS_DIR.rglob("test_*.py")):
        relative = test_file.relative_to(REPO_ROOT).as_posix()
        loops = find_unguarded_loops(test_file.read_text(encoding="utf-8"), relative)
        if loops:
            by_file[relative] = loops
    return by_file


def test_no_new_unguarded_loops_over_suggestions() -> None:
    """No test file may exceed its ratchet baseline (absent means zero)."""
    by_file = _scan_test_tree()
    regressions = [
        f"{path}: {len(loops)} unguarded (baseline {KNOWN_UNGUARDED_LOOPS.get(path, 0)})\n    "
        + "\n    ".join(str(loop) for loop in loops)
        for path, loops in by_file.items()
        if len(loops) > KNOWN_UNGUARDED_LOOPS.get(path, 0)
    ]
    assert not regressions, (
        "Loops over suggestions must follow a non-empty assertion "
        "(assert suggestions / assert_valid_suggestions(...)); otherwise they pass "
        "on a dead geist. See tests/unit/GEIST_TESTING_TEMPLATE.md Iron Rule 2.\n"
        + "\n".join(regressions)
    )


def test_unguarded_loop_baseline_only_goes_down() -> None:
    """A baseline entry above the measured count must be lowered (ratchet)."""
    by_file = _scan_test_tree()
    stale = {
        path: (allowed, len(by_file.get(path, [])))
        for path, allowed in KNOWN_UNGUARDED_LOOPS.items()
        if len(by_file.get(path, [])) < allowed
    }
    assert not stale, (
        "Unguarded loops were fixed; lower KNOWN_UNGUARDED_LOOPS to the measured "
        f"count so they cannot come back (path: (baseline, measured)): {stale}"
    )


def test_example_geists_integration_file_is_fully_guarded() -> None:
    """The bundled-geist integration suite may never regress to vacuous loops."""
    path = "tests/integration/test_example_geists.py"
    assert path not in KNOWN_UNGUARDED_LOOPS
    source = (REPO_ROOT / path).read_text(encoding="utf-8")
    assert find_unguarded_loops(source, path) == []


# --- Teeth: the detector must fire on the pattern it exists to catch --------


def _lines(source: str) -> list[int]:
    return [loop.line for loop in find_unguarded_loops(source)]


def test_detector_flags_the_dead_geist_pattern() -> None:
    """The exact shape of the pre-port integration tests is reported."""
    source = (
        "def test_columbo_geist(ctx, executor):\n"
        "    suggestions = executor.execute_geist('columbo', ctx)\n"
        "    assert isinstance(suggestions, list)\n"
        "    assert len(suggestions) <= 3\n"
        "    for suggestion in suggestions:\n"
        "        assert suggestion.geist_id == 'columbo'\n"
    )
    assert _lines(source) == [5]


def test_detector_flags_vacuous_forms() -> None:
    """Wrapped iterables, all() generators and guards placed after the loop."""
    source = (
        "def test_enumerated(s):\n"
        "    suggestions = s()\n"
        "    for i, x in enumerate(suggestions):\n"  # 3
        "        assert x\n"
        "def test_all_generator(s):\n"
        "    suggestions = s()\n"
        "    assert all(x.text for x in suggestions)\n"  # 7
        "def test_guard_after_loop(s):\n"
        "    suggestions = s()\n"
        "    for x in suggestions:\n"  # 10
        "        assert x\n"
        "    assert suggestions\n"
        "def test_zip_one_side(s):\n"
        "    suggestions_1, suggestions_2 = s(), s()\n"
        "    assert suggestions_1\n"
        "    for a, b in zip(suggestions_1, suggestions_2):\n"  # 16
        "        assert a == b\n"
        "def test_min_count_zero(s):\n"
        "    suggestions = s()\n"
        "    assert_valid_suggestions(suggestions, 'g', min_count=0)\n"
        "    for x in suggestions:\n"  # 21
        "        assert x\n"
        "def test_weak_bounds(s):\n"
        "    suggestions = s()\n"
        "    assert len(suggestions) >= 0\n"
        "    assert 0 <= len(suggestions) <= 3\n"
        "    for x in suggestions:\n"  # 27
        "        assert x\n"
        "def test_skip_is_not_a_guard(s):\n"
        "    suggestions = s()\n"
        "    if not suggestions:\n"
        "        pytest.skip('nothing to check')\n"
        "    for x in suggestions:\n"  # 33
        "        assert x\n"
    )
    assert _lines(source) == [3, 7, 10, 16, 21, 27, 33]


def test_detector_accepts_real_guards() -> None:
    """Non-empty assertions in their common spellings satisfy the rule."""
    source = (
        "def test_truthy(s):\n"
        "    suggestions = s()\n"
        "    assert suggestions, 'designed to trigger'\n"
        "    for x in suggestions:\n"
        "        assert x\n"
        "def test_lengths(s):\n"
        "    a_suggestions, b_suggestions, c_suggestions = s(), s(), s()\n"
        "    assert len(a_suggestions) > 0\n"
        "    assert 1 <= len(b_suggestions) <= 3\n"
        "    assert len(c_suggestions) == 2\n"
        "    for x in sorted(a_suggestions):\n"
        "        pass\n"
        "    for x in b_suggestions:\n"
        "        assert x\n"
        "    for x in c_suggestions:\n"
        "        assert x\n"
        "def test_helper(s):\n"
        "    suggestions = s()\n"
        "    assert_valid_suggestions(suggestions, 'g')\n"
        "    assert all(x.text for x in suggestions)\n"
        "def test_equal_lengths_propagate(s):\n"
        "    suggestions_1, suggestions_2 = s(), s()\n"
        "    assert suggestions_1\n"
        "    assert len(suggestions_1) == len(suggestions_2)\n"
        "    for a, b in zip(suggestions_1, suggestions_2):\n"
        "        assert a == b\n"
        "def test_explicit_failure(s):\n"
        "    suggestions = s()\n"
        "    if not suggestions:\n"
        "        pytest.fail('geist is dead')\n"
        "    for x in suggestions:\n"
        "        assert x\n"
        "def test_same_assert(s):\n"
        "    suggestions = s()\n"
        "    assert suggestions and all(x.text for x in suggestions)\n"
        "def helper_not_a_test(suggestions):\n"
        "    for x in suggestions:\n"
        "        assert x\n"
    )
    assert _lines(source) == []
