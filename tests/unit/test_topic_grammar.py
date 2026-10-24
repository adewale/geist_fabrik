"""Contextual candidate quality preserves source identities and short subjects."""

import pytest

import geistfabrik.topic_grammar as grammar_module
from geistfabrik.topic_grammar import CandidateGrammar
from geistfabrik.topics import extract_topics


class _Candidates:
    def __init__(self, *labels: str) -> None:
        self.labels = labels

    def extract_keywords(self, text: str) -> list[tuple[str, float]]:
        return [(label, 0.1) for label in self.labels]


def test_finite_clause_cannot_displace_its_observed_subject() -> None:
    source = "The clinic moved the appointment."
    tags = extract_topics(source, _Candidates("clinic moved", "appointment"))
    assert [tag.key for tag in tags] == ["appointment"]
    assert source[tags[0].start : tags[0].end] == "appointment"


def test_later_noun_occurrence_remains_eligible_after_an_earlier_verb() -> None:
    source = "The tide changes the shoreline. Climate changes affect the coast."
    tags = extract_topics(source, _Candidates("changes"))
    assert len(tags) == 1
    assert tags[0].start == source.rindex("changes")
    assert tags[0].text == "changes"


@pytest.mark.parametrize("subject", ["Use cases", "Climate changes", "Game over", "Becoming"])
def test_isolated_short_subjects_are_not_lost_to_english_grammar(subject: str) -> None:
    assert [tag.key for tag in extract_topics(subject, _Candidates(subject))] == [
        subject.casefold()
    ]


def test_base_form_ambiguity_preserves_a_subject_in_context() -> None:
    source = "Use cases guide product design."
    assert "use cases" in {tag.key for tag in extract_topics(source, _Candidates("Use cases"))}


@pytest.mark.parametrize("subject", ["Python 3", "Area 51", "World War 2"])
def test_noun_headed_numeric_names_remain_eligible(subject: str) -> None:
    source = f"We discussed {subject} at the reading group."
    assert subject.casefold() in {
        tag.key for tag in extract_topics(source, _Candidates(subject))
    }


def test_nominal_note_keeps_its_adjectival_subjects() -> None:
    tags = extract_topics("blue amber jade", _Candidates("blue", "amber", "jade"))
    assert {tag.key for tag in tags} == {"blue", "amber", "jade"}


def test_authored_heading_and_link_labels_keep_their_independent_evidence() -> None:
    source = "# Game over\n\nConsider [[Use cases]] before making a decision."
    keys = {tag.key for tag in extract_topics(source, _Candidates())}
    assert {"game over", "use cases"} <= keys


@pytest.mark.parametrize("subject", ["my career", "our children", "His Dark Materials"])
def test_possessive_noun_phrases_remain_eligible_in_context(subject: str) -> None:
    source = f"We discussed {subject} at the reading group."
    assert subject.casefold() in {
        tag.key for tag in extract_topics(source, _Candidates(subject))
    }


def test_unmapped_words_do_not_borrow_a_later_identical_occurrence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(grammar_module, "_tag_block", lambda text: [[("records", "VBZ")]])
    source = "unmapped records"
    grammar = CandidateGrammar(source, ())
    assert grammar.allows("records", source.index("records"), len(source))


def test_missing_trailing_context_keeps_the_entire_block_uncertain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(grammar_module, "_tag_block", lambda text: [[("records", "VBZ")]])
    assert CandidateGrammar("records unmapped", ()).allows("records", 0, 7)


def test_grammar_identity_tracks_dependency_version(monkeypatch: pytest.MonkeyPatch) -> None:
    before = grammar_module.grammar_identity()
    monkeypatch.setattr(grammar_module, "version", lambda name: "changed")
    assert grammar_module.grammar_identity() != before


def test_empty_fields_do_not_erase_a_substantive_rare_topic_outline() -> None:
    source = (
        "dates:: 2022-11-21\n\n"
        "- Core principles of scientific reasoning\n"
        "\t- Gravity:\n\t- Entropy:\n\t- Topology:\n"
        "- Cyanotypes\n- Photograms\n- Causal inference\n"
        "\t- Intervention models with confounders:\n"
        "\t- Causal identification under selection:\n"
        "\t- Counterfactual inference methods:\n"
    )
    tags = extract_topics(source, _Candidates("Cyanotypes", "Photograms", "Causal inference"))
    assert {tag.key for tag in tags} == {"cyanotypes", "photograms", "causal inference"}
