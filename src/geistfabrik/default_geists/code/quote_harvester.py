"""Quote Harvester geist - extracts blockquotes from random notes.

Surfaces blockquote content (markdown ">") from notes. Blockquotes represent:
- External quotes from books, articles, people
- Passages worth preserving
- Reference material
- Ideas that resonated enough to capture

Core insight: Surfacing quotes randomly reveals what you valued at different
times—a temporal map of intellectual influences.
"""

from typing import TYPE_CHECKING

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

    note = vault.random_notes(k=1)[0]
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
            f"From [[{note.title}]]: \"{quote_clean}\" "
            f"What if you reflected on this again?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.title],
                geist_id="quote_harvester",
            )
        )

    # Sample 1-3 quotes to avoid overwhelming
    return vault.sample(suggestions, k=min(3, len(suggestions)))


def extract_quotes(content: str) -> list[str]:
    """Extract blockquotes from markdown content.

    Blockquotes are lines starting with ">", grouped together into multi-line
    blocks if consecutive.

    Args:
        content: Markdown content

    Returns:
        List of quote strings (multi-line quotes joined)
    """
    quotes = []

    # Match blockquote blocks (may span multiple lines)
    # Blockquote: lines starting with ">", grouped together
    lines = content.split('\n')
    current_quote = []

    for line in lines:
        stripped = line.strip()

        # If line starts with ">", it's part of a quote
        if stripped.startswith('>'):
            # Remove the ">" prefix and leading whitespace
            quote_text = stripped[1:].strip()
            if quote_text:  # Skip empty quote lines
                current_quote.append(quote_text)
        else:
            # End of quote block
            if current_quote:
                # Join multi-line quotes
                full_quote = ' '.join(current_quote)
                quotes.append(full_quote)
                current_quote = []

    # Handle quote at end of file
    if current_quote:
        full_quote = ' '.join(current_quote)
        quotes.append(full_quote)

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
            filtered_quotes.append(quote_clean)
            seen.add(quote_normalized)

    return filtered_quotes


def is_valid_quote(quote: str) -> bool:
    """Filter out false positives and low-quality quotes.

    Args:
        quote: Quote text

    Returns:
        True if valid quote, False otherwise
    """
    # Too short to be meaningful
    if len(quote) < 20:
        return False

    # Must contain at least some letters (not just punctuation)
    letter_count = sum(1 for c in quote if c.isalpha())
    if letter_count < 10:
        return False

    return True
