"""Local contextual grammar for statistically proposed topic labels.

This is candidate eligibility, not a claim about the author's meaning. Authored
heading/link priors and isolated short-note labels remain independently eligible.
The packaged English lexicon requires no downloaded NLTK corpus or external model.
"""

import hashlib
import importlib.resources
import re
import unicodedata
from dataclasses import dataclass
from importlib.metadata import version
from typing import cast

from nltk.tokenize import (  # type: ignore[import-untyped]
    PunktSentenceTokenizer,
    TreebankWordTokenizer,
)
from textblob._text import find_tags  # type: ignore[import-untyped]
from textblob.en import lexicon  # type: ignore[import-untyped]

WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
# Bare VB is ambiguous with subjects such as "Use cases". Finite inflections
# and personal/relative clauses provide stronger evidence than that base form.
_CLAUSE = frozenset({"VBD", "VBP", "VBZ", "MD", "PRP", "WP", "WRB"})
_Token = tuple[int, int, str, str]
_TOKENIZER = TreebankWordTokenizer()
_SENTENCES = PunktSentenceTokenizer()  # Data-free parameters; no Punkt resource lookup.
_SCORING_QUOTES = str.maketrans("’‘“”", "''\"\"")


def _words(text: str) -> list[str]:
    return [unicodedata.normalize("NFC", word).casefold() for word in WORD.findall(text)]


def grammar_identity() -> str:
    """Version the actual packaged grammar code and data used by the topic cache."""
    digest = hashlib.sha256(version("textblob").encode())
    digest.update(version("nltk").encode())
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
    nltk_root = importlib.resources.files("nltk")
    for path in (
        "tokenize/treebank.py",
        "tokenize/punkt.py",
        "tokenize/api.py",
        "tokenize/util.py",
    ):
        digest.update(nltk_root.joinpath(path).read_bytes())
    return digest.hexdigest()


def _tag_block(block: str) -> list[list[tuple[str, str]]]:
    # TextBlob's convenience parser does not forward these packaged rules.
    # Use the pinned Pattern implementation explicitly, without NLTK corpora.
    scored = block.translate(_SCORING_QUOTES)
    sentences: list[list[tuple[int, int]]] = []
    try:
        for start, end in _SENTENCES.span_tokenize(scored):
            sentence = scored[start:end]
            sentences.append(
                [(start + a, start + b) for a, b in _TOKENIZER.span_tokenize(sentence)]
            )
    except ValueError:
        return []  # Unsupported source alignment supplies no reliable grammatical context.
    result = []
    for spans in sentences:
        words = [scored[start:end] for start, end in spans]
        tagged = cast(
            list[tuple[str, str]],
            find_tags(
                words,
                lexicon=lexicon,
                morphology=lexicon.morphology,
                context=lexicon.context,
                entities=lexicon.entities,
                language="en",
            ),
        )
        if len(tagged) != len(spans) or any(row[0] != word for row, word in zip(tagged, words)):
            return []
        result.append([(block[start:end], tag) for (start, end), (_, tag) in zip(spans, tagged)])
    return result


@dataclass(frozen=True)
class GrammarDecision:
    """Candidate eligibility and its mapped, original-source sentence context.

    Reason codes describe this grammatical gate only, not overall topic quality.
    Missing context bounds mean alignment could not establish a safe sentence.
    """

    allowed: bool
    reason: str
    context_start: int | None
    context_end: int | None


@dataclass(frozen=True)
class _SentenceContext:
    start: int
    end: int
    tokens: tuple[_Token, ...]


class CandidateGrammar:
    """Judge each occurrence within its sentence; preserve uncertain alignments.

    Sentence segmentation and tagging are local to a visible block. Unrelated
    blocks or sentences cannot supply the finite-clause gate for a candidate.
    """

    def __init__(self, prose: str, boundaries: tuple[int, ...]) -> None:
        self.prose = prose
        self.boundaries = boundaries
        self._contexts: list[_SentenceContext] | None = None

    def _sentences(self) -> list[_SentenceContext]:
        if self._contexts is not None:
            return self._contexts
        result: list[_SentenceContext] = []
        edges = sorted({0, len(self.prose), *self.boundaries})
        for start, end in zip(edges, edges[1:]):
            block = self.prose[start:end]
            try:
                spans = list(_SENTENCES.span_tokenize(block.translate(_SCORING_QUOTES)))
            except ValueError:
                continue  # An unsupported source layout supplies no safe context.
            for local_start, local_end in spans:
                source = block[local_start:local_end]
                tagged = _tag_block(source)
                if len(tagged) != 1:
                    continue
                sentence = tagged[0]
                offset = start + local_start
                cursor = 0
                tokens: list[_Token] = []
                complete = True
                for word, tag in sentence:
                    word = word.replace("&slash;", "/")
                    position = source.find(word, cursor)
                    if position < 0:
                        if WORD.search(word):
                            complete = False
                            break
                        continue
                    if WORD.search(source[cursor:position]):
                        complete = False
                        break
                    cursor = position + len(word)
                    if WORD.fullmatch(word):
                        tokens.append((offset + position, offset + cursor, word, tag))
                # Check the entire source sentence, including omitted trailing
                # words. Never borrow a later occurrence or poison a different
                # sentence's alignment because this one could not be mapped.
                if complete and not WORD.search(source[cursor:]):
                    result.append(_SentenceContext(offset, start + local_end, tuple(tokens)))
        self._contexts = result
        return result

    def decision(self, label: str, start: int, end: int) -> GrammarDecision:
        """Explain the grammar gate for this exact candidate occurrence.

        Context bounds include the mapped sentence's punctuation and retain
        original offsets. Token alignment uncertainty keeps the candidate;
        packaged tagger failures propagate rather than becoming empty evidence.
        """
        if not 0 <= start < end <= len(self.prose):
            return GrammarDecision(True, "uncertain_alignment", None, None)
        context = next(
            (
                sentence
                for sentence in self._sentences()
                if sentence.start <= start and end <= sentence.end
            ),
            None,
        )
        if context is None:
            return GrammarDecision(True, "uncertain_alignment", None, None)

        context_start, context_end = context.start, context.end

        def outcome(allowed: bool, reason: str) -> GrammarDecision:
            return GrammarDecision(allowed, reason, context_start, context_end)

        words = _words(label)
        if not words or _words(self.prose[start:end]) != words:
            return outcome(True, "uncertain_alignment")
        # A candidate's own following colon supplies local fragment context.
        # It removes permissive shortcuts, not the candidate: noun/gerund
        # subjects remain eligible under the same fallible POS evidence below.
        field_fragment = re.match(r"[ \t]*:", self.prose[end : context.end]) is not None
        if not field_fragment and words == _words(self.prose[context.start : context.end]):
            return outcome(True, "isolated_subject")
        if not field_fragment and not any(
            token[3] in _CLAUSE and not token[2].isdecimal() for token in context.tokens
        ):
            return outcome(True, "nominal_context")
        tokens = [token for token in context.tokens if start <= token[0] and token[1] <= end]
        if [unicodedata.normalize("NFC", token[2]).casefold() for token in tokens] != words:
            return outcome(True, "uncertain_alignment")
        tags = [token[3] for token in tokens]
        if any(token[3] in _CLAUSE and not token[2].isdecimal() for token in tokens):
            return outcome(False, "clause_fragment")
        if len(tags) == 1 and tags[0] == "VBG":
            return outcome(True, "noun_phrase")
        nominal = (
            bool(tags)
            and (tags[-1].startswith(("NN", "JJ")) or tags[-1] == "CD" or tokens[-1][2].isdecimal())
            and any(tag.startswith("NN") for tag in tags)
        )
        if nominal:
            return outcome(True, "noun_phrase")
        return outcome(False, "non_nominal_field" if field_fragment else "non_nominal_fragment")

    def allows(self, label: str, start: int, end: int) -> bool:
        """Compatibility predicate for callers that do not need the explanation."""
        return self.decision(label, start, end).allowed
