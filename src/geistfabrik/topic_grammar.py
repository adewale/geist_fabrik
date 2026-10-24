"""Local contextual grammar for statistically proposed topic labels.

This is candidate eligibility, not a claim about the author's meaning. Authored
heading/link priors and isolated short-note labels remain independently eligible.
The packaged English lexicon requires no downloaded NLTK corpus or external model.
"""

import hashlib
import importlib.resources
import re
import unicodedata
from importlib.metadata import version
from typing import cast

from textblob._text import find_tags  # type: ignore[import-untyped]
from textblob.en import lexicon, tokenize  # type: ignore[import-untyped]

WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
# Bare VB is ambiguous with subjects such as "Use cases". Finite inflections
# and personal/relative clauses provide stronger evidence than that base form.
_CLAUSE = frozenset({"VBD", "VBP", "VBZ", "MD", "PRP", "PRP$", "WP", "WP$", "WRB"})
_Token = tuple[int, int, str, str]


def _words(text: str) -> list[str]:
    return [unicodedata.normalize("NFC", word).casefold() for word in WORD.findall(text)]


def grammar_identity() -> str:
    """Version the actual packaged grammar code and data used by the topic cache."""
    digest = hashlib.sha256(version("textblob").encode())
    root = importlib.resources.files("textblob")
    for path in (
        "_text.py",
        "en/__init__.py",
        "en/en-lexicon.txt",
        "en/en-context.txt",
        "en/en-morphology.txt",
        "en/en-entities.txt",
    ):
        digest.update(root.joinpath(path).read_bytes())
    return digest.hexdigest()


def _tag_block(block: str) -> list[list[tuple[str, str]]]:
    # TextBlob's convenience parser does not forward these packaged rules.
    # Use the pinned Pattern implementation explicitly, without NLTK corpora.
    return [
        cast(
            list[tuple[str, str]],
            find_tags(
                sentence.split(),
                lexicon=lexicon,
                morphology=lexicon.morphology,
                context=lexicon.context,
                entities=lexicon.entities,
                language="en",
            ),
        )
        for sentence in tokenize(block)
    ]


class CandidateGrammar:
    """Keep uncertain alignments; never borrow a later occurrence for a token."""

    def __init__(self, prose: str, boundaries: tuple[int, ...]) -> None:
        self.prose = prose
        self.boundaries = boundaries
        self.words = _words(prose)
        self.tokens: list[_Token] | None = None

    def _tokens(self) -> list[_Token]:
        if self.tokens is not None:
            return self.tokens
        result: list[_Token] = []
        edges = sorted({0, len(self.prose), *self.boundaries})
        for start, end in zip(edges, edges[1:]):
            block = self.prose[start:end]
            cursor = 0
            mapped: list[_Token] = []
            complete = True
            for sentence in _tag_block(block):
                for word, tag in sentence:
                    word = word.replace("&slash;", "/")
                    position = block.find(word, cursor)
                    if position < 0:
                        if WORD.search(word):
                            complete = False
                            break
                        continue
                    if WORD.search(block[cursor:position]):
                        complete = False
                        break
                    cursor = position + len(word)
                    if WORD.fullmatch(word):
                        mapped.append((start + position, start + cursor, word, tag))
                if not complete:
                    break
            if complete and not WORD.search(block[cursor:]):
                result.extend(mapped)
        self.tokens = result
        return result

    def allows(self, label: str, start: int, end: int) -> bool:
        words = _words(label)
        if words == self.words:
            return True
        tokens = [token for token in self._tokens() if start <= token[0] and token[1] <= end]
        if [unicodedata.normalize("NFC", token[2]).casefold() for token in tokens] != words:
            return True
        tags = [token[3] for token in tokens]
        if any(tag in _CLAUSE for tag in tags):
            return False
        if len(tags) == 1 and tags[0] == "VBG":
            return True
        return (
            bool(tags) and tags[-1].startswith("NN") and any(tag.startswith("NN") for tag in tags)
        )
