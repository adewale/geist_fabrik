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

# A note is an "I" note only when first-person singular is both dominant
# (> 85% of its first-person pronouns) and frequent (>= 1 per 100 words):
# without the rate, one stray "I" in a long technical note qualified it.
I_FOCUS_THRESHOLD = 0.85
I_RATE_THRESHOLD = 1.0
# A "we" note to contrast with: first-person plural > 2 per 100 words.
WE_RATE_THRESHOLD = 2.0
# "Only N of your notes say 'we'" is offered when fewer than 5% do.
RARE_WE_FRACTION = 0.05


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with contrasting pronoun patterns.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion contrasting "I" notes with "we" notes
    """
    notes = vault.notes()
    i_notes = [
        n
        for n in notes
        if (v := vault.voice(n)).self_focus_ratio > I_FOCUS_THRESHOLD
        and v.first_person_singular >= I_RATE_THRESHOLD
    ]

    if len(i_notes) < 2:
        return []

    i_paths = {n.path for n in i_notes}
    we_notes = [
        n
        for n in notes
        if n.path not in i_paths and vault.voice(n).first_person_plural > WE_RATE_THRESHOLD
    ]

    i_sample = vault.sample(i_notes, min(3, len(i_notes)))
    i_titles = ", ".join(f"[[{n.link_text}]]" for n in i_sample)

    if we_notes:
        we_sample = vault.sample(we_notes, min(2, len(we_notes)))
        we_titles = ", ".join(f"[[{n.link_text}]]" for n in we_sample)
        return [
            Suggestion(
                text=(
                    f"These notes say 'I': {i_titles}. "
                    f"These notes say 'we': {we_titles}. "
                    f"When do you think alone, and when do you think with others?"
                ),
                notes=[n.link_text for n in i_sample + we_sample],
                geist_id="self_and_other",
            )
        ]

    # No strong "we" note. Only claim rarity that is true of the whole vault:
    # count every note that says "we"/"us"/"our" at all.
    total = len(notes)
    we_count = sum(1 for n in notes if vault.voice(n).first_person_plural > 0)
    if we_count >= total * RARE_WE_FRACTION:
        return []

    if we_count == 0:
        rarity = f"None of your {total} notes say 'we'."
    else:
        verb = "says" if we_count == 1 else "say"
        rarity = f"Only {we_count} of your {total} notes {verb} 'we' at all."

    return [
        Suggestion(
            text=(f"These notes say 'I': {i_titles}. {rarity} Who could you be thinking with?"),
            notes=[n.link_text for n in i_sample],
            geist_id="self_and_other",
        )
    ]
