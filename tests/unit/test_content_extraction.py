"""Unit tests for the content extraction pipeline.

content_extraction.py is pure (no DB / VaultContext), so it is exercised here
directly. It backs the harvester geists (question/definition/quote/todo), so
its extraction strategies, filters, and pipeline (code-block removal,
filtering, case-insensitive deduplication) are worth locking down.
"""

from geistfabrik.content_extraction import (
    AlphaFilter,
    ClaimExtractor,
    DefinitionExtractor,
    ExtractionPipeline,
    HypothesisExtractor,
    LengthFilter,
    PatternFilter,
    QuestionExtractor,
)


def _stripped(items: list[str]) -> list[str]:
    return [i.strip() for i in items]


class TestRemoveCodeBlocks:
    def test_removes_fenced_code_blocks(self):
        content = "Before\n```\nWhat is this?\n```\nAfter"
        result = ExtractionPipeline._remove_code_blocks(content)
        assert "What is this?" not in result
        assert "Before" in result and "After" in result

    def test_removes_inline_code(self):
        content = "Use `len(x)?` carefully here"
        result = ExtractionPipeline._remove_code_blocks(content)
        assert "len(x)?" not in result
        assert "carefully here" in result

    def test_preserves_plain_text(self):
        content = "No code here at all."
        assert ExtractionPipeline._remove_code_blocks(content) == content


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

    def test_extracts_bold_colon_definition(self):
        result = DefinitionExtractor().extract("**Recursion**: a function calling itself")
        assert any("Recursion" in d and "function calling itself" in d for d in result)

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


class TestHypothesisExtractor:
    def test_extracts_if_then(self):
        result = HypothesisExtractor().extract("If we cache results, then queries get faster.")
        assert any(h.lower().startswith("if we cache") for h in result)

    def test_extracts_may_might(self):
        result = HypothesisExtractor().extract("This approach might reduce contention.")
        assert any("might reduce contention" in h for h in result)


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
    def test_ignores_questions_inside_code_blocks(self):
        pipeline = ExtractionPipeline(strategies=[QuestionExtractor()])
        content = "```\nWhat is hidden in code?\n```\nWhat is visible in prose?"
        result = pipeline.extract(content)
        assert any("visible in prose" in q for q in result)
        assert not any("hidden in code" in q for q in result)

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
