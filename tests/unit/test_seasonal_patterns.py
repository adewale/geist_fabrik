"""Tests for the seasonal_patterns geist.

Trigger: >= 50 non-journal notes, then two independent findings (capped at 2
overall):

1. Recurring month theme: of the months with >= 5 notes (at least two such
   months), the most internally coherent one has notes from >= 2 years, and
   its best cross-year pair has similarity > 0.65.
2. Seasonal tag: in a season with >= 10 notes, a tag used >= 5 times there
   whose share of all uses of the tag is > 0.6.

Fillers have unique vocabulary (similarity ~0) and no tags.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import seasonal_patterns
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

JULY, OCTOBER = datetime(2023, 7, 10), datetime(2023, 10, 10)
WINTER, SUMMER = datetime(2023, 1, 15), datetime(2023, 7, 15)
PLANTING = "planting seeds seedlings trays compost sowing"


def _fillers(builder: VaultBuilder, count: int, when: datetime, prefix: str) -> None:
    for i in range(count):
        builder.note(
            f"{prefix} {i}",
            " ".join(f"{prefix.lower()}{i}{w}" for w in ("alpha", "bravo", "charlie")),
            created=when,
        )


def _month_theme_vault(root: Path, *, march_per_year: int = 3, fillers: int = 44) -> VaultBuilder:
    """March notes in 2022 and 2023 share PLANTING (similarity 6/7 = 0.86);
    fillers are split between July and October."""
    builder = VaultBuilder(root)
    for year in (2022, 2023):
        for i in range(march_per_year):
            builder.note(f"Sowing {year} {i}", f"{PLANTING}", created=datetime(year, 3, 5 + i))
    _fillers(builder, fillers // 2, JULY, "July")
    _fillers(builder, fillers - fillers // 2, OCTOBER, "October")
    return builder


def _tag_vault(
    root: Path,
    *,
    in_season: int = 6,
    off_season: int = 2,
    winter_notes: int = 12,
    tags: tuple[str, ...] = ("skiing",),
) -> VaultBuilder:
    """``winter_notes`` winter notes, the first ``in_season`` carrying each tag;
    ``off_season`` summer notes carrying each tag; summer fillers up to 50."""
    builder = VaultBuilder(root)
    tag_text = " ".join(f"#{t}" for t in tags)
    for i in range(winter_notes):
        body = f"winter{i}alpha winter{i}bravo" + (f" {tag_text}" if i < in_season else "")
        builder.note(f"Winter {i}", body, created=datetime(2023, 1, 2 + i))
    for i in range(off_season):
        builder.note(f"Summer Tagged {i}", f"summer{i}alpha {tag_text}", created=SUMMER)
    _fillers(builder, 50 - winter_notes - off_season, SUMMER, "Filler")
    return builder


def test_seasonal_patterns_finds_theme_recurring_in_the_same_month(tmp_path):
    # Trigger arithmetic: 6 March notes + 44 fillers = 50. March coherence 0.86
    # beats July/October (~0); March spans 2022 and 2023; cross-year 0.86 > 0.65.
    ctx = _month_theme_vault(tmp_path).build()

    suggestions = seasonal_patterns.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "seasonal_patterns",
        must_reference=["Sowing 2022", "Sowing 2023"],
        must_not_reference=["geist journal", "July", "October"],
    )
    [suggestion] = suggestions
    assert suggestion.text.startswith("You consistently write about similar themes in March—")
    assert "despite being 1 years apart" in suggestion.text


def test_seasonal_patterns_needs_fifty_notes(tmp_path):
    """Boundary pair: 49 notes -> nothing; 50 -> the March theme."""
    assert seasonal_patterns.suggest(_month_theme_vault(tmp_path / "49", fillers=43).build()) == []
    assert_valid_suggestions(
        seasonal_patterns.suggest(_month_theme_vault(tmp_path / "50", fillers=44).build()),
        "seasonal_patterns",
    )


def test_seasonal_patterns_month_theme_needs_two_years(tmp_path):
    """A coherent March in a single year is a burst, not a recurring rhythm."""
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        builder.note(f"Sowing {i}", PLANTING, created=datetime(2023, 3, 5 + i))
    _fillers(builder, 22, JULY, "July")
    _fillers(builder, 22, OCTOBER, "October")

    assert seasonal_patterns.suggest(builder.build()) == []


def test_seasonal_patterns_finds_tag_concentrated_in_one_season(tmp_path):
    # Trigger arithmetic: 12 winter notes (>= 10); #skiing on 6 of them (>= 5)
    # and on 2 summer notes: 6/8 = 0.75 > 0.6.
    ctx = _tag_vault(tmp_path).build()

    suggestions = seasonal_patterns.suggest(ctx)

    assert_valid_suggestions(suggestions, "seasonal_patterns", must_reference=["Winter"])
    [suggestion] = suggestions
    assert suggestion.text.startswith(
        "You write about #skiing predominantly in winter (6 out of 8 notes). Examples: "
    )
    assert len(suggestion.notes) == 3
    assert all(ref.startswith("Winter ") and int(ref.split()[1]) < 6 for ref in suggestion.notes)


def test_seasonal_patterns_tag_share_must_exceed_sixty_percent(tmp_path):
    """Boundary pair: 6 of 10 uses in winter (0.6) -> nothing; 6 of 9 (0.67) -> flagged."""
    at_60 = _tag_vault(tmp_path / "60", off_season=4).build()
    above = _tag_vault(tmp_path / "67", off_season=3).build()

    assert seasonal_patterns.suggest(at_60) == []
    assert_valid_suggestions(
        seasonal_patterns.suggest(above), "seasonal_patterns", must_reference=["Winter"]
    )


def test_seasonal_patterns_tag_needs_five_uses_in_season(tmp_path):
    """Boundary pair: 4 winter uses (4/4 = 1.0 share) -> nothing; 5 -> flagged."""
    four = _tag_vault(tmp_path / "4", in_season=4, off_season=0).build()
    five = _tag_vault(tmp_path / "5", in_season=5, off_season=0).build()

    assert seasonal_patterns.suggest(four) == []
    assert_valid_suggestions(seasonal_patterns.suggest(five), "seasonal_patterns")


def test_seasonal_patterns_tag_season_needs_ten_notes(tmp_path):
    """Boundary pair: a 9-note winter is too small to judge; 10 notes is enough."""
    nine = _tag_vault(tmp_path / "9", winter_notes=9, off_season=0).build()
    ten = _tag_vault(tmp_path / "10", winter_notes=10, off_season=0).build()

    assert seasonal_patterns.suggest(nine) == []
    assert_valid_suggestions(seasonal_patterns.suggest(ten), "seasonal_patterns")


def test_seasonal_patterns_caps_at_two(tmp_path):
    """Cap: three concentrated winter tags yield three findings; two are returned."""
    ctx = _tag_vault(tmp_path, tags=("skiing", "cocoa", "sledding")).build()

    suggestions = seasonal_patterns.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "seasonal_patterns")
    assert suggestions[0].text.split()[3] != suggestions[1].text.split()[3]


def test_seasonal_patterns_excludes_geist_journal(tmp_path):
    """Session notes neither count towards a tag's seasons nor appear as examples.

    Both directions: 6 winter #skiing notes are reported as 6 of 8 uses even
    though 12 summer session notes also carry #skiing (which would make the
    share 6/20 = 0.3 if counted), and no session note is named.
    """
    builder = _tag_vault(tmp_path)
    for i in range(12):
        builder.journal(f"2023-07-{i + 1:02d}", "Suggestions about #skiing", created=SUMMER)
    ctx = builder.build()

    suggestions = seasonal_patterns.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "seasonal_patterns",
        must_reference=["Winter"],
        must_not_reference=["geist journal", "2023-07-"],
    )
    assert "(6 out of 8 notes)" in suggestions[0].text


def test_seasonal_patterns_is_deterministic_for_a_seed(tmp_path):
    tags = ("skiing", "cocoa", "sledding")

    first = seasonal_patterns.suggest(_tag_vault(tmp_path / "a", tags=tags).build())
    second = seasonal_patterns.suggest(_tag_vault(tmp_path / "b", tags=tags).build())

    assert len(first) == 2
    assert [s.text for s in first] == [s.text for s in second]
