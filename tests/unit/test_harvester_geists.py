"""Unit tests for harvester family geists."""

from geistfabrik.default_geists.code.question_harvester import (
    extract_questions,
    is_valid_question,
)
from geistfabrik.default_geists.code.quote_harvester import (
    extract_quotes,
    is_valid_quote,
)
from geistfabrik.default_geists.code.todo_harvester import extract_todos, is_valid_todo

# ============================================================================
# Question Harvester Tests
# ============================================================================


def test_extract_simple_questions() -> None:
    """Test extracting simple questions."""
    content = "What is this? How does it work?"
    questions = extract_questions(content)
    assert len(questions) == 2
    assert "What is this?" in questions
    assert "How does it work?" in questions


def test_extract_multiline_questions() -> None:
    """Test extracting questions that span multiple lines."""
    content = """What happens when
we do this?"""
    questions = extract_questions(content)
    assert len(questions) == 1
    assert "What happens when" in questions[0]
    assert "we do this?" in questions[0]


def test_extract_list_item_questions() -> None:
    """Test extracting questions from markdown lists."""
    content = """
    - What is A?
    - What is B?
    * What is C?
    + What is D?
    """
    questions = extract_questions(content)
    assert len(questions) >= 3
    # Check that at least some list questions were found
    question_texts = " ".join(questions)
    assert "What is A?" in question_texts or "What is A" in question_texts


def test_ignore_code_block_questions() -> None:
    """Test that questions in code blocks are ignored."""
    content = """
Real question: What is this?

```python
# What is this? (comment)
result = condition ? a : b
```

Another question: How does it work?
"""
    questions = extract_questions(content)
    assert len(questions) == 2
    assert "What is this?" in questions[0]  # Matches "Real question: What is this?"
    assert "How does it work?" in questions[1]  # Matches "Another question: How does it work?"
    # Code block questions should not appear
    assert not any("comment" in q.lower() for q in questions)
    assert not any("condition" in q.lower() for q in questions)


def test_ignore_inline_code_questions() -> None:
    """Test that questions in inline code are ignored."""
    content = "What is real? Code: `condition ? a : b` is ternary."
    questions = extract_questions(content)
    assert len(questions) == 1
    assert "What is real?" in questions
    assert not any("condition" in q for q in questions)


def test_question_deduplication() -> None:
    """Test that duplicate questions are removed."""
    content = """
    What is this?
    What is this?
    WHAT IS THIS?
    """
    questions = extract_questions(content)
    assert len(questions) == 1


def test_question_length_filtering() -> None:
    """Test that too-short and too-long questions are filtered."""
    content = "Why? What is the meaning of life, the universe, and everything? " + "x" * 500 + "?"
    questions = extract_questions(content)
    # "Why?" is too short (< 10 chars)
    assert not any(q == "Why?" for q in questions)
    # Normal question should be included
    assert any("meaning of life" in q for q in questions)
    # Very long question should be excluded (> 500 chars)
    assert not any(len(q) > 500 for q in questions)


def test_question_empty_content() -> None:
    """Test extracting from empty content."""
    questions = extract_questions("")
    assert questions == []


def test_question_no_questions() -> None:
    """Test content with no questions."""
    content = "This is a statement. Another statement."
    questions = extract_questions(content)
    assert questions == []


def test_is_valid_question_filtering() -> None:
    """Test question validation rules."""
    # Too short
    assert not is_valid_question("Why?")
    assert not is_valid_question("What?")

    # Valid length
    assert is_valid_question("What is happening here?")

    # Too long
    assert not is_valid_question("x" * 600)

    # No letters
    assert not is_valid_question("??? ??? ???")

    # Valid with letters
    assert is_valid_question("What are these symbols: ???")


# ============================================================================
# TODO Harvester Tests
# ============================================================================


def test_extract_todo_markers() -> None:
    """Test extracting various TODO markers."""
    content = """
TODO: investigate this feature
FIXME: broken behavior in edge case
HACK: temporary workaround
NOTE: remember to check this
XXX: urgent issue
"""
    todos = extract_todos(content)
    assert len(todos) == 5
    assert any("TODO: investigate" in t for t in todos)
    assert any("FIXME: broken" in t for t in todos)
    assert any("HACK: temporary" in t for t in todos)
    assert any("NOTE: remember" in t for t in todos)
    assert any("XXX: urgent" in t for t in todos)


def test_todo_case_insensitive() -> None:
    """Test that TODO markers are case-insensitive."""
    content = """
todo: lowercase
TODO: uppercase
ToDo: mixed case
"""
    todos = extract_todos(content)
    assert len(todos) == 3
    # All should be normalized to uppercase marker
    assert all(t.startswith("TODO:") or t.startswith("TODO:") for t in todos)


def test_ignore_code_block_todos() -> None:
    """Test that TODOs in code blocks are ignored."""
    content = """
TODO: fix this bug

```python
# TODO: code comment
def func():
    pass  # FIXME: refactor
```

FIXME: another real todo
"""
    todos = extract_todos(content)
    assert len(todos) == 2
    assert any("fix this bug" in t for t in todos)
    assert any("another real todo" in t for t in todos)
    # Code block TODOs should not appear
    assert not any("code comment" in t for t in todos)
    assert not any("refactor" in t for t in todos)


def test_todo_deduplication() -> None:
    """Test that duplicate TODOs are removed."""
    content = """
TODO: investigate feature
TODO: investigate feature
TODO: INVESTIGATE FEATURE
"""
    todos = extract_todos(content)
    assert len(todos) == 1


def test_todo_length_filtering() -> None:
    """Test that too-short and too-long TODOs are filtered."""
    content = "TODO: x\nTODO: valid todo item\nTODO: " + "x" * 400
    todos = extract_todos(content)
    # "x" is too short (< 5 chars)
    assert not any(t == "TODO: x" for t in todos)
    # Normal TODO should be included
    assert any("valid todo item" in t for t in todos)
    # Very long TODO should be excluded (> 300 chars)
    assert not any(len(t) > 305 for t in todos)  # 305 = "TODO: " + 300


def test_todo_placeholder_filtering() -> None:
    """Test that common placeholders are filtered."""
    content = """
TODO: add content
TODO: write this
TODO: fill in
TODO: investigate actual feature
"""
    todos = extract_todos(content)
    # Placeholders should be filtered
    assert not any("add content" in t for t in todos)
    assert not any("write this" in t for t in todos)
    assert not any("fill in" in t for t in todos)
    # Real TODO should be kept
    assert any("investigate actual feature" in t for t in todos)


def test_is_valid_todo_filtering() -> None:
    """Test TODO validation rules."""
    # Too short
    assert not is_valid_todo("x")
    assert not is_valid_todo("do")

    # Valid length
    assert is_valid_todo("investigate feature")

    # Too long
    assert not is_valid_todo("x" * 400)

    # Placeholders
    assert not is_valid_todo("add content")
    assert not is_valid_todo("write this")

    # Valid with content
    assert is_valid_todo("research API design patterns")


# ============================================================================
# Quote Harvester Tests
# ============================================================================


def test_extract_single_line_quote() -> None:
    """Test extracting single-line blockquote."""
    content = "> This is a quote from a book."
    quotes = extract_quotes(content)
    assert len(quotes) == 1
    assert "This is a quote from a book" in quotes[0]


def test_extract_multiline_quote() -> None:
    """Test extracting multi-line blockquote."""
    content = """> Line one of the quote.
> Line two of the quote.
> Line three of the quote."""
    quotes = extract_quotes(content)
    assert len(quotes) == 1
    assert "Line one" in quotes[0]
    assert "Line two" in quotes[0]
    assert "Line three" in quotes[0]


def test_extract_multiple_quotes() -> None:
    """Test extracting multiple separate blockquotes."""
    content = """
> First quote here with enough content to pass validation.

Some text in between.

> Second quote here with sufficient length.
> It continues on next line.

More text.

> Third quote also has enough text to be valid.
"""
    quotes = extract_quotes(content)
    assert len(quotes) == 3
    assert any("First quote" in q for q in quotes)
    assert any("Second quote" in q for q in quotes)
    assert any("Third quote" in q for q in quotes)


def test_quote_with_empty_lines() -> None:
    """Test that empty blockquote lines don't break extraction."""
    content = """> Quote starts here.
>
> And continues after empty line."""
    quotes = extract_quotes(content)
    assert len(quotes) == 1
    # Empty line should not appear in output
    assert "Quote starts here" in quotes[0]
    assert "And continues" in quotes[0]


def test_quote_deduplication() -> None:
    """Test that duplicate quotes are removed."""
    content = """
> Same quote.
> Same quote.
> Same Quote.
"""
    quotes = extract_quotes(content)
    # Note: These are separate blockquote blocks, not duplicates within same block
    # But our deduplication should still catch them
    assert len(quotes) == 1


def test_quote_length_filtering() -> None:
    """Test that too-short quotes are filtered."""
    content = "> x\n> This is a valid quote with enough content to be meaningful."
    quotes = extract_quotes(content)
    # "x" is too short (< 10 chars)
    assert not any(q == "x" for q in quotes)
    # Normal quote should be included
    assert any("valid quote" in q for q in quotes)


def test_quote_truncation() -> None:
    """Test that very long quotes are truncated."""
    long_quote = "x" * 600
    content = f"> {long_quote}"
    quotes = extract_quotes(content)
    assert len(quotes) == 1
    # Should be truncated to ~500 chars
    assert len(quotes[0]) <= 503  # 500 + "..."


def test_quote_empty_content() -> None:
    """Test extracting from empty content."""
    quotes = extract_quotes("")
    assert quotes == []


def test_quote_no_quotes() -> None:
    """Test content with no blockquotes."""
    content = "Regular text without any blockquotes."
    quotes = extract_quotes(content)
    assert quotes == []


def test_is_valid_quote_filtering() -> None:
    """Test quote validation rules."""
    # Too short (< 10 chars)
    assert not is_valid_quote("Short")
    assert not is_valid_quote("Too short")

    # Valid length (>= 10 chars with >= 10 letters)
    assert is_valid_quote("This is a valid quote with enough content.")

    # Too few letters (< 10 letters)
    assert not is_valid_quote("!!! ??? @@@ ### $$$ %%% ^^^")

    # Valid with letters
    assert is_valid_quote("This quote has numbers 123 and symbols!")


# ============================================================================
# Cross-Harvester Pattern Tests
# ============================================================================


def test_all_harvesters_handle_empty_content() -> None:
    """Test that all harvesters handle empty content gracefully."""
    assert extract_questions("") == []
    assert extract_todos("") == []
    assert extract_quotes("") == []


def test_all_harvesters_handle_code_blocks() -> None:
    """Test that all harvesters ignore code blocks."""
    code_content = """
```
What is this?
TODO: do something
> A fake quote
```
"""
    # None of these should be extracted from code blocks
    assert extract_questions(code_content) == []
    assert extract_todos(code_content) == []
    assert extract_quotes(code_content) == []


def test_harvesters_with_mixed_content() -> None:
    """Test extracting from content with mixed artifacts."""
    mixed_content = """
# My Note

What is the purpose of this?

TODO: research more

> "The only true wisdom is in knowing you know nothing." - Socrates

How does this apply?

FIXME: clarify argument

> Another insightful quote here.
"""
    questions = extract_questions(mixed_content)
    todos = extract_todos(mixed_content)
    quotes = extract_quotes(mixed_content)

    # Each harvester should find its own artifacts
    assert len(questions) >= 1
    assert len(todos) >= 1
    assert len(quotes) >= 1

    # Verify they're independent
    assert any("purpose" in q for q in questions)
    assert any("research" in t or "clarify" in t for t in todos)
    assert any("wisdom" in q or "insightful" in q for q in quotes)
