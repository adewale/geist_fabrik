"""Seasonal Topic Analysis geist.

Demonstrates TemporalSemanticQuery abstraction (Phase 5).
Finds topics that appear seasonally by analyzing notes created in specific
time periods with semantic similarity.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from geistfabrik.models import Suggestion
from geistfabrik.temporal_analysis import TemporalSemanticQuery

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

# Season start (month, day), Northern Hemisphere; each season ends where the
# next one starts, so winter runs from December 21 into the following year.
_SEASON_STARTS = (("winter", 12, 21), ("spring", 3, 21), ("summer", 6, 21), ("fall", 9, 21))


def _latest_season_windows(today: datetime) -> dict[str, tuple[datetime, datetime]]:
    """Each season's most recent occurrence that began on or before ``today``.

    Returns name -> (start, end), end inclusive to the last microsecond of the
    season's final day. A December 21+ session is in the winter that runs into
    the following year; earlier sessions look back to the previous winter.
    """
    windows: dict[str, tuple[datetime, datetime]] = {}
    for name, month, day in _SEASON_STARTS:
        start = datetime(today.year, month, day)
        if start > today:
            start = start.replace(year=today.year - 1)
        next_month = month % 12 + 3
        next_year = start.year + 1 if month == 12 else start.year
        next_start = datetime(next_year, next_month, day)
        windows[name] = (start, next_start - timedelta(microseconds=1))
    return windows


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with seasonal patterns in creation and similarity.

    Uses TemporalSemanticQuery to find notes created in specific seasons
    that are semantically similar, suggesting seasonal thinking patterns.
    """
    notes = vault.notes()

    if len(notes) < 20:
        return []

    # Initialize temporal-semantic query helper
    tsq = TemporalSemanticQuery(vault)

    seasons = _latest_season_windows(vault.session.date)

    suggestions = []

    # Try to find seasonal clusters for each season
    for season_name, (start_date, end_date) in seasons.items():
        # Get notes created in this season
        seasonal_notes = [n for n in notes if start_date <= n.created <= end_date]

        if len(seasonal_notes) < 3:
            continue

        # Pick a representative note from the season
        anchor = vault.sample(seasonal_notes, count=1)[0]

        # Find other notes in the same season that are similar to the anchor
        similar_in_season = tsq.notes_created_similar_to(
            anchor=anchor,
            start_date=start_date,
            end_date=end_date,
            min_similarity=0.60,
        )

        if len(similar_in_season) >= 2:
            # Found a seasonal pattern!
            note_titles = [f"[[{n.link_text}]]" for n in similar_in_season[:3]]
            pattern_text = ", ".join(note_titles)

            suggestions.append(
                Suggestion(
                    text=(
                        f"In {season_name} {start_date.year}, you explored "
                        f"related ideas: {pattern_text}. "
                        f"What seasonal pattern might this reflect?"
                    ),
                    notes=[n.link_text for n in similar_in_season[:3]],
                    geist_id="seasonal_topic_analysis",
                )
            )

    # Limit to 2 suggestions to avoid overwhelming
    return vault.sample(suggestions, count=min(2, len(suggestions)))
