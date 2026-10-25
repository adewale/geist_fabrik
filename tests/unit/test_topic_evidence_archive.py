"""Archive integrity/security checks also runnable using only the standard library.

python tests/unit/test_topic_evidence_archive.py
"""

import base64
import gzip
import hashlib
import importlib.util
import json
import lzma
import tempfile
import unittest
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "topic_evidence_archive.py"
SPEC = importlib.util.spec_from_file_location("topic_evidence_archive", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


class TopicEvidenceArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "reports").mkdir()
        self.originals = {
            "reports/a.json": b'{"utf8":"\xc3\xa9"}\r\n',
            "reports/b.bin": b"\x00\xff\x80\n",
            "empty": b"",
        }
        for name, content in self.originals.items():
            (self.root / name).write_bytes(content)
        self.output = self.root / "archive.json"

    def create(self) -> None:
        archive.create_archive(self.root, list(self.originals), self.output)

    def mutate(self, callback: Callable[[dict[str, Any]], None]) -> None:
        data = json.loads(self.output.read_text())
        callback(data)
        self.output.write_text(json.dumps(data, ensure_ascii=True))

    def test_exact_round_trip_and_deterministic_bytes(self) -> None:
        self.create()
        second = self.root / "second.json"
        archive.create_archive(self.root, list(reversed(self.originals)), second)
        self.assertEqual(self.output.read_bytes(), second.read_bytes())
        self.assertTrue(self.output.read_bytes().isascii())
        entries, contents = archive.load_archive(self.output)
        self.assertEqual(contents, self.originals)
        self.assertEqual([entry["path"] for entry in entries], sorted(self.originals))
        destination = self.root / "restore"
        archive.extract_archive(self.output, destination)
        for name, content in self.originals.items():
            self.assertEqual((destination / name).read_bytes(), content)
        with self.assertRaises(FileExistsError):
            archive.extract_archive(self.output, destination)

    def test_reject_checksum_corruption_before_creating_destination(self) -> None:
        self.create()
        self.mutate(lambda data: data["entries"][0].update(sha256="0" * 64))
        destination = self.root / "restore"
        with self.assertRaises(archive.ArchiveError):
            archive.extract_archive(self.output, destination)
        self.assertFalse(destination.exists())

    def test_reject_unsafe_and_duplicate_manifest_paths(self) -> None:
        self.create()
        original = self.output.read_bytes()
        unsafe = ["../escape", "/tmp/escape", "a/../../escape", "a\\escape", "C:/escape", "a//b"]
        for name in unsafe:
            with self.subTest(path=name):
                self.output.write_bytes(original)
                self.mutate(lambda data: data["entries"][0].update(path=name))
                with self.assertRaises(archive.ArchiveError):
                    archive.load_archive(self.output)
        self.output.write_bytes(original)
        self.mutate(lambda data: data["entries"].append(data["entries"][0]))
        with self.assertRaises(archive.ArchiveError):
            archive.load_archive(self.output)
        self.output.write_text('{"format":"one","format":"two"}')
        with self.assertRaises(archive.ArchiveError):
            archive.load_archive(self.output)

    def test_reject_symlink_parent_leaf_and_destination(self) -> None:
        self.create()
        outside = self.root / "outside"
        outside.mkdir()
        for mode in ["parent", "leaf", "destination"]:
            with self.subTest(mode=mode):
                destination = self.root / mode
                if mode == "destination":
                    destination.symlink_to(outside, target_is_directory=True)
                else:
                    destination.mkdir()
                    if mode == "parent":
                        (destination / "reports").symlink_to(outside, target_is_directory=True)
                    else:
                        (destination / "empty").symlink_to(outside / "empty")
                with self.assertRaises(OSError):
                    archive.extract_archive(self.output, destination)
                self.assertEqual(list(outside.iterdir()), [])

    def test_reject_source_symlinks_and_duplicate_selection(self) -> None:
        (self.root / "alias").symlink_to(self.root / "empty")
        with self.assertRaises(OSError):
            archive.create_archive(self.root, ["alias"], self.output)
        with self.assertRaises(archive.ArchiveError):
            archive.create_archive(self.root, ["empty", "empty"], self.output)

    def test_bounded_decompression_and_trailing_stream_rejection(self) -> None:
        self.create()
        original = self.output.read_bytes()
        payloads = [
            gzip.compress(b"x" * 500_000, mtime=0),
            gzip.compress(b"{}", mtime=0) + gzip.compress(b"more", mtime=0),
        ]
        for payload in payloads:
            self.output.write_bytes(original)

            def change(data: dict[str, Any]) -> None:
                data["payload"] = base64.b64encode(payload).decode("ascii")
                data["expanded_bytes"] = 2
                data["expanded_sha256"] = hashlib.sha256(b"{}").hexdigest()

            self.mutate(change)
            with self.assertRaises(archive.ArchiveError):
                archive.load_archive(self.output)

    def test_limits_and_invalid_encoding(self) -> None:
        with patch.object(archive, "MAX_ARCHIVE_BYTES", 100):
            with self.assertRaises(archive.ArchiveError):
                self.create()
        self.assertFalse(self.output.exists())
        self.create()
        self.mutate(lambda data: data.update(payload="not base64!"))
        with self.assertRaises(archive.ArchiveError):
            archive.load_archive(self.output)

    def test_xz_exact_round_trip_deterministic_and_default_gzip_unchanged(self) -> None:
        envelope = archive.create_archive(
            self.root, list(self.originals), self.output, compression="xz"
        )
        self.assertEqual(envelope["compression"], "xz+base64")
        second = self.root / "second.json"
        archive.create_archive(
            self.root, list(reversed(self.originals)), second, compression="xz"
        )
        self.assertEqual(self.output.read_bytes(), second.read_bytes())
        _, files = archive.load_archive(self.output)
        self.assertEqual(files, self.originals)
        default = archive.create_archive(
            self.root, list(self.originals), self.root / "default.json"
        )
        self.assertEqual(default["compression"], "gzip+base64")
        explicit = self.root / "gzip.json"
        archive.create_archive(self.root, list(self.originals), explicit, compression="gzip")
        self.assertEqual((self.root / "default.json").read_bytes(), explicit.read_bytes())

    def test_xz_bomb_truncation_and_trailing_stream_rejected_before_writing(self) -> None:
        archive.create_archive(self.root, list(self.originals), self.output, compression="xz")
        original = self.output.read_bytes()
        payloads = [
            lzma.compress(b"x" * 500_000),
            lzma.compress(b"{}") + lzma.compress(b"more"),
            lzma.compress(b"{}")[:-1],
        ]
        for index, payload in enumerate(payloads):
            with self.subTest(index=index):
                self.output.write_bytes(original)

                def change(data: dict[str, Any]) -> None:
                    data["payload"] = base64.b64encode(payload).decode("ascii")
                    data["expanded_bytes"] = 2
                    data["expanded_sha256"] = hashlib.sha256(b"{}").hexdigest()

                self.mutate(change)
                destination = self.root / f"restored-{index}"
                with self.assertRaises(archive.ArchiveError):
                    archive.extract_archive(self.output, destination)
                self.assertFalse(destination.exists())

    def test_xz_large_dictionary_header_exceeds_real_memory_limit(self) -> None:
        archive.create_archive(self.root, list(self.originals), self.output, compression="xz")
        # Change an ordinary XZ block's declared LZMA2 dictionary to 128 MiB.
        # Repair its header CRC without allocating that dictionary in a compressor.
        payload = bytearray(lzma.compress(b"{}", format=lzma.FORMAT_XZ, preset=6))
        header_end = 12 + (payload[12] + 1) * 4
        self.assertEqual(payload[14:17], b"\x21\x01\x16")
        payload[16] = 0x1e
        payload[header_end - 4 : header_end] = zlib.crc32(payload[12 : header_end - 4]).to_bytes(
            4, "little"
        )
        self.mutate(lambda data: data.update(payload=base64.b64encode(payload).decode("ascii")))
        with self.assertRaises(archive.ArchiveError) as caught:
            archive.load_archive(self.output)
        self.assertIsInstance(caught.exception.__cause__, lzma.LZMAError)
        self.assertIn("Memory usage limit exceeded", str(caught.exception.__cause__))

    def test_cli_xz_creation_and_unknown_codec_rejection(self) -> None:
        with patch("builtins.print"):
            self.assertEqual(
                archive.main(
                    [
                        "create", str(self.output), "empty", "--root", str(self.root),
                        "--compression", "xz",
                    ]
                ),
                0,
            )
        self.assertEqual(json.loads(self.output.read_text())["compression"], "xz+base64")
        self.mutate(lambda data: data.update(compression={"invalid": "codec"}))
        with self.assertRaises(archive.ArchiveError):
            archive.load_archive(self.output)

    def test_retained_archives_verify_without_restored_originals(self) -> None:
        directory = SCRIPT.parent.parent / "benchmarks/archives/topics"
        retained = sorted(directory.glob("*.archive.json"))
        self.assertTrue(retained)
        for path in retained:
            with self.subTest(archive=path.name):
                entries, files = archive.load_archive(path)
                self.assertEqual(len(entries), len(files))
                self.assertLessEqual(path.stat().st_size, archive.MAX_ARCHIVE_BYTES)


if __name__ == "__main__":
    unittest.main()
