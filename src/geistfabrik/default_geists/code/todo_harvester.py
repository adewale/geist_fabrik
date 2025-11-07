"""TODO Harvester geist - extracts TODO markers from random notes.

Surfaces inline TODO markers (TODO:, FIXME:, HACK:, NOTE:, XXX:) scattered
through notes. Unlike task_archaeology (which finds checkbox tasks), this
geist focuses on prose-style TODO markers that represent forgotten intentions
and deferred work.

Core insight: Personal knowledge bases accumulate TODO markers representing
intentions we meant to pursue but forgot about.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Extract TODO markers from a randomly selected note.

    Returns:
        List of 1-3 suggestions containing TODOs found (or empty if none)
    """
    from geistfabrik import Suggestion

    # Pick one random note (deterministic by session seed)
    notes = vault.notes()
    if not notes:
        return []

    note = vault.random_notes(k=1)[0]
    content = vault.read(note)

    # Extract TODOs
    todos = extract_todos(content)

    # If no TODOs found, return empty (geist abstains)
    if not todos:
        return []

    # Create suggestions from TODOs
    suggestions = []
    for todo in todos:
        # Clean up whitespace
        todo_clean = " ".join(todo.split())

        text = (
            f"From [[{note.obsidian_link}]]: \"{todo_clean}\" "
            f"What if you tackled this now?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.obsidian_link],
                geist_id="todo_harvester",
            )
        )

    # Sample 1-3 TODOs to avoid overwhelming
    return vault.sample(suggestions, k=min(3, len(suggestions)))


def extract_todos(content: str) -> list[str]:
    """Extract TODO markers from content.

    Finds TODO:, FIXME:, HACK:, NOTE:, XXX: markers with their associated text.

    Args:
        content: Markdown content

    Returns:
        List of TODO strings (formatted as "MARKER: text")
    """
    # Remove code blocks (those TODOs are for code, not notes)
    content_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    content_no_code = re.sub(r'`[^`]+`', '', content_no_code)

    todos = []

    # Match TODO markers with their text
    # Captures: TODO: text until end of line or period
    pattern = r'(TODO|FIXME|HACK|NOTE|XXX):\s*([^.\n]+(?:\.[^\n]+)?)'
    matches = re.findall(pattern, content_no_code, re.IGNORECASE)

    seen = set()
    for marker, text in matches:
        todo_text = text.strip()

        # Quality filtering
        if not is_valid_todo(todo_text):
            continue

        # Deduplication
        todo_normalized = todo_text.lower()
        if todo_normalized not in seen:
            # Format: "TODO: investigate this"
            formatted = f"{marker.upper()}: {todo_text}"
            todos.append(formatted)
            seen.add(todo_normalized)

    return todos


def is_valid_todo(todo_text: str) -> bool:
    """Filter out false positives and low-quality TODOs.

    Args:
        todo_text: TODO text (without marker)

    Returns:
        True if valid TODO, False otherwise
    """
    # Too short: likely placeholder
    if len(todo_text) < 5:
        return False

    # Too long: likely parsing error
    if len(todo_text) > 300:
        return False

    # Skip common placeholders
    placeholders = ['add content', 'write this', 'fill in', 'update']
    if todo_text.lower() in placeholders:
        return False

    # Must contain at least one letter
    if not re.search(r'[a-zA-Z]', todo_text):
        return False

    return True
