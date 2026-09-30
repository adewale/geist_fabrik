"""Tests for the on_this_day geist.

Trigger: a non-journal note whose ``created`` has the session date's month and
day in an earlier year. The geist keeps the 3 most recent such notes and
samples 2 of them.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import on_this_day
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

# SESSION_DATE is 2024-03-15, so every note below created on 03-15 of an
# earlier year is an anniversary note.


def _vault(root: Path, created: dict[str, datetime]) -> VaultContext:
    builder = VaultBuilder(root)
    for title, when in created.items():
        builder.note(title, f"Thoughts about {title.lower()}.", created=when)
    return builder.build()


def test_on_this_day_surfaces_note_from_same_date_last_year(tmp_path):
    # Trigger arithmetic: 2023-03-15 matches month 3 / day 15 and 2023 < 2024.
    ctx = _vault(tmp_path, {"Anniversary": datetime(2023, 3, 15, 8, 0)})

    suggestions = on_this_day.suggest(ctx)

    assert_valid_suggestions(suggestions, "on_this_day", must_reference=["Anniversary"])
    assert suggestions[0].text == (
        "One year ago today, you wrote [[Anniversary]]. What's changed since then?"
    )
    assert suggestions[0].notes == ["Anniversary"]


def test_on_this_day_names_years_for_older_anniversaries(tmp_path):
    ctx = _vault(tmp_path, {"Old Anniversary": datetime(2021, 3, 15, 8, 0)})

    suggestions = on_this_day.suggest(ctx)

    assert_valid_suggestions(suggestions, "on_this_day")
    assert suggestions[0].text.startswith("3 years ago today, you wrote [[Old Anniversary]].")


def test_on_this_day_requires_exact_month_and_day(tmp_path):
    """Boundary: the day before and after, and the same day in another month, never match."""
    ctx = _vault(
        tmp_path,
        {
            "Day Before": datetime(2023, 3, 14, 23, 0),
            "Day After": datetime(2023, 3, 16, 0, 30),
            "Other Month": datetime(2023, 4, 15, 12, 0),
        },
    )

    assert on_this_day.suggest(ctx) == []


def test_on_this_day_skips_current_and_future_years(tmp_path):
    """Earlier-year boundary: 2024-03-15 (today's year) and 2025-03-15 are not history."""
    ctx = _vault(
        tmp_path,
        {
            "Written Today": datetime(2024, 3, 15, 7, 0),
            "Future Dated": datetime(2025, 3, 15, 7, 0),
        },
    )

    assert on_this_day.suggest(ctx) == []


def test_on_this_day_caps_at_two_of_the_three_most_recent_years(tmp_path):
    """Cap: 14 anniversaries (2010-2023) give exactly 2 suggestions, both from 2021-2023."""
    ctx = _vault(
        tmp_path, {f"Year {year}": datetime(year, 3, 15, 9, 0) for year in range(2010, 2024)}
    )

    suggestions = on_this_day.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "on_this_day")
    referenced = {ref for s in suggestions for ref in s.notes}
    assert referenced <= {"Year 2021", "Year 2022", "Year 2023"}, referenced


def test_on_this_day_excludes_geist_journal(tmp_path):
    """A session note written on 2023-03-15 is output, not something the user wrote.

    Both directions: the regular anniversary note is surfaced, the journal
    note created on the same date is not.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Real Memory", "Spring walk.", created=datetime(2023, 3, 15, 9, 0))
    builder.journal("2023-03-15", "Suggestions.", created=datetime(2023, 3, 15, 9, 0))
    ctx = builder.build()

    suggestions = on_this_day.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "on_this_day",
        must_reference=["Real Memory"],
        must_not_reference=["geist journal", "2023-03-15"],
    )
    assert len(suggestions) == 1


def test_on_this_day_links_journal_file_entries_by_deeplink(tmp_path):
    """A date-collection entry headed 2023-03-15 is linked as File#heading."""
    (tmp_path / "Journal.md").write_text(
        "## 2023-03-15\n\nCherry blossoms.\n\n## 2023-03-16\n\nRain.\n"
    )
    ctx = VaultBuilder(tmp_path).build()

    suggestions = on_this_day.suggest(ctx)

    assert_valid_suggestions(suggestions, "on_this_day")
    assert [s.notes for s in suggestions] == [["Journal#2023-03-15"]]
    assert "[[Journal#2023-03-15]]" in suggestions[0].text


def test_on_this_day_is_deterministic_for_a_seed(tmp_path):
    """Same vault, date and seed choose the same 2 of 3 candidates."""
    created = {f"Year {year}": datetime(year, 3, 15, 9, 0) for year in (2021, 2022, 2023)}
    first = on_this_day.suggest(_vault(tmp_path / "a", created))
    second = on_this_day.suggest(_vault(tmp_path / "b", created))

    assert len(first) == 2
    assert [s.text for s in first] == [s.text for s in second]


def test_on_this_day_uses_session_date_not_wall_clock(tmp_path):
    """Replaying another session date finds that date's anniversaries."""
    builder = VaultBuilder(tmp_path)
    builder.note("Autumn Note", "Leaves.", created=datetime(2022, 10, 3, 9, 0))
    ctx = builder.build(session_date=datetime(2023, 10, 3))

    assert_valid_suggestions(
        on_this_day.suggest(ctx), "on_this_day", must_reference=["Autumn Note"]
    )
