"""Quote Harvester geist - extracts blockquotes from random notes.

Surfaces blockquote content (markdown ">") from notes. Blockquotes represent:
- External quotes from books, articles, people
- Passages worth preserving
- Reference material
- Ideas that resonated enough to capture

Core insight: Surfacing quotes randomly reveals what you valued at different
times—a temporal map of intellectual influences.
"""

import re
from typing import TYPE_CHECKING

from geistfabrik.content_extraction import quote_for_display, strip_code, unmask_code

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Extract blockquotes from a randomly selected note.

    Returns:
        List of 1-3 suggestions containing quotes found (or empty if none)
    """
    from geistfabrik import Suggestion

    # Pick one random note (deterministic by session seed)
    notes = vault.notes()
    if not notes:
        return []

    note = vault.random_notes(count=1)[0]
    content = vault.read(note)

    # Extract quotes
    quotes = extract_quotes(content)

    # If no quotes found, return empty (geist abstains)
    if not quotes:
        return []

    # Create suggestions from quotes
    suggestions = []
    for quote in quotes:
        # Clean up whitespace
        quote_clean = " ".join(quote.split())

        text = (
            f"From [[{note.link_text}]]: {quote_for_display(quote_clean)} "
            "What if you reflected on this again?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.link_text],
                geist_id="quote_harvester",
            )
        )

    # Sample 1-3 quotes to avoid overwhelming
    return vault.sample(suggestions, count=min(3, len(suggestions)))


def extract_quotes(content: str) -> list[str]:
    """Extract blockquotes from markdown content.

    Blockquotes are lines starting with ">", grouped together into multi-line
    blocks if consecutive.

    Args:
        content: Markdown content

    Returns:
        List of quote strings (multi-line quotes joined)
    """

    # Remove code blocks (those quotes are code examples, not actual quotes)
    content_no_code = strip_code(content)

    quotes = []

    # Match blockquote blocks (may span multiple lines)
    # Blockquote: lines starting with ">", grouped together
    lines = content_no_code.split("\n")
    current_quote: list[str] = []

    def end_block() -> None:
        quote = _quote_from_block(current_quote)
        if quote:
            quotes.append(quote)
        current_quote.clear()

    for line in lines:
        stripped = line.strip()

        # If line starts with ">", it's part of a quote
        if stripped.startswith(">"):
            # Remove every ">" marker of a nested quote ("> > reply")
            quote_text = re.sub(r"^(?:>\s*)+", "", stripped).strip()
            if quote_text:  # Skip empty quote lines
                current_quote.append(quote_text)
        elif current_quote:
            # End of quote block
            end_block()

    # Handle quote at end of file
    end_block()

    # Filter and deduplicate
    filtered_quotes = []
    seen = set()

    for quote in quotes:
        quote_clean = quote.strip()

        # Quality filtering
        if not is_valid_quote(quote_clean):
            continue

        # Truncate if too long (but keep it)
        if len(quote_clean) > 500:
            quote_clean = quote_clean[:497] + "..."

        # Deduplication
        quote_normalized = quote_clean.lower()
        if quote_normalized not in seen:
            filtered_quotes.append(unmask_code(quote_clean))
            seen.add(quote_normalized)

    return filtered_quotes


# Obsidian callout header: "[!warning]", "[!note]- Title", "[!tip]+ Title"
_CALLOUT = re.compile(r"^\[!([\w-]+)\][+-]?\s*")
# Callout types that hold a quotation; their body is harvested, the header
# line (type and optional title) is not.
_QUOTE_CALLOUTS = frozenset({"quote", "cite"})


def _quote_from_block(lines: list[str]) -> str:
    """Join one blockquote's lines; "" for a callout that is not a quotation.

    "> [!warning] Heads up" is an Obsidian callout - an admonition box, not
    something the author quoted - so warning/note/tip/... callouts are
    skipped. A [!quote] or [!cite] callout keeps its body.
    """
    if not lines:
        return ""
    callout = _CALLOUT.match(lines[0])
    if callout:
        if callout.group(1).lower() not in _QUOTE_CALLOUTS:
            return ""
        lines = lines[1:]
    return " ".join(lines)


def is_valid_quote(quote: str) -> bool:
    """Filter out false positives and low-quality quotes.

    Args:
        quote: Quote text

    Returns:
        True if valid quote, False otherwise
    """
    # Too short to be meaningful
    if len(quote) < 10:
        return False

    # Must contain at least some letters (not just punctuation)
    letter_count = sum(1 for c in quote if c.isalpha())
    if letter_count < 10:
        return False

    return True
