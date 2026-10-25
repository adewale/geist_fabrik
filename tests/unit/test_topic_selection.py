"""Selection explanations preserve the structural/relevance distinction."""

import json
from dataclasses import asdict

import pytest

from geistfabrik.topic_selection import SelectionPolicy, analyze_topics, extract_topics


class Candidates:
    def __init__(self, *rows: tuple[str, float]) -> None:
        self.rows = list(rows)

    def extract_keywords(self, text: str) -> list[tuple[str, float]]:
        assert "secret metadata" not in text
        return self.rows


def test_explanation_separates_structural_mask_and_relevance() -> None:
    source = "---\nprivate: secret metadata\n---\nThe clinic moved the appointment."
    explanation = analyze_topics(source, Candidates(("clinic moved", 0.1), ("appointment", 0.2)))
    assert [tag.key for tag in explanation.topics] == ["appointment"]
    rows = {row.key: row for row in explanation.candidates}
    assert rows["clinic moved"].stage == "relevance"
    assert rows["clinic moved"].reason == "clause_fragment"
    assert rows["appointment"].selected
    assert rows["appointment"].inspected_occurrences[0].reason == "noun_phrase"
    assert explanation.structural_exclusions
    rendered = json.dumps(asdict(explanation), allow_nan=False)
    assert "secret metadata" not in rendered
    assert all(source[tag.start : tag.end] == tag.text for tag in explanation.topics)


def test_every_proposal_has_a_final_decision_and_later_evidence_is_explained() -> None:
    source = "The tide changes the shoreline. Climate changes affect the coast."
    explanation = analyze_topics(source, Candidates(("changes", 0.1), ("absent", 0.2)))
    rows = {row.key: row for row in explanation.candidates}
    assert rows["changes"].selected
    occurrences = rows["changes"].inspected_occurrences
    assert [occurrence.allowed for occurrence in occurrences] == [False, True]
    assert occurrences[1].start == source.rindex("changes")
    assert rows["absent"].stage == "grounding"
    assert rows["absent"].reason == "no_source_match"


def test_plain_yake_comparator_disables_added_relevance_rules_only() -> None:
    plain = SelectionPolicy(**dict.fromkeys(vars(SelectionPolicy()), False))
    explanation = analyze_topics(
        "# Clinic\n\nThe clinic moved the appointment.",
        Candidates(("clinic moved", 0.1), ("appointment", 0.2)),
        policy=plain,
    )
    assert plain.name == "clean-yake" and plain.complexity == 0
    assert [tag.key for tag in explanation.topics] == ["clinic moved", "appointment"]
    assert explanation.candidates[0].reason == "authored_prior_disabled"
    assert all(tag.text for tag in explanation.topics)


@pytest.mark.parametrize("cost", [float("nan"), float("inf"), -1.0])
def test_invalid_scores_have_json_safe_grounding_rejections(cost: float) -> None:
    explanation = analyze_topics("Rare subject", Candidates(("Rare subject", cost)))
    assert not explanation.topics
    assert explanation.candidates[0].reason == "unsupported_label_or_score"
    json.dumps(asdict(explanation), allow_nan=False)


def test_explanation_and_normal_extraction_select_identical_topics() -> None:
    source = "# Cyanotypes\n\nCyanotypes use iron salts."
    candidates = Candidates(("Cyanotypes", 0.1), ("iron salts", 0.2))
    assert analyze_topics(source, candidates).topics == extract_topics(source, candidates)


def test_structurally_empty_text_has_no_candidates_or_topics() -> None:
    explanation = analyze_topics("---\ntags: [daily]\n---\n## Notes\n\n![[Daily.base]]\n")
    assert explanation.topics == [] and explanation.candidates == []
    assert explanation.structural_exclusions


@pytest.mark.parametrize(
    "source",
    [
        "# Community [[Private destination|gardens]]",
        "# [Community](https://secret.example) gardens",
        "[Community](https://secret.example) gardens",
        "# Community [[🔒|gardens]]",
    ],
)
def test_evidence_cannot_reconstruct_masked_destinations(source: str) -> None:
    explanation = analyze_topics(source, Candidates(("Community gardens", 0.1)))
    assert "community gardens" not in {tag.key for tag in explanation.topics}
    assert any(row.reason == "masked_evidence_span" for row in explanation.candidates)
    rendered = json.dumps(asdict(explanation), ensure_ascii=False)
    assert "Private destination" not in rendered
    assert "secret.example" not in rendered and "🔒" not in rendered
    assert all(source[tag.start:tag.end] == tag.text for tag in explanation.topics)


def test_masked_occurrence_does_not_hide_a_later_safe_occurrence() -> None:
    source = "[Community](https://secret.example) gardens. Community gardens thrive."
    explanation = analyze_topics(source, Candidates(("Community gardens", 0.1)))
    assert len(explanation.topics) == 1
    assert explanation.topics[0].start == source.rindex("Community gardens")
    row = next(row for row in explanation.candidates if row.key == "community gardens")
    assert row.inspected_occurrences[0].reason == "masked_evidence_span"
    assert row.inspected_occurrences[-1].allowed
