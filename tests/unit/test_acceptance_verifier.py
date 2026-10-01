"""Tests for the executable acceptance-criteria batching contract."""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_phase_completion import (
    AC_FILE,
    Criterion,
    combined_pytest_targets,
    evidence_problems,
    load_selection,
    normalize_command,
    parse_criteria,
    partition_pytest_criteria,
    pytest_targets,
    skipped_targets,
    uses_canonical_selection,
    with_selection_report,
)

pytest_plugins = ("pytester",)


def _criterion(ac_id: str, command: str) -> Criterion:
    return Criterion(ac_id, "1", "test", command, True, command, None)


def test_file_and_named_node_targets_are_both_preserved() -> None:
    criteria = [
        _criterion("AC-1.1", "uv run pytest tests/unit/test_cli.py"),
        _criterion(
            "AC-1.2",
            "uv run pytest tests/unit/test_cli.py::test_main_no_args_shows_help",
        ),
    ]
    batchable, standalone = partition_pytest_criteria(criteria)
    assert standalone == []
    assert combined_pytest_targets(batchable) == [
        "tests/unit/test_cli.py",
        "tests/unit/test_cli.py::test_main_no_args_shows_help",
    ]


def test_marker_specific_benchmark_criterion_is_never_fast_batched() -> None:
    ordinary = _criterion("AC-1.1", "uv run pytest tests/unit/test_cli.py")
    benchmark = _criterion(
        "AC-11.1",
        "uv run pytest tests/benchmarks/test_performance.py -m benchmark",
    )
    batchable, standalone = partition_pytest_criteria([ordinary, benchmark])
    assert batchable == [ordinary]
    assert standalone == [benchmark]


@pytest.mark.parametrize(
    "options",
    [
        "-k nonexistent",
        "--deselect tests/unit/test_cli.py::test_main_no_args_shows_help",
        "-x",
        "--lf",
    ],
)
def test_selection_changing_options_are_never_dropped_into_the_batch(options: str) -> None:
    """The batch rebuilds the command from targets only, so any option would be lost."""
    criterion = _criterion("AC-1.3", f"uv run pytest tests/unit/test_cli.py {options} -v")
    assert partition_pytest_criteria([criterion]) == ([], [criterion])


def test_output_only_flags_and_brace_lists_stay_batchable() -> None:
    criterion = _criterion("AC-1.4", "uv run pytest tests/unit/test_cli.py::test_{a,b} -v -q -s")
    assert partition_pytest_criteria([criterion]) == ([criterion], [])


def test_chained_or_targetless_pytest_commands_run_standalone() -> None:
    chained = _criterion("AC-1.5", "cd tests && uv run pytest tests/unit/test_cli.py -v")
    targetless = _criterion("AC-1.6", "uv run pytest --collect-only")
    assert partition_pytest_criteria([chained, targetless]) == ([], [chained, targetless])


@pytest.mark.parametrize(
    "marker",
    ["-m benchmark", '-m "benchmark"', '-m"benchmark"', "-mbenchmark", "-m=benchmark"],
)
def test_every_marker_spelling_is_standalone_and_not_canonical(marker: str) -> None:
    """One predicate decides both batching and the canonical filter (no -m"x" gap)."""
    command = f"uv run pytest tests/integration/test_scenarios.py {marker} -v"
    criterion = _criterion("AC-11.1", command)
    assert partition_pytest_criteria([criterion]) == ([], [criterion])
    assert "not production_model" not in normalize_command(command)
    assert not uses_canonical_selection(command)


def test_benchmark_acceptance_criterion_names_every_benchmark_file() -> None:
    criteria, errors = parse_criteria(AC_FILE.read_text())
    assert errors == []
    benchmark = next(criterion for criterion in criteria if criterion.ac_id == "AC-11.1")
    named_files = {target.split("::", 1)[0] for target in pytest_targets(benchmark.command or "")}
    actual_files = {
        str(path)
        for path in Path("tests").rglob("*.py")
        if any(line.strip() == "@pytest.mark.benchmark" for line in path.read_text().splitlines())
    }
    assert named_files == actual_files
    assert "-m benchmark" in (benchmark.command or "")


# --- Evidence gate: a criterion must select tests, and never a partial file.

_SCENARIOS = "tests/integration/test_scenarios.py"
# Shaped like the real file: two benchmark-marked tests the canonical filter drops.
_SELECTED = [f"{_SCENARIOS}::test_scenario_empty_vault", f"{_SCENARIOS}::test_scenario_daily[a]"]
_DESELECTED = [
    f"{_SCENARIOS}::test_scenario_first_time_setup",
    f"{_SCENARIOS}::test_scenario_incremental_sync",
]


def test_whole_file_with_deselected_tests_is_rejected_as_partial_evidence() -> None:
    problems = evidence_problems(
        f"uv run pytest {_SCENARIOS} -v", _SELECTED, _DESELECTED, canonical=True
    )
    assert len(problems) == 1
    assert "partial evidence" in problems[0]
    assert "deselects 2 of its tests" in problems[0]
    assert "test_scenario_first_time_setup" in problems[0]


def test_node_targets_in_a_partially_selected_file_are_whole_evidence() -> None:
    command = f"uv run pytest {_SCENARIOS}::test_scenario_{{empty_vault,daily}} -v"
    assert evidence_problems(command, _SELECTED, _DESELECTED, canonical=True) == []


def test_fully_selected_whole_file_is_accepted() -> None:
    selected = ["tests/unit/test_cli.py::test_a", "tests/unit/test_cli.py::TestB::test_c"]
    command = "uv run pytest tests/unit/test_cli.py -v"
    assert evidence_problems(command, selected, _DESELECTED, canonical=True) == []


def test_target_selecting_no_tests_is_rejected() -> None:
    command = f"uv run pytest {_SCENARIOS}::test_scenario_first_time_setup -v"
    assert evidence_problems(command, _SELECTED, _DESELECTED, canonical=True) == [
        f"{_SCENARIOS}::test_scenario_first_time_setup selects no tests"
    ]


def test_node_prefix_does_not_match_a_longer_sibling_name() -> None:
    command = f"uv run pytest {_SCENARIOS}::test_scenario_empty -v"
    assert evidence_problems(command, _SELECTED, [], canonical=True) == [
        f"{_SCENARIOS}::test_scenario_empty selects no tests"
    ]


def test_explicit_marker_commands_may_select_part_of_a_file_but_not_nothing() -> None:
    command = f"uv run pytest {_SCENARIOS} tests/unit/test_cli.py -m benchmark"
    problems = evidence_problems(command, _DESELECTED, _SELECTED, canonical=False)
    assert problems == ["tests/unit/test_cli.py selects no tests"]
    assert not uses_canonical_selection(command)
    assert uses_canonical_selection(f"uv run pytest {_SCENARIOS} -v")


def test_targetless_pytest_command_must_select_something() -> None:
    assert evidence_problems("uv run pytest --collect-only", [], [], canonical=True) == [
        "selects no tests"
    ]
    assert evidence_problems("uv run pytest --collect-only", _SELECTED, [], canonical=True) == []


def test_target_whose_selected_tests_all_skipped_is_reported() -> None:
    command = f"uv run pytest {_SCENARIOS} tests/unit/test_cli.py::test_a -v"
    selected = [*_SELECTED, "tests/unit/test_cli.py::test_a"]
    # One skip in a file that also ran a test is fine; a node that only skipped is not.
    assert skipped_targets(command, selected, [_SELECTED[0], "tests/unit/test_cli.py::test_a"]) == [
        "tests/unit/test_cli.py::test_a is not evidence: all 1 selected test(s) were skipped"
    ]
    assert skipped_targets(command, selected, [_SELECTED[0]]) == []


def test_selection_report_option_is_added_to_the_pytest_invocation(tmp_path: Path) -> None:
    report = tmp_path / "r.json"
    command = with_selection_report("cd x && uv run pytest tests/unit/test_cli.py -q", report)
    assert command == f"cd x && uv run pytest --selection-report={report} tests/unit/test_cli.py -q"


def test_selection_report_plugin_records_marker_deselection(pytester: pytest.Pytester) -> None:
    pytester.makeini("[pytest]\nmarkers =\n    benchmark: slow timing test\n")
    pytester.makepyfile(
        test_mixed=(
            "import pytest\n\n"
            "def test_fast():\n    assert True is not False\n\n"
            "@pytest.mark.benchmark\n"
            "def test_timing():\n    assert 2 > 1\n"
        )
    )
    report = pytester.path / "selection.json"

    result = pytester.runpytest(
        "-p",
        "tests.plugins.selection_report",
        f"--selection-report={report}",
        "-m",
        "not benchmark",
        "--collect-only",
        "-q",
    )

    assert result.ret == pytest.ExitCode.OK
    assert load_selection(report) == (
        ["test_mixed.py::test_fast"],
        ["test_mixed.py::test_timing"],
        [],  # nothing ran, so nothing was skipped
    )


def test_selection_report_plugin_records_tests_that_only_skipped(
    pytester: pytest.Pytester,
) -> None:
    pytester.makepyfile(
        test_skips=(
            "import pytest\n\n"
            "def test_runs():\n    assert 2 > 1\n\n"
            "@pytest.mark.skipif(True, reason='setup skip')\n"
            "def test_skipif():\n    assert 2 > 1\n\n"
            "def test_call_skip():\n    pytest.skip('call skip')\n\n"
            "@pytest.mark.xfail(reason='expected')\n"
            "def test_xfail():\n    assert 1 > 2\n"
        )
    )
    report = pytester.path / "selection.json"

    result = pytester.runpytest(
        "-p", "tests.plugins.selection_report", f"--selection-report={report}", "-q"
    )

    result.assert_outcomes(passed=1, skipped=2, xfailed=1)
    selection = load_selection(report)
    assert selection is not None
    assert selection[2] == [
        "test_skips.py::test_call_skip",
        "test_skips.py::test_skipif",
        "test_skips.py::test_xfail",
    ]


def test_main_rejects_partial_and_empty_evidence_end_to_end(tmp_path: Path) -> None:
    """The evidence checks are wired into main(): one real batched pytest run, exit 1."""
    hubs = "tests/unit/test_phase2_hubs_optimization.py"  # small; one benchmark test
    table = tmp_path / "ac.md"
    table.write_text(
        "## Phase 1: Demo\n\n"
        "| ID | Status | Criteria | Verification |\n"
        "|----|--------|----------|--------------|\n"
        f"| AC-1.1 | ✅ | whole file | `uv run pytest {hubs} -v` |\n"
        f"| AC-1.2 | ✅ | benchmark node | `uv run pytest {hubs}::test_hubs_performance -v` |\n",
        encoding="utf-8",
    )

    result = subprocess.run(  # noqa: S603 - repo-local script, fixed arguments
        [
            sys.executable,
            str(AC_FILE.parents[1] / "scripts/check_phase_completion.py"),
            "--ac-file",
            str(table),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert f"AC-1.1     EVIDENCE {hubs} is partial evidence" in result.stdout
    assert "deselects 1 of its tests (test_hubs_performance)" in result.stdout
    assert f"AC-1.2     EVIDENCE {hubs}::test_hubs_performance selects no tests" in result.stdout
    assert "AUTO: 2/2 passed" in result.stdout  # the tests ran green; evidence alone failed
