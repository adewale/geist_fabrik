"""Source grounding and inspectable, fallible topic selection.

Storage and source eligibility do not depend on relevance policy. Policy switches
exist for controlled experiments; routine use has one versioned default.
"""

import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast

import yake  # type: ignore[import-untyped]

from .topic_grammar import WORD, CandidateGrammar, GrammarDecision
from .topic_text import explicit_labels, topic_boundaries, topic_prose

MAX_TOPICS = 5
MAX_TOPIC_CHARS = 100_000
SETTINGS: dict[str, Any] = {
    "lan": "en",
    "n": 3,
    "top": 50,
    "dedup_lim": 0.9,
    "window_size": 2,
}
PREDICATE_HINTS = frozenset(
    "need needs use uses using make makes made help helps improve improves "
    "develop develops connect connects change changes reduce reduces include includes "
    "depend depends begin begins contain contains combine combines explore explores "
    "protect protects detect detects disagree evolve evolves discussed focused "
    "through over and or but".split()
)


class KeywordExtractor(Protocol):
    def extract_keywords(self, text: str, /) -> list[tuple[str, float]]: ...


class Grammar(Protocol):
    def decision(self, label: str, start: int, end: int) -> GrammarDecision: ...


@dataclass(frozen=True)
class SelectionPolicy:
    heading_prior: bool = True
    link_prior: bool = True
    predicate_penalty: bool = True
    score_gap: bool = True
    containment: bool = True
    repeated_words: bool = True
    grammar: bool = True

    @property
    def name(self) -> str:
        return "+".join(name for name, enabled in vars(self).items() if enabled) or "clean-yake"

    @property
    def complexity(self) -> int:
        return sum(bool(value) for value in vars(self).values())


DEFAULT_POLICY = SelectionPolicy()


@dataclass(frozen=True)
class TopicTag:
    key: str
    label: str
    score: float
    start: int
    end: int
    text: str
    line: int
    provenance: str = "yake"


@dataclass(frozen=True)
class OccurrenceDecision:
    start: int
    end: int
    allowed: bool
    reason: str
    context_start: int | None = None
    context_end: int | None = None


@dataclass
class CandidateDecision:
    label: str
    key: str
    provenance: str
    raw_score: float | None
    adjusted_score: float | None
    selected: bool = False
    stage: Literal["grounding", "relevance", "selection"] = "grounding"
    reason: str = "no_source_match"
    adjustments: list[str] = field(default_factory=list)
    inspected_occurrences: list[OccurrenceDecision] = field(default_factory=list)
    conflicting_key: str | None = None


@dataclass(frozen=True)
class StructuralExclusion:
    start: int
    end: int
    line: int
    reason: str = "non_prose_or_metadata"


@dataclass(frozen=True)
class TopicExplanation:
    policy: SelectionPolicy
    topics: list[TopicTag]
    candidates: list[CandidateDecision]
    structural_exclusions: list[StructuralExclusion]


def topic_key(label: str) -> str:
    """Only Unicode/case/whitespace identity; no semantic merging or stemming."""
    return " ".join(unicodedata.normalize("NFC", label).casefold().split())


def _visible_evidence(content: str, prose: str, start: int, end: int) -> bool:
    """A single raw evidence span cannot reconstruct masked syntax or content.

    Composite visible phrases remain YAKE proposals, but require a later safe
    occurrence or future multi-span evidence support before they can be stored.
    """
    return all(
        raw == visible or (raw.isspace() and visible.isspace())
        for raw, visible in zip(content[start:end], prose[start:end], strict=True)
    )


def analyze_topics(
    content: str,
    extractor: KeywordExtractor | None = None,
    *,
    policy: SelectionPolicy | None = None,
    grammar_factory: Callable[[str, tuple[int, ...]], Grammar] = CandidateGrammar,
    trace: bool = True,
) -> TopicExplanation:
    """Separate structural visibility, source grounding and relevance decisions.

    An explanation contains eligible candidate wording and inspected occurrences,
    never the hidden text of masked regions. Alignment uncertainty keeps a
    candidate; unavailable grammar remains an extraction error.
    """
    if len(content) > MAX_TOPIC_CHARS:
        raise ValueError(f"topic extraction exceeds {MAX_TOPIC_CHARS} characters")
    policy = DEFAULT_POLICY if policy is None else policy
    prose = topic_prose(content)
    boundaries = topic_boundaries(content)
    exclusions = (
        [
            StructuralExclusion(m.start(), m.end(), content.count("\n", 0, m.start()) + 1)
            for m in WORD.finditer(content)
            if prose[m.start() : m.end()] != m.group()
        ]
        if trace
        else []
    )
    decisions: list[CandidateDecision] = []
    if not WORD.search(prose):
        return TopicExplanation(policy, [], decisions, exclusions)
    if extractor is None:
        extractor = cast(KeywordExtractor, yake.KeywordExtractor(**SETTINGS))
    grammar = grammar_factory(prose, boundaries) if policy.grammar else None
    tags: dict[str, tuple[TopicTag, CandidateDecision]] = {}

    def admit(tag: TopicTag, decision: CandidateDecision) -> None:
        prior = tags.get(tag.key)
        if prior is None or tag.score < prior[0].score:
            if prior is not None:
                prior[1].stage = "selection"
                prior[1].reason = "better_same_key_candidate"
            tags[tag.key] = tag, decision
        else:
            decision.stage = "selection"
            decision.reason = "better_same_key_candidate"

    for label, start, end, provenance in explicit_labels(content, prose):
        key = topic_key(label)
        score = 0.0 if provenance == "heading" else 0.001
        row = CandidateDecision(label, key, provenance, score, score)
        decisions.append(row)
        if not (policy.heading_prior if provenance == "heading" else policy.link_prior):
            row.stage, row.reason = "relevance", "authored_prior_disabled"
            continue
        if not _visible_evidence(content, prose, start, end):
            row.reason = "masked_evidence_span"
            continue
        if len(key) < 2 or " ".join(WORD.findall(key)) != key or not any(c.isalpha() for c in key):
            row.reason = "unsupported_label_shape"
            continue
        row.inspected_occurrences.append(OccurrenceDecision(start, end, True, "authored_source"))
        admit(
            TopicTag(
                key,
                label,
                score,
                start,
                end,
                content[start:end],
                content.count("\n", 0, start) + 1,
                provenance,
            ),
            row,
        )

    for label, raw_score in extractor.extract_keywords(prose):
        key = topic_key(label)
        words = WORD.findall(key)
        score = float(raw_score)
        finite_score = score if math.isfinite(score) else None
        row = CandidateDecision(label, key, "yake", finite_score, finite_score)
        decisions.append(row)
        if (
            not words
            or " ".join(words) != key
            or not any(c.isalpha() for c in key)
            or len(key) < 2
            or not math.isfinite(score)
            or score < 0
        ):
            row.reason = "unsupported_label_or_score"
            continue
        if policy.repeated_words and len(set(words)) != len(words):
            row.stage, row.reason = "relevance", "repeated_words"
            continue
        if policy.predicate_penalty and any(word in PREDICATE_HINTS for word in words):
            score *= 32.0
            row.adjustments.append("predicate_hint_penalty_32")
        if not math.isfinite(score):
            row.adjusted_score = None
            row.stage, row.reason = "relevance", "adjusted_score_overflow"
            continue
        row.adjusted_score = score
        expression = r"(?<!\w)" + r"\s+".join(re.escape(w) for w in label.split()) + r"(?!\w)"
        chosen: re.Match[str] | None = None
        for occurrence in re.finditer(expression, prose, re.IGNORECASE):
            start, end = occurrence.span()
            if not _visible_evidence(content, prose, start, end):
                row.inspected_occurrences.append(
                    OccurrenceDecision(start, end, False, "masked_evidence_span")
                )
                row.stage, row.reason = "grounding", "masked_evidence_span"
                continue
            if any(start < edge < end for edge in boundaries):
                row.inspected_occurrences.append(
                    OccurrenceDecision(start, end, False, "crosses_structural_boundary")
                )
                row.reason = "crosses_structural_boundary"
                continue
            assessment = (
                grammar.decision(label, start, end)
                if grammar is not None
                else GrammarDecision(True, "grammar_disabled", None, None)
            )
            row.inspected_occurrences.append(
                OccurrenceDecision(
                    start,
                    end,
                    assessment.allowed,
                    assessment.reason,
                    assessment.context_start,
                    assessment.context_end,
                )
            )
            if assessment.allowed:
                chosen = occurrence
                break
            row.stage, row.reason = "relevance", assessment.reason
        if chosen is None:
            continue
        start, end = chosen.span()
        admit(
            TopicTag(
                key,
                " ".join(label.split()),
                score,
                start,
                end,
                content[start:end],
                content.count("\n", 0, start) + 1,
            ),
            row,
        )

    selected: list[TopicTag] = []
    previous_statistical_cost: float | None = None
    for tag, row in sorted(tags.values(), key=lambda pair: (pair[0].score, pair[0].key)):
        row.stage = "selection"
        conflict = next(
            (
                other
                for other in selected
                if f" {tag.key} " in f" {other.key} " or f" {other.key} " in f" {tag.key} "
            ),
            None,
        )
        if policy.containment and conflict is not None:
            row.reason, row.conflicting_key = "contained_label", conflict.key
            continue
        if (
            policy.score_gap
            and tag.provenance == "yake"
            and len(tag.key.split()) == 1
            and previous_statistical_cost is not None
            and previous_statistical_cost > 0
            and tag.score > previous_statistical_cost * 8.0
        ):
            row.reason = "standalone_score_gap_8"
            continue
        if len(selected) == MAX_TOPICS:
            row.reason = "label_limit"
            continue
        selected.append(tag)
        row.selected, row.reason = True, "selected"
        if tag.provenance == "yake":
            previous_statistical_cost = tag.score
    return TopicExplanation(policy, selected, decisions if trace else [], exclusions)


def extract_topics(content: str, extractor: KeywordExtractor | None = None) -> list[TopicTag]:
    return analyze_topics(content, extractor, trace=False).topics


def explain_topics(content: str) -> TopicExplanation:
    return analyze_topics(content)
