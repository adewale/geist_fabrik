#!/usr/bin/env python3
"""Publish a compact temporal report and a lossless compressed raw archive."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def summarize(source: Path, output: Path) -> dict:
    """Retain raw evidence durably without a multi-megabyte rendered JSON diff."""
    data = source.read_bytes()
    report = json.loads(data)
    summary = {key: value for key, value in report.items() if key != "snapshots"}
    summary["raw_sha256"] = hashlib.sha256(data).hexdigest()
    archive = output.with_suffix(".raw.json.gz")
    summary["raw_archive"] = archive.name
    summary["snapshots"] = []
    for snapshot in report["snapshots"]:
        row = {key: value for key, value in snapshot.items() if key not in {"lexical", "geists"}}
        row["lexical"] = {}
        for mode, analysis in snapshot["lexical"].items():
            row["lexical"][mode] = {
                "seconds": analysis["seconds"],
                "diagnostics": analysis["diagnostics"],
                "finding_count": len(analysis["findings"]),
                "planted_findings": [
                    {
                        **{k: v for k, v in f.items() if k != "support_paths"},
                        "support_count": len(f["support_paths"]),
                    }
                    for f in analysis["findings"]
                    if f["term"] in {"aurora", "quasar"}
                ],
            }
        row["geists"] = {
            name: {
                "seconds": result["seconds"],
                "suggestion_count": len(result.get("suggestions", [])),
                **({"error": result["error"]} if "error" in result else {}),
            }
            for name, result in snapshot.get("geists", {}).items()
        }
        summary["snapshots"].append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    compressed = gzip.compress(data, mtime=0)
    assert gzip.decompress(compressed) == data
    archive.write_bytes(compressed)
    output.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    summarize(args.source, args.output)
