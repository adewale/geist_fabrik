"""Tests for the seasonal_revisit geist.

Trigger: a non-journal note created in the session date's (Northern
Hemisphere) season of an EARLIER season-year. Seasons are Mar-May, Jun-Aug,
Sep-Nov and Dec-Feb; a winter runs from December into the next year, so
December belongs to the following year's winter. The geist keeps the 3 most
recent matches and samples 2.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import seasonal_revisit
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

# SESSION_DATE (VaultBuilder default) is 2024-03-15: Spring.


def _vault(
    root: Path, created: dict[str, datetime], session_date: datetime = SESSION_DATE
) -> VaultContext:
    builder = VaultBuilder(root)
    for title, when in created.items():
        builder.note(title, f"Thoughts about {title.lower()}.", created=when)
    return builder.build(session_date=session_date)


def test_seasonal_revisit_surfaces_last_springs_note(tmp_path):
    # Trigger arithmetic: 2023-04-20 is Spring (April) of 2023 < 2024.
    ctx = _vault(tmp_path, {"Spring Planting": datetime(2023, 4, 20)})

    suggestions = seasonal_revisit.suggest(ctx)

    assert_valid_suggestions(suggestions, "seasonal_revisit", must_reference=["Spring Planting"])
    assert suggestions[0].text == (
        "**Spring again**. Last year in spring, you wrote [[Spring Planting]]. "
        "What patterns repeat with the seasons?"
    )


def test_seasonal_revisit_season_edges(tmp_path):
    """Boundary pairs at both ends of Spring: Feb 28 / Mar 1 and May 31 / Jun 1."""
    outside = {
        "Late February": datetime(2023, 2, 28, 12),
        "First Of June": datetime(2023, 6, 1, 12),
    }
    inside = {"First Of March": datetime(2023, 3, 1, 12), "End Of May": datetime(2023, 5, 31, 12)}

    assert seasonal_revisit.suggest(_vault(tmp_path / "outside", outside)) == []

    suggestions = seasonal_revisit.suggest(_vault(tmp_path / "inside", inside))

    assert_valid_suggestions(
        suggestions, "seasonal_revisit", min_count=2, must_reference=list(inside)
    )


def test_seasonal_revisit_ignores_this_years_season(tmp_path):
    """A note from earlier this spring is not a memory of a past spring."""
    ctx = _vault(tmp_path, {"This Spring": datetime(2024, 3, 2)})

    assert seasonal_revisit.suggest(ctx) == []


def test_seasonal_revisit_december_belongs_to_the_current_winter(tmp_path):
    """Winter straddles New Year: in January 2024, December 2023 is THIS winter.

    Regression: the geist compared calendar years, so a note written three
    weeks earlier was announced as "Last year in winter". Last winter's notes
    (January 2023 and December 2022) are still one season-year back.
    """
    ctx = _vault(
        tmp_path,
        {
            "Three Weeks Ago": datetime(2023, 12, 20),
            "Last January": datetime(2023, 1, 10),
            "Last December": datetime(2022, 12, 20),
        },
        session_date=datetime(2024, 1, 10),
    )

    suggestions = seasonal_revisit.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "seasonal_revisit",
        min_count=2,
        must_reference=["Last January", "Last December"],
        must_not_reference=["geist journal", "Three Weeks Ago"],
    )
    assert all("Last year in winter" in s.text for s in suggestions)


def test_seasonal_revisit_caps_at_two_of_the_three_most_recent(tmp_path):
    """Cap: 14 past springs (2010-2023) give exactly 2 suggestions, both from 2021-2023."""
    ctx = _vault(tmp_path, {f"Spring {y}": datetime(y, 4, 1) for y in range(2010, 2024)})

    suggestions = seasonal_revisit.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "seasonal_revisit")
    referenced = {ref for s in suggestions for ref in s.notes}
    assert referenced <= {"Spring 2021", "Spring 2022", "Spring 2023"}, referenced


def test_seasonal_revisit_excludes_geist_journal(tmp_path):
    """Both directions: last spring's note is surfaced, last spring's session note is not."""
    builder = VaultBuilder(tmp_path)
    builder.note("Real Spring", "Garden.", created=datetime(2023, 4, 2))
    builder.journal("2023-04-02", "Session output.", created=datetime(2023, 4, 2))
    ctx = builder.build()

    suggestions = seasonal_revisit.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "seasonal_revisit",
        must_reference=["Real Spring"],
        must_not_reference=["geist journal", "2023-04-02"],
    )
    assert len(suggestions) == 1


def test_seasonal_revisit_is_deterministic_for_a_seed(tmp_path):
    created = {f"Spring {y}": datetime(y, 4, 1) for y in (2021, 2022, 2023)}

    first = seasonal_revisit.suggest(_vault(tmp_path / "a", created))
    second = seasonal_revisit.suggest(_vault(tmp_path / "b", created))

    assert len(first) == 2
    assert [s.text for s in first] == [s.text for s in second]
