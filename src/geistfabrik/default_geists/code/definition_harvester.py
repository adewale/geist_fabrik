"""Definition Harvester geist - extracts terminology definitions from notes.

Demonstrates the power of content_extraction.py abstractions. Uses the
DefinitionExtractor strategy to find definition patterns like "X is Y",
"X: Y", "X means Y", and "X refers to Y".

This geist showcases how the extraction pipeline generalizes the pattern
from question_harvester to enable new content types with minimal code.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Extract terminology definitions from a randomly selected note.

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
    )

    # Pick one random note (deterministic by session seed)
    notes = vault.notes()
    if not notes:
        return []

    note = vault.random_notes(k=1)[0]
    content = vault.read(note)

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

    # Extract definitions
    definitions = pipeline.extract(content)

    # If no definitions found, return empty (geist abstains)
    if not definitions:
        return []

    # Create suggestions from definitions
    suggestions = []
    for definition in definitions:
        # Clean up whitespace
        definition_clean = " ".join(definition.split())

        text = (
            f"From [[{note.obsidian_link}]]: \"{definition_clean}\" "
            f"What if you explored this definition further?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note.obsidian_link],
                geist_id="definition_harvester",
            )
        )

    # Sample 1-3 definitions to avoid overwhelming
    return vault.sample(suggestions, k=min(3, len(suggestions)))
