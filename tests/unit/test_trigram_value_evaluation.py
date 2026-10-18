"""The matched evaluation must preserve contexts and conceal its arm key."""

import json

from hypothesis import given
from hypothesis import strategies as st

from scripts.evaluate_trigram_value import compare_contexts, evaluate, review_packets
from scripts.generate_narrative_corpus import DEFAULT_SOURCE, generate_narrative_corpus


def _finding(term, *, paths=("A.md",), start="2024-01-01", end="2024-02-01"):
    return {
        "term": term,
        "direction": "rising",
        "start": start,
        "end": end,
        "support_paths": paths,
    }


@given(
    st.sampled_from(["direction", "start", "end", "support_paths"]),
    st.sampled_from(["short", "supported"]),
)
def test_a_contained_shorter_expression_only_shares_evidence_when_every_identity_field_matches(
    changed_field, first
):
    shorter = _finding(f"{first} practice")
    longer = _finding(f"{first} practice group")
    pairs = {"findings": [shorter], "suggestions": []}
    triples = {"findings": [shorter, longer], "suggestions": []}
    exact = compare_contexts(pairs, triples)
    assert exact["same_evidence_nested_episodes"] == 1
    replacements = {
        "direction": "declining",
        "start": "2024-01-08",
        "end": "2024-02-08",
        "support_paths": ("B.md",),
    }
    longer[changed_field] = replacements[changed_field]
    changed = compare_contexts(pairs, triples)
    assert changed["same_evidence_nested_episodes"] == 0
    assert changed["other_evidence_episodes"] == 1
    assert changed["common_findings_identical"]


def test_review_packet_deduplication_keeps_date_and_population_and_hides_arm_metadata():
    suggestion = {
        "text": "What changes through this phrase?",
        "source_documents": [{"path": "A.md", "content": "Actual source."}],
        "evidence_key": "opaque-evidence",
    }
    report = {
        "snapshots": [
            {
                "date": day,
                "arms": {
                    arm: {"modes": {mode: {"suggestions": [suggestion]} for mode in modes}}
                    for arm in ("2", "3")
                },
            }
            for day, modes in (
                ("2024-01-31", ("dated_cohorts", "observed_additions")),
                ("2024-02-29", ("dated_cohorts",)),
            )
        ]
    }
    packets, key = review_packets(report, {"scenarios": [{"id": "unchanged-ledger"}]})
    assert len(packets) == 3
    assert len({(p["date"], p["history_mode"]) for p in packets}) == 3
    assert all(
        set(p)
        == {
            "id",
            "date",
            "history_mode",
            "question",
            "source_documents",
            "frozen_scenario_facts",
            "assessment",
        }
        for p in packets
    )
    assert all(len(item["memberships"]) == 2 for item in key)
    assert review_packets(report, {"scenarios": [{"id": "unchanged-ledger"}]}) == (packets, key)


def test_matched_replay_uses_fresh_historical_sources_and_records_healthy_abstentions(tmp_path):
    corpus = tmp_path / "corpus"
    manifest = generate_narrative_corpus(corpus)
    protocol = tmp_path / "protocol.md"
    protocol.write_text("Frozen before evaluation: matched 2/3-gram source replay.")
    output = tmp_path / "receipts.json"
    result = evaluate(
        corpus,
        tmp_path / "arms",
        output=output,
        protocol=protocol,
        ledger=DEFAULT_SOURCE / "ledger.json",
        limit=2,
    )
    assert result["completed"]
    assert not result["errors"]
    assert not result["embedding_inference"]
    assert not result["downstream_filters"]
    assert json.loads(output.read_text()) == result
    assert [row["date"] for row in result["snapshots"]] == [
        row["date"] for row in manifest["snapshots"][:2]
    ]
    for row in result["snapshots"]:
        assert (
            row["arms"]["2"]["source_snapshot_sha256"]
            == (row["arms"]["3"]["source_snapshot_sha256"])
        )
        for mode in ("dated_cohorts", "observed_additions"):
            assert row["comparison"][mode]["common_findings_identical"]
            for arm in ("2", "3"):
                diagnostics = row["arms"][arm]["modes"][mode]["diagnostics"]
                assert diagnostics["reason"] == "insufficient_documents"
                assert row["arms"][arm]["modes"][mode]["suggestions"] == []
    assert output.with_name("receipts.review-packets.json").read_text() == "[]\n"


def test_corrupt_snapshot_is_a_failed_replay_not_a_healthy_empty_result(tmp_path):
    corpus = tmp_path / "corpus"
    manifest = generate_narrative_corpus(corpus)
    digest = next(iter(manifest["snapshots"][0]["files"].values()))
    (corpus / "objects" / f"{digest}.md").write_text("Corrupted")
    protocol = tmp_path / "protocol.md"
    protocol.write_text("Frozen before evaluation.")
    output = tmp_path / "receipts.json"
    result = evaluate(
        corpus,
        tmp_path / "arms",
        output=output,
        protocol=protocol,
        ledger=DEFAULT_SOURCE / "ledger.json",
    )
    assert not result["completed"]
    assert "corrupt corpus object" in result["errors"][0]["message"]
    assert not output.with_name("receipts.review-packets.json").exists()
