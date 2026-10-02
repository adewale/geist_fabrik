"""Columbo geist - detects contradictions between notes.

Named after the detective, this geist looks for claims that seem inconsistent
with evidence in other notes. It presents findings as "I think you're lying about X
because Y..." to provoke examination of contradictions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext
from geistfabrik.similarity_analysis import SimilarityLevel


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Detect potential contradictions between notes.

    Returns:
        List of suggestions highlighting contradictions
    """
    from geistfabrik import Suggestion

    suggestions = []
    # Each contradiction is reported once, whichever note of the pair is seen first
    reported_pairs: set[frozenset[str]] = set()

    # Sample notes to check for contradictions
    notes = vault.notes()
    if len(notes) < 3:
        return []

    # Sample a set of notes to analyze
    candidates = vault.sample(notes, min(30, len(notes)))

    for note in candidates:
        content = vault.read(note).lower()

        # Look for claims (notes with strong assertion language)
        if not any(
            word in content
            for word in ["all ", "never ", "always ", "must ", "should ", "is ", "are "]
        ):
            continue

        # Find semantically similar notes (OP-9: get scores to avoid recomputation)
        similar_with_scores = vault.neighbours(note, count=5, return_scores=True)

        for other, similarity in similar_with_scores:
            if other.path == note.path:
                continue
            pair = frozenset((note.path, other.path))
            if pair in reported_pairs:
                continue

            other_content = vault.read(other).lower()

            # Look for contradiction indicators
            note_positive_words = sum(
                1 for w in ["always", "all", "must", "should"] if w in content
            )
            other_negative_words = sum(
                1
                for w in ["never", "no", "not", "cannot", "but", "however", "except"]
                if w in other_content
            )

            # Also check reverse
            note_negative_words = sum(
                1
                for w in ["never", "no", "not", "cannot", "but", "however", "except"]
                if w in content
            )
            other_positive_words = sum(
                1 for w in ["always", "all", "must", "should"] if w in other_content
            )

            # High semantic similarity but opposite linguistic patterns suggests contradiction
            # (already have similarity from neighbours)

            if similarity > SimilarityLevel.HIGH and (
                (note_positive_words > 2 and other_negative_words > 2)
                or (note_negative_words > 2 and other_positive_words > 2)
            ):
                # Notes BOTH of them link to (resolved targets), to strengthen
                # the case. Only genuinely shared links are named: listing the
                # first raw targets of either note claimed "Both connect to"
                # links that only one note had, or that resolved to nothing.
                other_targets = {n.path for n in vault.outgoing_links(other)}
                shared = sorted(
                    (n for n in vault.outgoing_links(note) if n.path in other_targets),
                    key=lambda n: n.link_text,
                )

                if shared:
                    connection_list = ", ".join(f"[[{n.link_text}]]" for n in shared[:2])
                    text = (
                        f"I think you're lying about your claim in "
                        f"[[{note.link_text}]] because [[{other.link_text}]] "
                        f"argues something that seems to contradict it. "
                        f"Both connect to {connection_list}, "
                        f"so maybe there's a missing piece?"
                    )
                else:
                    text = (
                        f"[[{note.link_text}]] and [[{other.link_text}]] seem "
                        f"to contradict each other—what gives?"
                    )

                reported_pairs.add(pair)
                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.link_text, other.link_text],
                        geist_id="columbo",
                    )
                )

    return vault.sample(suggestions, count=3)
