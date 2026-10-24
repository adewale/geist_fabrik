"""Score frozen topic calibration fixtures and a frequency baseline, without tuning labels.

These small source-first model annotations are regression evidence, not a
representative human-reviewed quality study or an untouched holdout after tuning.
"""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from geistfabrik.topics import MAX_TOPICS, extract_topics, topic_key, topic_prose

REPO = Path(__file__).resolve().parents[1]
FIXTURE_NAMES = ("topic_gold", "topic_real_gold")


def _content(note: dict[str, Any], source_root: Path) -> str:
    if "source_path" not in note:
        return str(note["content"])
    source = source_root / note["source_path"]
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != note["source_sha256"]:
        raise AssertionError(f"Frozen source changed: {note['source_path']}")
    return raw.decode("utf-8")


def evaluate_gold(path: Path, *, source_root: Path = REPO) -> dict[str, Any]:
    """Evaluate every assigned label; source-first relevance remains the oracle."""
    gold = json.loads(path.read_text())
    if gold["limit"] != MAX_TOPICS:
        raise AssertionError("Fixture limit must equal the shipped maximum assigned labels")
    totals: dict[str, list[tuple[float, float]]] = {"yake": [], "frequency": []}
    cases: list[dict[str, Any]] = []
    empty_violations: list[dict[str, Any]] = []
    for note in gold["notes"]:
        content = _content(note, source_root)
        tags = extract_topics(content)
        if len(tags) > MAX_TOPICS:
            raise AssertionError("Extractor assigned more labels than its public limit")
        words = re.findall(r"(?u)\b[^\W\d_]{2,}\b", topic_prose(content).casefold())
        counts = Counter(word for word in words if word not in ENGLISH_STOP_WORDS)
        predictions = {
            "yake": [tag.key for tag in tags],
            "frequency": sorted(counts, key=lambda word: (-counts[word], word))[:MAX_TOPICS],
        }
        expected = [{topic_key(alias) for alias in group} for group in note["expected"]]
        acceptable = {topic_key(label) for label in note["acceptable"]}
        case: dict[str, Any] = {"id": note["id"], "predictions": predictions}
        for name, labels in predictions.items():
            precision = sum(label in acceptable for label in labels) / max(1, len(labels))
            recall = sum(bool(group.intersection(labels)) for group in expected) / max(
                1, len(expected)
            )
            case[name] = {"precision": precision, "recall": recall}
            if expected:
                totals[name].append((precision, recall))
            elif any(label not in acceptable for label in labels):
                empty_violations.append({"id": note["id"], "extractor": name, "labels": labels})
        cases.append(case)
    metrics = {
        name: {
            "precision": sum(precision for precision, _ in scores) / max(1, len(scores)),
            "recall": sum(recall for _, recall in scores) / max(1, len(scores)),
        }
        for name, scores in totals.items()
    }
    passed = (
        bool(totals["yake"])
        and metrics["yake"]["precision"] >= gold["minimum_precision"]
        and metrics["yake"]["recall"] >= gold["minimum_recall"]
        and not any(item["extractor"] == "yake" for item in empty_violations)
    )
    return {
        "passed": passed,
        "limit": MAX_TOPICS,
        "cases_with_required_topics": len(totals["yake"]),
        "minimum_precision": gold["minimum_precision"],
        "minimum_recall": gold["minimum_recall"],
        "metrics": metrics,
        "cases": cases,
        "empty_violations": empty_violations,
        "annotation_provenance": gold.get("provenance"),
        "limitation": "Small model-annotated calibration/regression set; broad quality unverified",
    }


def main() -> int:
    """Emit both fixed reports and fail if either published threshold is unmet."""
    reports = {
        name: evaluate_gold(REPO / "tests" / "fixtures" / f"{name}.json")
        for name in FIXTURE_NAMES
    }
    print(json.dumps(reports, indent=2, ensure_ascii=False))
    return 0 if all(report["passed"] for report in reports.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
