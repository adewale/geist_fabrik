"""Question Harvester geist - extracts questions from random notes.

Inspired by:
- https://x.com/pomeranian99/status/1497969902581272577
- https://uxdesign.cc/the-power-of-seeing-only-the-questions-in-a-piece-of-writing-8f486d2c6d7d

The power of seeing only the questions: when you strip away everything except
the questions from a piece of writing, you reveal the shape of curiosity and
the implicit structure of inquiry.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Extract questions from a randomly selected note.

    Returns:
        List of 1-3 suggestions containing questions found (or empty if none)
    """
    from geistfabrik import Suggestion

    # Pick one random note (deterministic by session seed)
    notes = vault.notes()
    if not notes:
        return []

    note = vault.random_notes(k=1)[0]
    content = vault.read(note)

    # Extract questions
    questions = extract_questions(content)

    # If no questions found, return empty (geist abstains)
    if not questions:
        return []

    # Create suggestions from questions
    suggestions = []
    for question in questions:
        # Clean up whitespace
        question_clean = " ".join(question.split())

        text = (
            f"From [[{note.title}]]: \"{question_clean}\" "
            f"What if you revisited this question now?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.title],
                geist_id="question_harvester",
            )
        )

    # Sample 1-3 questions to avoid overwhelming
    return vault.sample(suggestions, k=min(3, len(suggestions)))


def extract_questions(content: str) -> list[str]:
    """Extract questions from markdown content.

    Uses multiple strategies:
    1. Remove code blocks (avoid false positives)
    2. Find sentence-ending questions
    3. Find list item questions
    4. Filter and deduplicate

    Args:
        content: Markdown content

    Returns:
        List of question strings (deduplicated, filtered)
    """
    # Strategy 1: Remove code blocks to avoid false positives
    content_no_code = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    content_no_code = re.sub(r'`[^`]+`', '', content_no_code)

    questions = []

    # Strategy 2: Sentence-ending questions
    # Match text ending with '?' (handles multi-line)
    sentence_questions = re.findall(
        r'([^.!?\n][^.!?]*\?)',
        content_no_code,
        re.MULTILINE
    )

    # Strategy 3: List item questions
    # Match Markdown list items ending with '?'
    list_questions = re.findall(
        r'^\s*[-*+]\s+(.+\?)\s*$',
        content_no_code,
        re.MULTILINE
    )

    # Combine and deduplicate
    all_questions = sentence_questions + list_questions
    seen = set()

    for q in all_questions:
        q_clean = q.strip()
        q_normalized = q_clean.lower()

        # Strategy 4: Quality filtering
        if not is_valid_question(q_clean):
            continue

        # Strategy 5: Deduplication (case-insensitive)
        if q_normalized not in seen:
            questions.append(q_clean)
            seen.add(q_normalized)

    return questions


def is_valid_question(q: str) -> bool:
    """Filter out false positives and low-quality matches.

    Args:
        q: Question string

    Returns:
        True if valid question, False otherwise
    """
    # Too short: likely false positive
    if len(q) < 10:
        return False

    # Too long: likely parsing error
    if len(q) > 500:
        return False

    # Must contain at least one letter
    if not re.search(r'[a-zA-Z]', q):
        return False

    # Common false positives to exclude
    false_positive_patterns = [
        r'^#+\s*\?',  # Markdown headings that are just "?"
        r'^\s*\?\s*$',  # Just a question mark
    ]

    for pattern in false_positive_patterns:
        if re.match(pattern, q):
            return False

    return True
