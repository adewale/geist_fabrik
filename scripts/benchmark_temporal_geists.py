#!/usr/bin/env python3
"""Replay synthetic snapshots through real production components.

No test inference stubs. --real-embeddings enables the bundled offline model;
without it only lexical evidence is benchmarked and semantic work is skipped.
"""

import argparse
import importlib
import json
import os
import platform
import time
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

from generate_temporal_corpus import apply_snapshot

from geistfabrik import EmbeddingComputer, Session, Vault, VaultContext
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


def replay(corpus: Path, vault_path: Path, *, real_embeddings: bool = False) -> dict:
    """Sequential replay with timings, raw findings/suggestions, and stable-vector checks."""
    manifest = json.loads((corpus / "manifest.json").read_text())
    if vault_path.exists() and any(vault_path.iterdir()):
        raise ValueError("benchmark requires a fresh replay vault")
    vault_path.mkdir(parents=True, exist_ok=True)
    report = {
        "synthetic": True,
        "python": platform.python_version(),
        "initial_notes": manifest["initial_notes"],
        "real_embeddings": real_embeddings,
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
            _ = computer.model
            report["model_startup_seconds"] = time.perf_counter() - started
        stage = "open_vault"
        with closing(Vault(vault_path, db_path=vault_path / "_geistfabrik/vault.db")) as vault:
            for index, snapshot in enumerate(manifest["snapshots"]):
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
                row["lexical_sync"] = vault.last_lexical_stats
                row["lexical"] = {}
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
                        "findings": [asdict(f) for f in findings],
                    }
                vault.config.word_burst.history_mode = "dated_cohorts"
                if computer is not None:
                    stage = "embeddings"
                    with Session(
                        observed.replace(tzinfo=None), vault.db, computer=computer
                    ) as session:
                        started = time.perf_counter()
                        session.compute_embeddings(vault.all_notes())
                        row["embedding_seconds"] = time.perf_counter() - started
                        context = VaultContext(vault, session)
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
                        row["geists"] = {}
                        stage = "geists"
                        for name in GEISTS:
                            started = time.perf_counter()
                            try:
                                module = importlib.import_module(
                                    "geistfabrik.default_geists.code." + name
                                )
                                suggestions = module.suggest(context)
                                row["geists"][name] = {
                                    "seconds": time.perf_counter() - started,
                                    "suggestions": [asdict(s) for s in suggestions],
                                }
                            except Exception as exc:
                                failure = {"index": index, "geist": name, "error": repr(exc)}
                                report["errors"].append(failure)
                                row["geists"][name] = {
                                    "seconds": time.perf_counter() - started,
                                    "error": repr(exc),
                                }
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
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("vault", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--real-embeddings", action="store_true")
    args = parser.parse_args()
    result = replay(args.corpus, args.vault, real_embeddings=args.real_embeddings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    if result["errors"] or result["stable_meaning_changes"]:
        raise SystemExit(1)
