"""Experimental local grammar eligibility; not wired into production extraction."""

import re
import unicodedata

from textblob.en import parse

WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
_CLAUSE = frozenset({"VB", "VBD", "VBP", "VBZ", "MD", "PRP", "PRP$", "WP", "WP$", "WRB"})


def _words(text):
    return [unicodedata.normalize("NFC", word).casefold() for word in WORD.findall(text)]


class CandidateGrammar:
    """Use contextual tags conservatively; unmappable blocks keep candidates.

    Authored heading/link priors never call this helper. A whole short-note label
    remains eligible even when the English tagger calls it a verb or adjective.
    """

    def __init__(self, prose, boundaries):
        self.prose = prose
        self.boundaries = boundaries
        self.tokens = None

    def _tokens(self):
        if self.tokens is not None:
            return self.tokens
        result = []
        edges = sorted({0, len(self.prose), *self.boundaries})
        for start, end in zip(edges, edges[1:]):
            block = self.prose[start:end]
            cursor = 0
            mapped = []
            complete = True
            for sentence in parse(block, chunks=True, relations=False, lemmata=False).split():
                for word, tag, *_ in sentence:
                    word = word.replace("&slash;", "/")
                    position = block.find(word, cursor)
                    if position < 0:
                        if WORD.search(word):
                            complete = False
                            break
                        continue  # A normalized quotation mark need not own source text.
                    if WORD.search(block[cursor:position]):
                        complete = False
                        break  # Never borrow a later identical word after an unmapped word.
                    cursor = position + len(word)
                    if WORD.fullmatch(word):
                        mapped.append((start + position, start + cursor, word, tag))
                if not complete:
                    break
            if complete:
                result.extend(mapped)
        self.tokens = result
        return result

    def allows(self, label, start, end):
        words = _words(label)
        if words == _words(self.prose):
            return True
        tokens = [t for t in self._tokens() if start <= t[0] and t[1] <= end]
        if [unicodedata.normalize("NFC", t[2]).casefold() for t in tokens] != words:
            return True
        tags = [token[3] for token in tokens]
        if any(tag in _CLAUSE for tag in tags):
            return False
        if len(tags) == 1 and tags[0] == "VBG":
            return True  # Nominal gerunds such as "becoming" are possible subjects.
        return bool(tags) and tags[-1].startswith("NN") and any(tag.startswith("NN") for tag in tags)
