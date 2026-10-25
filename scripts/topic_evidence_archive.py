#!/usr/bin/env python3
"""Deterministic, ASCII archives for historical topic evaluation evidence.

Archives retain original file bytes and paths, including historical provenance.
They do not refresh a report's runtime hashes or certify its conclusions. Source
vault bodies must not be selected. Only regular files are stored; extraction
never follows symlinks or overwrites an existing file. All data is verified
before extraction begins. Limits apply to compressed input and expanded data.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any
import zlib

FORMAT = "geistfabrik-topic-evidence-v1"
MAX_ARCHIVE_BYTES = 500_000
MAX_EXPANDED_BYTES = 32 * 1024 * 1024
MAX_FILES = 10_000
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class ArchiveError(ValueError):
    """Malformed, unsafe, oversized or corrupted evidence archive."""


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("ascii")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ArchiveError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _parse_json(raw: bytes) -> Any:
    try:
        return json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ArchiveError(f"Invalid archive JSON: {exc}") from exc


def _safe_path(path: Any) -> str:
    if not isinstance(path, str) or not path or "\\" in path or "\x00" in path:
        raise ArchiveError(f"Unsafe archive path: {path!r}")
    parts = path.split("/")
    if any(part in {"", ".", ".."} or ":" in part for part in parts):
        raise ArchiveError(f"Unsafe archive path: {path!r}")
    if PurePosixPath(path).is_absolute():
        raise ArchiveError(f"Unsafe archive path: {path!r}")
    return path


def _decode(value: Any) -> bytes:
    if not isinstance(value, str):
        raise ArchiveError("Expected base64 string")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ArchiveError("Invalid base64 payload") from exc


def _directory_fd(path: Path, *, create: bool) -> int:
    """Walk from filesystem root with descriptor-relative, no-follow opens."""
    absolute = path.absolute()
    descriptor = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in absolute.parts[1:]:
            if component in {".", ".."}:
                raise ArchiveError("Destination cannot contain dot segments")
            if create:
                try:
                    os.mkdir(component, mode=0o755, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_source(root: Path, path: str) -> bytes:
    descriptor = _directory_fd(root, create=False)
    try:
        parts = path.split("/")
        for component in parts[:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        source = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=descriptor)
        with os.fdopen(source, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ArchiveError(f"Not a regular file: {path}")
            data = handle.read(MAX_EXPANDED_BYTES + 1)
        if len(data) > MAX_EXPANDED_BYTES:
            raise ArchiveError(f"Source exceeds expanded limit: {path}")
        return data
    finally:
        os.close(descriptor)


def create_archive(root: Path, paths: list[str], output: Path) -> dict[str, Any]:
    """Create without timestamps, absolute machine paths or changing source data."""
    paths = sorted(_safe_path(path) for path in paths)
    if not paths or len(paths) > MAX_FILES or len(set(paths)) != len(paths):
        raise ArchiveError("Expected a nonempty, unique, bounded file selection")
    entries = []
    files = {}
    total_bytes = 0
    for path in paths:
        data = _read_source(root, path)
        total_bytes += len(data)
        if total_bytes > MAX_EXPANDED_BYTES:
            raise ArchiveError("Source data exceeds expanded limit")
        entries.append(
            {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
        files[path] = base64.b64encode(data).decode("ascii")
    payload = _json_bytes(files)
    if len(payload) > MAX_EXPANDED_BYTES:
        raise ArchiveError("Serialized data exceeds expanded limit; split the archive")
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", compresslevel=9, mtime=0, fileobj=buffer) as stream:
        stream.write(payload)
    envelope = {
        "format": FORMAT,
        "compression": "gzip+base64",
        "expanded_bytes": len(payload),
        "expanded_sha256": hashlib.sha256(payload).hexdigest(),
        "entries": entries,
        "payload": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }
    encoded = _json_bytes(envelope)
    if len(encoded) > MAX_ARCHIVE_BYTES:
        raise ArchiveError("Archive exceeds 500000 bytes; split by run")
    with output.open("xb") as handle:
        handle.write(encoded)
    return envelope


def load_archive(path: Path) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    """Bound and verify every layer, including duplicate paths and exact bytes."""
    with path.open("rb") as handle:
        raw = handle.read(MAX_ARCHIVE_BYTES + 1)
    if len(raw) > MAX_ARCHIVE_BYTES:
        raise ArchiveError("Archive exceeds compressed input limit")
    if not raw.isascii():
        raise ArchiveError("Archive must be ASCII")
    envelope = _parse_json(raw)
    if (not isinstance(envelope, dict) or envelope.get("format") != FORMAT
            or envelope.get("compression") != "gzip+base64"):
        raise ArchiveError("Unsupported archive format")
    expanded_size = envelope.get("expanded_bytes")
    if type(expanded_size) is not int or not 0 <= expanded_size <= MAX_EXPANDED_BYTES:
        raise ArchiveError("Invalid expanded size")
    entries = envelope.get("entries")
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_FILES:
        raise ArchiveError("Invalid file manifest")
    expected: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise ArchiveError("Invalid manifest entry")
        name = _safe_path(entry["path"])
        if name in expected:
            raise ArchiveError(f"Duplicate path: {name}")
        if (type(entry["bytes"]) is not int or not 0 <= entry["bytes"] <= MAX_EXPANDED_BYTES
                or not isinstance(entry["sha256"], str)
                or not _SHA256.fullmatch(entry["sha256"])):
            raise ArchiveError("Invalid manifest size or checksum")
        expected[name] = entry
    if list(expected) != sorted(expected):
        raise ArchiveError("Manifest is not sorted")
    if sum(entry["bytes"] for entry in entries) > MAX_EXPANDED_BYTES:
        raise ArchiveError("Manifest exceeds expanded limit")
    compressed = _decode(envelope.get("payload"))
    try:
        decoder = zlib.decompressobj(wbits=31)
        payload = decoder.decompress(compressed, expanded_size + 1)
    except zlib.error as exc:
        raise ArchiveError("Invalid gzip payload") from exc
    if (len(payload) != expanded_size or not decoder.eof
            or decoder.unused_data or decoder.unconsumed_tail):
        raise ArchiveError(
            "Expanded size mismatch, trailing stream or decompression limit exceeded"
        )
    if hashlib.sha256(payload).hexdigest() != envelope.get("expanded_sha256"):
        raise ArchiveError("Expanded payload checksum mismatch")
    encoded_files = _parse_json(payload)
    if not isinstance(encoded_files, dict) or set(encoded_files) != set(expected):
        raise ArchiveError("Payload does not match manifest")
    files = {}
    for name, entry in expected.items():
        data = _decode(encoded_files[name])
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ArchiveError(f"File checksum or size mismatch: {name}")
        files[name] = data
    return entries, files


def extract_archive(path: Path, destination: Path) -> list[dict[str, Any]]:
    entries, files = load_archive(path)
    root_descriptor = _directory_fd(destination, create=True)
    try:
        for name, data in files.items():
            descriptor = os.dup(root_descriptor)
            try:
                parts = name.split("/")
                for component in parts[:-1]:
                    try:
                        os.mkdir(component, mode=0o755, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                    child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=descriptor)
                    os.close(descriptor)
                    descriptor = child
                output = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o644, dir_fd=descriptor)
                with os.fdopen(output, "wb") as handle:
                    handle.write(data)
            finally:
                os.close(descriptor)
    finally:
        os.close(root_descriptor)
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Archive explicit regular files; never overwrite")
    create.add_argument("archive", type=Path)
    create.add_argument("paths", nargs="+")
    create.add_argument("--root", type=Path, default=Path("."))
    for name in ("list", "verify", "extract"):
        command = commands.add_parser(name)
        command.add_argument("archive", type=Path)
        if name == "extract":
            command.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            entries = create_archive(args.root, args.paths, args.archive)["entries"]
        elif args.command == "extract":
            entries = extract_archive(args.archive, args.destination)
        else:
            entries, _ = load_archive(args.archive)
        if args.command == "list":
            print(json.dumps(entries, indent=2, ensure_ascii=True))
        else:
            print(f"{args.command}: {len(entries)} files verified")
    except (ArchiveError, OSError) as exc:
        parser.exit(1, f"Archive error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
