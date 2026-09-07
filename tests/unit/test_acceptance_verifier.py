"""Tests for the executable acceptance-criteria batching contract."""

from pathlib import Path

from scripts.check_phase_completion import (
    AC_FILE,
    Criterion,
    combined_pytest_targets,
    parse_criteria,
    partition_pytest_criteria,
    pytest_targets,
)


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
