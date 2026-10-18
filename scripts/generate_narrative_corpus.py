#!/usr/bin/env python3
"""Compile authored fiction into the existing safe, content-addressed replay format.

Run as ``python -m scripts.generate_narrative_corpus OUTPUT`` from the checkout.
The independent persona/ledger stay outside the ingested snapshots.
"""

import argparse
import calendar
import hashlib
import json
from datetime import date
from pathlib import Path

from geistfabrik.markdown_parser import parse_frontmatter
from scripts.generate_temporal_corpus import _store

DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "testdata/narrative_vault"


def generate_narrative_corpus(output: Path, source: Path = DEFAULT_SOURCE) -> dict:
    """Compile exactly 24 month-end snapshots without consulting engine outputs."""
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError("output must be outside the immutable author sources")
    entries = json.loads((source / "entries.json").read_text())
    revisions = json.loads((source / "revisions.json").read_text())
    journal = json.loads((source / "journal.json").read_text())
    source_hashes = {
        str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(source.rglob("*"))
        if path.is_file()
    }
    assert len({entry["path"] for entry in entries}) == len(entries)
    output.mkdir(parents=True, exist_ok=False)
    objects = output / "objects"
    objects.mkdir()
    records = []
    previous = {}
    for month in range(24):
        year, number = 2024 + month // 12, month % 12 + 1
        day = date(year, number, calendar.monthrange(year, number)[1])
        files = {}
        for entry in entries:
            created = date.fromisoformat(entry["created"])
            available = date.fromisoformat(entry.get("available_from", entry["created"]))
            if available > day:
                continue
            path = entry["path"]
            text = (source / "notes" / path).read_text()
            metadata, _ = parse_frontmatter(text)
            if str(metadata["created"]) != created.isoformat():
                raise ValueError(f"creation date disagrees with source: {path}")
            deleted = False
            for revision in sorted(revisions, key=lambda item: item["at"]):
                if revision["path"] == path and date.fromisoformat(revision["at"]) <= day:
                    if revision["kind"] == "delete":
                        deleted = True
                    else:
                        text = (source / revision["source"]).read_text()
            if not deleted:
                files[path] = _store(objects, text)
        dated_entries = [entry for entry in journal if date.fromisoformat(entry["date"]) <= day]
        text = "# Working journal\n" + "".join(
            f"\n## {entry['date']}\n\n{entry['text']}\n" for entry in dated_entries
        )
        files["Journal.md"] = _store(objects, text)
        records.append(
            {
                "index": month,
                "date": day.isoformat(),
                "observed_at": day.isoformat() + "T12:00:00+00:00",
                "files": files,
                "changed_paths": sorted(
                    path for path in files if previous.get(path) != files[path]
                ),
                "deleted_paths": sorted(previous.keys() - files.keys()),
            }
        )
        previous = files
    stable = [
        path
        for path in records[0]["files"]
        if len({row["files"].get(path) for row in records}) == 1
    ]
    manifest = {
        "version": 1,
        "synthetic": True,
        "profile": "narrative-mara-v1",
        "initial_notes": len(records[0]["files"]),
        "source_files_sha256": source_hashes,
        "ledger_sha256": source_hashes["ledger.json"],
        "snapshots": records,
        "stable_paths": stable,
        "scenarios": json.loads((source / "ledger.json").read_text())["scenarios"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = generate_narrative_corpus(args.output)
    print(
        f"{len(result['snapshots'])} snapshots; {len(result['snapshots'][-1]['files'])} final files"
    )
