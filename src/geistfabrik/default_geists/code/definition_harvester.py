"""Definition Harvester geist - extracts terminology definitions from notes.

Demonstrates the power of content_extraction.py abstractions. Uses the
DefinitionExtractor strategy to find definition patterns like "X is a Y",
"X means Y", "X refers to Y" and Markdown definition lists ("X" then ": Y").

This geist showcases how the extraction pipeline generalizes the pattern
from question_harvester to enable new content types with minimal code.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

# Notes tried per session before abstaining.
MAX_NOTES_TRIED = 10


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Extract terminology definitions from a randomly selected note.

    Tries up to MAX_NOTES_TRIED random notes and harvests the first that
    contains a definition.

    Returns:
        List of 1-3 suggestions containing definitions found (or empty if none)
    """
    from geistfabrik import Suggestion
    from geistfabrik.content_extraction import (
        AlphaFilter,
        DefinitionExtractor,
        ExtractionPipeline,
        LengthFilter,
        PatternFilter,
        quote_for_display,
    )

    notes = vault.notes()
    if not notes:
        return []

    # Create extraction pipeline
    pipeline = ExtractionPipeline(
        strategies=[DefinitionExtractor()],
        filters=[
            LengthFilter(min_len=15, max_len=300),  # Definitions tend to be medium-length
            AlphaFilter(),
            PatternFilter(
                [
                    r"^#+\s*:",  # Heading-only definitions
                    r"^\s*:\s*$",  # Just a colon
                ]
            ),
        ],
    )

    # Genuine definitions are sparse, so try a few random notes (deterministic
    # by session seed) and harvest the first one that has any.
    note = notes[0]
    definitions: list[str] = []
    for note in vault.sample(notes, MAX_NOTES_TRIED):
        definitions = pipeline.extract(vault.read(note))
        if definitions:
            break

    # If no definitions found, return empty (geist abstains)
    if not definitions:
        return []

    # Create suggestions from definitions
    suggestions = []
    for definition in definitions:
        # Clean up whitespace
        definition_clean = " ".join(definition.split())

        text = (
            f"From [[{note.link_text}]]: {quote_for_display(definition_clean)} "
            f"What if you explored this definition further?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.link_text],
                geist_id="definition_harvester",
            )
        )

    # Sample 1-3 definitions to avoid overwhelming
    return vault.sample(suggestions, count=min(3, len(suggestions)))
