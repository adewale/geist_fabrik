"""Narrative chronology and evidence isolation, independent of geist output."""

import hashlib
import json
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.markdown_parser import parse_frontmatter
from scripts.generate_narrative_corpus import DEFAULT_SOURCE, generate_narrative_corpus
from scripts.generate_temporal_corpus import apply_snapshot


@pytest.fixture
def narrative(tmp_path):
    corpus = tmp_path / "corpus"
    manifest = generate_narrative_corpus(corpus)
    return corpus, manifest


def test_authored_corpus_is_reproducible_and_contains_no_evaluation_notes(narrative, tmp_path):
    corpus, manifest = narrative
    second = tmp_path / "second"
    assert generate_narrative_corpus(second) == manifest
    assert (corpus / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    assert (
        manifest["ledger_sha256"]
        == hashlib.sha256((DEFAULT_SOURCE / "ledger.json").read_bytes()).hexdigest()
    )
    final = manifest["snapshots"][-1]["files"]
    assert 150 <= len(final) <= 300
    assert not {"persona.md", "ledger.json", "README.md"} & set(final)
    assert len(manifest["snapshots"]) == 24
    assert manifest["snapshots"][0]["date"] == "2024-01-31"
    assert manifest["snapshots"][-1]["date"] == "2025-12-31"


@given(st.integers(0, 23))
@settings(max_examples=24, deadline=None)
def test_no_future_note_or_future_journal_entry_leaks_into_a_snapshot(property_narrative, index):
    # Source-independent temporal oracle: declared note dates and virtual entry
    # headings must not exceed the observation cutoff in any chosen snapshot.
    corpus = property_narrative
    manifest = json.loads((corpus / "manifest.json").read_text())
    row = manifest["snapshots"][index]
    cutoff = date.fromisoformat(row["date"])
    for path, digest in row["files"].items():
        text = (corpus / "objects" / (digest + ".md")).read_text()
        metadata, _ = parse_frontmatter(text)
        if path == "Journal.md":
            dates = [
                date.fromisoformat(line[3:]) for line in text.splitlines() if line.startswith("## ")
            ]
            assert all(day <= cutoff for day in dates)
            assert len(dates) == index + 1
        else:
            assert metadata is not None, path
            assert date.fromisoformat(str(metadata["created"])) <= cutoff, path
            assert date.fromisoformat(str(metadata["modified"])) <= cutoff, path


@pytest.fixture(scope="module")
def property_narrative(tmp_path_factory):
    # Read-only and module-scoped: examples share no mutable replay state.
    corpus = tmp_path_factory.mktemp("property-narrative") / "corpus"
    generate_narrative_corpus(corpus)
    return corpus


def test_replay_preserves_actual_rewrites_import_provenance_and_stable_controls(
    narrative, tmp_path
):
    corpus, manifest = narrative
    vault = tmp_path / "vault"
    first = manifest["snapshots"][0]["files"]
    final = manifest["snapshots"][-1]["files"]
    assert first["Learning/Maintenance.md"] != final["Learning/Maintenance.md"]
    assert "Community/Repair fair draft.md" in manifest["snapshots"][8]["files"]
    assert "Community/Repair fair draft.md" not in manifest["snapshots"][9]["files"]
    assert not any(path.startswith("Clippings/") for path in manifest["snapshots"][7]["files"])
    imported = [path for path in manifest["snapshots"][8]["files"] if path.startswith("Clippings/")]
    assert len(imported) == 6
    for path in imported:
        text = (corpus / "objects" / (final[path] + ".md")).read_text()
        metadata, _ = parse_frontmatter(text)
        assert metadata is not None
        assert str(metadata["created"]).startswith("2022-")
    assert "Garden/Garden notebook.md" in manifest["stable_paths"]
    for index, row in enumerate(manifest["snapshots"]):
        apply_snapshot(corpus, vault, index)
        actual = {
            str(p.relative_to(vault)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in vault.rglob("*.md")
        }
        assert actual == row["files"]
        assert all(actual[path] == first[path] for path in manifest["stable_paths"])


def test_compilation_refuses_existing_output_without_touching_it(narrative):
    corpus, _ = narrative
    before = (corpus / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        generate_narrative_corpus(corpus)
    assert (corpus / "manifest.json").read_bytes() == before


def test_full_invocation_observer_keeps_all_geists_and_saved_selection(narrative, tmp_path):
    # The fast lane stubs only the external encoder constructor. The standalone
    # evaluation command uses real offline inference, not this pytest fixture.
    from geistfabrik.default_geists import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS
    from scripts.evaluate_narrative_vault import evaluate

    corpus, _ = narrative
    report = evaluate(
        corpus, tmp_path / "vault", mode="dated_cohorts", output=tmp_path / "result.json", limit=2
    )
    assert report["errors"] == []
    assert report["completed"]
    expected = set(DEFAULT_CODE_GEISTS + DEFAULT_TRACERY_GEISTS)
    for snapshot in report["snapshots"]:
        assert set(snapshot["by_geist"]) == expected
        assert len(snapshot["execution_log"]) == len(expected)
        assert all(event["status"] == "success" for event in snapshot["execution_log"])
        assert 0 < len(snapshot["selected"]) <= 5
        assert snapshot["saved_count"] == len(snapshot["selected"])
        assert all(item in snapshot["filtered"] for item in snapshot["selected"])
        assert snapshot["stable_meaning_changes"] == []
        assert snapshot["future_note_dates"] == []


def test_observer_retains_corruption_failure_instead_of_reporting_an_empty_success(
    narrative, tmp_path
):
    from scripts.evaluate_narrative_vault import evaluate

    corpus, manifest = narrative
    first = manifest["snapshots"][0]
    digest = first["files"][first["changed_paths"][-1]]
    (corpus / "objects" / (digest + ".md")).write_text("damaged object")
    output = tmp_path / "result.json"
    report = evaluate(corpus, tmp_path / "vault", mode="dated_cohorts", output=output)
    assert not report["completed"]
    assert report["snapshots"] == []
    assert "corrupt corpus object" in report["errors"][0]["error"]
    assert json.loads(output.read_text()) == report
