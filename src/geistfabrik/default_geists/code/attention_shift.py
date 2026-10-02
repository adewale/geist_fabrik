"""Attention shift geist - detects notes whose semantic neighbours have churned.

A reflective lens over stored semantic representations: a note's nearest
neighbours can change across snapshots. High churn means that the measured
neighbour set changed; it does not establish a change in the user's thinking.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion

# Share of a note's nearest neighbours that changed (1 - Jaccard) for it to
# count as a shifted note.
CHURN_THRESHOLD = 0.6


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Name one note whose semantic neighbourhood has changed a lot.

    Uses the session-cached, vectorised VaultContext.neighbour_churn()
    (one bulk historical-embedding load plus two blocked top-k passes),
    never per-note DB queries or similarity loops. Every note whose churn
    exceeds CHURN_THRESHOLD is a candidate and the session seed picks one:
    sample, don't rank, so the same highest-churn note is not named every
    session.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion naming a high-churn note
    """
    churn_map = vault.neighbour_churn(since_days=180)
    if not churn_map:
        return []  # No session history old enough — degrade gracefully

    candidates = []
    for path in sorted(churn_map):
        result = churn_map[path]
        if result.churn <= CHURN_THRESHOLD:
            continue
        note = vault.get_note(path)
        departed_notes = [vault.get_note(p) for p in result.departed[:3]]
        arrived_notes = [vault.get_note(p) for p in result.arrived[:3]]
        departed = [n.link_text for n in departed_notes if n is not None]
        arrived = [n.link_text for n in arrived_notes if n is not None]
        # Need both sides of the shift to tell the story
        if note is not None and departed and arrived:
            candidates.append((note.link_text, departed, arrived))

    if not candidates:
        return []

    link, departed, arrived = vault.sample(candidates, 1)[0]
    old_titles = ", ".join(f"[[{t}]]" for t in departed)
    new_titles = ", ".join(f"[[{t}]]" for t in arrived)

    return [
        Suggestion(
            text=(
                f"The measured neighbour set for [[{link}]] changed. "
                f"Old neighbours: {old_titles}. "
                f"New neighbours: {new_titles}. "
                f"What, if anything, do the source notes reveal?"
            ),
            notes=[link] + departed + arrived,
            geist_id="attention_shift",
        )
    ]
