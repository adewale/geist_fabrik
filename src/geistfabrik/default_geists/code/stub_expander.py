"""Stub expander geist - finds short notes that might benefit from expansion.

Identifies stub notes (short notes that other notes link to) that could be
developed into more substantial notes. A backlink is what makes a stub worth
expanding: other notes already lean on it. Outgoing links alone don't count
(a daily note embedding a template, or a frontmatter-only note listing
unresolved links, is not a stub anyone depends on).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

# Fewer body words than this (YAML frontmatter excluded) makes a note a stub.
MAX_STUB_WORDS = 50
# At most this many stubs per session.
CAP = 3


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find stub notes worth expanding.

    Candidates are notes under MAX_STUB_WORDS body words with at least one
    backlink from another user note. The most linked-to stubs come first;
    ties are broken by the session's seeded shuffle.

    Returns:
        List of suggestions for expanding stubs
    """
    from geistfabrik import Suggestion

    candidates = []
    for note in vault.notes():
        word_count = vault.metadata(note).get("word_count", 0)
        backlink_count = len(vault.backlinks(note))
        if word_count < MAX_STUB_WORDS and backlink_count >= 1:
            candidates.append((note, word_count, backlink_count))

    # Seeded shuffle, then a stable sort: rank by backlinks, random among ties.
    ranked = sorted(vault.sample(candidates, len(candidates)), key=lambda c: -c[2])

    suggestions = []
    for note, word_count, backlink_count in ranked[:CAP]:
        linkers = "1 note links" if backlink_count == 1 else f"{backlink_count} notes link"
        word_label = "word" if word_count == 1 else "words"
        suggestions.append(
            Suggestion(
                text=(
                    f"What if you expanded [[{note.link_text}]]? "
                    f"It's only {word_count} {word_label}, but {linkers} to it. "
                    f"This stub might be worth developing."
                ),
                notes=[note.link_text],
                geist_id="stub_expander",
            )
        )

    return suggestions
