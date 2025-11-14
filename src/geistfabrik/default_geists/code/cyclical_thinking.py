"""Cyclical Thinking geist - detects notes that cycle through semantic states.

Demonstrates the power of temporal_analysis.py abstractions. Uses
TemporalPatternFinder to detect notes that return to previous semantic
states over time, revealing cyclical thought patterns and recurring themes.

This geist showcases how pattern finding enables sophisticated temporal
analysis with just a few lines of code.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Detect notes that cycle through semantic states over sessions.

    Returns:
        List of 1-2 suggestions showing cyclical thinking patterns
    """
    from geistfabrik import Suggestion
    from geistfabrik.temporal_analysis import TemporalPatternFinder

    # Need multiple sessions for cycle detection
    cursor = vault.db.execute("SELECT COUNT(*) FROM sessions")
    session_count = cursor.fetchone()[0]

    if session_count < 6:  # Need at least 6 sessions for 2 cycles
        return []

    notes = vault.notes()
    finder = TemporalPatternFinder(vault)

    # Find notes with cyclical patterns
    cycling_notes = finder.find_cycling_notes(notes, min_cycles=2)

    if not cycling_notes:
        return []

    suggestions = []

    # Create suggestions for cycling notes
    for note in cycling_notes[:5]:  # Limit to 5 for sampling
        # Get session dates for context
        cursor = vault.db.execute(
            """
            SELECT s.date
            FROM session_embeddings se
            JOIN sessions s ON se.session_id = s.session_id
            WHERE se.note_path = ?
            ORDER BY s.date ASC
            """,
            (note.path,),
        )
        sessions = cursor.fetchall()

        if len(sessions) >= 3:
            first_date = sessions[0][0].strftime("%Y-%m")
            last_date = sessions[-1][0].strftime("%Y-%m")

            text = (
                f"[[{note.obsidian_link}]] shows cyclical thinking—"
                f"returning to similar semantic states across sessions "
                f"({first_date} to {last_date}). "
                f"What recurring theme keeps drawing you back?"
            )

            suggestions.append(
                Suggestion(
                    text=text,
                    notes=[note.obsidian_link],
                    geist_id="cyclical_thinking",
                )
            )

    # Return top 2 cyclical patterns
    return vault.sample(suggestions, k=min(2, len(suggestions)))
