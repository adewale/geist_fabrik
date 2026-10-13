#!/usr/bin/env python3
"""Measure real sync/index/analysis on an immutable large Markdown corpus.

Each trial uses a fresh copy and temporary database. Artificial date overlays
are explicitly labelled: the original corpus does not establish chronology.
Embedding inference and full invocation are not measured. Source hashes must
remain unchanged. Linux RSS includes package/ML imports.
"""

import argparse
import hashlib
import json
import platform
import resource
import shutil
import tempfile
import time
from contextlib import closing
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

from geistfabrik import GeistFabrikConfig, Vault
from geistfabrik.lexical_index import week_start
from geistfabrik.sqlite_transaction import owned_transaction
from geistfabrik.word_burst_analysis import WordBurstDiagnostics, analyze_word_bursts


def _manifest(source: Path) -> dict[str, str]:
    return {
        str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(source.rglob("*.md"))
    }


def benchmark(source: Path, *, trials: int = 3, ngram_max: int = 1) -> dict:
    """Fresh independent DB/copy per trial; retain exact source and result digests."""
    before = _manifest(source)
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "files": len(before),
        "bytes": sum((source / path).stat().st_size for path in before),
        "source_manifest_sha256": hashlib.sha256(
            json.dumps(before, sort_keys=True).encode()
        ).hexdigest(),
        "ngram_max": ngram_max,
        "trials": [],
        "synthetic_date_overlay": True,
        "embedding_inference": False,
    }
    end = date(2026, 10, 11)
    first = week_start(end) - timedelta(weeks=103)
    for trial in range(trials):
        with tempfile.TemporaryDirectory(prefix="word-burst-benchmark-") as directory:
            root = Path(directory) / "vault"
            shutil.copytree(source, root)
            config = GeistFabrikConfig()
            config.lexical_analysis.ngram_max = ngram_max
            with closing(Vault(root, db_path=Path(directory) / "vault.db", config=config)) as vault:
                row = {"trial": trial}
                started = time.perf_counter()
                vault.sync()
                row["cold_sync_seconds"] = time.perf_counter() - started
                started = time.perf_counter()
                vault.sync()
                row["warm_sync_seconds"] = time.perf_counter() - started
                row["warm_lexical_stats"] = vault.last_lexical_stats
                stats = WordBurstDiagnostics()
                started = time.perf_counter()
                raw = analyze_word_bursts(vault, end_day=end, diagnostics=stats)
                row["raw_analysis_seconds"] = time.perf_counter() - started
                row["raw_diagnostics"] = asdict(stats)
                row["raw_findings"] = len(raw)
                paths = [
                    r[0] for r in vault.db.execute("SELECT path FROM lexical_notes ORDER BY path")
                ]
                with owned_transaction(vault.db, "synthetic benchmark dates"):
                    vault.db.executemany(
                        "UPDATE lexical_notes SET cohort_day=?, "
                        "provenance='synthetic_overlay' WHERE path=?",
                        (
                            ((first + timedelta(weeks=i % 104)).isoformat(), path)
                            for i, path in enumerate(paths)
                        ),
                    )
                stats = WordBurstDiagnostics()
                started = time.perf_counter()
                findings = analyze_word_bursts(vault, end_day=end, diagnostics=stats)
                row["analysis_seconds"] = time.perf_counter() - started
                row["diagnostics"] = asdict(stats)
                row["findings"] = len(findings)
                started = time.perf_counter()
                cached = analyze_word_bursts(vault, end_day=end)
                row["cached_seconds"] = time.perf_counter() - started
                assert findings == cached
                row["result_sha256"] = hashlib.sha256(
                    json.dumps([asdict(f) for f in findings], sort_keys=True).encode()
                ).hexdigest()
                for path in list(before)[:100]:
                    target = root / path
                    target.write_text(
                        target.read_text(encoding="utf-8") + "\nbenchmarkmarker\n", encoding="utf-8"
                    )
                started = time.perf_counter()
                vault.sync()
                row["edit_100_sync_seconds"] = time.perf_counter() - started
                row["edit_lexical_stats"] = vault.last_lexical_stats
                row["dictionary_terms"] = vault.db.execute(
                    "SELECT count(*) FROM lexical_terms"
                ).fetchone()[0]
                row["database_bytes"] = (Path(directory) / "vault.db").stat().st_size
                row["process_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                report["trials"].append(row)
                print(
                    f"trial {trial + 1}/{trials}: decode {row['analysis_seconds']:.3f}s", flush=True
                )
    report["source_unchanged"] = _manifest(source) == before
    if not report["source_unchanged"]:
        raise RuntimeError("benchmark changed its source corpus")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--ngram-max", type=int, choices=[1, 2, 3], default=1)
    args = parser.parse_args()
    result = benchmark(args.source, trials=args.trials, ngram_max=args.ngram_max)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
