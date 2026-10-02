"""Stub expander geist - finds short notes that might benefit from expansion.

Identifies stub notes (short notes that other notes link to) that could be
developed into more substantial notes. A backlink is what makes a stub worth
expanding: other notes already lean on it. Outgoing links alone don't count
(a daily note embedding a template, or a frontmatter-only note listing
unresolved links, is not a stub anyone depends on).

Two kinds of note qualify:
- a stub: under MAX_STUB_WORDS body words and at least one backlink;
- a well-linked stub: under MAX_WELL_LINKED_WORDS body words and at least
  MIN_WELL_LINKED_BACKLINKS backlinks. So many notes lean on it that even a
  note of a paragraph or two is thin for the weight it carries.

hub_explorer only names hubs of at least MAX_WELL_LINKED_WORDS words, so it
never asks to split a note this geist asks to expand.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

# Fewer body words than this (YAML frontmatter excluded) makes a note a stub.
MAX_STUB_WORDS = 50
# A note this many other notes link to is well linked ...
MIN_WELL_LINKED_BACKLINKS = 5
# ... and is still thin under this many body words.
MAX_WELL_LINKED_WORDS = 100
# At most this many stubs per session.
CAP = 3


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find stub notes worth expanding.

    Candidates are notes under MAX_STUB_WORDS body words with at least one
    backlink from another user note, and notes under MAX_WELL_LINKED_WORDS
    words with at least MIN_WELL_LINKED_BACKLINKS backlinks. The most
    linked-to stubs come first; ties are broken by the session's seeded
    shuffle.

    Returns:
        List of suggestions for expanding stubs
    """
    from geistfabrik import Suggestion

    candidates = []
    for note in vault.notes():
        word_count = vault.metadata(note).get("word_count", 0)
        backlink_count = len(vault.backlinks(note))
        is_stub = word_count < MAX_STUB_WORDS and backlink_count >= 1
        is_well_linked_stub = (
            word_count < MAX_WELL_LINKED_WORDS and backlink_count >= MIN_WELL_LINKED_BACKLINKS
        )
        if is_stub or is_well_linked_stub:
            candidates.append((note, word_count, backlink_count))

    # Seeded shuffle, then a stable sort: rank by backlinks, random among ties.
    ranked = sorted(vault.sample(candidates, len(candidates)), key=lambda c: -c[2])

    suggestions = []
    for note, word_count, backlink_count in ranked[:CAP]:
        linkers = "1 note links" if backlink_count == 1 else f"{backlink_count} notes link"
        word_label = "word" if word_count == 1 else "words"
        closer = (
            "Is its brevity intentional, a hinge that works because it is short, "
            "or a placeholder waiting to grow?"
            if backlink_count >= MIN_WELL_LINKED_BACKLINKS
            else "Is it a seed waiting to grow, or finished as it is?"
        )
        suggestions.append(
            Suggestion(
                text=(
                    f"[[{note.link_text}]] has only {word_count} {word_label}, "
                    f"but {linkers} to it. {closer}"
                ),
                notes=[note.link_text],
                geist_id="stub_expander",
            )
        )

    return suggestions
