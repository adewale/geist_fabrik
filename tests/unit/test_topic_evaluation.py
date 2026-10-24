"""Frozen quality gates plus checks that the evaluator cannot hide bad labels."""

import hashlib
import json
from pathlib import Path

import pytest

from geistfabrik.topics import MAX_TOPICS, TopicTag
from scripts import evaluate_topics


@pytest.mark.parametrize("name", evaluate_topics.FIXTURE_NAMES)
def test_frozen_topic_calibration_thresholds(name: str) -> None:
    report = evaluate_topics.evaluate_gold(
        evaluate_topics.REPO / "tests" / "fixtures" / f"{name}.json"
    )
    assert report["passed"], json.dumps(report, indent=2, ensure_ascii=False)


def _fixture(path: Path, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "limit": MAX_TOPICS,
        "minimum_precision": 0.9,
        "minimum_recall": 0.6,
        "notes": [
            {
                "id": "complete-output",
                "content": "alpha beta gamma delta noisy",
                "expected": [["alpha"]],
                "acceptable": ["alpha", "beta", "gamma", "delta"],
            }
        ],
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload))
    return path


def _tag(label: str) -> TopicTag:
    return TopicTag(label, label, 0.1, 0, len(label), label, 1)


def test_evaluator_scores_every_assigned_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _fixture(tmp_path / "gold.json")
    monkeypatch.setattr(
        evaluate_topics,
        "extract_topics",
        lambda _content: [_tag(label) for label in ["alpha", "beta", "gamma", "delta", "noisy"]],
    )
    report = evaluate_topics.evaluate_gold(path)
    assert report["metrics"]["yake"] == {"precision": 0.8, "recall": 1.0}
    assert not report["passed"]
    assert len(report["cases"][0]["predictions"]["yake"]) == MAX_TOPICS


def test_evaluation_limit_cannot_hide_an_assigned_suffix(tmp_path: Path) -> None:
    path = _fixture(tmp_path / "gold.json", limit=MAX_TOPICS - 1)
    with pytest.raises(AssertionError, match="shipped maximum"):
        evaluate_topics.evaluate_gold(path)


def test_real_source_checksum_is_checked_before_extraction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.md"
    original = b"alpha"
    source.write_bytes(original)
    path = _fixture(
        tmp_path / "gold.json",
        notes=[
            {
                "id": "frozen-source",
                "source_path": "note.md",
                "source_sha256": hashlib.sha256(original).hexdigest(),
                "expected": [["alpha"]],
                "acceptable": ["alpha"],
            }
        ],
    )
    monkeypatch.setattr(evaluate_topics, "extract_topics", lambda _content: [_tag("alpha")])
    assert evaluate_topics.evaluate_gold(path, source_root=tmp_path)["passed"]
    source.write_bytes(b"beta")
    with pytest.raises(AssertionError, match="Frozen source changed: note.md"):
        evaluate_topics.evaluate_gold(path, source_root=tmp_path)


def test_empty_case_noise_cannot_disappear_from_macro_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _fixture(
        tmp_path / "gold.json",
        notes=[
            {"id": "subject", "content": "alpha", "expected": [["alpha"]], "acceptable": ["alpha"]},
            {"id": "stub", "content": "", "expected": [], "acceptable": []},
        ],
    )
    monkeypatch.setattr(evaluate_topics, "extract_topics", lambda _content: [_tag("alpha")])
    report = evaluate_topics.evaluate_gold(path)
    assert report["metrics"]["yake"] == {"precision": 1.0, "recall": 1.0}
    assert report["empty_violations"] == [{"id": "stub", "extractor": "yake", "labels": ["alpha"]}]
    assert not report["passed"]
