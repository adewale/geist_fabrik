"""Sentence variance geist - surfaces notes with choppy sentence structure.

A reflective lens over rhythm: a note whose sentence lengths swing
between short bursts and long stretches often records thinking-in-
progress — working something out on the page rather than presenting a
finished thought. This geist finds the statistical outlier.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

from geistfabrik.models import Suggestion


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find the note with unusually choppy sentence structure.

    Compares each note's sentence-length variance against the vault-wide
    distribution and surfaces the strongest outlier (> mean + 2 std).
    Requires at least 10 substantial notes for the statistics to mean
    anything.

    Args:
        vault: The vault context providing access to notes and utilities

    Returns:
        At most one suggestion naming the choppiest note
    """
    note_variances = []

    for note in vault.notes_excluding_journal():
        voice = vault.voice(note)
        variance = voice.sentence_length_variance
        mean_len = voice.mean_sentence_length

        if mean_len > 5:  # Ignore very short notes
            note_variances.append((note, variance))

    if len(note_variances) < 10:
        return []

    # Find statistical outliers
    values = [v for _, v in note_variances]
    mean_var = sum(values) / len(values)
    std_var = (sum((v - mean_var) ** 2 for v in values) / len(values)) ** 0.5

    outliers = [(n, v) for n, v in note_variances if v > mean_var + 2 * std_var]
    if not outliers:
        return []

    note, _variance = max(outliers, key=lambda x: x[1])

    return [
        Suggestion(
            text=(
                f"[[{note.obsidian_link}]] has unusually choppy sentences — "
                f"short bursts mixed with long stretches. "
                f"Were you working something out when you wrote this?"
            ),
            notes=[note.obsidian_link],
            geist_id="sentence_variance",
        )
    ]
