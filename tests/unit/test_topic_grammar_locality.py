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
    context: str, label: str, allowed: bool, reason: str, separate_blocks: bool,
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
        boundaries = (
            (context_start, context_start + len(context))
            if separate_blocks else ()
        )
        grammar = CandidateGrammar(source, boundaries)
        decision = grammar.decision(label, start, start + len(label))
        assert decision == GrammarDecision(
            allowed, reason, context_start, context_start + len(context),
        )
        assert grammar.allows(label, start, start + len(label)) is allowed
        assert source[decision.context_start:decision.context_end] == context


def test_nominal_outline_is_not_reinterpreted_by_an_unrelated_clause() -> None:
    outline = "blue amber jade"
    unrelated = "The clinic moved the appointment."
    for source in (outline, outline + "\n\n" + unrelated, unrelated + "\n\n" + outline):
        tags = extract_topics(source, _Candidates("blue", "amber", "jade"))
        assert {tag.key for tag in tags} == {"blue", "amber", "jade"}
        for tag in tags:
            assert source[tag.start:tag.end] == tag.text == tag.label
            assert tag.start == source.index(outline) + outline.index(tag.label)


@pytest.mark.parametrize(
    "subject", ["vault's knowledge graph", "vault’s knowledge graph", "Python 3", "Area 51",
                "World War 2", "attorney general", "accounts receivable"],
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
        False, "clause_fragment", 0, source.index(".") + 1,
    )
    assert grammar.decision("changes", later, later + 7) == GrammarDecision(
        True, "noun_phrase", source.index("Climate"), len(source),
    )
    tags = extract_topics(source, _Candidates("changes"))
    assert len(tags) == 1
    assert tags[0].start == later
    assert source[tags[0].start:tags[0].end] == tags[0].text == "changes"


@pytest.mark.parametrize("source", ["unmapped records", "records unmapped"])
def test_incomplete_alignment_explains_preservation_without_borrowing_tokens(
    monkeypatch: pytest.MonkeyPatch, source: str,
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
        grammar_module, "_tag_block",
        lambda text: (
            [[("blue", "JJ"), ("amber", "JJ"), (".", ".")]]
            if text == "blue amber." else [[("They", "PRP"), ("moved", "VBD"), (".", ".")]]
        ),
    )
    decision = CandidateGrammar("blue amber. They moved.", ()).decision("blue", 0, 4)
    assert decision == GrammarDecision(True, "nominal_context", 0, 11)


def test_missing_sentence_tokens_preserve_the_candidate_with_mapped_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        grammar_module, "_tag_block",
        lambda text: [[("We", "PRP"), ("discussed", "VBD"), ("vault", "NN"),
                       ("'s", "POS"), ("graph", "NN"), (".", ".")]],
    )
    source = "We discussed vault's graph."
    start = source.index("vault's")
    assert CandidateGrammar(source, ()).decision("vault's", start, start + 7) == GrammarDecision(
        True, "uncertain_alignment", 0, len(source),
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
    monkeypatch: pytest.MonkeyPatch, missing_tags: bool, other_first: bool,
) -> None:
    monkeypatch.setattr(
        grammar_module, "_tag_block",
        lambda text: (
            ([] if missing_tags else [[("unmapped", "NN")]])
            if text == "unmapped omitted." else
            [[("The", "DT"), ("clinic", "NN"), ("moved", "VBD"),
              ("the", "DT"), ("appointment", "NN"), (".", ".")]]
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
