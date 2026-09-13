"""Regression contracts for deterministic sessions and honest diagnostics."""

import subprocess
import sys
import tomllib
from argparse import Namespace
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from geistfabrik.cli import create_parser
from geistfabrik.commands.invoke import GeistResults, InvokeCommand
from geistfabrik.config import TOTAL_DIM
from geistfabrik.config_loader import GeistFabrikConfig
from geistfabrik.default_geists import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS
from geistfabrik.embeddings import Session
from geistfabrik.filtering import SuggestionFilter
from geistfabrik.journal_writer import JournalWriter
from geistfabrik.models import Suggestion
from geistfabrik.schema import init_db
from geistfabrik.session_time import normalise_session_date, session_seed
from geistfabrik.stats import StatsCollector
from geistfabrik.temporal_analysis import EmbeddingTrajectoryCalculator
from geistfabrik.tracery import TraceryGeist
from geistfabrik.validator import GeistValidator
from geistfabrik.vault import Vault

ROOT = Path(__file__).resolve().parents[2]


class _ExecutorLog:
    def __init__(self, entries: list[dict[str, object]]) -> None:
        self.entries = entries

    def get_execution_log(self) -> list[dict[str, object]]:
        return self.entries


def _suggestion(text: str, geist_id: str = "test") -> Suggestion:
    return Suggestion(text=text, notes=["note"], geist_id=geist_id)


def test_session_seed_is_calendar_day_only() -> None:
    morning = datetime(2025, 1, 15, 0, 1, tzinfo=timezone(timedelta(hours=12)))
    evening = datetime(2025, 1, 15, 23, 59, tzinfo=timezone(timedelta(hours=-11)))

    assert normalise_session_date(morning) == datetime(2025, 1, 15)
    assert normalise_session_date(evening) == datetime(2025, 1, 15)
    assert session_seed(morning) == session_seed(evening) == 20250115


def test_implicit_cli_date_is_canonical_midnight() -> None:
    command = InvokeCommand(Namespace(quiet=False, verbose=False))
    parsed = command.parse_session_date()

    assert parsed is not None
    assert parsed.time().isoformat() == "00:00:00"


def test_public_session_constructor_normalises_time_of_day() -> None:
    db = init_db()
    try:
        session = Session(datetime(2025, 1, 15, 23, 59), db)
        assert session.date == datetime(2025, 1, 15)
        session.close()
    finally:
        db.close()


def test_invoke_parser_exposes_count_only_explanation() -> None:
    args = create_parser().parse_args(["invoke", "/tmp/vault", "--explain"])
    assert args.explain is True


def test_filter_report_accounts_for_each_rejection(tmp_path: Path) -> None:
    db = init_db(tmp_path / "filter.db")
    try:
        config = {
            "strategies": ["quality"],
            "quality": {
                "enabled": True,
                "min_length": 10,
                "max_length": 100,
                "check_repetition": True,
            },
        }
        computer: Any = SimpleNamespace()
        pipeline = SuggestionFilter(db, computer, config=config)
        kept, report = pipeline.filter_all_with_report(
            [_suggestion("too short"), _suggestion("long enough to keep")],
            datetime(2025, 1, 15),
        )

        assert [item.text for item in kept] == ["long enough to keep"]
        assert report.input_count == 2
        assert report.output_count == 1
        assert report.stages[0].rejected_count == 1
    finally:
        db.close()


def test_execution_summary_distinguishes_empty_failure_and_skip() -> None:
    result_map = {
        "produced": [_suggestion("long enough output", "produced")],
        "empty": [],
        "failed": [],
        "skipped": [],
    }
    executor: Any = _ExecutorLog(
        [
            {"geist_id": "produced", "status": "success"},
            {"geist_id": "empty", "status": "success"},
            {"geist_id": "failed", "status": "error", "error": "private text"},
            {"geist_id": "skipped", "status": "skipped"},
        ]
    )

    assert InvokeCommand._outcome_counts(result_map, executor) == {
        "produced": 1,
        "healthy_empty": 1,
        "failed": 1,
        "skipped": 1,
        "unknown": 0,
    }


def test_diff_history_is_bounded_by_replay_date(tmp_path: Path) -> None:
    db = init_db(tmp_path / "journal.db")
    try:
        rows = [
            ("2024-01-01", "old", "at cutoff", "old-1", "2024-01-01"),
            ("2024-02-01", "past", "prior", "past-1", "2024-02-01"),
            ("2024-03-01", "same", "current", "same-1", "2024-03-01"),
            ("2024-04-01", "future", "future", "future-1", "2024-04-01"),
        ]
        db.executemany(
            "INSERT INTO session_suggestions VALUES (?, ?, ?, ?, ?)", rows
        )
        db.commit()

        writer = JournalWriter(tmp_path, db)
        assert writer.get_recent_suggestions(
            days=60, as_of=datetime(2024, 3, 1)
        ) == ["prior", "at cutoff"]
    finally:
        db.close()


def test_trajectory_uses_one_ordered_select_and_ignores_calendar_dimensions() -> None:
    db = init_db()
    try:
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES ('note.md', 'Note', 'content', '2024-01-01', '2024-01-01', 0)"
        )
        semantic = np.zeros(TOTAL_DIM, dtype=np.float32)
        semantic[0] = 0.9
        first_date = datetime(2023, 1, 1)
        for index in range(730):
            date = (first_date + timedelta(days=index)).strftime("%Y-%m-%d")
            cursor = db.execute(
                "INSERT INTO sessions (date, created_at) VALUES (?, ?)", (date, date)
            )
            embedding = semantic.copy()
            embedding[-3:] = index
            db.execute(
                "INSERT INTO session_embeddings VALUES (?, 'note.md', ?, NULL)",
                (cursor.lastrowid, embedding.tobytes()),
            )
        db.commit()

        statements: list[str] = []
        db.set_trace_callback(statements.append)
        context: Any = SimpleNamespace(
            db=db, session=SimpleNamespace(date=first_date + timedelta(days=729))
        )
        note: Any = SimpleNamespace(path="note.md")
        calculator = EmbeddingTrajectoryCalculator(context, note)

        assert len(calculator.snapshots()) == 730
        assert calculator.total_drift() == 0.0
        selects = [sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]
        assert len(selects) == 1
        assert "JOIN sessions" in selects[0]
    finally:
        db.close()


def test_validator_rejects_the_same_unsafe_grammar_as_runtime(tmp_path: Path) -> None:
    grammar = tmp_path / "unsafe.yaml"
    grammar.write_text(
        """type: geist-tracery
id: unsafe
tracery:
  origin: "$vault.neighbours(#note#, 3)"
  note: "example"
"""
    )

    result = GeistValidator().validate_tracery_geist(grammar)

    assert result.passed is False
    assert any("Unsafe vault function pattern" in issue.message for issue in result.issues)


@pytest.mark.parametrize(
    "document",
    [
        "type: wrong\nid: invalid\ntracery:\n  origin: text\n",
        "type: geist-tracery\nid: ''\ntracery:\n  origin: text\n",
        "type: geist-tracery\nid: invalid\ncount: true\ntracery:\n  origin: text\n",
        "type: geist-tracery\nid: invalid\ncount: 0\ntracery:\n  origin: text\n",
        "type: geist-tracery\nid: invalid\ntracery: []\n",
        "type: geist-tracery\nid: invalid\ntracery:\n  other: text\n",
    ],
)
def test_validator_and_runtime_reject_the_same_structural_definitions(
    tmp_path: Path, document: str
) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(document)

    assert GeistValidator().validate_tracery_geist(path).passed is False
    with pytest.raises(ValueError):
        TraceryGeist.from_yaml(path)


def test_stats_separate_geist_types_and_written_session_average(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    config = GeistFabrikConfig(
        default_geists={
            **dict.fromkeys(DEFAULT_CODE_GEISTS, False),
            **dict.fromkeys(DEFAULT_TRACERY_GEISTS, False),
        }
    )
    with closing(Vault(vault_path, config=config)) as vault:
        for day in range(1, 4):
            date = f"2025-01-0{day}"
            vault.db.execute(
                "INSERT INTO sessions (date, created_at) VALUES (?, ?)", (date, date)
            )
        vault.db.executemany(
            "INSERT INTO session_suggestions VALUES (?, ?, ?, ?, ?)",
            [
                ("2025-01-02", "a", "one", "a-1", "2025-01-02"),
                ("2025-01-02", "b", "two", "b-1", "2025-01-02"),
            ],
        )
        vault.db.commit()

        stats = StatsCollector(vault, config).stats

        assert stats["geists"]["code_enabled"] == 0
        assert stats["geists"]["tracery_enabled"] == 0
        assert stats["geists"]["total_enabled"] == 0
        assert stats["sessions"]["total"] == 3
        assert stats["sessions"]["suggestion_sessions"] == 1
        assert stats["sessions"]["average_suggestions_per_session"] == 2.0


def test_explanation_never_prints_executor_error_contents(capsys: Any) -> None:
    args = Namespace(
        quiet=False,
        verbose=False,
        full=False,
        no_filter=True,
    )
    command = InvokeCommand(args)
    results = GeistResults(
        code_results={"broken": []}, tracery_results={}, all_suggestions=[]
    )
    executor: Any = _ExecutorLog(
        [{"geist_id": "broken", "status": "error", "error": "SECRET NOTE TEXT"}]
    )

    command._print_explanation(
        results,
        executor,
        None,
        filtered_count=0,
        selected_count=0,
        session_date=datetime(2025, 1, 15),
    )
    output = capsys.readouterr().out
    assert "broken: failed" in output
    assert "SECRET NOTE TEXT" not in output


def test_release_version_check_accepts_only_matching_artifacts(tmp_path: Path) -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        version = tomllib.load(handle)["project"]["version"]
    (tmp_path / f"geistfabrik-{version}-py3-none-any.whl").touch()
    (tmp_path / f"geistfabrik-{version}.tar.gz").touch()
    command = [
        sys.executable,
        str(ROOT / "scripts" / "check_release_version.py"),
        f"v{version}",
        "--artifact-dir",
        str(tmp_path),
    ]

    assert subprocess.run(command, cwd=ROOT, check=False).returncode == 0
    command[2] = "v999.0.0"
    assert subprocess.run(command, cwd=ROOT, check=False).returncode == 1


def test_tag_workflow_promotes_the_retained_smoke_artifacts() -> None:
    workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text()

    assert "PACKAGE_SMOKE_WORKDIR: ${{ github.workspace }}/package-smoke-work" in workflow
    assert "cp package-smoke-work/run.*/dist/geistfabrik-*.whl release-dist/" in workflow
    assert "cp package-smoke-work/run.*/dist/geistfabrik-*.tar.gz release-dist/" in workflow
    assert "path: release-dist/*" in workflow
    assert ".package-smoke" not in workflow
    assert "name: release-artifacts" in workflow
    assert "needs: [test, package-smoke]" in workflow
    assert 'check_release_version.py "$GITHUB_REF_NAME" --artifact-dir dist' in workflow
    assert "sha256sum geistfabrik-*.whl geistfabrik-*.tar.gz > SHA256SUMS" in workflow
    assert 'gh release create "$GITHUB_REF_NAME" dist/*' in workflow
