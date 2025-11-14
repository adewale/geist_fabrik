"""Method Scrambler geist - applies SCAMPER technique to note connections.

Uses SCAMPER (Substitute, Combine, Adapt, Modify, Put to another use, Eliminate, Reverse)
to generate creative provocations about existing notes and concepts.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Apply SCAMPER transformations to notes.

    Returns:
        List of SCAMPER-based provocations
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes_excluding_journal()

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
        linked_notes = vault.outgoing_links(note)[:3]
        similar = vault.neighbours(note, k=5)

        # Deduplicate by combining into a set
        all_candidates = list(set(linked_notes + similar))

        # Filter out geist journal notes
        candidates = [n for n in all_candidates if not n.path.startswith("geist journal/")]

        if len(candidates) < 2:
            continue

        # Pick a random other note and SCAMPER operation
        other = vault.sample(candidates, k=1)[0]
        operation, template = vault.sample(scamper_operations, k=1)[0]

        text = template.format(note=note.obsidian_link, other=other.obsidian_link)

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.obsidian_link, other.obsidian_link],
                geist_id="method_scrambler",
            )
        )

    # Also generate SCAMPER questions for unlinked but similar pairs
    pairs = vault.unlinked_pairs(k=10)

    for note_a, note_b in pairs:
        operation, template = vault.sample(scamper_operations, k=1)[0]

        # Adjust template for unlinked pairs
        if operation in ["substitute", "combine", "adapt"]:
            text = template.format(note=note_a.obsidian_link, other=note_b.obsidian_link)

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note_a.obsidian_link, note_b.obsidian_link],
                    geist_id="method_scrambler",
                )
            )

    return vault.sample(suggestions, k=3)
