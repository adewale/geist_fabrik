"""Link density analyser geist - finds notes with unusual link patterns.

Identifies notes that have too many or too few links relative to their content,
suggesting opportunities for better integration or focus.

Each branch states only what it measures:
- "too many links" counts the wikilinks written in the note (embeds and links
  back to the note itself, e.g. a "[[#Heading]]" table of contents, excluded);
- "needs more connections" uses the resolved link graph: outgoing links that
  reach another note in the vault, plus the notes that link back. A note full
  of unresolved links, or one that many notes link to, is not called sparse
  because of its raw link count.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext

# Per 100 words
DENSE_THRESHOLD = 5.0
SPARSE_THRESHOLD = 0.5
MIN_WORDS = 50
MIN_WORDS_SPARSE = 200
# A note with more backlinks than this is connected, whatever it links to.
MAX_BACKLINKS_SPARSE = 1


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _written_link_count(vault: "VaultContext", note: "Note") -> int:
    """Wikilinks in the text, excluding embeds and links to the note itself."""
    index = vault.link_index()
    return sum(
        1
        for link in note.links
        if not link.is_embed and index.resolve(link.target, note.path) != note.path
    )


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Analyse link density and suggest improvements.

    Returns:
        List of suggestions for link density improvements
    """
    from geistfabrik import Suggestion

    suggestions = []

    for note in vault.notes():
        word_count = int(vault.metadata(note).get("word_count", 0))
        if word_count < MIN_WORDS:
            continue  # Too short to analyse

        link_count = _written_link_count(vault, note)

        # Case 1: Too many links (> 5 per 100 words)
        if link_count * 100 / word_count > DENSE_THRESHOLD:
            text = (
                f"What if [[{note.link_text}]] has too many links? "
                f"With {link_count} links in {word_count} words, "
                f"it might be overwhelming. Consider focusing on key connections."
            )
            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text],
                    geist_id="link_density_analyser",
                )
            )
            continue

        if word_count <= MIN_WORDS_SPARSE:
            continue

        # Case 2: Too few connections (< 0.5 resolved outgoing links per 100
        # words, and at most one note linking back)
        outgoing = len(vault.outgoing_links(note))
        backlinks = len(vault.backlinks(note))
        if outgoing * 100 / word_count < SPARSE_THRESHOLD and backlinks <= MAX_BACKLINKS_SPARSE:
            text = (
                f"What if [[{note.link_text}]] needs more connections? "
                f"Its {word_count} words link to {_plural(outgoing, 'other note')} "
                f"in your vault, and {_plural(backlinks, 'note')} "
                f"{'links' if backlinks == 1 else 'link'} back to it."
            )
            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text],
                    geist_id="link_density_analyser",
                )
            )

    return vault.sample(suggestions, count=3)
