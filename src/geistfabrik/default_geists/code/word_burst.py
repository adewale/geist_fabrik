"""Word-burst geist: questions grounded in exact lexical episode evidence."""

from typing import TYPE_CHECKING

from geistfabrik.config import MAX_SUGGESTION_NOTES
from geistfabrik.document_rate import percentage_pair
from geistfabrik.evidence_identity import interval_evidence_key
from geistfabrik.models import Suggestion

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext
    from geistfabrik.word_burst_analysis import WordBurstFinding


def suggest(vault: "VaultContext") -> list[Suggestion]:
    """Sample episodes, describe the measured population, and link their evidence."""
    findings = vault.word_bursts()
    if not findings:
        return []
    # Nested word/phrase variants on identical evidence are one invitation.
    # Prefer the specific expression, then sample rather than ranking by gain.
    groups: dict[tuple[str, str, str, tuple[str, ...]], list[WordBurstFinding]] = {}
    for finding in findings:
        if len(finding.term) <= 100:
            groups.setdefault(
                (finding.direction, finding.start, finding.end, finding.support_paths), []
            ).append(finding)
    eligible: list[WordBurstFinding] = []
    for group in groups.values():
        covered: set[str] = set()
        for finding in group:
            words = finding.term.split()
            covered.update(
                " ".join(words[i : i + size])
                for size in range(1, len(words))
                for i in range(len(words) - size + 1)
            )
        eligible.extend(finding for finding in group if finding.term not in covered)
    maximum = vault.vault.config.word_burst.max_suggestions
    chosen = []
    if maximum > 1 and {f.direction for f in eligible} == {"rising", "declining"}:
        for direction in vault.sample(["rising", "declining"], count=2):
            chosen.extend(vault.sample([f for f in eligible if f.direction == direction], count=1))
    remaining = [f for f in eligible if f not in chosen]
    chosen.extend(vault.sample(remaining, count=maximum - len(chosen)))
    suggestions = []
    for finding in chosen:
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
            qualifiers.append(
                "still elevated at the last observation"
                if finding.direction == "rising"
                else "still quieter at the last observation"
            )
        if finding.provisional:
            qualifiers.append("the final week is incomplete")
        qualification = f" ({'; '.join(qualifiers)})" if qualifiers else ""
        shown = vault.sample([note for note in notes if note is not None], count=3)
        shown_links = [note.link_text for note in shown]
        named = ", ".join(f"[[{note.link_text}]]" for note in shown)
        passages = []
        for note in shown[:2]:
            excerpt = vault.word_burst_excerpt(note, finding.term)
            if excerpt:
                passages.append(f"[[{note.link_text}]]: “{excerpt}”")
        wording = " Current passages: " + "; ".join(passages) + "." if passages else ""
        if finding.direction == "declining":
            if finding.reference is None:
                continue
            rate, reference_rate = percentage_pair(finding.prevalence, finding.reference)
            comparison = (
                f"compared with {reference_rate} during the earlier period "
                f"{finding.reference_start} to {finding.reference_end}"
            )
            question = (
                f"Could the earlier use in {named} offer a useful lens for what you are "
                "working on now, or has this language done its work?"
            )
        else:
            rate, baseline_rate = percentage_pair(finding.prevalence, finding.baseline)
            comparison = f"compared with {baseline_rate} across the window"
            question = (
                f"What changes if you read {named} beside one another through ‘{finding.term}’?"
            )
        text = (
            f"From {finding.start} to {finding.end}, ‘{finding.term}’ appeared in "
            f"{rate} of observations, {comparison}, "
            f"using {population}{qualification}.{wording} {question}"
        )
        suggestions.append(
            Suggestion(
                text=text,
                notes=list(dict.fromkeys([*shown_links, *links]))[:MAX_SUGGESTION_NOTES],
                geist_id="word_burst",
                evidence_key=interval_evidence_key(
                    ["word_burst", finding.history_mode, finding.direction, finding.term],
                    finding.start,
                    finding.end,
                ),
            )
        )
    return suggestions
