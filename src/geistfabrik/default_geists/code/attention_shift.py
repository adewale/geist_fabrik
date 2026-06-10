"""Attention shift geist - detects notes whose semantic context has churned.

A reflective lens over temporal embeddings: as the vault grows and your
thinking moves, a note's nearest semantic neighbours change. High churn
means the context you read a note in has been replaced — old companions
departed, new ones arrived. What changed in how you see this?
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find the note whose semantic neighbourhood has changed the most.

    Uses the session-cached, vectorised VaultContext.neighbour_churn()
    (one bulk historical-embedding load plus two blocked top-k passes),
    never per-note DB queries or similarity loops.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion naming the highest-churn note
    """
    churn_map = vault.neighbour_churn(since_days=180)
    if not churn_map:
        return []  # No session history old enough — degrade gracefully

    candidates = [(p, r) for p, r in churn_map.items() if r.churn > 0.6]
    if not candidates:
        return []

    path, result = max(candidates, key=lambda x: x[1].churn)
    note = vault.get_note(path)
    if note is None:
        return []

    departed_notes = [vault.get_note(p) for p in result.departed[:3]]
    arrived_notes = [vault.get_note(p) for p in result.arrived[:3]]
    departed = [n.obsidian_link for n in departed_notes if n is not None]
    arrived = [n.obsidian_link for n in arrived_notes if n is not None]

    if not departed or not arrived:
        return []  # Need both sides of the shift to tell the story

    old_titles = ", ".join(f"[[{t}]]" for t in departed)
    new_titles = ", ".join(f"[[{t}]]" for t in arrived)

    return [
        Suggestion(
            text=(
                f"Your thinking around [[{note.obsidian_link}]] has shifted. "
                f"Old neighbours: {old_titles}. "
                f"New neighbours: {new_titles}. "
                f"What changed in how you see this?"
            ),
            notes=[note.obsidian_link] + departed + arrived,
            geist_id="attention_shift",
        )
    ]
