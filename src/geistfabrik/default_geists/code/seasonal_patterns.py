"""Seasonal Patterns geist - discovers rhythmic thinking patterns.

Identifies topics, themes, or types of notes that recur seasonally or at
specific times of year, revealing cyclical patterns in thinking.

Two independent analyses feed the same geist:
1. Recurring month themes - months whose notes are semantically coherent,
   with similar notes recurring across different years.
2. Seasonal tag concentration - tags used predominantly in one season.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext
from geistfabrik.similarity_analysis import SimilarityLevel
from geistfabrik.temporal_analysis import get_season

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


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find seasonal and cyclical thinking patterns.

    Returns:
        List of suggestions highlighting rhythmic patterns
    """
    notes = vault.notes_excluding_journal()

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

        # batch_similarity() is cache-aware, optimal for matrix operations
        if len(sample) > 1:
            sim_matrix = vault.batch_similarity(sample, sample)
            # Extract upper triangle (avoid diagonal and duplicates)
            similarities = []
            for i in range(len(sample)):
                for j in range(i + 1, len(sample)):
                    similarities.append(sim_matrix[i, j])

            avg_similarity = sum(similarities) / len(similarities)
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
        sim_matrix = vault.batch_similarity(notes1, notes2)

        for i, (note1, note2) in enumerate(cross_year_pairs):
            sim = sim_matrix[i, i]  # Diagonal for pairwise similarities
            cross_year_sims.append((note1, note2, sim))

    if not cross_year_sims:
        return suggestions

    cross_year_sims.sort(key=lambda x: x[2], reverse=True)
    note1, note2, similarity = cross_year_sims[0]

    if similarity > SimilarityLevel.HIGH:
        month_name = MONTH_NAMES[top_month_num - 1]
        year1 = note1.created.year
        year2 = note2.created.year

        text = (
            f"You consistently write about similar themes in {month_name}—"
            f"[[{note1.link_text}]] ({year1}) and "
            f"[[{note2.link_text}]] ({year2}) are semantically similar "
            f"despite being {abs(year2 - year1)} years apart. Seasonal "
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

                if season_ratio > 0.6:  # 60% of this tag appears in one season
                    sample_notes = vault.sample([n for n in season_notes if tag in n.tags], count=3)
                    note_names = ", ".join([f"[[{n.link_text}]]" for n in sample_notes])

                    text = (
                        f"You write about #{tag} predominantly in {season.lower()} "
                        f"({count} out of {total_with_tag} notes). "
                        f"Examples: {note_names}. Rhythmic interest?"
                    )

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[n.link_text for n in sample_notes],
                            geist_id="seasonal_patterns",
                        )
                    )

    return suggestions
