"""Scale Shifter geist - suggests viewing concepts at different levels of abstraction.

Identifies notes and suggests examining the same concept at different scales:
zooming in (more specific/concrete) or zooming out (more abstract/general).

A note's scale is read from which scale words it uses (whole words, with
plural forms: "case" does not match "because", nor "real" "really"). A
partner offered as the other scale must lean that way by the same measure
(more abstract than concrete words for a "broader framework", the reverse
for a "more concrete instance") and must be at least moderately similar.
Each pair of notes is suggested at most once.
"""

import re
from typing import TYPE_CHECKING

from geistfabrik.similarity_analysis import SimilarityLevel

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext

# Scale indicators
ABSTRACT_WORDS = [
    "theory",
    "principle",
    "concept",
    "framework",
    "paradigm",
    "model",
    "pattern",
    "system",
    "structure",
    "abstract",
    "general",
    "universal",
    "category",
    "class",
]

CONCRETE_WORDS = [
    "example",
    "case",
    "instance",
    "specific",
    "particular",
    "detail",
    "concrete",
    "actual",
    "practical",
    "real",
    "individual",
    "tangible",
    "implementation",
]


def _word_pattern(words: list[str]) -> "re.Pattern[str]":
    """Whole-word matcher for words and their plurals (theory/theories)."""
    forms = []
    for word in words:
        forms.append(f"{word}(?:s|es)?")
        if word.endswith("y"):
            forms.append(f"{word[:-1]}ies")
    return re.compile(r"\b(" + "|".join(forms) + r")\b")


_ABSTRACT = _word_pattern(ABSTRACT_WORDS)
_CONCRETE = _word_pattern(CONCRETE_WORDS)


def _singular(form: str) -> str:
    if form.endswith("ies"):
        return form[:-3] + "y"
    for word in (*ABSTRACT_WORDS, *CONCRETE_WORDS):
        if form.startswith(word):
            return word
    return form


def _scores(content: str) -> tuple[int, int]:
    """(abstract, concrete): how many distinct scale words of each kind occur."""
    text = content.lower()
    abstract = {_singular(m) for m in _ABSTRACT.findall(text)}
    concrete = {_singular(m) for m in _CONCRETE.findall(text)}
    return len(abstract), len(concrete)


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Suggest scale shifts for notes (zoom in/out on abstraction).

    Returns:
        List of suggestions for changing perspective scale
    """
    from geistfabrik import Suggestion

    suggestions = []
    seen_pairs: set[frozenset[str]] = set()

    notes = vault.notes()

    if len(notes) < 20:
        return []

    score_cache: dict[str, tuple[int, int]] = {}

    def scores(n: "Note") -> tuple[int, int]:
        if n.path not in score_cache:
            score_cache[n.path] = _scores(vault.read(n))
        return score_cache[n.path]

    def is_new_pair(a: "Note", b: "Note") -> bool:
        pair = frozenset((a.path, b.path))
        if pair in seen_pairs:
            return False
        seen_pairs.add(pair)
        return True

    def similar_notes(n: "Note") -> list["Note"]:
        return [
            other
            for other, score in vault.neighbours(n, count=10, return_scores=True)
            if score >= SimilarityLevel.MODERATE
        ]

    for note in vault.sample(notes, min(30, len(notes))):
        # Determine if note is abstract or concrete
        abstract_score, concrete_score = scores(note)

        # Highly abstract note - suggest zooming in
        if abstract_score >= 3 and concrete_score <= 1:
            # Find similar notes that lean concrete
            concrete_neighbours = []
            for other in similar_notes(note):
                other_abstract, other_concrete = scores(other)
                if other_concrete >= 2 and other_concrete > other_abstract:
                    concrete_neighbours.append(other)

            if concrete_neighbours:
                example = vault.sample(concrete_neighbours, count=1)[0]
                if not is_new_pair(note, example):
                    continue

                text = (
                    f"[[{note.link_text}]] operates at a high level of abstraction. "
                    f"What if you zoomed in? [[{example.link_text}]] might be a "
                    f"more concrete instance of the same ideas."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.link_text, example.link_text],
                        geist_id="scale_shifter",
                    )
                )

        # Highly concrete note - suggest zooming out
        elif concrete_score >= 3 and abstract_score <= 1:
            # Find similar notes that lean abstract
            abstract_neighbours = []
            for other in similar_notes(note):
                other_abstract, other_concrete = scores(other)
                if other_abstract >= 2 and other_abstract > other_concrete:
                    abstract_neighbours.append(other)

            if abstract_neighbours:
                framework = vault.sample(abstract_neighbours, count=1)[0]
                if not is_new_pair(note, framework):
                    continue

                text = (
                    f"[[{note.link_text}]] is very specific and concrete. "
                    f"What if you zoomed out? [[{framework.link_text}]] might provide "
                    f"a broader framework for understanding what makes this case interesting."
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.link_text, framework.link_text],
                        geist_id="scale_shifter",
                    )
                )

    # Also suggest cross-scale connections (very abstract + very concrete on same topic)
    abstract_notes = []
    concrete_notes = []

    for note in vault.sample(notes, min(50, len(notes))):
        abstract_score, concrete_score = scores(note)

        if abstract_score >= 3 and concrete_score <= 1:
            abstract_notes.append(note)
        elif concrete_score >= 3 and abstract_score <= 1:
            concrete_notes.append(note)

    # Find abstract-concrete pairs with high similarity
    for abstract in vault.sample(abstract_notes, min(10, len(abstract_notes))):
        for concrete in vault.sample(concrete_notes, min(10, len(concrete_notes))):
            if vault.similarity(abstract, concrete) > 0.6:
                if not vault.links_between(abstract, concrete) and is_new_pair(abstract, concrete):
                    text = (
                        f"[[{abstract.link_text}]] (abstract/theoretical) and "
                        f"[[{concrete.link_text}]] (concrete/specific) are "
                        f"semantically similar but operate at different scales. Could one "
                        f"illuminate the other?"
                    )

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[abstract.link_text, concrete.link_text],
                            geist_id="scale_shifter",
                        )
                    )

    return vault.sample(suggestions, count=2)
