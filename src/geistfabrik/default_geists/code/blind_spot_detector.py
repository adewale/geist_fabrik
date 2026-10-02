"""Blind Spot Detector - Identify semantic gaps in your vault.

This geist finds what your vault ISN'T about by comparing recent notes
to their semantic opposites. If you've been writing about certain topics
but their contrarian perspectives are sparse or old, it suggests blind spots
in your thinking.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import VaultContext

from geistfabrik import Suggestion

# A contrarian shorter than this is treated as a stub, not a perspective
MIN_CONTRARIAN_WORDS = 50
# A contrarian untouched for longer than this counts as neglected
STALE_DAYS = 180


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find blind spots by identifying underexplored semantic opposites.

    Args:
        vault: VaultContext with access to vault data

    Returns:
        List of suggestions about potential blind spots
    """
    suggestions = []

    # Get recent notes to understand current focus
    recent = vault.recent_notes(count=5)
    if len(recent) < 2:
        return []

    # For each recent note, find its semantic opposite
    for note in recent[:3]:  # Check top 3 recent notes
        # Get contrarian note titles (contrarian_to returns List[str])
        contrarian_titles = vault.call_function("contrarian_to", note.title, 10)

        if not contrarian_titles:
            continue

        # Check if contrarian notes are sparse or old
        # Take the most contrarian note that still resolves
        for contrarian_title in contrarian_titles:
            # contrarian_to returns bracketed links ("[[Title]]"); strip the
            # brackets and resolve by title/path. (Passing the bracketed
            # string to get_note() - an exact-path lookup - always returned
            # None, which left this geist permanently inert.)
            contrarian = vault.resolve_link_target(contrarian_title.strip("[]"))
            if contrarian is None:
                continue

            metadata = vault.metadata(contrarian)

            # The least-similar note in a mixed vault is often a near-empty
            # stub; a stub is not a perspective, so look further down the list.
            if metadata.get("word_count", 0) < MIN_CONTRARIAN_WORDS:
                continue

            # Check if it's a blind spot (old or rarely linked)
            days_old = metadata.get("days_since_modified", 0)
            backlink_count = len(vault.backlinks(contrarian))

            # Name only the condition(s) that actually triggered
            reasons = []
            if days_old > STALE_DAYS:
                reasons.append(f"it's been {days_old} days since you touched it")
            if backlink_count == 0:
                reasons.append("no other note links to it")

            if reasons:
                # This is a potential blind spot
                text = (
                    f"You've been writing about [[{note.link_text}]] lately. "
                    f"[[{contrarian.link_text}]] seems like the opposite perspective, "
                    f"but {' and '.join(reasons)}. "
                    f"What perspectives are you missing?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.link_text, contrarian.link_text],
                        geist_id="blind_spot_detector",
                    )
                )

            # Only the most contrarian substantial note is considered
            break

    # Limit to 2 suggestions to avoid overwhelming
    return vault.sample(suggestions, min(2, len(suggestions)))
