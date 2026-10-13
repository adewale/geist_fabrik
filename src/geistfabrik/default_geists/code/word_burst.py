"""Word-burst geist: questions grounded in exact lexical episode evidence."""

from typing import TYPE_CHECKING

from geistfabrik.config import MAX_SUGGESTION_NOTES
from geistfabrik.models import Suggestion

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext


def suggest(vault: "VaultContext") -> list[Suggestion]:
    """Sample episodes, describe the measured population, and link their evidence."""
    findings = vault.word_bursts()
    if not findings:
        return []
    suggestions = []
    for finding in vault.sample(findings, count=vault.vault.config.word_burst.max_suggestions):
        notes = [vault.get_note(path) for path in finding.support_paths]
        links = [note.link_text for note in notes if note is not None]
        if not links:
            continue
        # Full evidence stays in WordBurstFinding. Check all its references
        # before bounding the rendered payload so hidden supports cannot escape
        # the same fail-closed boundary used by the downstream filter.
        if not vault.references_allowed(links):
            continue
        population = (
            "current text grouped by declared dates"
            if finding.history_mode == "dated_cohorts"
            else "additions captured since observation began"
        )
        qualifiers = []
        if finding.gaps:
            qualifiers.append("with unobserved weeks between evidence")
        if finding.left_censored:
            qualifiers.append("already elevated at the observation boundary")
        if finding.open:
            qualifiers.append("still elevated at the last observation")
        if finding.provisional:
            qualifiers.append("the final week is incomplete")
        qualification = f" ({'; '.join(qualifiers)})" if qualifiers else ""
        named = ", ".join(f"[[{link}]]" for link in links[:3])
        text = (
            f"From {finding.start} to {finding.end}, ‘{finding.term}’ appeared in "
            f"{finding.rate:.0%} of observations, compared with {finding.baseline_rate:.0%} "
            f"across the window, using {population}{qualification}. "
            f"What connects {named}, and what question was this language opening up?"
        )
        suggestions.append(
            Suggestion(text=text, notes=links[:MAX_SUGGESTION_NOTES], geist_id="word_burst")
        )
    return suggestions
