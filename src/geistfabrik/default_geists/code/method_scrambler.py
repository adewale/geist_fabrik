"""Method Scrambler geist - applies SCAMPER technique to note connections.

Uses SCAMPER (Substitute, Combine, Adapt, Modify, Put to another use, Eliminate, Reverse)
to generate creative provocations about existing notes and concepts.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Apply SCAMPER transformations to notes.

    Returns:
        List of SCAMPER-based provocations
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes()

    if len(notes) < 10:
        return []

    # SCAMPER templates
    scamper_operations = [
        ("substitute", "What if you substituted [[{note}]] with [[{other}]]?"),
        ("combine", "What if you combined [[{note}]] and [[{other}]] into something new?"),
        ("adapt", "What if you adapted [[{note}]] to work like [[{other}]]?"),
        (
            "modify",
            "What if you magnified or minimized aspects of [[{note}]] based on [[{other}]]?",
        ),
        (
            "put_to_use",
            "What if you used [[{note}]] for a completely different purpose, like [[{other}]]?",
        ),
        (
            "eliminate",
            "What if you eliminated the parts of [[{note}]] that overlap with [[{other}]]?",
        ),
        ("reverse", "What if you reversed the relationship between [[{note}]] and [[{other}]]?"),
    ]

    # Sample notes for SCAMPER operations
    sample_notes = vault.sample(notes, min(30, len(notes)))

    for note in sample_notes:
        # Find related notes (both linked and semantically similar)
        linked_notes: List["Note"] = [
            resolved
            for link in note.links[:3]
            if (resolved := vault.resolve_link_target(link.target)) is not None
        ]

        similar = vault.neighbours(note, k=5)

        # Deduplicate by combining into a set
        candidates = list(set(linked_notes + similar))

        if len(candidates) < 2:
            continue

        # Pick a random other note and SCAMPER operation
        other = vault.sample(candidates, k=1)[0]
        operation, template = vault.sample(scamper_operations, k=1)[0]

        text = template.format(note=note.title, other=other.title)

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.title, other.title],
                geist_id="method_scrambler",
            )
        )

    # Also generate SCAMPER questions for unlinked but similar pairs
    pairs = vault.unlinked_pairs(k=10)

    for note_a, note_b in pairs:
        operation, template = vault.sample(scamper_operations, k=1)[0]

        # Adjust template for unlinked pairs
        if operation in ["substitute", "combine", "adapt"]:
            text = template.format(note=note_a.title, other=note_b.title)

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note_a.title, note_b.title],
                    geist_id="method_scrambler",
                )
            )

    return vault.sample(suggestions, k=3)
