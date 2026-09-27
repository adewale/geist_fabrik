"""Tests for the scheduled-tiers job summary renderer."""

from pathlib import Path

from scripts.junit_summary import main, read_cases, render

REPORT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="4">
  <testcase classname="tests.unit.test_a" name="test_fast" time="0.10"/>
  <testcase classname="tests.unit.test_a" name="test_slow" time="3.50"/>
  <testcase classname="tests.unit.test_b" name="test_broken" time="1.25">
    <failure message="assert 1 == 2">boom</failure>
  </testcase>
  <testcase classname="tests.unit.test_b" name="test_skipped" time="0.00">
    <skipped message="no sqlite-vec"/>
  </testcase>
</testsuite></testsuites>
"""


def test_reads_every_outcome(tmp_path: Path) -> None:
    report = tmp_path / "r.xml"
    report.write_text(REPORT)
    outcomes = {case.name.split("::")[1]: case.outcome for case in read_cases(report)}
    assert outcomes == {
        "test_fast": "passed",
        "test_slow": "passed",
        "test_broken": "failed",
        "test_skipped": "skipped",
    }


def test_render_counts_and_orders_slowest_first(tmp_path: Path) -> None:
    report = tmp_path / "r.xml"
    report.write_text(REPORT)
    text = render("Benchmarks", read_cases(report))
    assert "1 failed, 2 passed, 1 skipped" in text
    rows = [line for line in text.splitlines() if line.startswith("| `")]
    assert [row.split("`")[1].split("::")[1] for row in rows] == [
        "test_slow",
        "test_broken",
        "test_fast",
        "test_skipped",
    ]
    assert "| 3.50 |" in rows[0]


def test_missing_report_is_reported_not_hidden(tmp_path: Path, capsys) -> None:
    assert main([str(tmp_path / "absent.xml")]) == 1
    assert "No JUnit report was produced" in capsys.readouterr().out
