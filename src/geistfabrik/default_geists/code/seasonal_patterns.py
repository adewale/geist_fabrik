"""Seasonal Patterns geist - discovers rhythmic thinking patterns.

Identifies topics, themes, or types of notes that recur seasonally or at
specific times of year, revealing cyclical patterns in thinking.

Two independent analyses feed the same geist:
1. Recurring month themes - months whose notes are semantically coherent,
   with similar notes recurring across different years. The evidence is one
   similar cross-year pair, so the text names that pair rather than claiming
   the theme recurs "consistently".
2. Seasonal tag concentration - tags used predominantly in one season, and
   far more often there than the season's share of all notes (a tag is not
   "seasonal" just because most of the vault was written in that season).
   Tagged examples must span at least two occurrences of that season; one
   imported or backdated batch is not evidence of recurrence.
"""

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext
from geistfabrik.similarity_analysis import SimilarityLevel
from geistfabrik.temporal_analysis import get_season

# A seasonal tag's in-season share must be at least this many times the
# season's share of all notes.
MIN_TAG_LIFT = 1.5

MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def _season_year(when: datetime) -> int:
    """Label each northern-hemisphere winter by its January/February year.

    December and the following January are one winter, not cross-year
    recurrence. For the other seasons the calendar year is unambiguous.
    """
    return when.year + (when.month == 12)


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find seasonal and cyclical thinking patterns.

    Returns:
        List of suggestions highlighting rhythmic patterns
    """
    notes = vault.notes()

    if len(notes) < 50:  # Need enough notes to detect patterns
        return []

    suggestions = _recurring_month_themes(vault, notes)
    suggestions.extend(_seasonal_tag_concentration(vault, notes))

    return vault.sample(suggestions, count=2)


def _recurring_month_themes(vault: "VaultContext", notes: list["Note"]) -> list["Suggestion"]:
    """Months whose notes cohere semantically, with themes recurring across years."""
    from geistfabrik import Suggestion

    suggestions: list[Suggestion] = []

    # Group notes by month
    months = defaultdict(list)
    for note in notes:
        months[note.created.month].append(note)

    # Find months with distinctive semantic clusters
    month_profiles = []

    for month_num, month_notes in months.items():
        if len(month_notes) < 5:
            continue

        # Calculate average intra-month similarity
        sample = vault.sample(month_notes, min(10, len(month_notes)))

        if len(sample) > 1:
            avg_similarity = vault.mean_similarity(sample)
            month_profiles.append((month_num, month_notes, avg_similarity))

    # Find months with high internal coherence (seasonal themes)
    month_profiles.sort(key=lambda x: x[2], reverse=True)

    if len(month_profiles) < 2:
        return suggestions

    # Check if the same themes recur across years
    top_month_num, top_month_notes, _top_coherence = month_profiles[0]

    # Sample notes from this month across different years
    years_represented = defaultdict(list)
    for note in top_month_notes:
        years_represented[note.created.year].append(note)

    # If we have notes from this month across multiple years, check for recurrence
    if len(years_represented) < 2:
        return suggestions

    # Sample from different years
    year_samples = []
    for year, year_notes in years_represented.items():
        if year_notes:
            sampled = vault.sample(year_notes, min(2, len(year_notes)))
            year_samples.extend([(year, n) for n in sampled])

    if len(year_samples) < 3:
        return suggestions

    # Check if notes from different years but same month are similar:
    # collect cross-year pairs, then batch compute similarities.
    cross_year_pairs = []
    for i, (year1, note1) in enumerate(year_samples):
        for year2, note2 in year_samples[i + 1 :]:
            if year1 != year2:  # Different years
                cross_year_pairs.append((note1, note2))

    cross_year_sims = []
    if cross_year_pairs:
        notes1 = [pair[0] for pair in cross_year_pairs]
        notes2 = [pair[1] for pair in cross_year_pairs]
        similarities = vault.paired_similarity(notes1, notes2)

        for i, (note1, note2) in enumerate(cross_year_pairs):
            sim = similarities[i]
            cross_year_sims.append((note1, note2, sim))

    if not cross_year_sims:
        return suggestions

    cross_year_sims.sort(key=lambda x: x[2], reverse=True)
    note1, note2, similarity = cross_year_sims[0]

    if similarity > SimilarityLevel.HIGH:
        month_name = MONTH_NAMES[top_month_num - 1]
        if note2.created.year < note1.created.year:
            note1, note2 = note2, note1
        year1 = note1.created.year
        year2 = note2.created.year
        gap = year2 - year1

        text = (
            f"You came back to similar themes in {month_name}—"
            f"[[{note1.link_text}]] ({year1}) and "
            f"[[{note2.link_text}]] ({year2}) are semantically similar "
            f"despite being {gap} year{'' if gap == 1 else 's'} apart. Seasonal "
            f"thinking rhythm?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=[note1.link_text, note2.link_text],
                geist_id="seasonal_patterns",
            )
        )

    return suggestions


def _seasonal_tag_concentration(vault: "VaultContext", notes: list["Note"]) -> list["Suggestion"]:
    """Tags that appear predominantly in a single season."""
    from geistfabrik import Suggestion

    suggestions: list[Suggestion] = []

    season_tags = defaultdict(list)
    for note in notes:
        season_tags[get_season(note.created)].append(note)

    # Find tags that appear predominantly in one season
    for season, season_notes in season_tags.items():
        if len(season_notes) < 10:
            continue

        # Find common tags in this season
        tag_counts: defaultdict[str, int] = defaultdict(int)
        for note in season_notes:
            for tag in note.tags:
                tag_counts[tag] += 1

        # Find tags that appear frequently in this season
        for tag, count in tag_counts.items():
            if count >= 5:
                # Check how often this tag appears in other seasons
                total_with_tag = sum(1 for n in notes if tag in n.tags)
                season_ratio = count / total_with_tag if total_with_tag > 0 else 0
                # Base rate: the season's share of all notes
                lift = season_ratio / (len(season_notes) / len(notes))

                # 60% of this tag appears in one season, well above base rate
                tagged_by_year: defaultdict[int, list[Note]] = defaultdict(list)
                for note in season_notes:
                    if tag in note.tags:
                        tagged_by_year[_season_year(note.created)].append(note)

                if season_ratio > 0.6 and lift >= MIN_TAG_LIFT and len(tagged_by_year) >= 2:
                    # The linked evidence must demonstrate the recurrence,
                    # rather than randomly showing only one year's batch.
                    years = vault.sample(list(tagged_by_year), count=2)
                    sample_notes = [
                        vault.sample(tagged_by_year[year], count=1)[0] for year in years
                    ]
                    sampled_paths = {note.path for note in sample_notes}
                    remaining = [
                        note
                        for year_notes in tagged_by_year.values()
                        for note in year_notes
                        if note.path not in sampled_paths
                    ]
                    sample_notes.extend(vault.sample(remaining, count=1))
                    note_names = ", ".join([f"[[{n.link_text}]]" for n in sample_notes])

                    text = (
                        f"#{tag} appears predominantly in notes dated in {season.lower()} "
                        f"({count} out of {total_with_tag} notes), across "
                        f"{len(tagged_by_year)} {season.lower()} seasons. "
                        f"Examples: {note_names}. Recurring interest?"
                    )

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[n.link_text for n in sample_notes],
                            geist_id="seasonal_patterns",
                        )
                    )

    return suggestions
