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

Each density is reported against the median of the same measure across the
notes this geist analyses (MIN_WORDS words or more), and a note on the
wrong side of that median is never flagged: in a vault where most notes
are link-heavy, a note at 6 links per 100 words is not the one with "too
many", and the text never pairs "too many" with a density below the median.

Notes with no links in or out at all are orphan_connector's: this geist
only looks at notes with at least one link. When three or more sparse notes
are also isolated (at most one resolved link in either direction), three
of them are grouped into one "what do these have in common?" suggestion.
"""

from statistics import median
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
# A sparse note with at most this many resolved links (in + out) is isolated.
MAX_ISOLATED_LINKS = 1
# Notes in an "isolated" group.
GROUP_SIZE = 3
CAP = 3


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

    orphans = {note.path for note in vault.orphans()}
    # (note, word_count, written links, resolved outgoing, backlinks)
    analysed = []
    for note in vault.notes():
        word_count = int(vault.metadata(note).get("word_count", 0))
        if word_count < MIN_WORDS:
            continue  # Too short to analyse
        analysed.append(
            (
                note,
                word_count,
                _written_link_count(vault, note),
                len(vault.outgoing_links(note)),
                len(vault.backlinks(note)),
            )
        )
    if not analysed:
        return []

    median_written = median(written * 100 / words for _, words, written, _, _ in analysed)
    median_resolved = median(out * 100 / words for _, words, _, out, _ in analysed)

    individual = []
    isolated = []
    for note, word_count, written, outgoing, backlinks in analysed:
        if note.path in orphans:
            continue  # No links in or out: orphan_connector's note

        # Case 1: Too many links (> 5 per 100 words, and not below the median)
        density = written * 100 / word_count
        if density > DENSE_THRESHOLD and density >= median_written:
            text = (
                f"[[{note.link_text}]] has {written} links in {word_count} words "
                f"({density:.1f} per 100 words; the median among your notes of "
                f"{MIN_WORDS}+ words is {median_written:.1f}). Is it a hub spreading "
                f"through your vault, or is the density hiding which links matter?"
            )
            individual.append(
                Suggestion(text=text, notes=[note.link_text], geist_id="link_density_analyser")
            )
            continue

        if word_count <= MIN_WORDS_SPARSE:
            continue

        # Case 2: Too few connections (< 0.5 resolved outgoing links per 100
        # words and not above the median, and at most one note linking back)
        density = outgoing * 100 / word_count
        if (
            density < SPARSE_THRESHOLD
            and density <= median_resolved
            and backlinks <= MAX_BACKLINKS_SPARSE
        ):
            if outgoing + backlinks <= MAX_ISOLATED_LINKS:
                isolated.append((note, word_count))
            text = (
                f"What if [[{note.link_text}]] needs more connections? "
                f"Its {word_count} words link to {_plural(outgoing, 'other note')} "
                f"in your vault ({density:.1f} per 100 words; the median among your "
                f"notes of {MIN_WORDS}+ words is {median_resolved:.1f}), and "
                f"{_plural(backlinks, 'note')} {'links' if backlinks == 1 else 'link'} "
                f"back to it."
            )
            individual.append(
                Suggestion(text=text, notes=[note.link_text], geist_id="link_density_analyser")
            )

    suggestions = []
    grouped: set[str] = set()
    if len(isolated) >= GROUP_SIZE:
        group = vault.sample(isolated, GROUP_SIZE)
        grouped = {note.link_text for note, _ in group}
        suggestions.append(
            Suggestion(
                text=(
                    "What do these have in common?\n"
                    + "\n".join(f"- [[{note.link_text}]] ({words} words)" for note, words in group)
                    + f"\n\nEach is over {MIN_WORDS_SPARSE} words and links to or from at "
                    + "most one other note in your vault. What pattern does this reveal?"
                ),
                notes=[note.link_text for note, _ in group],
                geist_id="link_density_analyser",
            )
        )

    rest = [s for s in individual if s.notes[0] not in grouped]
    return suggestions + vault.sample(rest, CAP - len(suggestions))
