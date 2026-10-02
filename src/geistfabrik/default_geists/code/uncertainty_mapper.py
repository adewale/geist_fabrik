"""Uncertainty mapper geist - surfaces notes with heavy hedging.

A reflective lens over epistemic voice: hedge words ("maybe", "perhaps",
"I think", "sort of") mark claims you are not yet ready to commit to.
This geist finds a note where you hedge the most (per 100 words, among
notes long enough to have a habit) and asks what is holding you back.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion
from geistfabrik.voice_analysis import (
    count_hedges,
    split_sentences,
    strip_for_analysis,
    tokenize,
)

# A one-line "Maybe call Bob." is not a hedging habit: only notes with real
# prose (after stripping frontmatter, code and URLs) are considered.
MIN_SENTENCES = 5
MIN_WORDS = 80
# Hedges per 100 words needed to count as heavy hedging (about 0.3 hedges
# per sentence at a typical 15 words per sentence).
HEDGES_PER_100_WORDS = 2.0
# Sample among the most heavily hedged few, so the same note is not named
# every session.
TOP_CANDIDATES = 3


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes where you're hedging heavily.

    Ranks notes of at least MIN_SENTENCES sentences and MIN_WORDS words by
    hedges per 100 words and names one of the TOP_CANDIDATES heaviest.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion naming a heavily hedged note
    """
    hedgy_notes = []
    for note in vault.notes():
        text = strip_for_analysis(note.content)
        word_count = len(tokenize(text))
        if word_count < MIN_WORDS or len(split_sentences(text)) < MIN_SENTENCES:
            continue
        hedge_count = count_hedges(note.content)
        rate = hedge_count / word_count * 100.0
        if rate >= HEDGES_PER_100_WORDS:
            hedgy_notes.append((note, hedge_count, word_count, rate))

    if not hedgy_notes:
        return []

    hedgy_notes.sort(key=lambda x: (-x[3], x[0].path))
    note, hedge_count, word_count, _rate = vault.sample(hedgy_notes[:TOP_CANDIDATES], 1)[0]
    times = "time" if hedge_count == 1 else "times"

    return [
        Suggestion(
            text=(
                f"[[{note.link_text}]] hedges {hedge_count} {times} "
                f"in {word_count} words. What are you not ready to commit to?"
            ),
            notes=[note.link_text],
            geist_id="uncertainty_mapper",
        )
    ]
