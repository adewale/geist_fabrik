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


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find blind spots by identifying underexplored semantic opposites.

    Args:
        vault: VaultContext with access to vault data

    Returns:
        List of suggestions about potential blind spots
    """
    suggestions = []

    # Get recent notes to understand current focus
    # recent_notes() includes geist-journal output; session notes are not
    # "current focus", so drop them before analysing.
    recent = [n for n in vault.recent_notes(count=10) if not n.path.startswith("geist journal/")][
        :5
    ]
    if len(recent) < 2:
        return []

    # For each recent note, find its semantic opposite
    for note in recent[:3]:  # Check top 3 recent notes
        # Get contrarian note titles (contrarian_to returns List[str])
        contrarian_titles = vault.call_function("contrarian_to", note.title, 3)

        if not contrarian_titles:
            continue

        # Check if contrarian notes are sparse or old
        for contrarian_title in contrarian_titles[:1]:  # Take the most contrarian
            # contrarian_to returns bracketed links ("[[Title]]"); strip the
            # brackets and resolve by title/path. (Passing the bracketed
            # string to get_note() - an exact-path lookup - always returned
            # None, which left this geist permanently inert.)
            contrarian = vault.resolve_link_target(contrarian_title.strip("[]"))
            if contrarian is None or contrarian.path.startswith("geist journal/"):
                continue

            metadata = vault.metadata(contrarian)

            # Check if it's a blind spot (old or rarely linked)
            days_old = metadata.get("days_since_modified", 0)
            backlink_count = len(vault.backlinks(contrarian))

            if days_old > 180 or backlink_count == 0:
                # This is a potential blind spot
                text = (
                    f"You've been writing about [[{note.link_text}]] lately. "
                    f"[[{contrarian.link_text}]] seems like the opposite perspective, "
                    f"but it's been {days_old} days since you touched it. "
                    f"What perspectives are you missing?"
                )

                suggestions.append(
                    Suggestion(
                        text=text,
                        notes=[note.link_text, contrarian.link_text],
                        geist_id="blind_spot_detector",
                    )
                )

                # Only one suggestion per recent note
                break

    # Limit to 2 suggestions to avoid overwhelming
    return vault.sample(suggestions, min(2, len(suggestions)))
