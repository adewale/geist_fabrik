"""Columbo geist - detects contradictions between notes.

Named after the detective, this geist looks for claims that seem inconsistent
with evidence in other notes. It presents findings as "I think you're lying about X
because Y..." to provoke examination of contradictions.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Detect potential contradictions between notes.

    Returns:
        List of suggestions highlighting contradictions
    """
    from geistfabrik import Suggestion

    suggestions = []

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

        # Find semantically similar notes
        similar = vault.neighbours(note, k=5)

        for other in similar:
            if other.path == note.path:
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
            similarity = vault.similarity(note, other)

            if similarity > 0.6 and (
                (note_positive_words > 2 and other_negative_words > 2)
                or (note_negative_words > 2 and other_positive_words > 2)
            ):
                # Find linked notes to strengthen the case
                connections = []
                for n in [note, other]:
                    if len(n.links) > 0:
                        connections.extend([link.target for link in n.links[:2]])

                if connections:
                    text = (
                        f"I think you're lying about your claim in [[{note.title}]] "
                        f"because [[{other.title}]] argues something that seems to contradict it"
                    )

                    if connections:
                        text += f". Both connect to {', '.join([f'[[{c}]]' for c in connections[:2]])}, so maybe there's a missing piece?"
                else:
                    text = f"[[{note.title}]] and [[{other.title}]] seem to contradict each other—what gives?"

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.title, other.title],
                        geist_id="columbo",
                    )
                )

    return vault.sample(suggestions, k=3)
