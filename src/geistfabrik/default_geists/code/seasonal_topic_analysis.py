"""Seasonal Topic Analysis geist.

Demonstrates TemporalSemanticQuery abstraction (Phase 5).
Looks at the most recent occurrence of each season and, when an anchor note
from that season has closely related companions written in the same season,
names the anchor and its two closest companions as a thread of thought.

It does not compare seasons across years, so the text recalls a thread from
that season rather than claiming a seasonal pattern. Seasons are the
meteorological ones of temporal_analysis.get_season() (winter = Dec-Feb), as
in seasonal_revisit and seasonal_patterns, so a note's season agrees across
the seasonal geists.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from geistfabrik.models import Suggestion
from geistfabrik.temporal_analysis import TemporalSemanticQuery, get_season

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext

# First month of each season, as get_season() defines them (Northern
# Hemisphere); each season ends where the next one starts, so winter runs
# from December 1 into the following year.
_SEASON_START_MONTHS = (12, 3, 6, 9)
MIN_SIMILARITY = 0.60


def _latest_season_windows(today: datetime) -> dict[str, tuple[datetime, datetime]]:
    """Each season's most recent occurrence that began on or before ``today``.

    Returns label -> (start, end), end inclusive to the last microsecond of the
    season's final day. Winter is labelled with both years it spans
    ("winter 2023-24"); a December session is in the winter that runs into the
    following year, earlier sessions look back to the previous winter.
    """
    windows: dict[str, tuple[datetime, datetime]] = {}
    for month in _SEASON_START_MONTHS:
        start = datetime(today.year, month, 1)
        if start > today:
            start = start.replace(year=today.year - 1)
        next_month = month % 12 + 3
        next_year = start.year + 1 if month == 12 else start.year
        end = datetime(next_year, next_month, 1) - timedelta(microseconds=1)
        name = get_season(start).lower()
        if month == 12:
            label = f"{name} {start.year}-{(start.year + 1) % 100:02d}"
        else:
            label = f"{name} {start.year}"
        windows[label] = (start, end)
    return windows


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find a thread of closely related notes written within one season.

    Uses TemporalSemanticQuery to find notes created in the same season that
    are semantically similar to a sampled anchor note from that season.
    """
    notes = vault.notes()

    if len(notes) < 20:
        return []

    # Initialize temporal-semantic query helper
    tsq = TemporalSemanticQuery(vault)

    seasons = _latest_season_windows(vault.session.date)

    suggestions = []

    # Try to find seasonal clusters for each season
    for label, (start_date, end_date) in seasons.items():
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
            min_similarity=MIN_SIMILARITY,
        )

        if len(similar_in_season) >= 2:
            # The anchor and its two closest companions (not the first two in
            # vault order)
            companions = sorted(
                similar_in_season, key=lambda n: (-vault.similarity(anchor, n), n.path)
            )[:2]
            thread = [anchor, *companions]
            pattern_text = ", ".join(f"[[{n.link_text}]]" for n in thread)

            suggestions.append(
                Suggestion(
                    text=(
                        f"In {label}, you wrote closely related notes: {pattern_text}. "
                        f"Is that thread still alive?"
                    ),
                    notes=[n.link_text for n in thread],
                    geist_id="seasonal_topic_analysis",
                )
            )

    # Limit to 2 suggestions to avoid overwhelming
    return vault.sample(suggestions, count=min(2, len(suggestions)))
