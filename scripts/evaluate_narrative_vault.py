#!/usr/bin/env python3
"""Observe full production invocations on a fictional changing vault.

No inference stubs or replaced scoring/filtering paths. The only clock patch
gives successful source captures their explicitly fictional observation time.
Run as ``python -m scripts.evaluate_narrative_vault`` from the checkout.
"""

import argparse
import gc
import hashlib
import io
import json
import os
import platform
import random
import resource
import subprocess
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from geistfabrik.cli import create_parser
from geistfabrik.commands.invoke import InvokeCommand
from geistfabrik.config_loader import GeistFabrikConfig, save_config
from geistfabrik.default_geists import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS
from geistfabrik.semantic_vectors import SEMANTIC_BYTES
from geistfabrik.session_time import session_seed
from geistfabrik.word_burst_analysis import WordBurstDiagnostics, analyze_word_bursts
from scripts.generate_temporal_corpus import apply_snapshot


class RecordingInvokeCommand(InvokeCommand):
    """Record inputs/outcomes around unmodified production command stages."""

    def __init__(self, args, record, stable_paths, stable_vectors):
        super().__init__(args)
        self.record = record
        self.stable_paths = stable_paths
        self.stable_vectors = stable_vectors

    def setup_execution_context(self, cmd_ctx, session_date):
        started = time.perf_counter()
        context = super().setup_execution_context(cmd_ctx, session_date)
        self.record["embedding_and_context_seconds"] = time.perf_counter() - started
        self.record["notes"] = len(context.vault_context.notes())
        self.record["lexical_sync"] = dict(context.vault.last_lexical_stats)
        self.record["future_note_dates"] = [
            note.path
            for note in context.vault_context.notes()
            if max(note.created.date(), note.modified.date()) > session_date.date()
        ]
        if self.record["future_note_dates"]:
            raise RuntimeError("replay leaked future note dates into the session")
        changed = []
        for path in self.stable_paths:
            row = context.vault.db.execute(
                "SELECT embedding FROM session_embeddings WHERE session_id=? AND note_path=?",
                (context.session.session_id, path),
            ).fetchone()
            if row is None:
                raise RuntimeError(f"stable source missing embedding: {path}")
            meaning = row[0][:SEMANTIC_BYTES]
            if path in self.stable_vectors and self.stable_vectors[path] != meaning:
                changed.append(path)
            self.stable_vectors.setdefault(path, meaning)
        self.record["stable_meaning_changes"] = changed
        # A deliberately simple, seeded linked-note reference prompt. It does
        # not enter the production candidates, selection or saved history.
        pairs = sorted(
            (note.link_text, other.link_text)
            for note in context.vault_context.notes()
            for other in context.vault_context.outgoing_links(note)
        )
        pair = random.Random(session_seed(session_date)).choice(pairs) if pairs else None
        self.record["linked_note_baseline"] = (
            {
                "text": f"What might change if you read [[{pair[0]}]] beside [[{pair[1]}]]?",
                "notes": list(pair),
            }
            if pair
            else None
        )
        return context

    def _execute_geists(self, exec_ctx, code_executor, tracery_geists):
        started = time.perf_counter()
        results = super()._execute_geists(exec_ctx, code_executor, tracery_geists)
        self.record["all_geists_seconds"] = time.perf_counter() - started
        self.record["execution_log"] = code_executor.get_execution_log()
        self.record["execution_profiles"] = [asdict(p) for p in code_executor.execution_profiles]
        if results is not None:
            self.record["by_geist"] = {
                name: [asdict(item) for item in suggestions]
                for name, suggestions in {**results.code_results, **results.tracery_results}.items()
            }
            self.record["raw"] = [asdict(item) for item in results.all_suggestions]
        return results

    def _filter_suggestions(self, suggestions, session_date):
        started = time.perf_counter()
        filtered, report = super()._filter_suggestions(suggestions, session_date)
        self.record["filter_seconds"] = time.perf_counter() - started
        self.record["filter_report"] = asdict(report) if report else None
        self.record["filtered"] = [asdict(item) for item in filtered]
        return filtered, report

    def _select_final_suggestions(self, filtered, session_date):
        selected = super()._select_final_suggestions(filtered, session_date)
        self.record["selected"] = [asdict(item) for item in selected]
        return selected

    def _write_journal(self, exec_ctx, session_date, suggestions):
        result = super()._write_journal(exec_ctx, session_date, suggestions)
        self.record["journal_written"] = result
        self.record["saved_count"] = exec_ctx.vault.db.execute(
            "SELECT count(*) FROM session_suggestions WHERE session_date=?",
            (session_date.strftime("%Y-%m-%d"),),
        ).fetchone()[0]
        # Inspect lexical evidence only AFTER normal execution/selection/write.
        # This diagnostic does not prime the measured executor or alter history.
        stats = WordBurstDiagnostics()
        findings = analyze_word_bursts(
            exec_ctx.vault, end_day=session_date.date(), diagnostics=stats
        )
        self.record["word_burst_diagnostics_after_invocation"] = asdict(stats)
        self.record["word_burst_findings"] = [finding.to_dict() for finding in findings]
        return result


def evaluate(
    corpus: Path, vault: Path, *, mode: str, output: Path, limit: int | None = None
) -> dict:
    """Replay a fresh dedicated vault, retaining partial evidence on failure."""
    if output.resolve().is_relative_to(vault.resolve()):
        raise ValueError("evaluation output must stay outside the ingested vault")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        raise ValueError("limit must be positive")
    if mode not in {"dated_cohorts", "observed_additions"}:
        raise ValueError("unknown history mode")
    os.environ["GEISTFABRIK_OFFLINE"] = "1"
    manifest_bytes = (corpus / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("profile") != "narrative-mara-v1":
        raise ValueError("requires the versioned narrative corpus")
    expected = sorted(DEFAULT_CODE_GEISTS + DEFAULT_TRACERY_GEISTS)
    checkout = Path(__file__).resolve().parents[1]
    code_files = sorted((checkout / "src/geistfabrik").rglob("*.py")) + [
        checkout / "scripts" / name
        for name in (
            "generate_temporal_corpus.py",
            "generate_narrative_corpus.py",
            "evaluate_narrative_vault.py",
        )
    ]
    report = {
        "synthetic": True,
        "mode": mode,
        "real_embeddings": True,
        "execution_path": "InvokeCommand.run with observational stage hooks",
        "clock_policy": "v2: capture clock and changed-source mtime use observed_at",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "ledger_sha256": manifest["ledger_sha256"],
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
        ).strip(),
        "code_sha256": {
            str(path.relative_to(checkout)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in code_files
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "expected_geists": expected,
        "ngram_max": 3,
        "limit": limit,
        "snapshots": [],
        "errors": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    logs = output.with_suffix(".logs")
    logs.mkdir(exist_ok=False)
    stable_vectors = {}
    started = time.perf_counter()
    try:
        for index, snapshot in enumerate(manifest["snapshots"][:limit]):
            apply_snapshot(corpus, vault, index)
            if index == 0:
                config = GeistFabrikConfig()
                config.lexical_analysis.ngram_max = 3
                config.word_burst.history_mode = mode
                config.default_geists = dict.fromkeys(expected, True)
                save_config(config, vault / "_geistfabrik/config.yaml")
                report["config"] = config.to_dict()
            observed = datetime.fromisoformat(snapshot["observed_at"])

            class Clock(datetime):
                @classmethod
                def now(cls, tz=None):
                    return observed.astimezone(tz or UTC)

            row = {"index": index, "date": snapshot["date"]}
            report["snapshots"].append(row)
            args = create_parser().parse_args(
                ["invoke", str(vault), "--date", snapshot["date"], "--write", "--explain"]
            )
            command = RecordingInvokeCommand(args, row, manifest["stable_paths"], stable_vectors)
            stream = io.StringIO()
            tick = time.perf_counter()
            with (
                redirect_stdout(stream),
                redirect_stderr(stream),
                patch("geistfabrik.vault.datetime", Clock),
            ):
                row["exit_code"] = command.run()
            row["invoke_seconds"] = time.perf_counter() - tick
            (logs / f"{index:02d}.log").write_text(stream.getvalue())
            actual = sorted(row.get("by_geist", {}))
            if actual != expected:
                report["errors"].append(
                    {"index": index, "kind": "missing_geists", "actual": actual}
                )
            for event in row.get("execution_log", []):
                if event["status"] != "success":
                    report["errors"].append({"index": index, **event})
            if row["exit_code"] or not row.get("journal_written"):
                report["errors"].append({"index": index, "kind": "invocation_or_write_failure"})
            row["peak_process_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (
                1024**2 if platform.system() == "Darwin" else 1024
            )
            row["db_bytes"] = (vault / "_geistfabrik/vault.db").stat().st_size
            output.write_text(json.dumps(report, indent=2) + "\n")
            print(
                f"{mode} {index + 1}/{len(manifest['snapshots'])}: {row['date']}, "
                f"{len(row.get('raw', []))} raw, {len(row.get('selected', []))} selected, "
                f"{row['invoke_seconds']:.2f}s",
                flush=True,
            )
            gc.collect()
            if row["exit_code"]:
                break
    except Exception as exc:
        report["errors"].append({"kind": "harness_failure", "error": repr(exc)})
    finally:
        report["wall_seconds"] = time.perf_counter() - started
        report["completed"] = len(report["snapshots"]) == len(manifest["snapshots"][:limit])
        output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("vault", type=Path)
    parser.add_argument("--mode", choices=("dated_cohorts", "observed_additions"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    result = evaluate(args.corpus, args.vault, mode=args.mode, output=args.output, limit=args.limit)
    raise SystemExit(bool(result["errors"]))
