"""Unit tests for harvester family geists."""

from pathlib import Path
from types import ModuleType

import pytest

from geistfabrik.default_geists.code import (
    definition_harvester,
    question_harvester,
    quote_harvester,
    todo_harvester,
)
from geistfabrik.default_geists.code.question_harvester import (
    extract_questions,
    is_valid_question,
)
from geistfabrik.default_geists.code.quote_harvester import (
    extract_quotes,
    is_valid_quote,
)
from geistfabrik.default_geists.code.todo_harvester import extract_todos, is_valid_todo
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

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
    """List-item questions are harvested once each, without their markers.

    Regression: each item was harvested twice, once with its marker by the
    sentence pattern ("- What is A?") and once without by the list pattern.
    """
    content = """
    - What is A?
    - What is B?
    * What is C?
    + What is D?
    """
    assert extract_questions(content) == ["What is A?", "What is B?", "What is C?", "What is D?"]


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
FIXME: broken behaviour in edge case
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
    # All should be normalised to uppercase marker
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


def test_ignore_code_block_quotes() -> None:
    """Test that quotes in code blocks are ignored."""
    content = """
Real quote outside code:

> This is a legitimate quote that should be extracted from the document.

```python
# Code example with a fake blockquote
> This is just a code example, not a real quote to extract.
```

Another real quote:

> Another legitimate quote that should be found and extracted here.
"""
    quotes = extract_quotes(content)
    assert len(quotes) == 2
    assert any("legitimate quote that should be extracted" in q for q in quotes)
    assert any("Another legitimate quote" in q for q in quotes)
    # Code block quote should not appear
    assert not any("code example" in q.lower() for q in quotes)


def test_ignore_inline_code_quotes() -> None:
    """Test that quotes in inline code are ignored."""
    content = "> Real quote here with valid content.\n\nCode: `> fake quote` is inline."
    quotes = extract_quotes(content)
    assert len(quotes) == 1
    assert "Real quote here" in quotes[0]
    assert not any("fake quote" in q for q in quotes)


# ============================================================================
# Cross-Harvester Pattern Tests
# ============================================================================


def test_all_harvesters_handle_empty_content() -> None:
    """Test that all harvesters handle empty content gracefully."""
    assert extract_questions("") == []
    assert extract_todos("") == []
    assert extract_quotes("") == []


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
    # Each harvester finds exactly its own artifacts. Regression: the "# My
    # Note" heading has no closing punctuation, so it was glued onto the first
    # question ("# My Note What is the purpose of this?").
    assert extract_questions(mixed_content) == [
        "What is the purpose of this?",
        "How does this apply?",
    ]
    assert extract_todos(mixed_content) == ["TODO: research more", "FIXME: clarify argument"]
    assert extract_quotes(mixed_content) == [
        '"The only true wisdom is in knowing you know nothing." - Socrates',
        "Another insightful quote here.",
    ]


# ============================================================================
# suggest(): the harvester family through the real VaultContext
# ============================================================================
#
# Trigger: every harvester reads ONE note picked by vault.random_notes(1) and
# turns each extracted item into a suggestion, sampling up to 3. A vault whose
# only user note holds planted items therefore triggers deterministically.
# Each row plants five items (more than the cap of 3); the item strings are
# what the extractor must return verbatim.

HARVEST_NOTE = "Harvest Note"

HARVESTERS = [
    pytest.param(
        question_harvester,
        [
            "What is soil made of?",
            "Why do seeds sprout in spring?",
            "How deep should compost go?",
            "When do worms surface after rain?",
            "Where do bees overwinter safely?",
        ],
        "\n".join,
        "What if you revisited this question now?",
        id="question_harvester",
    ),
    pytest.param(
        quote_harvester,
        [
            "The soil is alive and breathing.",
            "A garden is never finished, only abandoned.",
            "Plant the seed and trust the season.",
            "Compost is the memory of the garden.",
            "Every weed is a flower out of place.",
        ],
        lambda items: "\n\n".join(f"> {item}" for item in items),
        "What if you reflected on this again?",
        id="quote_harvester",
    ),
    pytest.param(
        todo_harvester,
        [
            "TODO: sharpen the trowel blades",
            "FIXME: the gate latch sticks",
            "HACK: tape holds the hose together",
            "NOTE: frost arrives mid October",
            "XXX: the shed roof leaks",
        ],
        "\n".join,
        "What if you tackled this now?",
        id="todo_harvester",
    ),
    pytest.param(
        definition_harvester,
        [
            "Compost is a mix of rotted leaves and scraps.",
            "Humus means the dark stable fraction of soil.",
            "Tilth refers to the crumbly structure of worked soil.",
            "Mulch is defined as any layer spread over soil.",
            "Loam is an even blend of sand, silt and clay.",
        ],
        "\n".join,
        "What if you explored this definition further?",
        id="definition_harvester",
    ),
]
HARVEST_ARGS = ("geist", "items", "render", "prompt")


def _harvest_vault(root: Path, body: str, *, journal: dict[str, str] | None = None) -> VaultContext:
    builder = VaultBuilder(root)
    builder.note(HARVEST_NOTE, body)
    for title, journal_body in (journal or {}).items():
        builder.journal(title, journal_body)
    return builder.build()


def _geist_id(geist: ModuleType) -> str:
    return geist.__name__.rsplit(".", 1)[-1]


@pytest.mark.parametrize(HARVEST_ARGS, HARVESTERS)
def test_harvester_quotes_the_planted_item(tmp_path, geist, items, render, prompt) -> None:
    """Happy path and the abstain boundary: one planted item gives exactly one
    suggestion quoting it verbatim; the same note without it gives nothing.

    Regressions: question_harvester glued the "# Harvest Note" heading onto
    the first question, and definition_harvester dropped the article ("Compost
    is mix of ..."), so both misquoted the note.
    """
    item = items[0]
    planted = _harvest_vault(tmp_path / "planted", render([item]))
    empty = _harvest_vault(tmp_path / "empty", "Plain soil notes without anything to harvest")

    suggestions = geist.suggest(planted)

    assert_valid_suggestions(suggestions, _geist_id(geist), must_reference=[HARVEST_NOTE])
    assert [(s.text, s.notes) for s in suggestions] == [
        (f'From [[{HARVEST_NOTE}]]: "{item}" {prompt}', [HARVEST_NOTE])
    ]
    assert geist.suggest(empty) == []


@pytest.mark.parametrize(HARVEST_ARGS, HARVESTERS)
def test_harvester_caps_at_three(tmp_path, geist, items, render, prompt) -> None:
    """Cap: five planted items yield exactly three suggestions, each quoting a
    different planted item."""
    ctx = _harvest_vault(tmp_path, render(items))

    suggestions = geist.suggest(ctx)

    assert len(suggestions) == 3
    assert_valid_suggestions(suggestions, _geist_id(geist))
    prefix = f'From [[{HARVEST_NOTE}]]: "'
    quoted = {s.text.removeprefix(prefix).removesuffix(f'" {prompt}') for s in suggestions}
    assert len(quoted) == 3 and quoted <= set(items)


@pytest.mark.parametrize(HARVEST_ARGS, HARVESTERS)
def test_harvester_excludes_geist_journal(tmp_path, geist, items, render, prompt) -> None:
    """Both directions: eight session notes full of harvestable items are never
    picked; the one user note always is."""
    journal = {f"2024-03-{day:02d}": render(items[1:]) for day in range(1, 9)}
    ctx = _harvest_vault(tmp_path, render(items[:1]), journal=journal)

    suggestions = geist.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        _geist_id(geist),
        must_reference=[items[0]],
        must_not_reference=["geist journal", "2024-03-0", *items[1:]],
    )


INLINE_CODE_ITEMS = [
    pytest.param(question_harvester, "Should `--timeout` beat the config value?", id="question"),
    pytest.param(quote_harvester, "> Pass `--count` (or `-c`) before planting.", id="quote"),
    pytest.param(todo_harvester, "TODO: rename the `--count` flag to `--limit`", id="todo"),
    pytest.param(
        definition_harvester,
        "Tilth is a measure of `soil_crumb` (or `crumb`) form.",
        id="definition",
    ),
]


@pytest.mark.parametrize(("geist", "line"), INLINE_CODE_ITEMS)
def test_harvester_keeps_inline_code_in_the_quoted_text(tmp_path, geist, line) -> None:
    """Contract: inline code inside a harvested sentence is quoted intact.

    Regression: inline code spans were deleted before extraction, so
    "explicit CLI flag (`--timeout`, `--count`) wins" was quoted as
    "explicit CLI flag (, ) wins".
    """
    ctx = _harvest_vault(tmp_path, line)

    suggestions = geist.suggest(ctx)

    assert_valid_suggestions(suggestions, _geist_id(geist), must_reference=[HARVEST_NOTE])
    (suggestion,) = suggestions
    expected = line.removeprefix("> ")
    assert f'"{expected}"' in suggestion.text


@pytest.mark.parametrize(
    ("quote", "shown"),
    [
        ('"A garden is never finished."', '"A garden is never finished."'),
        ("“A garden is never finished.”", '"A garden is never finished."'),
        (
            '"A garden is never finished." - Karel Capek',
            '“"A garden is never finished." - Karel Capek”',
        ),
    ],
    ids=["straight", "curly", "attributed"],
)
def test_quote_harvester_does_not_double_quotation_marks(tmp_path, quote, shown) -> None:
    """Contract: a blockquote that is already in quotation marks is shown once.

    Regression: the suggestion wrapped every quote in straight quotes, so a
    quoted blockquote came out as ""A garden is never finished."".
    """
    ctx = _harvest_vault(tmp_path, f"> {quote}")

    (suggestion,) = quote_harvester.suggest(ctx)

    assert suggestion.text == (
        f"From [[{HARVEST_NOTE}]]: {shown} What if you reflected on this again?"
    )
