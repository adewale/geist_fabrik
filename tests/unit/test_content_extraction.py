"""Unit tests for the content extraction pipeline.

content_extraction.py is pure (no DB / VaultContext), so it is exercised here
directly. It backs the harvester geists (question/definition/quote/todo), so
its extraction strategies, filters, and pipeline (code-block removal,
filtering, case-insensitive deduplication) are worth locking down.
"""

import random
import re

import pytest

from geistfabrik.content_extraction import (
    _ABBREVIATIONS,
    _BLOCK_START,
    _CLOSED_LINE,
    _FIELD_LABEL,
    _LINE_PREFIX,
    _SENTENCE_END,
    AlphaFilter,
    ClaimExtractor,
    ContentFilter,
    DefinitionExtractor,
    ExtractionPipeline,
    HypothesisExtractor,
    LengthFilter,
    PatternFilter,
    QuestionExtractor,
    _paragraph_lines,
    prose_sentences,
    quote_for_display,
    sentence_questions,
    strip_code,
    unmask_code,
)


def _stripped(items: list[str]) -> list[str]:
    return [i.strip() for i in items]


class TestQuestionExtractor:
    def test_extracts_sentence_question(self):
        result = _stripped(QuestionExtractor().extract("What is recursion?"))
        assert "What is recursion?" in result

    def test_extracts_multiple_questions(self):
        text = "Statements here. What is X? And then Y?"
        result = _stripped(QuestionExtractor().extract(text))
        assert "What is X?" in result
        assert "And then Y?" in result

    def test_extracts_list_item_question(self):
        text = "- How does this work?\n- A plain item"
        result = _stripped(QuestionExtractor().extract(text))
        assert "How does this work?" in result

    def test_no_questions_returns_empty(self):
        assert QuestionExtractor().extract("Just a statement.") == []


class TestDefinitionExtractor:
    def test_extracts_is_a_definition(self):
        result = DefinitionExtractor().extract("Recursion is a technique for repetition")
        assert any("Recursion" in d for d in result)

    def test_bold_field_labels_are_not_definitions(self):
        """Contract: a bold "**Label**: value" line is a form field, not a definition.

        Regression: this test used to require "**Recursion**: a function calling
        itself" to be extracted. That pattern matched every bold label, and on a
        real vault 98.6% of definition_harvester's extractions were fields such
        as "Problem: ...", "Status: ..." and "Memory usage: <100MB".
        """
        content = (
            "**Recursion**: a function calling itself\n"
            "- **Problem**: Cache misses on every call\n"
            "**Status**: done and dusted\n"
        )
        assert DefinitionExtractor().extract(content) == []

    def test_extracts_markdown_definition_list(self):
        """Contract: Markdown definition-list syntax (term line, then ": definition")
        is extracted as "term: definition"."""
        content = "Recursion\n: A function calling itself\n\nPlain prose follows here."
        assert DefinitionExtractor().extract(content) == ["Recursion: A function calling itself"]

    def test_term_must_be_a_short_noun_phrase(self):
        """Contract: the defined term is a short noun phrase opening a sentence.

        Regression: the term was "anything from line start", so wrapped-line
        fragments ("application, so this is an optimistic"), pronouns ("It is
        a ..."), clauses ("Detect if file is a ..."), wikilink titles ("[[Everything
        is a remix]]") and table rows were harvested as definitions.
        """
        content = (
            "Files being edited by another application, so this is an optimistic\n"
            "lock that may fail.\n\n"
            "It is a good idea to sync often.\n\n"
            "Detect if file is a journal note\n\n"
            "- [[Everything is a remix]]\n\n"
            "| Cache | is a store of results |\n\n"
            "A file is a date-collection note if it meets these criteria:\n"
        )
        assert DefinitionExtractor().extract(content) == []

    def test_definition_is_the_whole_sentence_across_decimals_and_wraps(self):
        """Contract: a definition is quoted as the whole sentence.

        Regression: the sentence stopped at the first period ("approaching 1.")
        and at the end of a hard-wrapped line.
        """
        content = (
            "GeistFabrik is a well-architected project approaching 1.0 readiness.\n\n"
            "`embedding_metrics` is a derived cache keyed by exact source and\n"
            "algorithm digests.\n"
        )
        assert DefinitionExtractor().extract(content) == [
            "GeistFabrik is a well-architected project approaching 1.0 readiness.",
            "`embedding_metrics` is a derived cache keyed by exact source and algorithm digests.",
        ]

    def test_extracts_means_definition(self):
        result = DefinitionExtractor().extract("Latency means delay before transfer")
        assert any("Latency" in d and "means" in d for d in result)

    def test_extracts_refers_to_definition(self):
        result = DefinitionExtractor().extract("Throughput refers to data rate over time")
        assert any("Throughput" in d and "refers to" in d for d in result)


class TestClaimExtractor:
    def test_extracts_research_claim(self):
        result = ClaimExtractor().extract("Studies show that sleep improves memory.")
        assert any("sleep improves memory" in c for c in result)

    def test_extracts_assertion_verb_claim(self):
        result = ClaimExtractor().extract("This experiment proves the hypothesis.")
        assert any("proves the hypothesis" in c for c in result)

    def test_extracts_causal_claim(self):
        result = ClaimExtractor().extract("Friction causes heat in moving parts.")
        assert any("causes heat" in c for c in result)

    def test_imperatives_and_nouns_are_not_claims(self):
        """Contract: only an assertion made by a subject counts as a claim.

        Regression: "shows?/proves?" matched imperatives ("Show numerically ...",
        "show me notes ...") and "causes?" matched the noun ("**Root cause**:",
        "Common causes of ...").
        """
        content = (
            "Show numerically how much the notes have evolved.\n\n"
            "**Root cause**: the cache was never invalidated.\n\n"
            "Common causes of drift are frequent edits.\n\n"
            "- show me notes that drifted more than 0.3 this year.\n"
        )
        assert ClaimExtractor().extract(content) == []

    def test_decimals_and_abbreviations_do_not_end_the_claim(self):
        """Contract: a claim is the whole sentence.

        Regression: any period ended the sentence, giving fragments such as
        "research shows ... (d = ." and "show me notes that drifted >0.".
        """
        content = (
            "Recent research shows an effect size of d = .40 for maladaptive "
            "strategies (e.g. rumination) in 3.5 studies."
        )
        assert ClaimExtractor().extract(content) == [content]

    def test_field_label_and_bold_markers_are_stripped(self):
        """Contract: the quoted claim has no leading "**Label**:" and no stray "**".

        Regression: claims were quoted as "**Result**: Confirms ..." with the
        Markdown emphasis left in.
        """
        content = "**Result**: The benchmark **confirms** the speedup on large vaults."
        assert ClaimExtractor().extract(content) == [
            "The benchmark confirms the speedup on large vaults."
        ]

    def test_table_rows_and_quoted_examples_are_not_claims(self):
        """Contract: table cells and quoted example output are not the author's claims.

        Regression: '**Value**: "[[Productivity systems]] shows interpretive
        rhythm ...' (example geist output in a spec) was harvested as a claim.
        """
        content = (
            "| BUG-5 | The timeout handler shows a race condition. |\n\n"
            '**Value**: "[[Productivity systems]] shows interpretive rhythm."\n'
        )
        assert ClaimExtractor().extract(content) == []


class TestHypothesisExtractor:
    def test_extracts_if_then(self):
        result = HypothesisExtractor().extract("If we cache results, then queries get faster.")
        assert any(h.lower().startswith("if we cache") for h in result)

    def test_extracts_may_might(self):
        result = HypothesisExtractor().extract("This approach might reduce contention.")
        assert any("might reduce contention" in h for h in result)

    def test_hypothesis_starts_at_the_sentence_start(self):
        """Contract: a hypothesis is the whole sentence, from its real start.

        Regression: a period inside "1.0" or "e.g." split the sentence, giving
        "0 encoded vectors may become more similar." and "How could physical
        artifacts (e.".
        """
        content = (
            "Version 1.0 encoded vectors may become more similar.\n\n"
            "Physical artifacts (e.g. notebooks) could extend memory."
        )
        assert HypothesisExtractor().extract(content) == [
            "Version 1.0 encoded vectors may become more similar.",
            "Physical artifacts (e.g. notebooks) could extend memory.",
        ]

    def test_hard_wrapped_sentence_is_rejoined(self):
        """Contract: a sentence wrapped over two lines is one hypothesis.

        Regression: the wrapped tail was harvested on its own ("Hypothesis range
        checks may survive).").
        """
        content = "Mutation testing finds what the\nrange checks may miss in voice.py.\n"
        assert HypothesisExtractor().extract(content) == [
            "Mutation testing finds what the range checks may miss in voice.py."
        ]

    def test_quoted_modals_months_and_tables_are_not_hypotheses(self):
        """Contract: a modal quoted as a word, the month May and table rows are
        not speculation.

        Regression: 'Use "might", "could" ...' and "| BUG-5 | ... could interfere |"
        were harvested as hypotheses.
        """
        content = (
            'Use "might" and "could" sparingly in suggestions.\n\n'
            "In May we planted beans along the fence.\n\n"
            "| BUG-5 | A global handler that could interfere with nesting. |\n"
        )
        assert HypothesisExtractor().extract(content) == []


class TestFilters:
    def test_length_filter_bounds(self):
        f = LengthFilter(min_len=5, max_len=10)
        assert f.is_valid("abcde") is True  # exactly min
        assert f.is_valid("abcdefghij") is True  # exactly max
        assert f.is_valid("abcd") is False  # too short
        assert f.is_valid("abcdefghijk") is False  # too long

    def test_alpha_filter(self):
        f = AlphaFilter()
        assert f.is_valid("hello") is True
        assert f.is_valid("12345 ?!") is False
        assert f.is_valid("a1") is True

    def test_pattern_filter_excludes_matches(self):
        f = PatternFilter(patterns=[r"^TODO", r"^\d+$"])
        assert f.is_valid("TODO fix this") is False
        assert f.is_valid("12345") is False
        assert f.is_valid("a real item") is True


class TestExtractionPipeline:
    def test_ignores_questions_inside_code(self):
        """Fenced blocks and inline code are code, not prose, and yield nothing."""
        pipeline = ExtractionPipeline(strategies=[QuestionExtractor()])
        content = (
            "```\nWhat is hidden in code?\n```\n"
            "Call `is_this_inline_code_hidden()?` first. What is visible in prose?"
        )
        result = pipeline.extract(content)
        assert any("visible in prose" in q for q in result)
        assert not any("hidden in code" in q or "inline_code" in q for q in result)

    def test_deduplicates_case_insensitively(self):
        pipeline = ExtractionPipeline(
            strategies=[QuestionExtractor()],
            filters=[LengthFilter(min_len=1, max_len=500)],
        )
        # Same question twice with different case -> one result.
        content = "What is entropy? what is entropy?"
        result = pipeline.extract(content)
        normalized = [q.lower() for q in result]
        assert normalized.count("what is entropy?") == 1

    def test_default_length_filter_drops_short_items(self):
        # Default LengthFilter has min_len=10, so "Why?" (4 chars) is dropped.
        pipeline = ExtractionPipeline(strategies=[QuestionExtractor()])
        result = pipeline.extract("Why? This is a much longer question, yes?")
        assert not any(q.strip() == "Why?" for q in result)
        assert any("longer question" in q for q in result)

    def test_multiple_strategies_combined(self):
        pipeline = ExtractionPipeline(
            strategies=[QuestionExtractor(), DefinitionExtractor()],
            filters=[LengthFilter(min_len=1, max_len=500)],
        )
        content = "Recursion is a technique for repetition. What is iteration?"
        result = pipeline.extract(content)
        assert any("iteration" in r for r in result)  # question
        assert any("Recursion" in r for r in result)  # definition

    def test_empty_content_returns_empty(self):
        pipeline = ExtractionPipeline(strategies=[QuestionExtractor()])
        assert pipeline.extract("") == []


class TestCodeMasking:
    def test_fenced_blocks_are_removed_and_inline_text_survives(self):
        content = "```\nprint('x?')\n```\nSet `a.b?` now."
        masked = strip_code(content)
        assert "print" not in masked
        # The span stays (with backticks) but its punctuation cannot end a
        # sentence or form a question...
        assert "?" not in masked and "a.b" not in masked
        # ...and unmasking restores it exactly.
        assert unmask_code(masked) == "\nSet `a.b?` now."

    def test_inline_todo_marker_is_not_a_marker(self):
        assert "TODO:" not in strip_code("Write `TODO: x` markers like this.")


class TestQuoteForDisplay:
    def test_plain_text_gets_straight_quotes(self):
        assert quote_for_display("plain words") == '"plain words"'

    def test_wrapping_pair_is_not_doubled(self):
        assert quote_for_display('"wrapped"') == '"wrapped"'
        assert quote_for_display("\u2018wrapped\u2019") == '"wrapped"'

    def test_two_quoted_spans_are_not_unwrapped(self):
        # '"a" and "b"' starts and ends with a quote but is not one span.
        assert quote_for_display('"a" and "b"') == '\u201c"a" and "b"\u201d'


# ============================================================================
# Pathological inputs: every scan must stay linear (regression)
# ============================================================================
#
# Each input below took more than 30 s before its fix (a hard-wrapped or
# unpunctuated paste, a bibliography, a run-on sentence) and takes
# milliseconds after. The equivalence tests pin each fix to the former
# implementation, kept here as a reference.

_LONG_LINE = "abcdefghij" * 20_000
_FUZZ_ALPHABET = [
    *"ab ",
    *["\n", "\n\n", ".", "!", "?", "*", "**", "- ", "* ", "+ ", "# ", "|", ">", ":"],
    *["---", "===", "e.g.", "J.", " A.", "Dr.", "approx.", "  ", "\t", "if ", "would "],
    *["then ", "`x`", "1. ", "[x] ", '"', "May ", "is a ", "Studies show ", "causes "],
]


def _fuzz_texts(count: int, max_tokens: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    return [
        "".join(rng.choice(_FUZZ_ALPHABET) for _ in range(rng.randint(0, max_tokens)))
        for _ in range(count)
    ]


def _reference_paragraph_lines(content: str) -> list[str]:
    """The former implementation (string concatenation per continuation)."""
    lines = content.split("\n")
    if lines and lines[0].strip() == "---":
        closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if closing is not None:
            lines = lines[closing + 1 :]
    logical: list[str] = []
    previous_blank = True
    for line in lines:
        if not line.strip():
            previous_blank = True
            continue
        continues = not previous_blank and not _BLOCK_START.match(line)
        if continues and not _CLOSED_LINE.match(logical[-1]):
            logical[-1] = f"{logical[-1].rstrip()} {line.strip()}"
        else:
            logical.append(line)
        previous_blank = False
    return logical


def _reference_prose_sentences(content: str) -> list[str]:
    """The former implementation (abbreviation search over the whole slice)."""
    sentences: list[str] = []
    for line in _reference_paragraph_lines(content):
        stripped = line.strip()
        if stripped.startswith(("|", "#")):
            continue
        body = _LINE_PREFIX.sub("", line, count=1)
        body = _FIELD_LABEL.sub("", body, count=1).replace("**", "").strip()
        start = 0
        for match in _SENTENCE_END.finditer(body):
            if _ABBREVIATIONS.search(body[start : match.start() + 1]):
                continue
            sentences.append(body[start : match.end()].strip())
            start = match.end()
        if body[start:].strip():
            sentences.append(body[start:].strip())
    return [s for s in sentences if s]


class TestLinearScans:
    def test_sentence_questions_equals_the_former_regex(self):
        known = {
            "Why? Because. How so?": ["Why?", " How so?"],
            "\n\nWhy\nnot?": ["Why\nnot?"],
            "a??b?": ["a?", "b?"],
            "No question here.": [],
            "Ends open?!": ["Ends open?"],
        }
        for text, expected in known.items():
            assert sentence_questions(text) == expected
        for text in [*known, *_fuzz_texts(3000, 30, seed=1)]:
            assert sentence_questions(text) == re.findall(r"([^.!?\n][^.!?]*\?)", text)

    def test_paragraph_lines_and_sentences_equal_the_former_implementation(self):
        texts = _fuzz_texts(3000, 30, seed=2) + _fuzz_texts(200, 300, seed=3)
        for text in texts:
            assert _paragraph_lines(text) == _reference_paragraph_lines(text)
            assert prose_sentences(text) == _reference_prose_sentences(text)

    def test_bold_line_closed_by_a_later_wrapped_line_stays_closed(self):
        # "**Step two" + "of three**" renders as one bold pseudo-heading, so
        # the following line starts a new logical line.
        assert _paragraph_lines("**Step two\nof three**\nNext line.") == [
            "**Step two of three**",
            "Next line.",
        ]
        assert _paragraph_lines("-\n**Bold**\nNext.") == ["- **Bold**", "Next."]

    @pytest.mark.timeout(10)
    def test_question_extractor_is_linear_on_a_long_line(self):
        content = f"{_LONG_LINE}. Is this still found?"
        assert QuestionExtractor().extract(content) == [" Is this still found?"]

    @pytest.mark.timeout(10)
    def test_bibliography_of_initials_is_one_sentence(self):
        """Regression: each initial ("A.") re-searched the growing sentence."""
        names = ["Smith", "Jones", "Lee", "Garcia", "Okafor", "Novak", "Tanaka"]
        bib = " ".join(
            f"{names[i % 7]}, {chr(65 + i % 26)}. {chr(65 + (i * 7) % 26)}.," for i in range(12_000)
        )
        sentences = prose_sentences(f"{bib} and others. Next sentence.")
        assert len(sentences) == 2
        assert sentences[0].endswith("and others.") and sentences[1] == "Next sentence."

    @pytest.mark.timeout(10)
    def test_hard_wrapped_paragraph_under_an_unclosed_bold_opening_is_linear(self):
        """Regression: every continuation rebuilt the joined line and re-ran
        _CLOSED_LINE over it, whose bold branch scans to the first "*"."""
        lines = ["words go here and on"] * 60_000
        assert _paragraph_lines("**Speaker one\n" + "\n".join(lines)) == [
            " ".join(["**Speaker one", *lines])
        ]

    @pytest.mark.timeout(10)
    def test_hypothesis_extractor_skips_sentences_beyond_its_limit(self):
        """Regression: _IF_THEN / _WOULD_IF cost (#if x length) on a run-on sentence."""
        run_on = "I think " + " ".join(["if soil and roots would maybe"] * 14_000) + " would."
        content = f"{run_on}\n\nIf it rains, then the soil would soften."
        filters: list[ContentFilter] = [LengthFilter(min_len=20, max_len=300), AlphaFilter()]
        bounded = ExtractionPipeline([HypothesisExtractor(max_sentence_length=300)], filters)

        assert bounded.extract(content) == ["If it rains, then the soil would soften."]

    def test_hypothesis_limit_does_not_change_pipeline_output(self):
        content = (
            "If the seeds sprout, then the beds are warm. "
            + "It might rain " * 30
            + "today. The harvest could be early."
        )
        filters: list[ContentFilter] = [LengthFilter(min_len=20, max_len=300), AlphaFilter()]
        unbounded = ExtractionPipeline([HypothesisExtractor()], filters).extract(content)
        bounded = ExtractionPipeline(
            [HypothesisExtractor(max_sentence_length=300)], filters
        ).extract(content)

        assert len(unbounded) == 2  # the long "might" sentence is filtered either way
        assert bounded == unbounded
