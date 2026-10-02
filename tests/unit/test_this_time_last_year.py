"""Tests for the this_time_last_year geist (absorbs on_this_day and seasonal_revisit).

Trigger, in three tiers over every earlier year (dates from Note.created):
1. a note written on the session date's month and day -> "N years ago today";
2. else a note within 7 days of an anniversary -> "Around this time N years ago";
3. else a note from the session's (Northern Hemisphere) season of an earlier
   season-year -> "Last spring" / "N springs ago". Seasons are Mar-May,
   Jun-Aug, Sep-Nov and Dec-Feb; December belongs to the following year's
   winter.
One suggestion, sampled within the tier. Window-boundary cases also live in
tests/unit/test_reflective_geists.py.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import this_time_last_year
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

# SESSION_DATE (VaultBuilder default) is 2024-03-15: spring.
QUESTION = "What's different now? What's the same?"


def _vault(
    root: Path, created: dict[str, datetime], session_date: datetime = SESSION_DATE
) -> VaultContext:
    builder = VaultBuilder(root)
    for title, when in created.items():
        builder.note(title, f"Thoughts about {title.lower()}.", created=when)
    return builder.build(session_date=session_date)


def _surfaced(base: VaultContext, seeds: int = 20) -> set[str]:
    """Every note named across ``seeds`` sessions of the same vault and date."""
    return {
        ref
        for seed in range(seeds)
        for s in this_time_last_year.suggest(
            VaultContext(base.vault, base.session, seed=seed, function_registry=FunctionRegistry())
        )
        for ref in s.notes
    }


# --- Tier 1: this very day ---------------------------------------------------


def test_this_time_last_year_says_today_for_an_exact_anniversary(tmp_path):
    """Contract: a note written on this month and day last year is "One year
    ago today".

    Regression (merged from on_this_day): the geist said "Around this time a
    year ago" even when the note was written on this exact day.
    """
    ctx = _vault(tmp_path, {"Anniversary": datetime(2023, 3, 15, 8, 0)})

    suggestions = this_time_last_year.suggest(ctx)

    assert [(s.text, s.notes) for s in suggestions] == [
        (f"One year ago today, you wrote [[Anniversary]]. {QUESTION}", ["Anniversary"])
    ]


def test_this_time_last_year_counts_years_for_older_exact_anniversaries(tmp_path):
    """Contract: an exact anniversary from any earlier year is found and its
    real year count stated.

    Regression: only 1-3 years back were searched, so a note from this day
    in 2010 was never resurfaced.
    """
    three = this_time_last_year.suggest(_vault(tmp_path / "3", {"Old": datetime(2021, 3, 15)}))
    fourteen = this_time_last_year.suggest(
        _vault(tmp_path / "14", {"Ancient": datetime(2010, 3, 15)})
    )

    assert [s.text for s in three] == [f"3 years ago today, you wrote [[Old]]. {QUESTION}"]
    assert [s.text for s in fourteen] == [f"14 years ago today, you wrote [[Ancient]]. {QUESTION}"]


def test_this_time_last_year_prefers_the_exact_day_over_the_week(tmp_path):
    """Contract: when a note was written on this very day, the geist names it,
    not a note from a few days either side.

    Regression: an exact-day note was only one of the window candidates, so
    most sessions named a nearby note instead.
    """
    base = _vault(
        tmp_path,
        {
            "On The Day": datetime(2023, 3, 15),
            "Three Days Before": datetime(2023, 3, 12),
            "Five Days After": datetime(2023, 3, 20),
        },
    )

    assert _surfaced(base) == {"On The Day"}


def test_this_time_last_year_skips_this_year_and_future_dates(tmp_path):
    """A note dated today this year, or this day next year, is not history."""
    ctx = _vault(
        tmp_path, {"Written Today": datetime(2024, 3, 15), "Future": datetime(2025, 3, 15)}
    )

    assert this_time_last_year.suggest(ctx) == []


# --- Tier 2: within a week of an anniversary --------------------------------


def test_this_time_last_year_looks_back_over_every_earlier_year(tmp_path):
    """Contract: the +/- 7-day window applies to every earlier year.

    Regression: the window was searched 1, 2 and 3 years back only.
    """
    ctx = _vault(tmp_path, {"Decade Note": datetime(2014, 3, 12)})

    suggestions = this_time_last_year.suggest(ctx)

    assert [s.text for s in suggestions] == [
        f"Around this time 10 years ago, you wrote [[Decade Note]]. {QUESTION}"
    ]


def test_this_time_last_year_window_reaches_across_new_year(tmp_path):
    """A January 3 session's window starts on December 27 of the year before."""
    ctx = _vault(
        tmp_path, {"Winter Break": datetime(2022, 12, 28)}, session_date=datetime(2024, 1, 3)
    )

    assert [s.text for s in this_time_last_year.suggest(ctx)] == [
        f"Around this time a year ago, you wrote [[Winter Break]]. {QUESTION}"
    ]


def test_this_time_last_year_samples_every_note_in_the_window(tmp_path):
    """Any note from the window can be surfaced across sessions."""
    titles = [f"Week Note {c}" for c in "ABCDEF"]
    base = _vault(tmp_path, {t: datetime(2023, 3, 9 + i) for i, t in enumerate(titles)})

    assert _surfaced(base) == set(titles)


# --- Tier 3: same season, earlier year ---------------------------------------


def test_this_time_last_year_falls_back_to_last_years_season(tmp_path):
    """Contract: with nothing within a week of any anniversary, a note from
    this season in an earlier year is surfaced as "Last spring".

    Regression (merged from seasonal_revisit): an empty window meant no
    suggestion at all.
    """
    ctx = _vault(tmp_path, {"Spring Planting": datetime(2023, 4, 20)})

    suggestions = this_time_last_year.suggest(ctx)

    assert_valid_suggestions(suggestions, "this_time_last_year", must_reference=["Spring Planting"])
    assert suggestions[0].text == f"Last spring, you wrote [[Spring Planting]]. {QUESTION}"


def test_this_time_last_year_counts_seasons_for_older_years(tmp_path):
    """Contract: a same-season note from three season-years back is "3 springs ago".

    Regression: the season fallback did not exist.
    """
    ctx = _vault(tmp_path, {"Old Spring": datetime(2021, 4, 20)})

    assert [s.text for s in this_time_last_year.suggest(ctx)] == [
        f"3 springs ago, you wrote [[Old Spring]]. {QUESTION}"
    ]


def test_this_time_last_year_season_edges(tmp_path):
    """Boundary pairs at both ends of spring: Feb 28 / Mar 1 and May 31 / Jun 1.

    Contract: March 1 and May 31 of last year are last spring (both more than
    7 days from March 15); Feb 28 and June 1 are not.

    Regression: no season fallback.
    """
    outside = {"Late February": datetime(2023, 2, 28), "First Of June": datetime(2023, 6, 1)}
    inside = {"First Of March": datetime(2023, 3, 1), "End Of May": datetime(2023, 5, 31)}

    assert this_time_last_year.suggest(_vault(tmp_path / "outside", outside)) == []
    assert _surfaced(_vault(tmp_path / "inside", inside)) == set(inside)


def test_this_time_last_year_december_belongs_to_the_current_winter(tmp_path):
    """Contract: in January 2024, December 2023 is THIS winter, while February
    2023 and December 2022 are last winter.

    Regression: no season fallback (and seasonal_revisit once compared
    calendar years, calling a three-week-old note "last year").
    """
    base = _vault(
        tmp_path,
        {
            "Three Weeks Ago": datetime(2023, 12, 20),
            "Last February": datetime(2023, 2, 1),
            "Last December": datetime(2022, 12, 20),
        },
        session_date=datetime(2024, 1, 10),
    )

    texts = {
        s.text
        for seed in range(20)
        for s in this_time_last_year.suggest(
            VaultContext(base.vault, base.session, seed=seed, function_registry=FunctionRegistry())
        )
    }

    assert texts == {
        f"Last winter, you wrote [[Last February]]. {QUESTION}",
        f"Last winter, you wrote [[Last December]]. {QUESTION}",
    }


def test_this_time_last_year_ignores_this_seasons_notes(tmp_path):
    """A note from earlier this spring is not a memory of a past spring."""
    ctx = _vault(tmp_path, {"This Spring": datetime(2024, 3, 2)})

    assert this_time_last_year.suggest(ctx) == []


# --- Shared ------------------------------------------------------------------


def test_this_time_last_year_excludes_geist_journal(tmp_path):
    """Both directions: the user's anniversary note is surfaced, a session
    note from the same day is not."""
    builder = VaultBuilder(tmp_path)
    builder.note("Real Memory", "Spring walk.", created=datetime(2023, 3, 15, 9, 0))
    builder.journal("2023-03-15", "Suggestions.", created=datetime(2023, 3, 15, 9, 0))
    base = builder.build()

    assert _surfaced(base) == {"Real Memory"}


def test_this_time_last_year_links_journal_file_entries_by_deeplink(tmp_path):
    """A date-collection entry headed 2023-03-15 is linked as File#heading."""
    (tmp_path / "Journal.md").write_text(
        "## 2023-03-15\n\nCherry blossoms.\n\n## 2023-03-16\n\nRain.\n"
    )
    ctx = VaultBuilder(tmp_path).build()

    suggestions = this_time_last_year.suggest(ctx)

    assert [(s.text, s.notes) for s in suggestions] == [
        (
            f"One year ago today, you wrote [[Journal#2023-03-15]]. {QUESTION}",
            ["Journal#2023-03-15"],
        )
    ]


def test_this_time_last_year_uses_session_date_not_wall_clock(tmp_path):
    """Replaying another session date finds that date's anniversaries."""
    ctx = _vault(
        tmp_path, {"Autumn Note": datetime(2022, 10, 3)}, session_date=datetime(2023, 10, 3)
    )

    assert_valid_suggestions(
        this_time_last_year.suggest(ctx), "this_time_last_year", must_reference=["Autumn Note"]
    )


def test_this_time_last_year_is_deterministic_for_a_seed(tmp_path):
    created = {f"Year {year}": datetime(year, 3, 15) for year in (2021, 2022, 2023)}

    first = this_time_last_year.suggest(_vault(tmp_path / "a", created))
    second = this_time_last_year.suggest(_vault(tmp_path / "b", created))

    assert len(first) == 1
    assert [s.text for s in first] == [s.text for s in second]
