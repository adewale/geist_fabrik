"""Question Harvester geist - extracts questions from notes, preferring question-dense ones.

Inspired by:
- https://x.com/pomeranian99/status/1497969902581272577
- https://uxdesign.cc/the-power-of-seeing-only-the-questions-in-a-piece-of-writing-8f486d2c6d7d

The power of seeing only the questions: when you strip away everything except
the questions from a piece of writing, you reveal the shape of curiosity and
the implicit structure of inquiry.

Absorbed the retired questioning_mind Tracery geist: question-dense notes are
preferred, and one full of questions is read back with "Which one keeps you up
at night?".
"""

import re
from typing import TYPE_CHECKING

from geistfabrik.content_extraction import (
    quote_for_display,
    sentence_questions,
    strip_code,
    unmask_code,
)

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


# A note with more than this many "?" per 100 words is question-dense (the
# same threshold as the questioning_notes vault function).
QUESTION_DENSE = 1.0
# Question-dense notes tried per session before falling back to a random note.
MAX_NOTES_TRIED = 10
# A question-dense note with at least this many short questions is read back
# as one gathered suggestion instead of one suggestion per question.
GATHER_MIN = 3
# Longest question (characters) shown in a gathered suggestion.
GATHER_MAX_LEN = 120


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Extract questions from a note, preferring question-dense notes.

    Tries up to MAX_NOTES_TRIED sampled question-dense notes (more than
    QUESTION_DENSE "?" per 100 words) and harvests the first with questions;
    with none, falls back to one random note. A question-dense note with at
    least GATHER_MIN short questions yields ONE suggestion reading three of
    them back ("Which one keeps you up at night?", absorbed from the retired
    questioning_mind geist); otherwise each question is its own suggestion.

    Returns:
        List of 1-3 suggestions containing questions found (or empty if none)
    """
    from geistfabrik import Suggestion

    notes = vault.notes()
    if not notes:
        return []

    dense = [n for n in notes if vault.voice(n).question_density > QUESTION_DENSE]
    note = notes[0]
    questions: list[str] = []
    for note in vault.sample(dense, MAX_NOTES_TRIED):
        questions = extract_questions(vault.read(note))
        if questions:
            break
    from_dense = bool(questions)
    if not questions:
        # Pick one random note (deterministic by session seed)
        note = vault.random_notes(count=1)[0]
        questions = extract_questions(vault.read(note))

    # If no questions found, return empty (geist abstains)
    if not questions:
        return []

    # Clean up whitespace
    cleaned = [" ".join(question.split()) for question in questions]

    short = [q for q in cleaned if len(q) <= GATHER_MAX_LEN]
    if from_dense and len(short) >= GATHER_MIN:
        quoted = " ".join(quote_for_display(q) for q in vault.sample(short, GATHER_MIN))
        return [
            Suggestion(
                text=(
                    f"[[{note.link_text}]] is full of questions: {quoted} "
                    "Which one keeps you up at night?"
                ),
                notes=[note.link_text],
                geist_id="question_harvester",
            )
        ]

    # Create suggestions from questions
    suggestions = [
        Suggestion(
            text=(
                f"From [[{note.link_text}]]: {quote_for_display(question)} "
                f"What if you revisited this question now?"
            ),
            notes=[note.link_text],
            geist_id="question_harvester",
        )
        for question in cleaned
    ]

    # Sample 1-3 questions to avoid overwhelming
    return vault.sample(suggestions, count=min(3, len(suggestions)))


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
    content_no_code = strip_code(content)

    questions = []

    # Strategy 2: Sentence-ending questions
    # Match text ending with '?'. A question may wrap across lines of one
    # paragraph, but never across a blank line, out of a heading, or across
    # list items: those lines end without punctuation, so "# Heading" followed
    # by "Why?" would otherwise be harvested as one question.
    # (sentence_questions() runs in linear time; the equivalent regex was
    # quadratic on long runs without terminal punctuation.)
    questions_in_sentences = [
        question
        for segment in _segments(content_no_code)
        for question in sentence_questions(segment)
    ]

    # Strategy 3: List item questions
    # Match Markdown list items ending with '?'
    list_questions = re.findall(r"^\s*[-*+]\s+(.+\?)\s*$", content_no_code, re.MULTILINE)

    # Combine and deduplicate
    all_questions = questions_in_sentences + list_questions
    seen = set()

    for q in all_questions:
        q_clean = _clean_question(q)
        q_normalized = q_clean.lower()

        # Strategy 4: Quality filtering
        if not is_valid_question(q_clean):
            continue

        # Strategy 5: Deduplication (case-insensitive)
        if q_normalized not in seen:
            questions.append(unmask_code(q_clean))
            seen.add(q_normalized)

    return questions


# A bold label before the question: "**Question**: ", "**Q9:** "
_BOLD_LABEL = re.compile(r"^\*\*[^*\n]{1,40}?(?:\*\*\s*:|:\*\*)\s*")


def _clean_question(question: str) -> str:
    """Strip formatting debris the sentence regex keeps before the "?".

    Removes a bold label ("**Q9**: Does...?" -> "Does...?"), every "**"
    (an emphasis span the question cut in half leaves "**Who are...?"), and
    an unbalanced opening double quote together with any lead-in before it
    ('He asked "why not?' -> 'why not?'), which would otherwise double up
    inside the suggestion's own quotation marks.
    """
    q = _BOLD_LABEL.sub("", question.strip())
    q = q.replace("**", "")
    if q.count('"') % 2 == 1:
        q = q[q.rfind('"') + 1 :]
    if q.count("\u201c") > q.count("\u201d"):
        q = q[q.rfind("\u201c") + 1 :]
    return q.strip()


def _segments(content: str) -> list[str]:
    """Split content into runs of lines a single sentence may span.

    A blank line ends a run; a heading or list-item line starts a new one
    (and a heading also ends its own run). Heading and list markers are
    dropped so "- Why?" and "## Why?" harvest as "Why?". Blockquote markers
    (and an Obsidian callout's "[!type]") are dropped too. Table rows are not
    prose: they end a run and are skipped, so a cell ending in "?" is not
    harvested together with the rest of its row.
    """
    segments: list[str] = []
    current: list[str] = []
    for line in content.split("\n"):
        line = re.sub(r"^\s*(?:>\s*)+(?:\[![\w-]+\][+-]?\s*)?", "", line)
        if line.lstrip().startswith("|"):
            if current:
                segments.append("\n".join(current))
            current = []
            continue
        heading = re.match(r"\s*#{1,6}\s+", line)
        item = re.match(r"\s*[-*+]\s+", line)
        if not line.strip() or heading or item:
            if current:
                segments.append("\n".join(current))
            current = []
        if heading:
            segments.append(line[heading.end() :])
        elif item:
            current.append(line[item.end() :])
        elif line.strip():
            current.append(line)
    if current:
        segments.append("\n".join(current))
    return segments


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
    if not re.search(r"[a-zA-Z]", q):
        return False

    # Common false positives to exclude
    false_positive_patterns = [
        r"^#+\s*\?",  # Markdown headings that are just "?"
        r"^\s*\?\s*$",  # Just a question mark
    ]

    for pattern in false_positive_patterns:
        if re.match(pattern, q):
            return False

    return True
