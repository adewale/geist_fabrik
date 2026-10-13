"""Generator determinism, independent planted controls and safe replay contracts."""

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.generate_temporal_corpus import apply_snapshot, generate_corpus


@given(st.integers(64, 200), st.integers(2, 8))
@settings(max_examples=20, deadline=None)
def test_generation_is_byte_deterministic(notes, snapshots):
    with TemporaryDirectory() as temp:
        root = Path(temp)
        a = generate_corpus(root / "a", notes=notes, snapshots=snapshots)
        b = generate_corpus(root / "b", notes=notes, snapshots=snapshots)
        assert a == b
        assert (root / "a/manifest.json").read_bytes() == (root / "b/manifest.json").read_bytes()


def test_replay_matches_every_snapshot_and_stable_controls(tmp_path):
    corpus, vault = tmp_path / "corpus", tmp_path / "vault"
    manifest = generate_corpus(corpus, notes=64)
    for i, snapshot in enumerate(manifest["snapshots"]):
        apply_snapshot(corpus, vault, i)
        actual = {
            str(p.relative_to(vault)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in vault.rglob("*.md")
        }
        assert actual == snapshot["files"]
    for path in manifest["stable_paths"]:
        assert len({s["files"][path] for s in manifest["snapshots"]}) == 1
    assert manifest["snapshots"][24]["deleted_paths"]
    assert len(manifest["snapshots"][16]["changed_paths"]) > len(
        manifest["snapshots"][15]["changed_paths"]
    )


def test_corrupt_object_rejection_precedes_source_mutation(tmp_path):
    corpus, vault = tmp_path / "corpus", tmp_path / "vault"
    manifest = generate_corpus(corpus, notes=64, snapshots=2)
    apply_snapshot(corpus, vault, 0)
    before = {str(p.relative_to(vault)): p.read_bytes() for p in vault.rglob("*.md")}
    second = manifest["snapshots"][1]
    digest = second["files"][second["changed_paths"][-1]]
    (corpus / "objects" / (digest + ".md")).write_text("corrupt")
    with pytest.raises(ValueError, match="corrupt"):
        apply_snapshot(corpus, vault, 1)
    assert {str(p.relative_to(vault)): p.read_bytes() for p in vault.rglob("*.md")} == before


def test_replay_refuses_unowned_vault_and_wrong_sequence(tmp_path):
    corpus, vault = tmp_path / "corpus", tmp_path / "vault"
    generate_corpus(corpus, notes=64, snapshots=2)
    vault.mkdir()
    original = vault / "personal.md"
    original.write_text("personal")
    with pytest.raises(ValueError, match="empty dedicated"):
        apply_snapshot(corpus, vault, 0)
    assert original.read_text() == "personal"
    original.unlink()
    apply_snapshot(corpus, vault, 0)
    with pytest.raises(ValueError, match="sequentially"):
        apply_snapshot(corpus, vault, 0)


def test_snapshot_paths_cannot_escape_vault(tmp_path):
    corpus, vault = tmp_path / "corpus", tmp_path / "vault"
    manifest = generate_corpus(corpus, notes=64, snapshots=2)
    manifest["snapshots"][0]["changed_paths"].insert(0, "../outside.md")
    (corpus / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unsafe"):
        apply_snapshot(corpus, vault, 0)
    assert not (tmp_path / "outside.md").exists()
