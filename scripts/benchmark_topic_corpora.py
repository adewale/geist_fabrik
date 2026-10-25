"""Exercise topics on the merged-PR corpora, retaining provenance and unrated samples.

No inferred owner judgments, embeddings, geists or source edits. Lexical capture
is disabled to isolate raw sync plus topic indexing from the word-burst index.
"""

import argparse
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
from collections import Counter
from contextlib import closing
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from geistfabrik import GeistFabrikConfig, Vault
from geistfabrik.topics import TopicIndex, extract_topics
from scripts.evaluate_topics import evaluate_gold
from scripts.generate_narrative_corpus import generate_narrative_corpus
from scripts.generate_temporal_corpus import apply_snapshot, generate_corpus

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "benchmarks/corpora/topic_corpora.json"


def inventory(root: Path, expected: dict[str, str] | None = None) -> dict:
    """Hash every source before/after; do not include generated database state."""
    rows = []
    total = 0
    for path in sorted(root.rglob("*.md")):
        if path.is_symlink():
            raise ValueError("corpus source symlink is not allowed")
        raw = path.read_bytes()
        total += len(raw)
        rows.append([str(path.relative_to(root)), hashlib.sha256(raw).hexdigest()])
    if expected is not None and dict(rows) != expected:
        raise AssertionError("replayed source manifest differs in paths or content")
    digest = hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()
    return {"files": len(rows), "bytes": total, "sha256": digest}


def topic_digest(vault: Vault, paths: list[str] | None = None) -> str:
    """Compare full derived evidence, rather than count-only success."""
    rows = list(
        vault.db.execute(
            "SELECT note_path,topic_key,label,score,source_start,source_end,source_text,"
            "source_line,provenance FROM note_topics ORDER BY note_path,topic_key"
        )
    )
    if paths is not None:
        allowed = set(paths)
        rows = [row for row in rows if row[0] in allowed]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


def observe(vault: Vault) -> dict:
    """Check current states, source spans and positive membership independently."""
    index = TopicIndex(vault.db, vault.config.filtering.exclude_paths)
    states = index.states()
    index.require_complete(states)
    for content, start, end, text, line in vault.db.execute(
        "SELECT n.content,t.source_start,t.source_end,t.source_text,t.source_line "
        "FROM note_topics t JOIN notes n ON n.path=t.note_path"
    ):
        if content[start:end] != text or content.count("\n", 0, start) + 1 != line:
            raise AssertionError("topic evidence no longer matches its exact source")
    started = perf_counter()
    catalog = index.catalog()
    catalog_seconds = perf_counter() - started
    queries = []
    for key, count in catalog[:5]:
        started = perf_counter()
        paths = index.paths(key)
        elapsed = perf_counter() - started
        expected = [
            row[0]
            for row in vault.db.execute(
                "SELECT note_path FROM note_topics WHERE topic_key=? ORDER BY note_path", (key,)
            )
        ]
        if not paths or paths != expected or len(paths) != count:
            raise AssertionError("positive membership does not match stored eligible evidence")
        queries.append({"topic": key, "matches": count, "seconds": elapsed})
    return {
        "notes": len(states),
        "virtual_entries": vault.db.execute(
            "SELECT COUNT(*) FROM notes WHERE is_virtual=1"
        ).fetchone()[0],
        "states": dict(Counter(state.status for state in states.values())),
        "assigned_labels": vault.db.execute("SELECT COUNT(*) FROM note_topics").fetchone()[0],
        "vocabulary": len(catalog),
        "catalog_seconds": catalog_seconds,
        "positive_queries": queries,
        "exact_evidence_checked": True,
    }


def sync_probe(vault: Vault) -> dict:
    started = perf_counter()
    with patch("geistfabrik.topics.extract_topics", wraps=extract_topics) as extractor:
        processed = vault.sync()
        extracted = extractor.call_count
    return {
        "seconds": perf_counter() - started,
        "raw_processed": processed,
        "topic_extractions": extracted,
    }


def samples(vault: Vault, root: Path, selection: list[dict], spec: dict) -> list[dict]:
    index = TopicIndex(vault.db, vault.config.filtering.exclude_paths)
    result = []
    for selected in selection:
        relative = selected["path"]
        raw = (root / relative).read_bytes()
        if selected.get("source_sha256") not in (None, hashlib.sha256(raw).hexdigest()):
            raise AssertionError("frozen narrative sample source changed")
        if "sha" in selected:
            git_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            if git_blob != selected["sha"]:
                raise AssertionError("frozen sample source changed")
        state = index.state(relative)
        result.append(
            {
                "path": relative,
                "stratum": selected.get("stratum"),
                "source_sha256": hashlib.sha256(raw).hexdigest(),
                "source_repository": spec.get("repository"),
                "source_commit": spec.get("commit"),
                "state": asdict(state),
                "topics": (
                    [asdict(tag) for tag in index.tags(relative)]
                    if state.status == "complete"
                    else []
                ),
                "human_reviewed": False,
                "usefulness": None,
            }
        )
        if selected.get("stratum") == "excluded-template" and state.status != "excluded":
            raise AssertionError("configured template entered the eligible population")
    return result


def run_corpus(
    spec: dict, root: Path, output: Path, replay: tuple[Path, dict] | None = None
) -> dict:
    checkout_commit = None
    if spec.get("repository"):
        checkout_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        if checkout_commit != spec["commit"]:
            raise AssertionError("external corpus checkout differs from its pinned commit")
        subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "."], cwd=root, check=True)
    config = GeistFabrikConfig()
    config.lexical_analysis.enabled = False
    config.filtering.exclude_paths = spec.get("exclude_paths", [])
    records = replay[1]["snapshots"][: spec["snapshots"]] if replay else [None]
    report = {
        "corpus": spec,
        "source_checkout_commit": checkout_commit,
        "lexical_capture_enabled": False,
        "snapshots": [],
    }
    stable = replay[1]["stable_paths"] if replay else None
    with closing(Vault(root, config=config)) as vault:
        first_stable = None
        for record in records:
            if record is not None:
                apply_snapshot(replay[0], root, record["index"])
            before = inventory(root, record["files"] if record is not None else None)
            run = sync_probe(vault)
            run.update(observe(vault))
            run["snapshot"] = record["index"] if record else 0
            run["source_inventory"] = before
            if inventory(root) != before:
                raise AssertionError("sync modified source notes")
            if stable is not None:
                current = topic_digest(vault, stable)
                if first_stable is None:
                    first_stable = current
                if current != first_stable:
                    raise AssertionError("stable source topic evidence changed across snapshots")
            report["snapshots"].append(run)
            print(
                json.dumps(
                    {
                        "progress": spec["name"],
                        "snapshot": run["snapshot"],
                        "seconds": run["seconds"],
                        "notes": run["notes"],
                    }
                ),
                flush=True,
            )
        digest = topic_digest(vault)
        before_warm = inventory(root)
        report["warm_sync"] = sync_probe(vault)
        if (
            report["warm_sync"]["raw_processed"]
            or report["warm_sync"]["topic_extractions"]
            or topic_digest(vault) != digest
        ):
            raise AssertionError("unchanged sync redid extraction or changed evidence")
        report["warm_observation"] = observe(vault)
        selection = spec.get("quality_sample", [])
        report["unrated_quality_sample"] = samples(vault, root, selection, spec)
        if spec.get("quality_proxy_fixture"):
            report["model_quality_proxy"] = evaluate_gold(
                REPO / spec["quality_proxy_fixture"], source_root=root
            )
        if replay is not None:
            with closing(Vault(root, config=config)) as rebuilt:
                rebuilt.sync()
                report["rebuilt_observation"] = observe(rebuilt)
                original_states = TopicIndex(vault.db, config.filtering.exclude_paths).states()
                rebuilt_states = TopicIndex(rebuilt.db, config.filtering.exclude_paths).states()
                if original_states != rebuilt_states:
                    raise AssertionError("clean rebuild differs in note completeness or population")
                if topic_digest(rebuilt) != digest:
                    raise AssertionError("incremental evidence differs from a clean rebuild")
        if inventory(root) != before_warm:
            raise AssertionError("warm/rebuild verification modified source notes")
        report["clean_rebuild_matches"] = True if replay is not None else None
        report["source_unchanged"] = True
        report["stable_controls_unchanged"] = stable is not None
        report["final_digest"] = digest
    expected_files = spec.get("expected_markdown_files")
    if expected_files is not None and before_warm["files"] != expected_files:
        raise AssertionError("corpus population differs from its pinned inventory")
    if "expected_bytes" in spec and before_warm["bytes"] != spec["expected_bytes"]:
        raise AssertionError("corpus byte count differs from historical input")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--lyt", type=Path, required=True)
    parser.add_argument("--stress", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(MANIFEST.read_text())
    reports = []
    for spec in manifest["corpora"]:
        name = spec["name"]
        if name == "narrative-mara-v1":
            corpus = args.work / (name + "-corpus")
            data = generate_narrative_corpus(corpus)
        elif name.startswith("temporal-"):
            corpus = args.work / (name + "-corpus")
            data = generate_corpus(corpus, notes=spec["initial_notes"], snapshots=32)
        else:
            root = args.lyt if name == "lyt-kit-mirror" else args.stress
            reports.append(run_corpus(spec, root, args.work / (name + ".json")))
            continue
        root = args.work / (name + "-replay")
        root.mkdir()
        reports.append(run_corpus(spec, root, args.work / (name + ".json"), (corpus, data)))
    bundle = {
        "runtime_source_commit": os.environ.get("TOPIC_SOURCE_COMMIT"),
        "measured_git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip(),
        "source_files_sha256": {
            relative: hashlib.sha256((REPO / relative).read_bytes()).hexdigest()
            for relative in (
                "src/geistfabrik/topics.py",
                "src/geistfabrik/topic_text.py",
                "src/geistfabrik/topic_grammar.py",
                "src/geistfabrik/topic_selection.py",
                "src/geistfabrik/vault.py",
                "scripts/benchmark_topic_corpora.py",
                "scripts/generate_temporal_corpus.py",
                "scripts/generate_narrative_corpus.py",
            )
        },
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "yake": version("yake"),
        "markdown_it": version("markdown-it-py"),
        "textblob": version("textblob"),
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "reports": reports,
        "limitation": (
            "Functional/scale evidence and unrated authored-note samples; "
            "not human usefulness ratings."
        ),
    }
    (args.work / "summary.json").write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n")
    print("TOPIC_CORPORA_REPORT_BEGIN", flush=True)
    print(json.dumps(bundle, ensure_ascii=False), flush=True)
    print("TOPIC_CORPORA_REPORT_END", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
