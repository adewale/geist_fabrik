"""Self and other geist - contrasts "I" notes with "we" notes.

A reflective lens over pronoun voice: notes written almost entirely in
the first person singular reveal solitary thinking, while "we" notes
reveal thinking done with others. This geist surfaces the contrast and
asks when you think alone and when you think together.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with contrasting pronoun patterns.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion contrasting "I" notes with "we" notes
    """
    notes = vault.notes_excluding_journal()
    i_notes = [n for n in notes if vault.metadata(n).get("self_focus_ratio", 0.5) > 0.85]
    we_notes = [n for n in notes if vault.metadata(n).get("first_person_plural", 0) > 2.0]

    if len(i_notes) < 2:
        return []

    i_sample = vault.sample(i_notes, min(3, len(i_notes)))
    i_titles = ", ".join(f"[[{n.obsidian_link}]]" for n in i_sample)

    if we_notes:
        we_sample = vault.sample(we_notes, min(2, len(we_notes)))
        we_titles = ", ".join(f"[[{n.obsidian_link}]]" for n in we_sample)
        return [
            Suggestion(
                text=(
                    f"These notes say 'I': {i_titles}. "
                    f"These notes say 'we': {we_titles}. "
                    f"When do you think alone, and when do you think with others?"
                ),
                notes=[n.obsidian_link for n in i_sample + we_sample],
                geist_id="self_and_other",
            )
        ]

    return [
        Suggestion(
            text=(
                f"These notes are all 'I': {i_titles}. "
                f"You have no 'we' notes. Who could you be thinking with?"
            ),
            notes=[n.obsidian_link for n in i_sample],
            geist_id="self_and_other",
        )
    ]
