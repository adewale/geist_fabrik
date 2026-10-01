"""Suite hygiene: no test may be shaped so that it cannot fail.

The scanner lives in ``tests/plugins/hygiene_scan.py``; this module runs it over
every ``tests/**/test_*.py`` and owns the allowlist. Each allowlist entry names
an exact test id and rule with a written reason. An entry fails as stale when
its test no longer exists or no longer violates that rule, so the list can only
shrink as tests are fixed.
"""

from pathlib import Path

import pytest

from tests.plugins.hygiene_scan import (
    ALWAYS_TRUE,
    ISINSTANCE_LIST_ONLY,
    LOOP_ONLY,
    NO_ASSERT,
    collect_test_ids,
    scan_source,
    scan_tree,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"

# (test id, rule) -> reason. Keep reasons specific; "legacy" is not a reason.
ALLOWLIST: dict[tuple[str, str], str] = {}


def test_no_test_is_shaped_so_it_cannot_fail() -> None:
    violations = scan_tree(TESTS_ROOT, REPO_ROOT)
    unexpected = [v for v in violations if (v.test_id, v.rule) not in ALLOWLIST]
    assert not unexpected, "Tests that cannot fail (fix them, or allowlist with a reason):\n" + (
        "\n".join(f"  {v.rule}: {v.test_id} (line {v.line}): {v.detail}" for v in unexpected)
    )


def test_allowlist_entries_are_not_stale() -> None:
    violations = {(v.test_id, v.rule) for v in scan_tree(TESTS_ROOT, REPO_ROOT)}
    existing = collect_test_ids(TESTS_ROOT, REPO_ROOT)
    stale = [
        f"{test_id} [{rule}]: " + ("test no longer exists" if test_id not in existing else "fixed")
        for test_id, rule in ALLOWLIST
        if (test_id, rule) not in violations
    ]
    assert not stale, "Remove stale hygiene allowlist entries:\n" + "\n".join(stale)
    assert all(len(reason) > 30 for reason in ALLOWLIST.values())


def _rules(source: str) -> list[tuple[str, str]]:
    return [(v.test_id.split("::", 1)[1], v.rule) for v in scan_source(source, "t.py")]


# --- scanner unit tests: each rule fires on a minimal bad example and stays
# quiet on the closest legitimate shape.


def test_no_assert_rule() -> None:
    source = """
import subprocess
import pytest

def _check(x):
    assert x

def _indirect(x):
    _check(x)

@pytest.fixture
def test_data_path():
    return 1

def test_bad():
    compute()

def test_raises():
    with pytest.raises(ValueError):
        compute()

def test_helper():
    _indirect(compute())

def test_assert_prefix_helper(mock):
    mock.assert_called_once_with(1)

def test_checked_subprocess():
    subprocess.run(["x"], check=True)

def test_unchecked_subprocess():
    subprocess.run(["x"])

class TestThing:
    def test_method_bad(self):
        compute()
"""
    assert _rules(source) == [
        ("test_bad", NO_ASSERT),
        ("test_unchecked_subprocess", NO_ASSERT),
        ("TestThing::test_method_bad", NO_ASSERT),
    ]


@pytest.mark.parametrize(
    "expression",
    ["True", "1", "len(x) >= 0", "0 <= len(x)", "len(x) > -1", "abs(d) >= 0", "-1 < len(x)"],
)
def test_always_true_rule_flags(expression: str) -> None:
    assert _rules(f"def test_x():\n    assert {expression}\n") == [("test_x", ALWAYS_TRUE)]


@pytest.mark.parametrize(
    "expression", ["len(x) >= 1", "len(x) > 0", "x >= 0", "0 < len(x)", "len(x) <= 3", "False"]
)
def test_always_true_rule_ignores_real_bounds(expression: str) -> None:
    assert _rules(f"def test_x():\n    assert {expression}\n") == []


def test_loop_only_rule() -> None:
    source = """
def test_bad():
    suggestions = geist.suggest(vault)
    for s in suggestions:
        assert s.text

def test_bad_all():
    results = run()
    assert all(r.ok for r in results)

def test_guarded():
    suggestions = geist.suggest(vault)
    assert len(suggestions) == 2
    for s in suggestions:
        assert s.text

def test_guarded_by_helper():
    suggestions = geist.suggest(vault)
    assert_valid_suggestions(suggestions, vault)
    for s in suggestions:
        assert s.text

def test_loop_over_inputs():
    for name in ["a", "b"]:
        assert name
"""
    assert _rules(source) == [("test_bad", LOOP_ONLY), ("test_bad_all", LOOP_ONLY)]


def test_isinstance_list_only_rule() -> None:
    source = """
def test_bad():
    assert isinstance(geist.suggest(vault), list)

def test_with_more():
    result = geist.suggest(vault)
    assert isinstance(result, list)
    assert result == []

def test_other_type():
    assert isinstance(value, dict)
"""
    assert _rules(source) == [("test_bad", ISINSTANCE_LIST_ONLY)]


def test_validate_and_ci_unit_lanes_both_require_geist_firing() -> None:
    """CLAUDE.md: validate.sh must match CI. Both unit steps carry the gate flag."""
    validate = (REPO_ROOT / "scripts" / "validate.sh").read_text()
    workflow = (REPO_ROOT / ".github" / "workflows" / "test.yml").read_text()
    validate_unit = validate.split('run_check "Unit tests"', 1)[1].split("|| FAILED=1", 1)[0]
    ci_unit = workflow.split("- name: Run unit tests", 1)[1].split("- name:", 1)[0]
    for step in (validate_unit, ci_unit):
        assert "tests/unit" in step
        assert "--require-geist-firing" in step
        assert "--timeout=60" in step
