"""Content extraction pipeline for GeistFabrik.

Provides a generalizable pipeline for extracting structured content from
markdown notes. Supports multiple extraction strategies (questions, definitions,
claims, hypotheses) with pluggable filtering and deduplication.

The pipeline pattern:
1. Remove code blocks (avoid false positives)
2. Apply extraction strategies (regex, patterns)
3. Filter (quality checks)
4. Deduplicate

This module generalizes the pattern from question_harvester.py to enable
8+ new content extractor geist types.
"""

import re
from typing import Protocol

# Punctuation that extraction patterns key on (sentence ends, "TODO:",
# blockquote ">", list bullets, quotes). Inside inline code spans these are
# swapped for private-use code points so code cannot start, end or fake an
# extraction, while the span's text survives; unmask_code() swaps them back.
_CODE_PUNCTUATION = ".?!:;#>*+-[]()\"'"
_MASK = str.maketrans({c: chr(0xE000 + i) for i, c in enumerate(_CODE_PUNCTUATION)})
_UNMASK = str.maketrans({chr(0xE000 + i): c for i, c in enumerate(_CODE_PUNCTUATION)})


def strip_code(content: str) -> str:
    """Drop fenced code blocks and neutralise inline code spans.

    Fenced blocks are code samples and are removed. Inline spans are usually
    part of a sentence ("set `--timeout` to 30"), so deleting them leaves
    gaps like "set  to 30" or "(, )"; instead they are kept, backticks and
    all, with their pattern-significant punctuation masked. Pass extracted
    text through unmask_code() before showing it.
    """
    no_fences = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    return re.sub(r"`[^`\n]+`", lambda m: m.group(0).translate(_MASK), no_fences)


def unmask_code(text: str) -> str:
    """Restore punctuation masked inside inline code by strip_code()."""
    return text.translate(_UNMASK)


_QUOTE_PAIRS = {'"': '"', "\u201c": "\u201d", "'": "'", "\u2018": "\u2019"}


def quote_for_display(text: str) -> str:
    """Wrap harvested text in quotation marks without doubling them.

    Text already wrapped in a matching pair is unwrapped first. If the text
    still contains straight double quotes (e.g. '"To be..." - Hamlet'), curly
    outer quotes keep the two levels distinguishable.
    """
    inner = text.strip()
    if len(inner) >= 2 and _QUOTE_PAIRS.get(inner[0]) == inner[-1]:
        candidate = inner[1:-1].strip()
        # Only unwrap a single quoted span, not '"a" and "b"'.
        if inner[0] not in candidate:
            inner = candidate
    if '"' in inner:
        return f"\u201c{inner}\u201d"
    return f'"{inner}"'


class ExtractionStrategy(Protocol):
    """Protocol for extraction strategies.

    Extraction strategies locate and extract specific types of content from
    markdown text using regex patterns, linguistic heuristics, or other methods.
    """

    def extract(self, content: str) -> list[str]:
        """Extract content items from markdown.

        Args:
            content: Markdown content (with code blocks already removed)

        Returns:
            List of extracted items (not filtered or deduplicated)
        """
        ...


class ContentFilter(Protocol):
    """Protocol for content filters.

    Content filters validate extracted items to remove false positives,
    low-quality matches, or irrelevant content.
    """

    def is_valid(self, item: str) -> bool:
        """Check if extracted item is valid.

        Args:
            item: Extracted content item

        Returns:
            True if item should be kept, False to filter out
        """
        ...


class ExtractionPipeline:
    """Generalizable content extraction pipeline.

    Coordinates extraction strategies and filters to extract structured
    content from markdown. Handles code block removal, deduplication,
    and quality filtering.

    Example:
        >>> pipeline = ExtractionPipeline(
        ...     strategies=[QuestionExtractor(), DefinitionExtractor()],
        ...     filters=[LengthFilter(min_len=10, max_len=500)]
        ... )
        >>> items = pipeline.extract(note.content)
    """

    def __init__(
        self,
        strategies: list[ExtractionStrategy],
        filters: list[ContentFilter] | None = None,
    ):
        """Initialize pipeline with strategies and filters.

        Args:
            strategies: List of extraction strategies to apply
            filters: Optional list of filters (default: basic length filter)
        """
        self.strategies = strategies
        self.filters = filters if filters is not None else [LengthFilter()]

    def extract(self, content: str) -> list[str]:
        """Run full pipeline: remove code → strategies → filters → deduplicate.

        Args:
            content: Raw markdown content

        Returns:
            Extracted and filtered items (deduplicated)
        """
        # Step 1: Remove code blocks to avoid false positives
        content_no_code = strip_code(content)

        # Step 2: Apply all extraction strategies
        all_items = []
        for strategy in self.strategies:
            items = strategy.extract(content_no_code)
            all_items.extend(items)

        # Step 3: Filter extracted items
        filtered_items = []
        for item in all_items:
            item_clean = item.strip()

            # Apply all filters
            if all(f.is_valid(item_clean) for f in self.filters):
                filtered_items.append(unmask_code(item_clean))

        # Step 4: Deduplicate (case-insensitive)
        seen = set()
        deduplicated = []
        for item in filtered_items:
            item_normalized = item.lower()
            if item_normalized not in seen:
                deduplicated.append(item)
                seen.add(item_normalized)

        return deduplicated


# ============================================================================
# Built-in Extraction Strategies
# ============================================================================


class QuestionExtractor:
    """Extract questions (sentences ending with ?).

    Uses multiple patterns to capture:
    - Sentence-ending questions
    - List item questions
    """

    def extract(self, content: str) -> list[str]:
        """Extract questions from content.

        Args:
            content: Markdown content (code blocks already removed)

        Returns:
            List of questions
        """
        questions = []

        # Pattern 1: Sentence-ending questions
        sentence_questions = re.findall(r"([^.!?\n][^.!?]*\?)", content, re.MULTILINE)
        questions.extend(sentence_questions)

        # Pattern 2: List item questions
        list_questions = re.findall(r"^\s*[-*+]\s+(.+\?)\s*$", content, re.MULTILINE)
        questions.extend(list_questions)

        return questions


class DefinitionExtractor:
    """Extract definitions (X is Y, X: Y patterns).

    Captures:
    - "X is defined as Y"
    - "X: Y" (definition lists)
    - "X means Y"
    - "X refers to Y"
    """

    def extract(self, content: str) -> list[str]:
        """Extract definitions from content.

        Args:
            content: Markdown content (code blocks already removed)

        Returns:
            List of definitions
        """
        definitions = []

        # Pattern 1: "X is Y" definitions
        is_definitions = re.findall(
            r"^([^.\n]+?)\s+is\s+((?:defined as|a|an)\s+[^.\n]+\.?)",
            content,
            re.MULTILINE | re.IGNORECASE,
        )
        definitions.extend([f"{term} is {definition}" for term, definition in is_definitions])

        # Pattern 2: "X: Y" definition lists
        colon_definitions = re.findall(
            r"^\s*[-*+]?\s*\*\*([^:*]+)\*\*:\s*([^.\n]+\.?)",
            content,
            re.MULTILINE,
        )
        definitions.extend([f"{term}: {definition}" for term, definition in colon_definitions])

        # Pattern 3: "X means Y"
        means_definitions = re.findall(
            r"^([^.\n]+?)\s+means\s+([^.\n]+\.?)",
            content,
            re.MULTILINE | re.IGNORECASE,
        )
        definitions.extend([f"{term} means {definition}" for term, definition in means_definitions])

        # Pattern 4: "X refers to Y"
        refers_definitions = re.findall(
            r"^([^.\n]+?)\s+refers to\s+([^.\n]+\.?)",
            content,
            re.MULTILINE | re.IGNORECASE,
        )
        definitions.extend(
            [f"{term} refers to {definition}" for term, definition in refers_definitions]
        )

        return definitions


class ClaimExtractor:
    """Extract claims (assertive statements).

    Captures:
    - Sentences with strong assertion verbs (shows, proves, demonstrates)
    - Research findings ("Studies show...")
    - Causal claims ("X causes Y")
    """

    def extract(self, content: str) -> list[str]:
        """Extract claims from content.

        Args:
            content: Markdown content (code blocks already removed)

        Returns:
            List of claims
        """
        claims = []

        # Pattern 1: Strong assertion verbs
        assertion_verbs = r"(?:shows?|proves?|demonstrates?|establishes?|confirms?)"
        assertions = re.findall(
            rf"([^.\n]*?\b{assertion_verbs}\b[^.\n]+\.)",
            content,
            re.IGNORECASE,
        )
        claims.extend(assertions)

        # Pattern 2: Research findings
        research_claims = re.findall(
            r"((?:Research|Studies|Evidence|Data)\s+(?:shows?|suggests?|indicates?)[^.\n]+\.)",
            content,
            re.IGNORECASE,
        )
        claims.extend(research_claims)

        # Pattern 3: Causal claims
        causal_claims = re.findall(
            r"([^.\n]+?\b(?:causes?|leads to|results in)\b[^.\n]+\.)",
            content,
            re.IGNORECASE,
        )
        claims.extend(causal_claims)

        return claims


class HypothesisExtractor:
    """Extract hypotheses (if/then, may/might patterns).

    Captures:
    - If/then statements
    - May/might speculation
    - Could/would conditionals
    """

    def extract(self, content: str) -> list[str]:
        """Extract hypotheses from content.

        Args:
            content: Markdown content (code blocks already removed)

        Returns:
            List of hypotheses
        """
        hypotheses = []

        # Pattern 1: If/then statements
        if_then = re.findall(
            r"(If\s+[^.\n]+?,?\s+then\s+[^.\n]+\.)",
            content,
            re.IGNORECASE,
        )
        hypotheses.extend(if_then)

        # Pattern 2: May/might speculation
        may_might = re.findall(
            r"([^.\n]+?\b(?:may|might|could)\b[^.\n]+\.)",
            content,
            re.IGNORECASE,
        )
        hypotheses.extend(may_might)

        # Pattern 3: Would conditionals
        would_conditionals = re.findall(
            r"([^.\n]+?\bwould\b[^.\n]+if[^.\n]+\.)",
            content,
            re.IGNORECASE,
        )
        hypotheses.extend(would_conditionals)

        return hypotheses


# ============================================================================
# Built-in Content Filters
# ============================================================================


class LengthFilter:
    """Filter by text length.

    Removes items that are too short (likely false positives) or too long
    (likely parsing errors).
    """

    def __init__(self, min_len: int = 10, max_len: int = 500):
        """Initialize length filter.

        Args:
            min_len: Minimum character length
            max_len: Maximum character length
        """
        self.min_len = min_len
        self.max_len = max_len

    def is_valid(self, item: str) -> bool:
        """Check if item length is within bounds.

        Args:
            item: Extracted content item

        Returns:
            True if length is valid
        """
        return self.min_len <= len(item) <= self.max_len


class AlphaFilter:
    """Filter by alphabetic content.

    Removes items that don't contain alphabetic characters (likely parsing
    artifacts or false positives).
    """

    def is_valid(self, item: str) -> bool:
        """Check if item contains alphabetic characters.

        Args:
            item: Extracted content item

        Returns:
            True if contains alphabetic characters
        """
        return bool(re.search(r"[a-zA-Z]", item))


class PatternFilter:
    """Filter by regex pattern (blacklist).

    Removes items matching known false positive patterns.
    """

    def __init__(self, patterns: list[str]):
        """Initialize pattern filter.

        Args:
            patterns: List of regex patterns to exclude
        """
        self.patterns = [re.compile(p) for p in patterns]

    def is_valid(self, item: str) -> bool:
        """Check if item matches any exclusion pattern.

        Args:
            item: Extracted content item

        Returns:
            True if item does NOT match any exclusion pattern
        """
        for pattern in self.patterns:
            if pattern.match(item):
                return False
        return True
