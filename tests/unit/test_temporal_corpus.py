"""Generator determinism, independent planted controls and safe replay contracts."""

import hashlib
import json
import runpy
import subprocess
import sys
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


@pytest.mark.parametrize("mutation", ["marker_symlink", "manifest_change"])
def test_replay_rejects_redirected_marker_or_changed_manifest_before_mutation(tmp_path, mutation):
    corpus, vault = tmp_path / "corpus", tmp_path / "vault"
    generate_corpus(corpus, notes=64, snapshots=2)
    apply_snapshot(corpus, vault, 0)
    marker = vault / ".temporal-replay.json"
    external = tmp_path / "external.json"
    external.write_bytes(marker.read_bytes())
    if mutation == "marker_symlink":
        marker.unlink()
        marker.symlink_to(external)
    else:
        manifest = corpus / "manifest.json"
        manifest.write_bytes(manifest.read_bytes() + b"\n")
    before = {str(p.relative_to(vault)): p.read_bytes() for p in vault.rglob("*") if p.is_file()}
    external_before = external.read_bytes()
    with pytest.raises(ValueError, match="marker|manifest"):
        apply_snapshot(corpus, vault, 1)
    assert {
        str(p.relative_to(vault)): p.read_bytes() for p in vault.rglob("*") if p.is_file()
    } == before
    assert external.read_bytes() == external_before


def test_runner_retains_completed_evidence_on_pipeline_failure(tmp_path):
    corpus, vault = tmp_path / "corpus", tmp_path / "vault"
    manifest = generate_corpus(corpus, notes=64, snapshots=2)
    second = manifest["snapshots"][1]
    digest = second["files"][second["changed_paths"][-1]]
    (corpus / "objects" / (digest + ".md")).write_text("corrupt")
    output = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/benchmark_temporal_geists.py",
            str(corpus),
            str(vault),
            "--output",
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1
    assert output.exists(), result.stderr
    report = json.loads(output.read_text())
    assert report["snapshots"][0]["index"] == 0
    assert set(report["snapshots"][0]["lexical"]) == {"dated_cohorts", "observed_additions"}
    assert report["errors"][-1]["index"] == 1
    assert report["errors"][-1]["stage"] == "apply_snapshot"
    assert "corrupt corpus object" in report["errors"][-1]["error"]


def test_semantic_replay_context_uses_completed_embedding_snapshot(tmp_path, monkeypatch):
    """Fast lane stubs only inference; real session/backend/executor lifecycles run."""
    script = Path(__file__).resolve().parents[2] / "scripts/benchmark_temporal_geists.py"
    monkeypatch.syspath_prepend(str(script.parent))
    runner = runpy.run_path(str(script), run_name="temporal_benchmark_under_test")
    corpus = tmp_path / "corpus"
    generate_corpus(corpus, notes=64, snapshots=2)
    report = runner["replay"](corpus, tmp_path / "vault", real_embeddings=True)
    assert len(report["snapshots"]) == 2
    assert report["errors"] == []
    assert report["stable_meaning_changes"] == []
    for snapshot in report["snapshots"]:
        assert len(snapshot["geists"]) == 8
        assert all(result["status"] == "success" for result in snapshot["geists"].values())
