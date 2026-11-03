"""Pattern Finder geist - identifies repeated phrases across unconnected notes.

Discovers 3-word phrases that recur in several notes that aren't linked to
each other, suggesting implicit recurring interests. (Its former second branch,
semantic clusters of unlinked notes, duplicated concept_cluster and was merged
into it.)
"""

import re
from collections import defaultdict
from collections.abc import Iterator
from typing import TYPE_CHECKING

from geistfabrik.lexical_candidacy import ENGLISH_FUNCTION_WORDS as STOPWORDS

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext
from geistfabrik.markdown_parser import (
    INLINE_CODE_PATTERN,
    markdown_prose_lines,
    parse_frontmatter,
)

# Whole-token stopwords. A phrase may not start or end with one (a single
# stopword inside, as in "theory of mind", is fine). Matching whole tokens
# matters: the old substring test rejected any phrase containing "other",
# "understand" or "together" while letting "for large vaults" through.
_WORD = re.compile(r"[a-z](?:[a-z'-]*[a-z])?")
# Punctuation that ends a run of words: a phrase never spans a sentence,
# clause, bracket, table cell or emphasis boundary.
_BREAK = re.compile(r"[.!?;:,()\[\]{}|<>\"=+*/\\]+")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
# The leading \b anchors each attempt at the start of a word: without it a
# long run of word characters with no "://" was retried from every offset
# (quadratic; a 200 KB unbroken line timed the geist out). A URL's scheme
# always starts a word, so the matches are unchanged.
_URL = re.compile(r"\b\w+://\S+")


def _phrases(content: str, *, body: str | None = None) -> Iterator[str]:
    """Yield the 3-word phrases of a note's prose.

    Frontmatter, fenced/indented code, inline code, headings (often template
    boilerplate such as "## Success Metrics"), table rows and URLs are not
    prose. Any token that is not a plain word (a number, "note.links",
    "list[link]", a list marker) ends the current run of words.
    """
    if body is None:
        body = parse_frontmatter(content)[1]
    for _, line in markdown_prose_lines(body):
        if _HEADING.match(line) or line.lstrip().startswith("|"):
            continue
        line = line.lower().replace("\u2019", "'")
        line = _URL.sub(" | ", INLINE_CODE_PATTERN.sub(" | ", line))
        for segment in _BREAK.split(line):
            run: list[str] = []
            for token in segment.split() + [""]:
                word = token.strip("'_~`\u2018\u201c\u201d")
                if word and _WORD.fullmatch(word):
                    run.append(word)
                    continue
                for i in range(len(run) - 2):
                    tri = run[i : i + 3]
                    if tri[0] in STOPWORDS or tri[2] in STOPWORDS:
                        continue
                    phrase = " ".join(tri)
                    if len(phrase) > 15:
                        yield phrase
                run = []


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find phrases repeated across unconnected notes.

    Returns:
        List of suggestions highlighting hidden patterns
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    if len(notes) < 15:
        return []

    graph = vault.resolved_graph()
    marks = [0] * len(graph.notes)

    # Look for repeated significant 3-word phrases
    phrase_to_notes: dict[str, list[int]] = defaultdict(list)

    # Every note is read: sampling the corpus here (Phase 3B) lost most
    # patterns on large vaults (tests/integration/test_phase3b_regression.py).
    for note in notes:
        # Count each phrase once per note so a note repeating itself is not
        # mistaken for several notes. (A dict, not a set: insertion order
        # keeps output independent of hash seeds.)
        note_phrases = dict.fromkeys(_phrases(note.content, body=note.body))
        for phrase in note_phrases:
            phrase_to_notes[phrase].append(graph.ids[note.path])

    # Find phrases that appear in multiple unlinked notes
    for generation, (phrase, phrase_notes) in enumerate(phrase_to_notes.items(), start=1):
        if len(phrase_notes) >= 3:
            unlinked_group = [
                graph.notes[i] for i in graph.isolated_members(phrase_notes, marks, generation)
            ]

            if len(unlinked_group) >= 3:
                sample = vault.sample(unlinked_group, count=3)
                note_names = ", ".join([f"[[{n.link_text}]]" for n in sample])

                text = (
                    f'The phrase "{phrase}" appears in multiple unconnected notes: {note_names}. '
                    f"Recurring theme you haven't explicitly connected?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[n.link_text for n in sample],
                        geist_id="pattern_finder",
                    )
                )

    return vault.sample(suggestions, count=2)
