"""Tests for the seasonal_topic_analysis geist.

Trigger: >= 20 user notes, and in at least one season window (the
meteorological seasons of temporal_analysis.get_season(): winter Dec 1 -
end of Feb, spring Mar - May, summer Jun - Aug, autumn Sep - Nov, each at its
most recent occurrence that began on or before the session date) an anchor
note with >= 2 other in-season notes at similarity >= 0.60. The suggestion
names the anchor and its two closest companions. One suggestion per season,
2 sampled. Winter is labelled with both years it spans ("winter 2023-24").

Fixture arithmetic (lexical stub): the three notes of a season share their
title words and five topic words and differ only by a digit (ignored by the
stub), so their semantic similarity is 1.0; created days apart, their
calendar features are near-identical too, so similarity is far above 0.60.
Filler notes are created in 2022, before every window, with words of their own.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import seasonal_topic_analysis
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

WINTER_2023 = [datetime(2023, 12, 28), datetime(2024, 1, 10), datetime(2024, 2, 5)]
TOPICS = {
    "Snow": "frost lantern cocoa blizzard sledge",
    "Bloom": "tulips pollen meadow blossom bees",
    "Tide": "surf sandcastle sunscreen harbour waves",
}


def _vault(
    root: Path,
    seasons: dict[str, list[datetime]],
    *,
    session_date: datetime = SESSION_DATE,
    fillers: int = 17,
    journal: dict[str, list[datetime]] | None = None,
) -> VaultContext:
    """``seasons`` maps a TOPICS key to the creation dates of its notes."""
    builder = VaultBuilder(root)
    for topic, dates in seasons.items():
        for i, created in enumerate(dates):
            builder.note(f"{topic} Note {i}", TOPICS[topic], created=created)
    for topic, dates in (journal or {}).items():
        for i, created in enumerate(dates):
            builder.journal(f"{topic} Session {i}", TOPICS[topic], created=created)
    for i in range(fillers):
        builder.note(
            f"Filler {i}", f"ledger{i} invoice{i} receipt{i}", created=datetime(2022, 1, 5)
        )
    return builder.build(session_date=session_date)


@pytest.mark.parametrize(
    ("session_date", "created", "label"),
    [
        # January: inside the winter that began the previous December.
        (datetime(2024, 1, 15), [datetime(2023, 12, 22), *WINTER_2023[1:]], "winter 2023-24"),
        # Mid March, spring: the latest winter is the one that began last December.
        (SESSION_DATE, WINTER_2023, "winter 2023-24"),
        # November: winter has not begun, so look back a year.
        (datetime(2024, 11, 20), WINTER_2023, "winter 2023-24"),
        # December: the winter that runs into the following year.
        (
            datetime(2024, 12, 30),
            [datetime(2024, 12, 2), datetime(2024, 12, 24), datetime(2024, 12, 27)],
            "winter 2024-25",
        ),
    ],
    ids=["january", "mid-march", "november", "december"],
)
def test_seasonal_topic_analysis_finds_the_latest_winter(tmp_path, session_date, created, label):
    """Happy path, and the regression for the winter window.

    Bug: for session dates from March 1 on, the winter window was the one
    starting the coming December, after the session date, so winter notes
    were never found (mid-march and november failed).
    """
    ctx = _vault(tmp_path, {"Snow": created}, session_date=session_date)

    suggestions = seasonal_topic_analysis.suggest(ctx)

    assert_valid_suggestions(suggestions, "seasonal_topic_analysis", must_reference=["Snow Note"])
    assert len(suggestions) == 1
    assert suggestions[0].text.startswith(f"In {label}, you wrote closely related notes: [[Snow")
    # The anchor and its two in-season companions
    assert sorted(suggestions[0].notes) == ["Snow Note 0", "Snow Note 1", "Snow Note 2"]


def test_seasonal_topic_analysis_window_ends_on_the_last_day(tmp_path):
    """Boundary pair on the spring/summer edge (session in July).

    Contract: seasons are get_season()'s, as in the sibling seasonal geists:
    a note made on May 31 (late in the day) is the third spring note; one
    made on June 1 is summer, leaving spring one note short.

    Regression: the windows were astronomical (spring ran to June 20), so
    June 1-20 notes were "spring" here and "summer" in seasonal_revisit and
    seasonal_patterns. (Earlier regression: each window ended at midnight at
    the START of its last day.)
    """
    last_day = [datetime(2024, 4, 2), datetime(2024, 5, 2), datetime(2024, 5, 31, 15)]
    next_day = [datetime(2024, 4, 2), datetime(2024, 5, 2), datetime(2024, 6, 1)]
    july = datetime(2024, 7, 15)

    inside = _vault(tmp_path / "inside", {"Bloom": last_day}, session_date=july)
    outside = _vault(tmp_path / "outside", {"Bloom": next_day}, session_date=july)

    assert_valid_suggestions(
        seasonal_topic_analysis.suggest(inside),
        "seasonal_topic_analysis",
        must_reference=["In spring 2024"],
    )
    assert seasonal_topic_analysis.suggest(outside) == []


def test_seasonal_topic_analysis_needs_an_anchor_and_two_companions(tmp_path):
    """Boundary pair: two alike winter notes are not a pattern; three are."""
    two = _vault(tmp_path / "two", {"Snow": WINTER_2023[:2]}, fillers=18)
    three = _vault(tmp_path / "three", {"Snow": WINTER_2023})

    assert seasonal_topic_analysis.suggest(two) == []
    assert_valid_suggestions(
        seasonal_topic_analysis.suggest(three),
        "seasonal_topic_analysis",
        must_reference=["Snow Note"],
    )


def test_seasonal_topic_analysis_needs_alike_notes(tmp_path):
    """Three winter notes on three different topics share no words: whichever
    is the anchor, no other note reaches 0.60 similarity."""
    builder = VaultBuilder(tmp_path)
    for (topic, words), created in zip(TOPICS.items(), WINTER_2023, strict=True):
        builder.note(f"{topic} Note", words, created=created)
    for i in range(17):
        builder.note(
            f"Filler {i}", f"ledger{i} invoice{i} receipt{i}", created=datetime(2022, 1, 5)
        )

    assert seasonal_topic_analysis.suggest(builder.build()) == []


def test_seasonal_topic_analysis_needs_twenty_notes(tmp_path):
    """Boundary pair: 3 winter notes + 16 fillers = 19 is too few; + 17 = 20 fires."""
    nineteen = _vault(tmp_path / "19", {"Snow": WINTER_2023}, fillers=16)
    twenty = _vault(tmp_path / "20", {"Snow": WINTER_2023}, fillers=17)

    assert len(nineteen.notes()) == 19
    assert seasonal_topic_analysis.suggest(nineteen) == []
    assert_valid_suggestions(
        seasonal_topic_analysis.suggest(twenty),
        "seasonal_topic_analysis",
        must_reference=["Snow Note"],
    )


def test_seasonal_topic_analysis_caps_at_two(tmp_path):
    """Cap: a November session sees last winter, this spring and this summer;
    a pattern in all three yields exactly two suggestions, from different seasons."""
    ctx = _vault(
        tmp_path,
        {
            "Snow": WINTER_2023,
            "Bloom": [datetime(2024, 4, d) for d in (2, 9, 16)],
            "Tide": [datetime(2024, 7, d) for d in (2, 9, 16)],
        },
        session_date=datetime(2024, 11, 1),
        fillers=11,
    )

    suggestions = seasonal_topic_analysis.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "seasonal_topic_analysis")
    seasons = {s.text.split(",")[0] for s in suggestions}
    assert len(seasons) == 2
    assert seasons <= {"In winter 2023-24", "In spring 2024", "In summer 2024"}


def test_seasonal_topic_analysis_excludes_geist_journal(tmp_path):
    """Both directions: session notes from the same winter on the same topic
    are never named (and never count as companions); the user's notes are."""
    ctx = _vault(tmp_path, {"Snow": WINTER_2023}, journal={"Snow": WINTER_2023})

    suggestions = seasonal_topic_analysis.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "seasonal_topic_analysis",
        must_reference=["Snow Note"],
        must_not_reference=["geist journal", "Snow Session"],
    )


def test_seasonal_topic_analysis_names_the_anchor_in_get_season_terms(tmp_path):
    """Contract: the suggestion names the anchor note itself plus its two
    closest companions, says what was measured (closely related notes from
    one season) without claiming a seasonal pattern, and places December
    notes in winter, as get_season() and the sibling seasonal geists do.

    Regression: the anchor was left out (only the companions were named), the
    text asked "What seasonal pattern might this reflect?" although nothing
    is compared across years, and December 1-20 counted as "fall".
    """
    december = [datetime(2024, 12, 5), datetime(2024, 12, 10), datetime(2024, 12, 15)]
    ctx = _vault(tmp_path, {"Snow": december}, session_date=datetime(2025, 1, 15))

    suggestions = seasonal_topic_analysis.suggest(ctx)

    assert [sorted(s.notes) for s in suggestions] == [["Snow Note 0", "Snow Note 1", "Snow Note 2"]]
    names = ", ".join(f"[[{n}]]" for n in suggestions[0].notes)
    assert suggestions[0].text == (
        f"In winter 2024-25, you wrote closely related notes: {names}. Is that thread still alive?"
    )
