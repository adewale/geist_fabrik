"""Unit tests for metadata_driven_discovery geist.

Trigger arithmetic (see the geist source; metadata is VaultContext's
built-in set, with "now" = the session date):
- complex-but-isolated: (lexical_diversity > 0.5 or reading_time > 3) and
  links + backlinks < 2; the pattern needs >= 3 such notes;
- buried gems: lexical_diversity > 0.6 and days_since_modified > 90; >= 2;
- abandoned tasks: an open "- [ ]" task and days_since_modified > 60; >= 2;
- each pattern yields at most one suggestion and output is capped at 2.

lexical_diversity counts every whitespace token, so a body of distinct words
scores ~1.0 and a body of one repeated word scores low. Background notes use
the repeated-word body and 2 links so no pattern can pick them up.
"""

from datetime import timedelta
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import metadata_driven_discovery
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

GEIST = "metadata_driven_discovery"
CAP = 2
DIVERSE = "quartz lichen harbour violin saffron glacier meadow lantern cobalt thistle"
LINKED_BACKGROUND = "echo echo echo echo echo echo echo echo echo echo [[Anchor A]] [[Anchor B]]"
OPEN_TASKS = "- [ ] echo\n- [ ] echo\n- [x] echo\n[[Anchor A]] [[Anchor B]]"


def _note(builder: VaultBuilder, title: str, body: str, *, age_days: int = 0) -> None:
    stamp = SESSION_DATE - timedelta(days=age_days)
    builder.note(title, body, created=stamp, modified=stamp)


def _background(builder: VaultBuilder, count: int = 4) -> None:
    _note(builder, "Anchor A", LINKED_BACKGROUND)
    _note(builder, "Anchor B", LINKED_BACKGROUND)
    for i in range(count):
        _note(builder, f"Background {i}", LINKED_BACKGROUND)


@pytest.mark.parametrize(("planted", "fires"), [(2, False), (3, True)])
def test_complex_isolated_pattern_needs_three_notes(
    tmp_path: Path, planted: int, fires: bool
) -> None:
    builder = VaultBuilder(tmp_path)
    titles = [f"Complex {i}" for i in range(planted)]
    for title in titles:
        _note(builder, title, DIVERSE)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    if not fires:
        assert suggestions == []
        return
    assert_valid_suggestions(suggestions, GEIST, must_reference=titles)
    assert [sorted(s.notes) for s in suggestions] == [titles]
    assert "complex topics with few connections" in suggestions[0].text


@pytest.mark.parametrize(("age_days", "fires"), [(90, False), (91, True)])
def test_buried_gems_need_more_than_ninety_days(tmp_path: Path, age_days: int, fires: bool) -> None:
    # Linked, so the diverse gems cannot be read as complex-and-isolated.
    builder = VaultBuilder(tmp_path)
    gems = ["Gem 1", "Gem 2"]
    for title in gems:
        _note(builder, title, f"{DIVERSE} [[Anchor A]] [[Anchor B]]", age_days=age_days)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    if not fires:
        assert suggestions == []
        return
    assert_valid_suggestions(suggestions, GEIST)
    assert [sorted(s.notes) for s in suggestions] == [gems]
    assert "high lexical diversity" in suggestions[0].text


@pytest.mark.parametrize(("age_days", "fires"), [(60, False), (61, True)])
def test_abandoned_task_notes_need_more_than_sixty_days(
    tmp_path: Path, age_days: int, fires: bool
) -> None:
    builder = VaultBuilder(tmp_path)
    projects = ["Project 1", "Project 2"]
    for title in projects:
        _note(builder, title, OPEN_TASKS, age_days=age_days)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    if not fires:
        assert suggestions == []
        return
    assert_valid_suggestions(suggestions, GEIST)
    assert [sorted(s.notes) for s in suggestions] == [projects]
    assert "[[Project 1]] (2 incomplete tasks)" in suggestions[0].text


def test_completed_task_notes_are_not_abandoned(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for title in ["Project 1", "Project 2"]:
        _note(builder, title, OPEN_TASKS.replace("[ ]", "[x]"), age_days=200)
    _background(builder)

    assert metadata_driven_discovery.suggest(builder.build()) == []


def test_output_is_capped_when_all_three_patterns_fire(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        _note(builder, f"Complex {i}", DIVERSE)
    for i in range(2):
        _note(builder, f"Gem {i}", f"{DIVERSE} [[Anchor A]] [[Anchor B]]", age_days=120)
        _note(builder, f"Project {i}", OPEN_TASKS, age_days=70)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert len(suggestions) == CAP
    assert len({s.text for s in suggestions}) == CAP


def test_geist_journal_notes_never_complete_a_pattern(tmp_path: Path) -> None:
    # Two regular complex notes are one short of the pattern; three diverse,
    # unlinked journal notes would complete it if the journal were scanned.
    # The abandoned-task pattern fires on regular notes as the positive side.
    builder = VaultBuilder(tmp_path)
    for i in range(2):
        _note(builder, f"Complex {i}", DIVERSE)
        _note(builder, f"Project {i}", OPEN_TASKS, age_days=70)
    for i in range(3):
        stamp = SESSION_DATE - timedelta(days=1)
        builder.journal(f"Session Log {i}", DIVERSE, created=stamp, modified=stamp)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    assert_valid_suggestions(
        suggestions,
        GEIST,
        must_reference=["Project 0", "Project 1"],
        must_not_reference=["Session Log"],
    )
    assert len(suggestions) == 1


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        _note(builder, f"Complex {i}", DIVERSE)
    for i in range(2):
        _note(builder, f"Gem {i}", f"{DIVERSE} [[Anchor A]] [[Anchor B]]", age_days=120)
        _note(builder, f"Project {i}", OPEN_TASKS, age_days=70)
    _background(builder)

    first = [s.text for s in metadata_driven_discovery.suggest(builder.build())]
    second = [s.text for s in metadata_driven_discovery.suggest(builder.build())]

    assert first
    assert first == second
