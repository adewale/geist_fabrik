"""Grammar eligibility depends on the candidate's own mapped sentence context."""

import pytest

import geistfabrik.topic_grammar as grammar_module
from geistfabrik.topic_grammar import CandidateGrammar, GrammarDecision
from geistfabrik.topics import extract_topics


class _Candidates:
    def __init__(self, *labels: str) -> None:
        self.labels = labels

    def extract_keywords(self, text: str) -> list[tuple[str, float]]:
        return [(label, 0.1) for label in self.labels]


@pytest.mark.parametrize(
    ("context", "label", "allowed", "reason"),
    [
        ("blue amber jade.", "blue", True, "nominal_context"),
        ("Use cases.", "Use cases", True, "isolated_subject"),
        ("The clinic moved the appointment.", "clinic moved", False, "clause_fragment"),
        ("The clinic moved the appointment.", "appointment", True, "noun_phrase"),
        ("The sky looked bright blue today.", "bright blue", False, "non_nominal_fragment"),
    ],
)
@pytest.mark.parametrize("separate_blocks", [False, True])
def test_unrelated_clauses_do_not_change_the_candidate_context(
    context: str,
    label: str,
    allowed: bool,
    reason: str,
    separate_blocks: bool,
) -> None:
    unrelated = "They record measurements. The astronomer counted distant stars."
    separator = "\n\n" if separate_blocks else " "
    sources = [
        (context, 0),
        (context + separator + unrelated, 0),
        (unrelated + separator + context, len(unrelated) + len(separator)),
    ]
    for source, context_start in sources:
        start = context_start + context.index(label)
        boundaries = (context_start, context_start + len(context)) if separate_blocks else ()
        grammar = CandidateGrammar(source, boundaries)
        decision = grammar.decision(label, start, start + len(label))
        assert decision == GrammarDecision(
            allowed,
            reason,
            context_start,
            context_start + len(context),
        )
        assert grammar.allows(label, start, start + len(label)) is allowed
        assert source[decision.context_start : decision.context_end] == context


def test_nominal_outline_is_not_reinterpreted_by_an_unrelated_clause() -> None:
    outline = "blue amber jade"
    unrelated = "The clinic moved the appointment."
    for source in (outline, outline + "\n\n" + unrelated, unrelated + "\n\n" + outline):
        tags = extract_topics(source, _Candidates("blue", "amber", "jade"))
        assert {tag.key for tag in tags} == {"blue", "amber", "jade"}
        for tag in tags:
            assert source[tag.start : tag.end] == tag.text == tag.label
            assert tag.start == source.index(outline) + outline.index(tag.label)


@pytest.mark.parametrize(
    "subject",
    [
        "vault's knowledge graph",
        "vault’s knowledge graph",
        "Python 3",
        "Area 51",
        "World War 2",
        "attorney general",
        "accounts receivable",
    ],
)
def test_local_context_preserves_possessives_and_nominal_names(subject: str) -> None:
    context = f"We discussed {subject} yesterday."
    start = context.index(subject)
    decision = CandidateGrammar(context, ()).decision(subject, start, start + len(subject))
    assert decision.allowed
    assert decision.context_start == 0
    assert decision.context_end == len(context)


def test_later_noun_occurrence_has_its_own_explanation_and_evidence() -> None:
    source = "The tide changes the shoreline. Climate changes affect the coast."
    grammar = CandidateGrammar(source, ())
    first = source.index("changes")
    later = source.rindex("changes")
    assert grammar.decision("changes", first, first + 7) == GrammarDecision(
        False,
        "clause_fragment",
        0,
        source.index(".") + 1,
    )
    assert grammar.decision("changes", later, later + 7) == GrammarDecision(
        True,
        "noun_phrase",
        source.index("Climate"),
        len(source),
    )
    tags = extract_topics(source, _Candidates("changes"))
    assert len(tags) == 1
    assert tags[0].start == later
    assert source[tags[0].start : tags[0].end] == tags[0].text == "changes"


@pytest.mark.parametrize("source", ["unmapped records", "records unmapped"])
def test_incomplete_alignment_explains_preservation_without_borrowing_tokens(
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    monkeypatch.setattr(grammar_module, "_tag_block", lambda text: [[("records", "VBZ")]])
    start = source.index("records")
    decision = CandidateGrammar(source, ()).decision("records", start, start + 7)
    assert decision == GrammarDecision(True, "uncertain_alignment", None, None)


def test_a_candidate_cannot_borrow_a_verb_from_a_different_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Deliberately ambiguous adjective tags expose the old global clause gate.
    monkeypatch.setattr(
        grammar_module,
        "_tag_block",
        lambda text: (
            [[("blue", "JJ"), ("amber", "JJ"), (".", ".")]]
            if text == "blue amber."
            else [[("They", "PRP"), ("moved", "VBD"), (".", ".")]]
        ),
    )
    decision = CandidateGrammar("blue amber. They moved.", ()).decision("blue", 0, 4)
    assert decision == GrammarDecision(True, "nominal_context", 0, 11)


def test_missing_sentence_tokens_preserve_the_candidate_with_mapped_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        grammar_module,
        "_tag_block",
        lambda text: [
            [
                ("We", "PRP"),
                ("discussed", "VBD"),
                ("vault", "NN"),
                ("'s", "POS"),
                ("graph", "NN"),
                (".", "."),
            ]
        ],
    )
    source = "We discussed vault's graph."
    start = source.index("vault's")
    assert CandidateGrammar(source, ()).decision("vault's", start, start + 7) == GrammarDecision(
        True,
        "uncertain_alignment",
        0,
        len(source),
    )


def test_model_failures_propagate_from_the_explanation_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(text: str) -> list[list[tuple[str, str]]]:
        raise RuntimeError("packaged grammar unavailable")

    monkeypatch.setattr(grammar_module, "_tag_block", unavailable)
    source = "The clinic moved the appointment."
    start = source.index("appointment")
    with pytest.raises(RuntimeError, match="packaged grammar unavailable"):
        CandidateGrammar(source, ()).decision("appointment", start, start + 11)


def test_allows_delegates_to_the_explanation_api(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(self: CandidateGrammar, label: str, start: int, end: int) -> GrammarDecision:
        return GrammarDecision(False, "clause_fragment", 0, 9)

    monkeypatch.setattr(CandidateGrammar, "decision", reject)
    assert not CandidateGrammar("any label", ()).allows("any label", 0, 9)


@pytest.mark.parametrize("missing_tags", [False, True])
@pytest.mark.parametrize("other_first", [False, True])
def test_an_uncertain_other_sentence_cannot_weaken_a_mapped_clause_rejection(
    monkeypatch: pytest.MonkeyPatch,
    missing_tags: bool,
    other_first: bool,
) -> None:
    monkeypatch.setattr(
        grammar_module,
        "_tag_block",
        lambda text: (
            ([] if missing_tags else [[("unmapped", "NN")]])
            if text == "unmapped omitted."
            else [
                [
                    ("The", "DT"),
                    ("clinic", "NN"),
                    ("moved", "VBD"),
                    ("the", "DT"),
                    ("appointment", "NN"),
                    (".", "."),
                ]
            ]
        ),
    )
    context = "The clinic moved the appointment."
    other = "unmapped omitted."
    source = other + " " + context if other_first else context + " " + other
    start = source.index("clinic moved")
    context_start = source.index(context)
    assert CandidateGrammar(source, ()).decision("clinic moved", start, start + 12) == (
        GrammarDecision(False, "clause_fragment", context_start, context_start + len(context))
    )


@pytest.mark.parametrize("label", ["Big", "Medium", "Small"])
@pytest.mark.parametrize("suffix", [":", ": partly filled", " : "])
def test_adjective_field_fragments_do_not_take_nominal_or_isolated_shortcuts(
    monkeypatch: pytest.MonkeyPatch, label: str, suffix: str,
) -> None:
    # Surface wording alone never rejects a field: this case supplies JJ tags.
    source = label + suffix
    rows = [(label, "JJ"), (":", ":")]
    if "partly" in suffix:
        rows.extend([("partly", "RB"), ("filled", "VBN")])
    monkeypatch.setattr(grammar_module, "_tag_block", lambda text: [rows])
    decision = CandidateGrammar(source, ()).decision(label, 0, len(label))
    assert not decision.allowed
    assert decision.reason == "non_nominal_field"


def test_a_finite_field_prompt_is_explained_as_a_clause_fragment() -> None:
    source = "Today I accomplished:"
    label = "Today I accomplished"
    decision = CandidateGrammar(source, ()).decision(label, 0, len(label))
    assert not decision.allowed
    assert decision.reason == "clause_fragment"
    assert extract_topics(source, _Candidates(label)) == []


@pytest.mark.parametrize(
    "subject",
    [
        "Ferric ammonium citrate",
        "Python 3",
        "Causal inference",
        "Becoming",
        "important action items",
    ],
)
@pytest.mark.parametrize("value", ["", " a partially filled description"])
def test_true_nominal_and_gerund_field_subjects_remain_eligible(
    subject: str, value: str,
) -> None:
    source = subject + ":" + value
    tags = extract_topics(source, _Candidates(subject))
    assert len(tags) == 1
    assert tags[0].key == subject.casefold()
    assert tags[0].text == source[tags[0].start : tags[0].end] == subject


def test_a_noun_reading_of_medium_is_not_blacklisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        grammar_module, "_tag_block", lambda text: [[("Medium", "NN"), (":", ":")]],
    )
    assert CandidateGrammar("Medium:", ()).decision("Medium", 0, 6) == GrammarDecision(
        True, "noun_phrase", 0, 7,
    )


@pytest.mark.parametrize("subject", ["Use cases", "Climate changes", "Game over", "Becoming"])
def test_non_colon_isolated_subjects_keep_their_ambiguous_readings(subject: str) -> None:
    decision = CandidateGrammar(subject, ()).decision(subject, 0, len(subject))
    assert decision.allowed
    assert decision.reason == "isolated_subject"


def test_a_later_colon_does_not_change_an_unchanged_nominal_candidate_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = "blue amber:"
    monkeypatch.setattr(
        grammar_module, "_tag_block",
        lambda text: [[("blue", "JJ"), ("amber", "NN"), (":", ":")]],
    )
    assert CandidateGrammar(source, ()).decision("blue", 0, 4) == GrammarDecision(
        True, "nominal_context", 0, len(source),
    )
    assert CandidateGrammar(source, ()).decision("blue amber", 0, 10) == GrammarDecision(
        True, "noun_phrase", 0, len(source),
    )


def test_unmapped_colon_field_alignment_still_preserves_the_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(grammar_module, "_tag_block", lambda text: [[("Small", "JJ")]])
    source = "unmapped Small:"
    start = source.index("Small")
    assert CandidateGrammar(source, ()).decision("Small", start, start + 5) == GrammarDecision(
        True, "uncertain_alignment", None, None,
    )


def test_authored_labels_keep_their_independent_heading_and_link_evidence() -> None:
    source = "# Small\n\nSmall:\n\n[[Medium]]:\n"
    tags = extract_topics(source, _Candidates("Small", "Medium"))
    small = next(tag for tag in tags if tag.key == "small")
    medium = next(tag for tag in tags if tag.key == "medium")
    assert small.provenance == "heading"
    assert small.text == "Small"
    assert medium.provenance == "wikilink"
    assert medium.text == "Medium"


def test_local_field_grammar_preserves_a_partly_filled_rare_topic_outline() -> None:
    source = (
        "- Cyanotypes\n"
        "- Ferric ammonium citrate:\n"
        "- Python 3: a partially filled description\n"
        "- Today I accomplished:\n"
    )
    subjects = ("Cyanotypes", "Ferric ammonium citrate", "Python 3")
    tags = extract_topics(source, _Candidates(*subjects, "Today I accomplished"))
    assert {tag.key for tag in tags} == {subject.casefold() for subject in subjects}
    assert all(source[tag.start : tag.end] == tag.text for tag in tags)
