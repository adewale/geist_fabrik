#!/usr/bin/env python3
"""Replay synthetic snapshots through real production components.

No test inference stubs. --real-embeddings enables the bundled offline model;
without it only lexical evidence is benchmarked and semantic work is skipped.
"""

import argparse
import hashlib
import importlib
import json
import os
import platform
import resource
import time
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

from generate_temporal_corpus import apply_snapshot

from geistfabrik import EmbeddingComputer, GeistFabrikConfig, Session, Vault, VaultContext
from geistfabrik.geist_executor import GeistExecutor
from geistfabrik.geist_status import GeistStatusStore
from geistfabrik.word_burst_analysis import WordBurstDiagnostics, analyze_word_bursts

GEISTS = (
    "word_burst",
    "concept_drift",
    "attention_shift",
    "temporal_drift",
    "recent_focus",
    "seasonal_patterns",
    "temporal_clustering",
    "this_time_last_year",
)


SIMILARITY_GEISTS = (
    "density_inversion",
    "concept_cluster",
    "bridge_builder",
    "method_scrambler",
    "surprisal",
)


def execute(executor, name, context, index, report):
    """Retain the production executor outcome, including swallowed failures."""
    started = time.perf_counter()
    suggestions = executor.execute_geist(name, context)
    event = executor.execution_log[-1]
    result = {
        "seconds": time.perf_counter() - started,
        "status": event["status"],
        "suggestions": [asdict(item) for item in suggestions],
    }
    if event["status"] != "success":
        failure = {"index": index, "geist": name, "error": event.get("error", event.get("reason"))}
        report["errors"].append(failure)
        result["error"] = failure["error"]
    return result


def replay(
    corpus: Path,
    vault_path: Path,
    *,
    real_embeddings: bool = False,
    ngram_max: int = 2,
    similarity_suite: bool = False,
    snapshot_limit: int | None = None,
) -> dict:
    """Sequential replay with timings, raw findings/suggestions, and stable-vector checks."""
    if snapshot_limit is not None and snapshot_limit < 1:
        raise ValueError("snapshot limit must be positive")
    manifest_bytes = (corpus / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    geists = GEISTS + (SIMILARITY_GEISTS if similarity_suite else ())
    encoder_work = {"calls": 0, "texts": 0}
    if vault_path.exists() and any(vault_path.iterdir()):
        raise ValueError("benchmark requires a fresh replay vault")
    vault_path.mkdir(parents=True, exist_ok=True)
    report = {
        "synthetic": True,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "similarity_suite": similarity_suite,
        "snapshot_limit": snapshot_limit,
        "execution_path": "GeistExecutor",
        "python": platform.python_version(),
        "initial_notes": manifest["initial_notes"],
        "real_embeddings": real_embeddings,
        "ngram_max": ngram_max,
        "snapshots": [],
        "errors": [],
        "stable_meaning_changes": [],
        "semantic_work_skipped": not real_embeddings,
    }
    computer = None
    stable_vectors = {}
    index = 0
    stage = "apply_snapshot"
    try:
        started = time.perf_counter()
        apply_snapshot(corpus, vault_path, 0)
        first_apply_seconds = time.perf_counter() - started
        if real_embeddings:
            stage = "model_startup"
            started = time.perf_counter()
            os.environ["GEISTFABRIK_OFFLINE"] = "1"
            computer = EmbeddingComputer()
            computer.device = "cpu"
            model = computer.model
            original_encode = model.encode

            def counted_encode(sentences, **kwargs):
                encoder_work["calls"] += 1
                encoder_work["texts"] += 1 if isinstance(sentences, str) else len(sentences)
                return original_encode(sentences, **kwargs)

            model.encode = counted_encode
            report["model_startup_seconds"] = time.perf_counter() - started
        stage = "open_vault"
        config = GeistFabrikConfig()
        config.lexical_analysis.ngram_max = ngram_max
        with closing(
            Vault(vault_path, db_path=vault_path / "_geistfabrik/vault.db", config=config)
        ) as vault:
            executor = GeistExecutor(
                vault_path / "_geistfabrik/geists/code", status_store=GeistStatusStore(vault.db)
            )
            for name in geists if real_embeddings else ("word_burst",):
                module = importlib.import_module("geistfabrik.default_geists.code." + name)
                executor.register_geist(name, Path(module.__file__), module.suggest)
            for index, snapshot in enumerate(manifest["snapshots"][:snapshot_limit]):
                stage = "apply_snapshot"
                started = time.perf_counter()
                if index:
                    apply_snapshot(corpus, vault_path, index)
                row = {
                    "index": index,
                    "date": snapshot["date"],
                    "apply_seconds": time.perf_counter() - started
                    if index
                    else first_apply_seconds,
                }
                observed = datetime.fromisoformat(snapshot["observed_at"])

                class Clock(datetime):
                    @classmethod
                    def now(cls, tz=None):
                        return observed.astimezone(tz or UTC)

                started = time.perf_counter()
                stage = "sync"
                with patch("geistfabrik.vault.datetime", Clock):
                    row["processed"] = vault.sync()
                row["sync_seconds"] = time.perf_counter() - started
                row["lexical_sync"] = dict(vault.last_lexical_stats)
                if similarity_suite:
                    started = time.perf_counter()
                    with patch("geistfabrik.vault.datetime", Clock):
                        row["unchanged_processed"] = vault.sync()
                    row["unchanged_sync_seconds"] = time.perf_counter() - started
                    row["unchanged_lexical_sync"] = dict(vault.last_lexical_stats)
                row["lexical"] = {}
                row["geists"] = {}
                with Session(observed.replace(tzinfo=None), vault.db, computer=computer) as session:
                    if computer is not None:
                        stage = "embeddings"
                        started = time.perf_counter()
                        session.compute_embeddings(vault.all_notes())
                        row["embedding_seconds"] = time.perf_counter() - started
                        if similarity_suite:
                            encoded_before = encoder_work["texts"]
                            changes_before = vault.db.total_changes
                            started = time.perf_counter()
                            session.compute_embeddings(vault.all_notes())
                            row["unchanged_embedding_seconds"] = time.perf_counter() - started
                            row["unchanged_embedding_texts"] = (
                                encoder_work["texts"] - encoded_before
                            )
                            row["unchanged_embedding_db_changes"] = (
                                vault.db.total_changes - changes_before
                            )
                    started = time.perf_counter()
                    context = VaultContext(vault, session)
                    row["context_seconds"] = time.perf_counter() - started
                    for mode in ("dated_cohorts", "observed_additions"):
                        stage = "analysis:" + mode
                        vault.config.word_burst.history_mode = mode
                        stats = WordBurstDiagnostics()
                        started = time.perf_counter()
                        findings = analyze_word_bursts(
                            vault, end_day=date.fromisoformat(snapshot["date"]), diagnostics=stats
                        )
                        row["lexical"][mode] = {
                            "seconds": time.perf_counter() - started,
                            "diagnostics": asdict(stats),
                            "findings": [f.to_dict() for f in findings],
                        }
                        stage = "executor:" + mode
                        row["lexical"][mode]["executor"] = execute(
                            executor, "word_burst", context, index, report
                        )
                    vault.config.word_burst.history_mode = "dated_cohorts"
                    row["geists"]["word_burst"] = row["lexical"]["dated_cohorts"]["executor"]
                    if computer is not None:
                        stage = "stable_vectors"
                        for path in manifest["stable_paths"]:
                            blob = vault.db.execute(
                                "SELECT embedding FROM session_embeddings WHERE session_id=? "
                                "AND note_path=?",
                                (session.session_id, path),
                            ).fetchone()[0][: 384 * 4]
                            if path in stable_vectors and stable_vectors[path] != blob:
                                report["stable_meaning_changes"].append(
                                    {"index": index, "path": path}
                                )
                            stable_vectors.setdefault(path, blob)
                        for name in geists[1:]:
                            stage = "executor:" + name
                            row["geists"][name] = execute(executor, name, context, index, report)
                row["encoder_cumulative"] = dict(encoder_work)
                row["text_cache_bytes"] = getattr(
                    getattr(computer, "text_cache", None), "retained_bytes", 0
                )
                row["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                report["snapshots"].append(row)
                print(
                    f"snapshot {index + 1}/{len(manifest['snapshots'])}: {row['date']}", flush=True
                )
    except Exception as exc:
        report["errors"].append({"index": index, "stage": stage, "error": repr(exc)})
    finally:
        if computer is not None:
            try:
                computer.close()
            except Exception as exc:
                report["errors"].append(
                    {"index": index, "stage": "close_model", "error": repr(exc)}
                )
    report["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["encoder"] = encoder_work
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("vault", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--real-embeddings", action="store_true")
    parser.add_argument("--ngram-max", type=int, choices=[1, 2, 3], default=2)
    parser.add_argument(
        "--similarity-suite",
        action="store_true",
        help="Also benchmark density, clusters, bridges, SCAMPER and surprisal",
    )
    parser.add_argument(
        "--snapshot-limit", type=int, help="Replay only this many initial snapshots"
    )
    args = parser.parse_args()
    result = replay(
        args.corpus,
        args.vault,
        real_embeddings=args.real_embeddings,
        ngram_max=args.ngram_max,
        similarity_suite=args.similarity_suite,
        snapshot_limit=args.snapshot_limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    if result["errors"] or result["stable_meaning_changes"]:
        raise SystemExit(1)
