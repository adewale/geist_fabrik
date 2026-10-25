"""Real command and Tracery integration for derived local topics."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from geistfabrik.cli import create_parser
from geistfabrik.commands.topics import TopicsCommand
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.tracery import TraceryGeist
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


def _vault_path(tmp_path: Path) -> Path:
    (tmp_path / ".obsidian").mkdir()
    (tmp_path / "cakes.md").write_text("# Chocolate cake\n\nChocolate cake needs cocoa.")
    return tmp_path


def _run(path: Path, *options: str) -> int:
    args = create_parser().parse_args(["topics", str(path), *options])
    return TopicsCommand(args).run()


def test_explained_inspection_matches_stored_labels(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _vault_path(tmp_path)
    assert _run(path, "--json", "--note", "cakes", "--explain") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["explanation"]["topics"] == report["topics"]
    assert any(row["selected"] for row in report["explanation"]["candidates"])


def test_explanation_does_not_extract_an_excluded_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import geistfabrik.commands.topics as command_module

    path = _vault_path(tmp_path)
    (path / "Templates").mkdir()
    (path / "Templates/hidden.md").write_text("# Secret subject\n")

    def forbidden(_content: str) -> None:
        raise AssertionError("excluded source must not enter explanation extraction")

    monkeypatch.setattr(command_module, "explain_topics", forbidden)
    assert _run(path, "--json", "--note", "Templates/hidden.md", "--explain") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["note"]["status"] == "excluded"
    assert report["explanation"] is None and report["topics"] is None


def test_inspection_is_model_free_clean_json_and_preserves_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import geistfabrik.commands.base as base

    path = _vault_path(tmp_path)
    config_dir = path / "_geistfabrik"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("filtering:\n  boundary:\n    exclude_paths: []\n")
    before = (path / "cakes.md").read_bytes()

    def forbidden_model(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("topic inspection must not construct an embedding session")

    monkeypatch.setattr(base, "Session", forbidden_model)
    assert _run(path, "--json", "--verbose") == 0
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["complete"] is True
    assert {entry["key"] for entry in report["topics"]} >= {"chocolate cake"}
    assert report["eligible_notes"] == 1
    assert (path / "cakes.md").read_bytes() == before
    assert not (path / "geist journal").exists()


def test_note_inspection_accepts_pasted_link_and_returns_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _vault_path(tmp_path)
    assert _run(path, "--json", "--note", "[[cakes]]") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["note"]["path"] == "cakes.md"
    assert report["note"]["link"] == "[[cakes|Chocolate cake]]"
    tag = next(tag for tag in report["topics"] if tag["key"] == "chocolate cake")
    source = (path / "cakes.md").read_text()
    assert source[tag["start"] : tag["end"]] == tag["text"]
    assert tag["line"] == 1


def test_incomplete_new_physical_source_is_visible_by_note_and_corpus(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _vault_path(tmp_path)
    (path / "unparsed.md").write_bytes(b"\xff\xfe")
    assert _run(path, "--json", "--note", "unparsed") == 2
    report = json.loads(capsys.readouterr().out)
    assert report["complete"] is False
    assert report["note"]["path"] == "unparsed.md"
    assert report["note"]["status"] == "error"
    assert report["note"]["link"] is None
    assert report["topics"] is None
    assert _run(path, "--json", "--topic", "chocolate cake") == 2
    report = json.loads(capsys.readouterr().out)
    assert report["notes"] is None and report["count"] is None
    assert [error["path"] for error in report["incomplete_notes"]] == ["unparsed.md"]


def test_topic_membership_query_returns_exact_source_links(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _vault_path(tmp_path)
    (path / "garden.md").write_text("# Urban gardens\n")
    assert _run(path, "--json", "--topic", "Chocolate cake") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["notes"] == [{"path": "cakes.md", "link": "[[cakes|Chocolate cake]]"}]
    assert report["count"] == 1
    assert _run(path, "--json", "--topic", "Chocolate cakes") == 0
    assert json.loads(capsys.readouterr().out)["notes"] == []


def test_registered_topics_work_in_real_tracery_grammar(tmp_path: Path) -> None:
    path = _vault_path(tmp_path)
    vault = Vault(path)
    try:
        vault.sync()
        registry = FunctionRegistry()
        context = VaultContext(
            vault, Session(datetime(2025, 1, 3), vault.db), seed=17, function_registry=registry
        )
        grammar = {
            "origin": ["What if #source# made you rethink #subject#?"],
            "source": ["$vault.topic_notes('Chocolate cake', 1)"],
            "subject": ["$vault.note_topics('cakes')"],
        }
        geist = TraceryGeist("topic_probe", grammar, seed=17)
        suggestions = geist.suggest(context)
        assert len(suggestions) == 1
        assert "[[cakes|Chocolate cake]]" in suggestions[0].text
        assert "Chocolate cake" in suggestions[0].text
        assert suggestions[0].notes == ["cakes|Chocolate cake"]
        assert not (path / "geist journal").exists()
    finally:
        vault.close()
