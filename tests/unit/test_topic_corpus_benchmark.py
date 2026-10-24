"""Corpus receipts must reject incomplete rebuilds and wrong replay inputs."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import geistfabrik.topics as topic_module
from geistfabrik import Vault
from geistfabrik.topics import TopicIndexIncompleteError, TopicTag
from scripts import benchmark_topic_corpora as benchmark


def _replay_fixture(tmp_path: Path, content: str = "") -> tuple[Path, Path, dict[str, Any]]:
    corpus = tmp_path / "corpus"
    objects = corpus / "objects"
    objects.mkdir(parents=True)
    raw = content.encode()
    digest = hashlib.sha256(raw).hexdigest()
    (objects / (digest + ".md")).write_bytes(raw)
    record = {
        "index": 0,
        "files": {"empty.md": digest},
        "changed_paths": ["empty.md"],
        "deleted_paths": [],
        "observed_at": "2024-01-01T12:00:00+00:00",
    }
    manifest = {"snapshots": [record], "stable_paths": ["empty.md"]}
    (corpus / "manifest.json").write_text(json.dumps(manifest))
    root = tmp_path / "replay"
    root.mkdir()
    return corpus, root, manifest


def test_complete_empty_rebuild_is_certified(tmp_path: Path) -> None:
    corpus, root, manifest = _replay_fixture(tmp_path)
    report = benchmark.run_corpus(
        {"name": "complete-empty-control", "snapshots": 1},
        root,
        tmp_path / "report.json",
        (corpus, manifest),
    )
    assert report["clean_rebuild_matches"] is True
    assert report["snapshots"][0]["states"] == {"complete": 1}
    assert report["warm_sync"]["topic_extractions"] == 0


def test_empty_memberships_cannot_certify_an_incomplete_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus, root, manifest = _replay_fixture(tmp_path)
    instances = 0

    def unavailable(_content: str) -> list[TopicTag]:
        raise ValueError("supported extraction failure during clean rebuild")

    def create_vault(*args: Any, **kwargs: Any) -> Vault:
        nonlocal instances
        instances += 1
        vault = Vault(*args, **kwargs)
        if instances == 2:
            monkeypatch.setattr(topic_module, "extract_topics", unavailable)
        return vault

    monkeypatch.setattr(benchmark, "Vault", create_vault)
    with pytest.raises(TopicIndexIncompleteError, match="incomplete"):
        benchmark.run_corpus(
            {"name": "rebuild-error-probe", "snapshots": 1},
            root,
            tmp_path / "report.json",
            (corpus, manifest),
        )
    assert instances == 2
    assert not (tmp_path / "report.json").exists()


@pytest.mark.parametrize("mutation", ["path", "content"])
def test_same_count_replay_mutation_cannot_be_certified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    corpus, root, manifest = _replay_fixture(tmp_path, "A")
    original = benchmark.apply_snapshot

    def corrupt_replay(corpus: Path, root: Path, index: int) -> dict[str, Any]:
        result = original(corpus, root, index)
        if mutation == "path":
            (root / "empty.md").rename(root / "replacement.md")
        else:
            (root / "empty.md").write_text("B")
        assert len(list(root.glob("*.md"))) == 1
        return result

    monkeypatch.setattr(benchmark, "apply_snapshot", corrupt_replay)
    with pytest.raises(AssertionError, match="paths or content"):
        benchmark.run_corpus(
            {"name": "same-count-replay-probe", "snapshots": 1},
            root,
            tmp_path / "report.json",
            (corpus, manifest),
        )
    assert not (tmp_path / "report.json").exists()
