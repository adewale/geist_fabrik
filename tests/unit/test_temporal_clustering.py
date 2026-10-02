"""Tests for the temporal_clustering geist.

Trigger: >= 20 non-journal notes; notes are grouped into eight consecutive
90-day windows ending at the session date (2 years). A window with >= 5 notes
whose (sampled) average pairwise similarity is > 0.5 is a coherent period.
With >= 2 coherent periods, ONE suggestion contrasts the two most coherent,
naming 3 notes from each.

Session 2024-03-15 windows: #0 2023-12-16..2024-03-15, #1 2023-09-17..
2023-12-16, #2 2023-06-19..2023-09-17, ... #7 ends 2022-03-26.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import temporal_clustering
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

WINTER, AUTUMN, SUMMER = datetime(2024, 2, 1), datetime(2023, 11, 1), datetime(2023, 8, 1)
LONG_AGO = datetime(2021, 6, 1)  # outside the 2-year horizon

# Each note is "<theme words> <one unique word>" under a "<Theme> i" title, so
# notes of one period share all but one word: pairwise similarity 8/9 = 0.89
# (garden), 7/8 = 0.88 (rocket), 2/3 = 0.67 (violin).
THEMES = {
    "Garden": "gardens soil compost mulch seeds worms rain",
    "Rocket": "rockets orbit fuel launch booster payload",
    "Violin": "rosin",
}


def _unique(prefix: str, i: int) -> str:
    return " ".join(f"{prefix}{i}{suffix}" for suffix in ("alpha", "bravo", "charlie"))


def _vault(
    root: Path, periods: list[tuple[str, datetime, int]], *, scattered: int = 0
) -> VaultContext:
    """``periods``: (theme, created, count) coherent groups; plus ``scattered``
    notes with unique vocabulary created in the SUMMER window."""
    builder = VaultBuilder(root)
    for theme, created, count in periods:
        for i in range(count):
            builder.note(f"{theme} {i}", f"{THEMES[theme]} {theme.lower()}{i}x", created=created)
    for i in range(scattered):
        builder.note(f"Scattered {i}", _unique("scatter", i), created=SUMMER)
    return builder.build()


def test_temporal_clustering_contrasts_two_coherent_periods(tmp_path):
    # Trigger arithmetic: 6 garden notes in window #0 and 6 rocket notes in
    # window #1 are coherent (> 0.5); 8 scattered notes (~0) in window #2 are
    # not. 20 notes in total.
    ctx = _vault(tmp_path, [("Garden", WINTER, 6), ("Rocket", AUTUMN, 6)], scattered=8)

    suggestions = temporal_clustering.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "temporal_clustering",
        must_reference=["Garden", "Rocket"],
        must_not_reference=["geist journal", "Scattered"],
    )
    [suggestion] = suggestions
    assert len(suggestion.notes) == 6
    assert sum(ref.startswith("Garden") for ref in suggestion.notes) == 3
    assert sum(ref.startswith("Rocket") for ref in suggestion.notes) == 3


def test_temporal_clustering_labels_periods_by_their_dates(tmp_path):
    """Regression: windows were labelled "Q{i % 4 + 1}-{year}" by their index,
    so November 2023 notes (window #1) were called "Q2-2023". Labels name the
    months each window spans."""
    ctx = _vault(tmp_path, [("Garden", WINTER, 6), ("Rocket", AUTUMN, 6)], scattered=8)

    [suggestion] = temporal_clustering.suggest(ctx)

    assert suggestion.text.startswith("Your Dec 2023 to Mar 2024 notes hang together semantically")
    assert "and so do your Sep 2023 to Dec 2023 notes" in suggestion.text
    assert "Q2-2023" not in suggestion.text


def test_temporal_clustering_does_not_claim_periods_are_separate(tmp_path):
    """Contract: the text claims only what is measured: each period is
    internally cohesive. It never says the periods are separate.

    Regression: it said one period formed "a distinct semantic cluster ...
    separate from" the other, but never compared the two periods. Here both
    periods are about the same theme, so "separate" would be false.
    """
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        builder.note(f"Garden {i}", f"{THEMES['Garden']} garden{i}x", created=WINTER)
        builder.note(f"Garden Again {i}", f"{THEMES['Garden']} again{i}x", created=AUTUMN)
    for i in range(8):
        builder.note(f"Scattered {i}", _unique("scatter", i), created=SUMMER)
    ctx = builder.build()

    [suggestion] = temporal_clustering.suggest(ctx)

    assert "separate" not in suggestion.text
    assert "distinct" not in suggestion.text
    assert suggestion.text.endswith("Different intellectual seasons, or one continuing thread?")


def test_temporal_clustering_needs_twenty_notes(tmp_path):
    """Boundary pair: 19 notes -> nothing; 20 -> contrasted."""
    periods = [("Garden", WINTER, 6), ("Rocket", AUTUMN, 6)]

    assert temporal_clustering.suggest(_vault(tmp_path / "19", periods, scattered=7)) == []
    assert_valid_suggestions(
        temporal_clustering.suggest(_vault(tmp_path / "20", periods, scattered=8)),
        "temporal_clustering",
    )


def test_temporal_clustering_period_needs_five_notes(tmp_path):
    """Boundary pair: a coherent 4-note period does not count; 5 notes does."""
    four = _vault(tmp_path / "4", [("Garden", WINTER, 6), ("Rocket", AUTUMN, 4)], scattered=10)
    five = _vault(tmp_path / "5", [("Garden", WINTER, 6), ("Rocket", AUTUMN, 5)], scattered=9)

    assert temporal_clustering.suggest(four) == []
    assert_valid_suggestions(
        temporal_clustering.suggest(five), "temporal_clustering", must_reference=["Rocket"]
    )


def test_temporal_clustering_reports_only_the_two_most_coherent_periods(tmp_path):
    """Three coherent periods yield one suggestion about the top two; the least
    coherent (violin, 0.67) is left out."""
    ctx = _vault(
        tmp_path,
        [("Garden", WINTER, 6), ("Rocket", AUTUMN, 6), ("Violin", SUMMER, 8)],
    )

    suggestions = temporal_clustering.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "temporal_clustering",
        must_reference=["Garden", "Rocket"],
        must_not_reference=["geist journal", "Violin"],
    )
    assert len(suggestions) == 1


def test_temporal_clustering_ignores_periods_older_than_two_years(tmp_path):
    """A coherent period from 2021 is outside the eight windows."""
    ctx = _vault(tmp_path, [("Garden", WINTER, 6), ("Rocket", LONG_AGO, 6)], scattered=8)

    assert temporal_clustering.suggest(ctx) == []


def test_temporal_clustering_excludes_geist_journal(tmp_path):
    """Session notes are near-identical, so they form the most coherent
    "period" of all. Both directions: the two user periods are contrasted and
    no session note is named."""
    builder = VaultBuilder(tmp_path)
    for theme, created in (("Garden", WINTER), ("Rocket", AUTUMN)):
        for i in range(6):
            builder.note(f"{theme} {i}", f"{THEMES[theme]} {theme.lower()}{i}x", created=created)
    for i in range(8):
        builder.journal(f"2023-08-{i + 1:02d}", "geist session suggestions output", created=SUMMER)
    for i in range(8):
        builder.note(f"Scattered {i}", _unique("scatter", i), created=datetime(2023, 3, 1))
    ctx = builder.build()

    suggestions = temporal_clustering.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "temporal_clustering",
        must_reference=["Garden", "Rocket"],
        must_not_reference=["geist journal", "2023-08-"],
    )


def test_temporal_clustering_is_deterministic_for_a_seed(tmp_path):
    periods = [("Garden", WINTER, 8), ("Rocket", AUTUMN, 8)]

    first = temporal_clustering.suggest(_vault(tmp_path / "a", periods, scattered=4))
    second = temporal_clustering.suggest(_vault(tmp_path / "b", periods, scattered=4))

    assert len(first) == 1
    assert [s.text for s in first] == [s.text for s in second]
