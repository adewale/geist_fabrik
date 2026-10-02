"""Assumption Challenger geist - identifies implicit assumptions in notes.

Looks for notes that make claims based on assumptions that might be questioned,
then suggests examining those assumptions.
"""

import re
from typing import TYPE_CHECKING

from geistfabrik.content_extraction import quote_for_display, strip_code, unmask_code

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

# Phrases that present something as beyond question. "always" and "must be"
# are deliberately absent: in technical notes they are requirement language
# ("the cache must be cleared"), not unexamined assumptions.
_ASSUMPTION = re.compile(
    r"\b(?:obviously|clearly|of course|everyone knows|it is well known|naturally|"
    r"needless to say|without a doubt|certainly|undoubtedly|has to|necessarily)\b",
    re.IGNORECASE,
)
_HEDGE = re.compile(
    r"\b(?:maybe|perhaps|might|could be|possibly|uncertain|unclear|debatable|"
    r"questionable|depends|varies|sometimes)\b",
    re.IGNORECASE,
)
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_LINE_PREFIX = re.compile(r"^\s*(?:[-*+>]\s+|\d+[.)]\s+)*")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z]{4,}")
_MAX_QUOTE = 200


def _sentences(content: str) -> list[str]:
    """Prose sentences of a note: no frontmatter, code, headings or tables."""
    body = strip_code(_FRONTMATTER.sub("", content))
    sentences: list[str] = []
    for line in body.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "|", "---")):
            continue
        prose = _LINE_PREFIX.sub("", stripped).replace("**", "")
        sentences.extend(part.strip() for part in _SENTENCE_END.split(prose) if part.strip())
    return sentences


def _display(sentence: str) -> str:
    """Quote a sentence for the journal, shortening very long ones."""
    text = unmask_code(sentence)
    if text.endswith(".") and not text.endswith(".."):
        text = text[:-1]  # the suggestion supplies its own punctuation
    if len(text) > _MAX_QUOTE:
        text = text[:_MAX_QUOTE].rsplit(" ", 1)[0] + "…"
    return quote_for_display(text)


def _terms(sentence: str) -> set[str]:
    """Content words (4+ letters) of a sentence, minus the marker phrases."""
    unmarked = _HEDGE.sub(" ", _ASSUMPTION.sub(" ", sentence.lower()))
    return set(_WORD.findall(unmarked))


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with questionable assumptions.

    Returns:
        List of suggestions challenging assumptions
    """
    from geistfabrik import Suggestion
    from geistfabrik.similarity_analysis import SimilarityLevel

    suggestions = []

    notes = vault.notes()

    if len(notes) < 10:
        return []

    # OPTIMISATION: Early termination after finding enough suggestions
    # Final sampling only returns 3, so generating 5 is sufficient
    max_suggestions_contrast = 5
    suggestion_count = 0

    for note in vault.sample(notes, min(40, len(notes))):
        # Early exit if we have enough suggestions
        if suggestion_count >= max_suggestions_contrast:
            break
        raw = vault.read(note)
        content = raw.lower()

        # A note qualifies with >= 2 distinct assumption phrases; the
        # suggestion quotes the first sentence that uses one, so "you wrote"
        # is shown rather than asserted.
        sentences = _sentences(raw)
        phrases = {m.group(0).lower() for s in sentences for m in _ASSUMPTION.finditer(s)}
        certain = next((s for s in sentences if _ASSUMPTION.search(s)), None)

        if len(phrases) >= 2 and certain is not None:
            # A semantically similar note that hedges about the same terms
            # (a hedged sentence sharing a content word with the quote).
            certain_terms = _terms(certain)
            hedged: tuple[str, str] | None = None
            for other, score in vault.neighbours(note, count=10, return_scores=True):
                if score < SimilarityLevel.WEAK:
                    continue
                for sentence in _sentences(vault.read(other)):
                    if _HEDGE.search(sentence) and _terms(sentence) & certain_terms:
                        hedged = (other.link_text, sentence)
                        break
                if hedged is not None:
                    break

            if hedged is not None:
                other_link, hedge = hedged
                text = (
                    f"In [[{note.link_text}]] you wrote {_display(certain)}, while "
                    f"[[{other_link}]] (semantically similar) hedges: {_display(hedge)}. "
                    f"What is the certainty in [[{note.link_text}]] resting on?"
                )
                refs = [note.link_text, other_link]
            else:
                text = (
                    f"In [[{note.link_text}]] you wrote {_display(certain)}. "
                    f"What is that assumption resting on?"
                )
                refs = [note.link_text]

            suggestions.append(Suggestion(text=text, notes=refs, geist_id="assumption_challenger"))
            suggestion_count += 1

        # Also look for causal claims without evidence
        causal_patterns = [
            "because",
            "therefore",
            "thus",
            "hence",
            "leads to",
            "results in",
            "causes",
            "due to",
        ]

        causal_count = sum(1 for pattern in causal_patterns if pattern in content)

        if causal_count >= 3 and len(note.links) < 2:
            # Makes causal claims but doesn't link to supporting evidence
            text = (
                f"[[{note.link_text}]] makes causal claims but has few links to "
                f"supporting notes. What evidence or reasoning supports these "
                f"cause-effect relationships?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.link_text],
                    geist_id="assumption_challenger",
                )
            )
            suggestion_count += 1

    return vault.sample(suggestions, count=3)
