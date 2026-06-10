"""Hypothesis Harvester geist - surfaces speculative statements from notes.

Peer of definition_harvester / claim_harvester, built on the shared
content_extraction pipeline. Uses HypothesisExtractor to find tentative
statements (if/then, may/might, would-conditionals) and asks how you would
test them.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Extract hypotheses from a randomly selected note and ask how to test them.

    Returns:
        List of 1-2 suggestions containing hypotheses found (empty if none).
    """
    from geistfabrik import Suggestion
    from geistfabrik.content_extraction import (
        AlphaFilter,
        ExtractionPipeline,
        HypothesisExtractor,
        LengthFilter,
    )

    notes = vault.notes_excluding_journal()
    if not notes:
        return []

    note = vault.random_notes(count=1)[0]
    content = vault.read(note)

    pipeline = ExtractionPipeline(
        strategies=[HypothesisExtractor()],
        filters=[LengthFilter(min_len=20, max_len=300), AlphaFilter()],
    )
    hypotheses = pipeline.extract(content)
    if not hypotheses:
        return []

    suggestions = []
    for hypothesis in hypotheses:
        hyp_clean = " ".join(hypothesis.split())
        text = (
            f'[[{note.link_text}]] speculates: "{hyp_clean}" '
            f"What is the smallest experiment that would tell you if it holds?"
        )
        suggestions.append(
            Suggestion(text=text, notes=[note.link_text], geist_id="hypothesis_harvester")
        )

    return vault.sample(suggestions, count=min(2, len(suggestions)))
