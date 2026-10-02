"""Sentence variance geist - surfaces notes with choppy sentence structure.

A reflective lens over rhythm: a note whose sentence lengths swing
between short bursts and long stretches often records thinking-in-
progress — working something out on the page rather than presenting a
finished thought. This geist finds the statistical outliers.
"""

import re
from statistics import pstdev
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.models import Note
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion
from geistfabrik.voice_analysis import strip_for_analysis, tokenize

# Sentence boundaries: terminal punctuation, blank lines, and the start of a
# list item (so a tight bullet list is many short sentences, not one long
# one). Single newlines inside hard-wrapped prose do not split.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n{2,}|\n(?=[ \t]*(?:[-*+]|\d+\.)\s)")
# Fewer sentences than this gives no meaningful spread.
MIN_SENTENCES = 10
# The vault needs at least this many candidate notes for the statistics.
MIN_CANDIDATES = 10


def sentence_lengths(content: str) -> list[int]:
    """Word counts of a note's prose sentences.

    Frontmatter, code and URLs are stripped; markdown table rows and
    headings are dropped (a table is not a sentence); list items are
    sentences of their own.
    """
    prose = "\n".join(
        line
        for line in strip_for_analysis(content).splitlines()
        if not line.lstrip().startswith(("|", "#"))
    )
    lengths = [len(tokenize(part)) for part in _SENTENCE_SPLIT_RE.split(prose)]
    return [n for n in lengths if n > 0]


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find a note with unusually choppy sentence structure.

    Measures each note's relative spread of sentence lengths (coefficient of
    variation: standard deviation / mean, so long-sentence notes are not
    favoured), compares it against the vault-wide distribution, and samples
    one of the outliers (> mean + 2 std). Requires at least MIN_CANDIDATES
    notes with MIN_SENTENCES sentences for the statistics to mean anything.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion naming a choppy note
    """
    note_spreads: list[tuple[Note, float]] = []

    for note in vault.notes():
        lengths = sentence_lengths(note.content)
        if len(lengths) < MIN_SENTENCES:
            continue
        mean_len = sum(lengths) / len(lengths)
        note_spreads.append((note, pstdev(lengths) / mean_len))

    if len(note_spreads) < MIN_CANDIDATES:
        return []

    # Find statistical outliers
    values = [v for _, v in note_spreads]
    mean_cv = sum(values) / len(values)
    std_cv = pstdev(values)

    outliers = [n for n, v in note_spreads if v > mean_cv + 2 * std_cv]
    if not outliers:
        return []

    note = vault.sample(outliers, 1)[0]

    return [
        Suggestion(
            text=(
                f"[[{note.link_text}]] has unusually choppy sentences — "
                f"short bursts mixed with long stretches. "
                f"Were you working something out when you wrote this?"
            ),
            notes=[note.link_text],
            geist_id="sentence_variance",
        )
    ]
