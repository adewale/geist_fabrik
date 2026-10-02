"""Surprisal geist - surfaces informationally unexpected notes.

A reflective lens over semantic neighbourhoods: a note with high
surprisal sits far from the centroid of its own nearest neighbours —
it says something different from everything around it. Such a note is
either a seed of new thinking or a stray thought.

Absorbed the retired unexpected_neighbour Tracery geist, which named the
single top-surprisal note every session; its closing questions live on in
CLOSERS.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion
from geistfabrik.voice_analysis import strip_for_analysis, tokenize

# Near-empty notes (a link, an embed, a frontmatter block) embed poorly and
# dominate the top surprisal ranks without saying anything different, so
# only notes with at least this many prose words are considered.
MIN_BODY_WORDS = 50
# Sample among the most surprising few rather than always naming the top one.
TOP_CANDIDATES = 5
# One closing question is sampled per suggestion (the last two come from the
# retired unexpected_neighbour geist).
CLOSERS = (
    "Is it a seed of new thinking, or a stray thought?",
    "What does it know that the others don't?",
    "What's it doing in your vault?",
)


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find a note that least fits its semantic neighbourhood.

    Uses the session-cached, vectorised VaultContext.surprisal_scores()
    (one blocked matrix pass shared across all geists), never a per-note
    similarity loop. Notes under MIN_BODY_WORDS prose words are skipped;
    one of the TOP_CANDIDATES most surprising remaining notes is sampled,
    and one of CLOSERS ends the suggestion.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion naming a surprising note
    """
    scores = vault.surprisal_scores()
    if not scores:
        return []  # Tiny vault — surprisal is meaningless

    candidates = []
    for path in sorted(scores, key=lambda p: (-scores[p], p)):
        candidate = vault.get_note(path)
        if candidate is None:
            continue
        if len(tokenize(strip_for_analysis(candidate.content))) < MIN_BODY_WORDS:
            continue
        candidates.append(candidate)
        if len(candidates) == TOP_CANDIDATES:
            break

    if not candidates:
        return []
    note = vault.sample(candidates, 1)[0]

    neighbours = vault.neighbours(note, count=3)
    if not neighbours:
        return []

    neighbour_titles = ", ".join(f"[[{n.link_text}]]" for n in neighbours)
    closer = vault.sample(CLOSERS, 1)[0]

    return [
        Suggestion(
            text=(
                f"[[{note.link_text}]] doesn't quite fit. "
                f"Its neighbours are {neighbour_titles}, but it says something different. "
                f"{closer}"
            ),
            notes=[note.link_text] + [n.link_text for n in neighbours],
            geist_id="surprisal",
        )
    ]
