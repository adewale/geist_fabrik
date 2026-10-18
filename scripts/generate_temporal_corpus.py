#!/usr/bin/env python3
"""Deterministic changing Obsidian corpus; all dates and histories are synthetic.

Content-addressed objects avoid storing an unchanged note 32 times. A manifest
records exact snapshots, transitions, stable controls and planted scenarios.
Replaying writes only to an explicitly empty/dedicated benchmark vault.
"""

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

VERSION = 1
PROFILES = {"smoke": 128, "standard": 1000, "large": 10_000}
TOPICS = (
    "Forest soil ecology studies roots, fungi, rainfall and biodiversity.",
    "Garden cultivation considers compost, seedlings, pollinators and irrigation.",
    "Urban planning considers public transport, housing, streets and community spaces.",
    "Software engineering considers algorithms, interfaces, testing and database design.",
    "Financial planning studies budgets, investment, interest rates and retirement.",
    "Music composition explores melody, rhythm, harmony and instrumental performance.",
    "Ocean science studies currents, coral reefs, plankton and marine ecosystems.",
    "Astronomy observes galaxies, telescopes, planetary orbits and stellar evolution.",
)


def identity(number: int) -> str:
    """Alphabetic identity survives lexical normalization (numeric IDs do not)."""
    letters = []
    while True:
        number, digit = divmod(number, 26)
        letters.append(chr(97 + digit))
        if not number:
            break
    return "specimen" + "".join(reversed(letters))


def generate_corpus(output: Path, *, notes: int = 1000, snapshots: int = 32) -> dict:
    """Create deterministic snapshots and SHA-256 objects; refuse existing output."""
    if isinstance(notes, bool) or not isinstance(notes, int) or not 64 <= notes <= 100_000:
        raise ValueError("notes must be an integer in [64, 100000]")
    if isinstance(snapshots, bool) or not isinstance(snapshots, int) or not 2 <= snapshots <= 104:
        raise ValueError("snapshots must be an integer in [2, 104]")
    output.mkdir(parents=True, exist_ok=False)
    objects = output / "objects"
    objects.mkdir()
    start = date(2026, 1, 5)
    stable_limit = notes * 3 // 5
    gradual_limit = notes * 7 // 10
    abrupt_limit = notes * 8 // 10
    writers_limit = notes * 9 // 10
    stable = [f"Notes/Note {i:05d}.md" for i in range(stable_limit)]
    records = []
    previous: dict[str, str] = {}
    for week in range(snapshots):
        observed = start + timedelta(weeks=week)
        files = {}
        for i in range(notes):
            path = f"Notes/Note {i:05d}.md"
            if i >= writers_limit and week >= 24:
                continue
            created = start - timedelta(days=540 - i % 520)
            modified = created
            topic = i % len(TOPICS)
            if stable_limit <= i < gradual_limit:
                topic = (topic + week // 4) % len(TOPICS)
                if week >= 4:
                    modified = start + timedelta(weeks=(week // 4) * 4)
            elif gradual_limit <= i < abrupt_limit and week >= 16:
                topic = (topic + 4) % len(TOPICS)
                modified = start + timedelta(weeks=16)
            if abrupt_limit <= i < writers_limit and week:
                modified = observed
            text = (
                f"---\ncreated: {created}\nmodified: {modified}\ntitle: {identity(i)}\n---\n"
                f"{TOPICS[topic]}\nAn independent field record for {identity(i)}.\n"
                f"Connected to [[Notes/Note {(i + 1) % notes:05d}|a related record]].\n"
                f"Also [[Notes/Note {(i + 2) % notes:05d}|another related record]].\n"
            )
            if abrupt_limit <= i < writers_limit:
                for event_week in range(1, week + 1):
                    burst = (
                        "aurora"
                        if 8 <= event_week <= 11
                        else ("quasar" if 22 <= event_week <= 25 else "reflection")
                    )
                    text += f"Observation {identity(event_week)}: {burst} prompts a new question.\n"
            files[path] = _store(objects, text)
        # New dated writing has an independent declared-date cohort each week.
        for writing_week in range(week + 1):
            day = start + timedelta(weeks=writing_week)
            for i in range(max(2, notes // 100)):
                term = (
                    "aurora"
                    if 8 <= writing_week <= 11
                    else ("quasar" if 22 <= writing_week <= 25 else "reflection")
                )
                text = (
                    f"---\ncreated: {day}\nmodified: {day}\n---\n{TOPICS[i % len(TOPICS)]}\n"
                    f"{term} connects field observations for "
                    f"{identity(notes + writing_week * notes + i)}.\n"
                )
                files[f"Writing/{day}-{i:05d}.md"] = _store(objects, text)
        # Virtual dated entries exercise journal identity, anchoring and edits.
        journal = "# Field journal\n"
        for entry_week in range(week + 1):
            day = start + timedelta(weeks=entry_week)
            journal += f"\n## {day}\n{TOPICS[entry_week % len(TOPICS)]}\n"
        if week >= 16:
            journal = journal.replace(TOPICS[0], TOPICS[4], 1)
        files["Journal.md"] = _store(objects, journal)
        records.append(
            {
                "index": week,
                "observed_at": observed.isoformat() + "T12:00:00+00:00",
                "date": observed.isoformat(),
                "files": files,
                "changed_paths": sorted(
                    path for path, digest in files.items() if previous.get(path) != digest
                ),
                "deleted_paths": sorted(previous.keys() - files.keys()),
            }
        )
        previous = files
    manifest = {
        "version": VERSION,
        "synthetic": True,
        "initial_notes": notes,
        "snapshots": records,
        "stable_paths": stable,
        "scenarios": {
            "aurora": {"weeks": [8, 9, 10, 11], "kind": "lexical burst"},
            "quasar": {"weeks": [22, 23, 24, 25], "kind": "lexical burst"},
            "gradual_rewrites": {"every_weeks": 4},
            "abrupt_rewrites": {"week": 16},
            "deletions": {"week": 24},
            "stable_controls": {"count": len(stable)},
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _store(objects: Path, text: str) -> str:
    data = text.encode()
    digest = hashlib.sha256(data).hexdigest()
    path = objects / (digest + ".md")
    if not path.exists():
        path.write_bytes(data)
    return digest


def apply_snapshot(corpus: Path, vault: Path, index: int) -> dict:
    """Apply a sequential snapshot, verifying changed objects before writing.

    The marker distinguishes this dedicated replay vault from user notes. Source
    corpora are immutable. Persisted engine outputs are outside the source snapshot.
    """
    manifest_bytes = (corpus / "manifest.json").read_bytes()
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    if (
        isinstance(index, bool)
        or not isinstance(index, int)
        or not 0 <= index < len(manifest["snapshots"])
    ):
        raise ValueError("snapshot index is out of range")
    if vault.resolve().is_relative_to(corpus.resolve()):
        raise ValueError("replay vault must be outside the immutable corpus")
    vault.mkdir(parents=True, exist_ok=True)
    marker = vault / ".temporal-replay.json"
    if marker.is_symlink() or (marker.exists() and not marker.is_file()):
        raise ValueError("replay marker must be a regular file")
    state = json.loads(marker.read_text()) if marker.exists() else None
    if state is None and (index != 0 or any(vault.iterdir())):
        raise ValueError("first snapshot requires an empty dedicated vault")
    if state is not None and index != state["index"] + 1:
        raise ValueError("snapshots must be applied sequentially")
    if state is not None and state["corpus"] != str(corpus.resolve()):
        raise ValueError("replay belongs to a different corpus")
    if state is not None and state.get("manifest_sha256") != manifest_digest:
        raise ValueError("replay manifest has changed")
    record = manifest["snapshots"][index]
    observed_time = datetime.fromisoformat(record["observed_at"])
    if observed_time.tzinfo is None:
        raise ValueError("snapshot observation time must include a timezone")
    observed = observed_time.timestamp()
    payloads = {}
    for relative in record["changed_paths"] + record["deleted_paths"]:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not relative.endswith(".md"):
            raise ValueError("unsafe snapshot path")
        destination = vault / path
        if not destination.resolve().is_relative_to(vault.resolve()):
            raise ValueError("snapshot path escapes replay vault")
        if relative in record["files"]:
            digest = record["files"][relative]
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("invalid object digest")
            data = (corpus / "objects" / (digest + ".md")).read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("corrupt corpus object")
            payloads[relative] = data
    for relative in record["deleted_paths"]:
        (vault / relative).unlink(missing_ok=True)
    for relative, data in payloads.items():
        destination = vault / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        # Notes without a declared modified date (including journals) inherit
        # mtime. Today's host clock must not leak into a historical replay.
        os.utime(destination, (observed, observed))
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=vault, delete=False) as temporary:
        temporary.write(
            json.dumps(
                {
                    "index": index,
                    "corpus": str(corpus.resolve()),
                    "manifest_sha256": manifest_digest,
                }
            )
            + "\n"
        )
    temporary_path = Path(temporary.name)
    try:
        temporary_path.replace(marker)
    finally:
        temporary_path.unlink(missing_ok=True)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--profile", choices=PROFILES, default="standard")
    parser.add_argument("--snapshots", type=int, default=32)
    args = parser.parse_args()
    generate_corpus(args.output, notes=PROFILES[args.profile], snapshots=args.snapshots)
