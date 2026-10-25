"""Frozen document-global comparator, for the policy benchmark only.

The class body is copied unchanged from the pre-locality implementation. Shared
word/tag helpers retain the pinned tokenizer; production never imports this file.
"""

import unicodedata

from geistfabrik.topic_grammar import WORD, GrammarDecision, _CLAUSE, _tag_block, _Token, _words


class LegacyGrammar:
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
        context = self._tokens()
        if not any(token[3] in _CLAUSE and not token[2].isdecimal() for token in context):
            return True  # Nominal outlines provide no clause context for disambiguation.
        tokens = [token for token in context if start <= token[0] and token[1] <= end]
        if [unicodedata.normalize("NFC", token[2]).casefold() for token in tokens] != words:
            return True
        tags = [token[3] for token in tokens]
        if any(token[3] in _CLAUSE and not token[2].isdecimal() for token in tokens):
            return False
        if len(tags) == 1 and tags[0] == "VBG":
            return True
        return (
            bool(tags)
            and (tags[-1].startswith(("NN", "JJ")) or tags[-1] == "CD" or tokens[-1][2].isdecimal())
            and any(tag.startswith("NN") for tag in tags)
        )

    def decision(self, label: str, start: int, end: int) -> GrammarDecision:
        allowed = self.allows(label, start, end)
        return GrammarDecision(allowed, "legacy_document_global", 0, len(self.prose))
