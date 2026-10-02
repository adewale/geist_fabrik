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


_TERMINAL_PUNCTUATION = re.compile(r"[.!?]")


def sentence_questions(text: str) -> list[str]:
    r"""Return the runs of text that end in "?" without crossing ".", "!" or "?".

    Same result as ``re.findall(r"([^.!?\n][^.!?]*\?)", text)`` (each
    question starts at the first non-newline character after the previous
    terminal mark), in linear time. That regex retried a failed match from
    every offset of a run that did not end in "?", so a long line or
    hard-wrapped paragraph without a question mark took quadratic time
    (minutes on a 200 KB line).
    """
    questions: list[str] = []
    start = 0
    for mark in _TERMINAL_PUNCTUATION.finditer(text):
        if mark.group() == "?":
            question = text[start : mark.start()].lstrip("\n")
            if question:
                questions.append(question + "?")
        start = mark.end()
    return questions


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
# Sentence segmentation shared by the definition/claim/hypothesis extractors
# ============================================================================

# Leading Markdown furniture on a line: blockquote ">", a list bullet or
# number, and a task checkbox.
_LINE_PREFIX = re.compile(r"^\s*(?:>\s*)*(?:(?:[-*+]|\d+[.)])\s+)?(?:\[[ xX]\]\s+)?")
# A line that starts a new Markdown block rather than continuing a
# hard-wrapped paragraph line.
_BLOCK_START = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|>|#|\||:\s|-{3,}\s*$|={3,}\s*$)")
# A line nothing can continue: a heading, table row, rule, or a line of bold
# text only (a pseudo-heading such as "**Step 2**").
_CLOSED_LINE = re.compile(r"^\s*(?:#|\||-{3,}\s*$|={3,}\s*$|(?:[-*+]\s+)?\*\*[^*\n]+\*\*:?\s*$)")
# A leading bold field label such as "**Problem**:" or "**Status:**".
_FIELD_LABEL = re.compile(r"^(?:\*\*[^*\n]{1,60}?\*\*\s*:|\*\*[^*\n]{1,60}?:\*\*)\s*")
# Sentence-ending punctuation (plus any closing quotes/brackets) followed by
# whitespace. A period followed directly by a non-space ("0.5", "v1.0",
# "file.md") therefore never ends a sentence.
_SENTENCE_END = re.compile(r"[.!?][\"'”’)\]]*\s+")
# Abbreviations whose period does not end a sentence ("e.g. foo").
_ABBREVIATIONS = re.compile(
    r"(?:\b(?:e\.g|i\.e|etc|vs|cf|approx|al|fig|eq|dr|mr|mrs|ms)|\b[A-Z])\.$",
    re.IGNORECASE,
)
# _ABBREVIATIONS only looks at the end of the text before a candidate
# sentence end: its longest match is "approx." (7 characters), plus one
# character of context for the leading \b. Searching just this many trailing
# characters gives the same answer as searching the whole sentence so far,
# which re-scanned a growing slice at every boundary (quadratic on a long
# paragraph of initials such as a bibliography).
_ABBREVIATION_WINDOW = 16
# Quote marks a sentence may open with when it is reported speech or example
# output rather than the author's own statement.
_OPENING_QUOTES = "\"'“‘"


def _paragraph_lines(content: str) -> list[str]:
    """Join hard-wrapped lines back into the line they render as.

    A line continues the previous one unless it is blank or starts a new
    Markdown block (list item, heading, table row, blockquote, definition
    list ":", rule). YAML frontmatter is dropped.
    """
    lines = content.split("\n")
    if lines and lines[0].strip() == "---":
        closing = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if closing is not None:
            lines = lines[closing + 1 :]
    # Each logical line is collected as parts and joined once: rebuilding the
    # joined string per continuation (and re-matching _CLOSED_LINE against
    # it) was quadratic in a long paragraph without blank lines.
    logical: list[str] = []
    current: _LogicalLine | None = None
    previous_blank = True
    for line in lines:
        if not line.strip():
            previous_blank = True
            continue
        continues = not previous_blank and not _BLOCK_START.match(line)
        if continues and current is not None and not current.closed:
            current.append(line.strip())
        else:
            if current is not None:
                logical.append(current.text())
            current = _LogicalLine(line)
        previous_blank = False
    if current is not None:
        logical.append(current.text())
    return logical


# A line that is (so far) a bold span still waiting for its closing "**":
# an optional list bullet, the opening "**", then text without "*".
_OPEN_BOLD = re.compile(r"\s*(?:[-*+]\s+)?\*\*[^*\n]*")
# A line that is only a list bullet; the next part may open a bold span.
_BARE_BULLET = re.compile(r"\s*[-*+]")
# The rest of a bold-only line after its text: closing "**", optional colon.
_BOLD_CLOSE = re.compile(r"\*\*:?\s*")


class _LogicalLine:
    """A hard-wrapped line being rejoined, with its _CLOSED_LINE status.

    The joined text is ``first`` when there is one part, otherwise
    ``first.rstrip()`` and the stripped continuation parts joined by single
    spaces. ``closed`` equals ``bool(_CLOSED_LINE.match(text()))`` but is
    updated from each new part alone, so appending is O(len(part)).

    Once a second part is appended only the bold-only alternative of
    _CLOSED_LINE can match (a "#" or "|" start or a rule would have closed
    the first part, so nothing would have been appended; and a joined line
    always has a space between non-space parts, which a rule cannot
    contain). The bold alternative needs everything after the opening "**"
    to be "*"-free until a closing "**" that ends the line.
    """

    def __init__(self, first: str) -> None:
        self.parts = [first]
        self.closed = bool(_CLOSED_LINE.match(first))
        self._set_shape(first.rstrip())

    def _set_shape(self, joined: str) -> None:
        # open_bold: the joined text is an opened, still unclosed bold span.
        # bare_bullet: the joined text is a list bullet alone.
        self.open_bold = _OPEN_BOLD.fullmatch(joined) is not None
        self.bare_bullet = _BARE_BULLET.fullmatch(joined) is not None

    def append(self, part: str) -> None:
        """Append a stripped, non-empty continuation line."""
        if self.open_bold:
            star = part.find("*")
            self.closed = star >= 0 and _BOLD_CLOSE.fullmatch(part, star) is not None
            self.open_bold = star < 0
            self.bare_bullet = False
        elif self.bare_bullet:
            # The joined text is short (a bullet and this part): check directly.
            joined = f"{self.parts[0].rstrip()} {part}"
            self.closed = bool(_CLOSED_LINE.match(joined))
            self._set_shape(joined)
        else:
            self.closed = False
        self.parts.append(part)

    def text(self) -> str:
        if len(self.parts) == 1:
            return self.parts[0]
        return " ".join([self.parts[0].rstrip(), *self.parts[1:]])


def prose_sentences(content: str) -> list[str]:
    """Split Markdown prose into sentences for the sentence-level extractors.

    Hard-wrapped lines are rejoined first, so a wrapped sentence is one
    sentence rather than a fragment per line. Table rows and headings are
    skipped. List bullets, blockquote markers, checkboxes, a leading bold
    field label ("**Problem**:") and stray ``**`` emphasis markers are
    removed. A sentence ends at ``.``, ``!`` or ``?`` followed by whitespace,
    except after common abbreviations, so decimals ("0.5") and "e.g." do not
    cut a sentence short.

    Args:
        content: Markdown content (code already handled by strip_code())

    Returns:
        Sentences, stripped of surrounding whitespace, in document order
    """
    sentences: list[str] = []
    for line in _paragraph_lines(content):
        stripped = line.strip()
        if stripped.startswith(("|", "#")):
            continue
        body = _LINE_PREFIX.sub("", line, count=1)
        body = _FIELD_LABEL.sub("", body, count=1).replace("**", "").strip()
        start = 0
        for match in _SENTENCE_END.finditer(body):
            end = match.start() + 1
            if _ABBREVIATIONS.search(body[max(start, end - _ABBREVIATION_WINDOW) : end]):
                continue
            sentences.append(body[start : match.end()].strip())
            start = match.end()
        if body[start:].strip():
            sentences.append(body[start:].strip())
    return [s for s in sentences if s]


def _is_own_statement(sentence: str) -> bool:
    """True if a sentence can be quoted back as something the author asserted.

    Rejects continuation fragments of hard-wrapped lines (lowercase start)
    and quoted example text or reported speech (opening quotation mark).
    """
    first = sentence[0]
    return not first.islower() and first not in _OPENING_QUOTES


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
        questions.extend(sentence_questions(content))

        # Pattern 2: List item questions
        list_questions = re.findall(r"^\s*[-*+]\s+(.+\?)\s*$", content, re.MULTILINE)
        questions.extend(list_questions)

        return questions


class DefinitionExtractor:
    """Extract definitions of a named term.

    Captures sentences that open with a short term (at most five words and
    40 characters, no punctuation) followed by:
    - "is defined as" / "is a" / "is an"
    - "means"
    - "refers to"

    and Markdown definition lists (a term line followed by ": definition").

    Bold field labels such as "**Status**: done" are not definitions and are
    not extracted: in real notes they are almost always form fields
    ("Problem:", "Source:", "Impact:").
    """

    # Term = 1-5 words (an inline code span counts as one word). Bold markers
    # are already gone: prose_sentences() strips "**".
    _TERM_WORD = r"(?:`[^`\n]+`|[\w'’-]+)"
    _SENTENCE_DEFINITION = re.compile(
        rf"^(?P<term>{_TERM_WORD}(?:[ \t]+{_TERM_WORD}){{0,4}})"
        r"[ \t]+(?P<verb>is[ \t]+defined[ \t]+as|is[ \t]+an?|means|refers[ \t]+to)[ \t]+\S",
        re.IGNORECASE,
    )
    _DEFINITION_LIST = re.compile(
        r"^(?P<term>[^\s|#>:*+-][^\n:]{0,59}?)[ \t]*\n:[ \t]+(?P<definition>\S[^\n]*)$",
        re.MULTILINE,
    )
    # Pronouns and deictic words open "It is a ...", "This means ...", which
    # describe rather than define.
    _NOT_TERMS = frozenset(
        "it this that these those there here which what who he she they we i you "
        "one each everything something nothing anything all".split()
    )
    # Clause words inside the "term" mean it is a clause, not a noun phrase
    # ("Detect if file is a ...", "Explanation of why this is a ...").
    _CLAUSE_WORDS = frozenset("if why when where how what which that this because whether".split())
    MAX_TERM_LENGTH = 40

    def extract(self, content: str) -> list[str]:
        """Extract definitions from content.

        Args:
            content: Markdown content (code blocks already removed)

        Returns:
            List of definitions (whole sentences, or "term: definition")
        """
        definitions = [
            f"{m.group('term').strip()}: {m.group('definition').strip()}"
            for m in self._DEFINITION_LIST.finditer(content)
        ]
        for sentence in prose_sentences(content):
            match = self._SENTENCE_DEFINITION.match(sentence)
            # "?" is a question, ":" introduces a list rather than defining.
            if match is None or sentence.endswith(("?", ":")):
                continue
            term = match.group("term")
            words = [w.lower() for w in term.split()]
            if len(term) > self.MAX_TERM_LENGTH or words[0] in self._NOT_TERMS:
                continue
            if self._CLAUSE_WORDS.intersection(words[1:]):
                continue
            definitions.append(sentence)
        return definitions


class ClaimExtractor:
    """Extract claims (assertive statements).

    Captures whole sentences containing:
    - A strong third-person assertion verb after a subject ("X shows ...",
      "proves", "demonstrates", "establishes", "confirms")
    - Research findings ("Studies show...")
    - Causal claims ("X causes Y", "leads to", "results in")

    Imperatives ("Show the numbers"), nouns ("Root cause", "causes of"),
    bold field labels, table rows and quoted example text are not claims.
    """

    _ASSERTION = re.compile(
        r"^\S.*?\s(?:shows|proves|demonstrates|establishes|confirms)\b", re.IGNORECASE
    )
    _RESEARCH = re.compile(
        r"\b(?:Research|Studies|Evidence|Data)\s+(?:shows?|suggests?|indicates?)\b",
        re.IGNORECASE,
    )
    _CAUSAL = re.compile(
        r"^\S.*?\s(?:causes(?!\s+of\b)|caused|leads\s+to|led\s+to|results\s+in)\b",
        re.IGNORECASE,
    )

    def extract(self, content: str) -> list[str]:
        """Extract claims from content.

        Args:
            content: Markdown content (code blocks already removed)

        Returns:
            List of claims (whole sentences ending in a period)
        """
        claims = []
        for sentence in prose_sentences(content):
            if not sentence.endswith(".") or not _is_own_statement(sentence):
                continue
            if any(p.search(sentence) for p in (self._ASSERTION, self._RESEARCH, self._CAUSAL)):
                claims.append(sentence)
        return claims


class HypothesisExtractor:
    """Extract hypotheses (if/then, may/might patterns).

    Captures whole sentences containing:
    - If/then statements
    - May/might/could speculation
    - Would ... if conditionals

    A modal quoted as a word ('use "might"'), the month "May", table rows
    and quoted example text are not hypotheses.

    ``max_sentence_length`` skips longer sentences before matching. The
    if/then and would/if patterns cost (number of "if"s or "would"s) x
    (sentence length), so a 200 KB run-on "sentence" took tens of seconds;
    a pipeline whose LengthFilter discards such sentences anyway should pass
    its maximum here, which leaves its output unchanged.
    """

    def __init__(self, max_sentence_length: int | None = None) -> None:
        self.max_sentence_length = max_sentence_length

    _IF_THEN = re.compile(r"\bif\s+\S.*?,?\s+then\s+\S", re.IGNORECASE)
    _MODAL = re.compile(r"\b(?:may|might|could|Might|Could)\b|^May\s+[a-z]")
    _WOULD_IF = re.compile(r"\bwould\b.+\bif\b", re.IGNORECASE)
    _QUOTED_MODAL = re.compile(r"[\"'“‘](?:may|might|could|would)[\"'”’]", re.IGNORECASE)

    def extract(self, content: str) -> list[str]:
        """Extract hypotheses from content.

        Args:
            content: Markdown content (code blocks already removed)

        Returns:
            List of hypotheses (whole sentences ending in a period)
        """
        hypotheses = []
        limit = self.max_sentence_length
        for sentence in prose_sentences(content):
            if limit is not None and len(sentence) > limit:
                continue
            if not sentence.endswith(".") or not _is_own_statement(sentence):
                continue
            if self._QUOTED_MODAL.search(sentence):
                continue
            if any(p.search(sentence) for p in (self._IF_THEN, self._MODAL, self._WOULD_IF)):
                hypotheses.append(sentence)
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
