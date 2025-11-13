"""Seasonal Topic Analysis geist.

Demonstrates TemporalSemanticQuery abstraction (Phase 5).
Finds topics that appear seasonally by analyzing notes created in specific
time periods with semantic similarity.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from geistfabrik.models import Suggestion
from geistfabrik.temporal_analysis import TemporalSemanticQuery

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with seasonal patterns in creation and similarity.

    Uses TemporalSemanticQuery to find notes created in specific seasons
    that are semantically similar, suggesting seasonal thinking patterns.
    """
    # Exclude geist journal to avoid analyzing session output
    all_notes = vault.notes()
    notes = [n for n in all_notes if not n.path.startswith("geist journal/")]

    if len(notes) < 20:
        return []

    # Initialize temporal-semantic query helper
    tsq = TemporalSemanticQuery(vault)

    # Define seasons (Northern Hemisphere)
    current_date = vault.session.date
    current_year = current_date.year

    # Winter wraps across year boundary: determine which year's winter based on current month
    winter_year = current_year if current_date.month >= 3 else current_year - 1

    seasons = {
        "winter": (datetime(winter_year, 12, 21), datetime(winter_year + 1, 3, 20)),
        "spring": (datetime(current_year, 3, 21), datetime(current_year, 6, 20)),
        "summer": (datetime(current_year, 6, 21), datetime(current_year, 9, 20)),
        "fall": (datetime(current_year, 9, 21), datetime(current_year, 12, 20)),
    }

    suggestions = []

    # Try to find seasonal clusters for each season
    for season_name, (start_date, end_date) in seasons.items():
        # Get notes created in this season (excluding geist journal)
        seasonal_notes = [
            n for n in notes if start_date <= n.created <= end_date
        ]

        if len(seasonal_notes) < 3:
            continue

        # Pick a representative note from the season
        anchor = vault.sample(seasonal_notes, k=1)[0]

        # Find other notes in the same season that are similar to the anchor
        similar_in_season = tsq.notes_created_similar_to(
            anchor=anchor,
            start_date=start_date,
            end_date=end_date,
            min_similarity=0.60,
        )

        # Filter out geist journal from results (query uses all vault notes)
        similar_in_season = [
            n for n in similar_in_season if not n.path.startswith("geist journal/")
        ]

        if len(similar_in_season) >= 2:
            # Found a seasonal pattern!
            note_titles = [f"[[{n.obsidian_link}]]" for n in similar_in_season[:3]]
            pattern_text = ", ".join(note_titles)

            suggestions.append(
                Suggestion(
                    text=(
                        f"In {season_name} {start_date.year}, you explored "
                        f"related ideas: {pattern_text}. "
                        f"What seasonal pattern might this reflect?"
                    ),
                    notes=[n.title for n in similar_in_season[:3]],
                    geist_id="seasonal_topic_analysis",
                )
            )

    # Limit to 2 suggestions to avoid overwhelming
    return vault.sample(suggestions, k=min(2, len(suggestions)))
