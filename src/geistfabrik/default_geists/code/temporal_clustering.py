"""Temporal Clustering geist - threads of closely related notes within a season.

Looks at the most recent occurrence of each season and, when a sampled anchor
note from that season has closely related companions written in the same
season, names the anchor and its two closest companions as a thread of
thought.

Only when two seasons both hold a thread does it compare them, and it claims a
thread continued across seasons only when it measured that: the mean
similarity between the notes of one thread and the notes of the other must
reach MIN_SIMILARITY. Seasons are the meteorological ones of temporal_analysis.get_season()
(winter = Dec-Feb), as in this_time_last_year and seasonal_patterns, so a
note's season agrees across the seasonal geists.

(Absorbs the former seasonal_topic_analysis geist, which demonstrated the
TemporalSemanticQuery abstraction.)
"""

from datetime import datetime, timedelta
from itertools import combinations
from typing import TYPE_CHECKING

from geistfabrik.models import Suggestion
from geistfabrik.temporal_analysis import TemporalSemanticQuery, get_season

if TYPE_CHECKING:
    from geistfabrik.models import Note
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


def _links(thread: list["Note"]) -> str:
    return ", ".join(f"[[{n.link_text}]]" for n in thread)


def _cross_similarity(vault: "VaultContext", a: list["Note"], b: list["Note"]) -> float:
    """Mean similarity between every note of thread ``a`` and every note of ``b``."""
    matrix = vault.batch_similarity(a, b)
    return float(matrix.mean())


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find threads of closely related notes written within one season.

    Uses TemporalSemanticQuery to find notes created in the same season that
    are semantically similar to a sampled anchor note from that season.
    """
    notes = vault.notes()

    if len(notes) < 20:
        return []

    tsq = TemporalSemanticQuery(vault)

    # label -> (season start, anchor + two closest companions)
    threads: dict[str, tuple[datetime, list[Note]]] = {}
    today = vault.session.date
    for label, (start_date, season_end) in _latest_season_windows(today).items():
        # The current season is not over: notes dated after the session date
        # (a --date replay) have not been written yet.
        end_date = min(season_end, today)
        seasonal_notes = [n for n in notes if start_date <= n.created <= end_date]

        if len(seasonal_notes) < 3:
            continue

        anchor = vault.sample(seasonal_notes, count=1)[0]
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
            threads[label] = (start_date, [anchor, *companions])

    suggestions = [
        Suggestion(
            text=(
                f"In {label}, you wrote closely related notes: {_links(thread)}. "
                f"Is that thread still alive?"
            ),
            notes=[n.link_text for n in thread],
            geist_id="temporal_clustering",
        )
        for label, (_, thread) in threads.items()
    ]

    # Cross-season claim, only where measured: the mean similarity between two
    # seasons' threads reaches the threshold a companion needs within a season.
    continuing = []
    for (label_a, (start_a, thread_a)), (label_b, (start_b, thread_b)) in combinations(
        threads.items(), 2
    ):
        if _cross_similarity(vault, thread_a, thread_b) < MIN_SIMILARITY:
            continue
        if start_b < start_a:
            label_a, thread_a, label_b, thread_b = label_b, thread_b, label_a, thread_a
        continuing.append(
            Suggestion(
                text=(
                    f"Your {label_a} thread ({_links(thread_a)}) and your {label_b} "
                    f"thread ({_links(thread_b)}) are closely related to each other too. "
                    f"Is it one line of thought you keep returning to?"
                ),
                notes=[n.link_text for n in thread_a + thread_b],
                geist_id="temporal_clustering",
            )
        )

    if continuing:
        # One measured cross-season link says more than the two separate
        # threads it joins; never offer both views of the same notes.
        return vault.sample(continuing, count=1)

    return vault.sample(suggestions, count=min(2, len(suggestions)))
