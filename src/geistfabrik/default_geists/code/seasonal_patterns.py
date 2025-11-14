"""Seasonal Patterns geist - discovers rhythmic thinking patterns.

Identifies topics, themes, or types of notes that recur seasonally or at
specific times of year, revealing cyclical patterns in thinking.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext
from geistfabrik.similarity_analysis import SimilarityLevel


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find seasonal and cyclical thinking patterns.

    Returns:
        List of suggestions highlighting rhythmic patterns
    """
    from geistfabrik import Suggestion

    suggestions = []

    notes = vault.notes_excluding_journal()

    if len(notes) < 50:  # Need enough notes to detect patterns
        return []

    # Group notes by month
    months = defaultdict(list)
    for note in notes:
        month = note.created.month
        months[month].append(note)

    # Month names for readable output
    month_names = [
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

    # Find months with distinctive semantic clusters
    month_profiles = []

    for month_num, month_notes in months.items():
        if len(month_notes) < 5:
            continue

        # Calculate average intra-month similarity
        sample = vault.sample(month_notes, min(10, len(month_notes)))

        # OPTIMISATION #5: Use batch_similarity for pairwise comparisons
        # Note: batch_similarity() is cache-aware (v0.9+), optimal for matrix operations
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

    if len(month_profiles) >= 2:
        # Check if the same themes recur across years
        top_month_num, top_month_notes, top_coherence = month_profiles[0]

        # Sample notes from this month across different years
        years_represented = defaultdict(list)
        for note in top_month_notes:
            years_represented[note.created.year].append(note)

        # If we have notes from this month across multiple years, check for recurrence
        if len(years_represented) >= 2:
            # Sample from different years
            year_samples = []
            for year, year_notes in years_represented.items():
                if year_notes:
                    sampled = vault.sample(year_notes, min(2, len(year_notes)))
                    year_samples.extend([(year, n) for n in sampled])

            if len(year_samples) >= 3:
                # Check if notes from different years but same month are similar
                # OPTIMISATION #5: Collect cross-year pairs, then batch compute similarities
                # Note: batch_similarity() is cache-aware (v0.9+), optimal for matrix operations
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

                if cross_year_sims:
                    cross_year_sims.sort(key=lambda x: x[2], reverse=True)
                    best_match = cross_year_sims[0]
                    note1, note2, similarity = best_match

                    if similarity > SimilarityLevel.HIGH:
                        month_name = month_names[top_month_num - 1]
                        year1 = note1.created.year
                        year2 = note2.created.year

                        text = (
                            f"You consistently write about similar themes in {month_name}—"
                            f"[[{note1.obsidian_link}]] ({year1}) and "
                            f"[[{note2.obsidian_link}]] ({year2}) are semantically similar "
                            f"despite being {abs(year2 - year1)} years apart. Seasonal "
                            f"thinking rhythm?"
                        )

                        suggestions.append(
                            Suggestion(
                                text=text,
                                notes=[note1.obsidian_link, note2.obsidian_link],
                                geist_id="seasonal_patterns",
                            )
                        )

    # Also check for seasonal tag patterns
    season_tags = defaultdict(list)
    for note in notes:
        month = note.created.month
        season = _get_season(month)
        season_tags[season].append(note)

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
                    sample_notes = vault.sample([n for n in season_notes if tag in n.tags], k=3)
                    note_names = ", ".join([f"[[{n.obsidian_link}]]" for n in sample_notes])

                    text = (
                        f"You write about #{tag} predominantly in {season.lower()} "
                        f"({count} out of {total_with_tag} notes). "
                        f"Examples: {note_names}. Rhythmic interest?"
                    )

                    suggestions.append(
                        Suggestion(
                            text=text,
                            notes=[n.obsidian_link for n in sample_notes],
                            geist_id="seasonal_patterns",
                        )
                    )

    return vault.sample(suggestions, k=2)


def _get_season(month: int) -> str:
    """Map month number to season."""
    if month in [12, 1, 2]:
        return "Winter"
    elif month in [3, 4, 5]:
        return "Spring"
    elif month in [6, 7, 8]:
        return "Summer"
    else:
        return "Autumn"
