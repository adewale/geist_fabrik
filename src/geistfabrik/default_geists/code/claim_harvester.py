"""Claim Harvester geist - surfaces assertive claims from notes.

Peer of definition_harvester / question_harvester, built on the shared
content_extraction pipeline. Uses ClaimExtractor to find assertive statements
(strong verbs, research findings, causal claims) and asks whether they still
hold - a muse, not a fact-checker.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Extract claims from a randomly selected note and question them.

    Returns:
        List of 1-2 suggestions containing claims found (empty if none).
    """
    from geistfabrik import Suggestion
    from geistfabrik.content_extraction import (
        AlphaFilter,
        ClaimExtractor,
        ExtractionPipeline,
        LengthFilter,
    )

    notes = vault.notes_excluding_journal()
    if not notes:
        return []

    note = vault.random_notes(count=1)[0]
    content = vault.read(note)

    pipeline = ExtractionPipeline(
        strategies=[ClaimExtractor()],
        filters=[LengthFilter(min_len=20, max_len=300), AlphaFilter()],
    )
    claims = pipeline.extract(content)
    if not claims:
        return []

    suggestions = []
    for claim in claims:
        claim_clean = " ".join(claim.split())
        text = (
            f'In [[{note.link_text}]] you claimed: "{claim_clean}" '
            f"Is that still true - and what would change your mind?"
        )
        suggestions.append(
            Suggestion(text=text, notes=[note.link_text], geist_id="claim_harvester")
        )

    return vault.sample(suggestions, count=min(2, len(suggestions)))
