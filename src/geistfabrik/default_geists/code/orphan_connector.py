"""Orphan connector geist - asks where an unlinked note belongs.

An orphan is a note with no links in or out (VaultContext.orphans(): no
outgoing link other than to itself or a geist journal note, and no backlink).
Each session names:
- one long orphan, if any has more than MIN_LONG_WORDS body words: a long
  note with no links in or out may be several notes in one, so it asks
  "split it, or link it?";
- one of the RECENT_POOL most recently modified orphans, sampled, so the
  newest orphan is not named every session.

Each suggestion names the orphan's nearest notes by meaning (up to
NEIGHBOURS) as places it might link to. No orphan is the subject of two
suggestions.

link_density_analyser covers notes with at least one link; this geist covers
the notes with none.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext

# An orphan with more body words than this gets "split it, or link it?".
MIN_LONG_WORDS = 1500
# The general suggestion samples among this many most recently modified orphans.
RECENT_POOL = 10
# Nearest notes by meaning named as link candidates.
NEIGHBOURS = 2

QUESTIONS = (
    "Where does it fit in your thinking?",
    "What question does it answer?",
    "What would connect it to your other work?",
)


def _nearest(vault: "VaultContext", orphan: "Note") -> tuple[str, list[str]]:
    """The orphan's nearest notes by meaning, as a phrase and as link texts.

    ("[[A]] or [[B]], the notes closest to it in meaning", ["A", "B"]), or
    ("", []) when it has no neighbours (e.g. no embedding).
    """
    link_texts = [n.link_text for n in vault.neighbours(orphan, NEIGHBOURS)]
    if not link_texts:
        return "", []
    which = "the note" if len(link_texts) == 1 else "the notes"
    links = " or ".join(f"[[{t}]]" for t in link_texts)
    return f"{links}, {which} closest to it in meaning", link_texts


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Suggest where orphaned notes might connect.

    Returns:
        Up to two suggestions: a long orphan (if any) and a recent orphan
    """
    from geistfabrik import Suggestion

    orphans = vault.orphans()  # most recently modified first
    suggestions = []

    long_orphans = [o for o in orphans if vault.metadata(o).get("word_count", 0) > MIN_LONG_WORDS]
    named: set[str] = set()
    for orphan in vault.sample(long_orphans, 1):
        named.add(orphan.path)
        word_count = vault.metadata(orphan).get("word_count", 0)
        candidates, link_texts = _nearest(vault, orphan)
        target = f"link it to {candidates}" if candidates else "link it into the rest of your vault"
        suggestions.append(
            Suggestion(
                text=(
                    f"[[{orphan.link_text}]] runs to {word_count} words with no links "
                    f"in or out. Could you split it into smaller notes, or {target}?"
                ),
                notes=[orphan.link_text, *link_texts],
                geist_id="orphan_connector",
            )
        )

    recent = [o for o in orphans[:RECENT_POOL] if o.path not in named]
    for orphan in vault.sample(recent, 1):
        question = vault.sample(QUESTIONS, 1)[0]
        candidates, link_texts = _nearest(vault, orphan)
        tail = f" Could it link to {candidates}?" if candidates else ""
        suggestions.append(
            Suggestion(
                text=f"[[{orphan.link_text}]] has no links in or out. {question}{tail}",
                notes=[orphan.link_text, *link_texts],
                geist_id="orphan_connector",
            )
        )

    return suggestions
