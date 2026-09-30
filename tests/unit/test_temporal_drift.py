"""Tests for the temporal_drift geist.

Trigger: among the 20 least recently modified non-journal notes, a note with
staleness > 0.7 and >= 3 outgoing links. Built-in staleness is
``round(1 - 1 / (1 + days_since_modified / 30), 3)``, so 70 days gives exactly
0.7 (not stale enough) and 71 days gives 0.703. Output is capped at 3.
"""

from datetime import datetime, timedelta
from pathlib import Path

from geistfabrik.default_geists.code import temporal_drift
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

LINKS = "See [[Alpha]], [[Beta]] and [[Gamma]]."


def _days_ago(days: int) -> datetime:
    return SESSION_DATE - timedelta(days=days)


def _stale_hub(builder: VaultBuilder, title: str, days: int, body: str = LINKS) -> None:
    when = _days_ago(days)
    builder.note(title, body, created=when - timedelta(days=30), modified=when)


def _build(root: Path, hubs: dict[str, int]) -> VaultContext:
    builder = VaultBuilder(root)
    for title, days in hubs.items():
        _stale_hub(builder, title, days)
    return builder.build()


def test_temporal_drift_flags_stale_well_linked_note(tmp_path):
    # Trigger arithmetic: 200 days unmodified -> staleness 0.87 > 0.7; 3 links >= 3.
    ctx = _build(tmp_path, {"Stale Hub": 200})

    suggestions = temporal_drift.suggest(ctx)

    assert_valid_suggestions(suggestions, "temporal_drift", must_reference=["Stale Hub"])
    assert suggestions[0].text == (
        "What if [[Stale Hub]] needs updating? It's been 200 days since you modified it, "
        "but it has 3 links - might your thinking have evolved?"
    )


def test_temporal_drift_staleness_boundary_is_71_days(tmp_path):
    """70 days -> staleness 0.7 (not > 0.7); 71 days -> 0.703."""
    assert temporal_drift.suggest(_build(tmp_path / "a", {"Seventy": 70})) == []

    suggestions = temporal_drift.suggest(_build(tmp_path / "b", {"Seventy One": 71}))

    assert_valid_suggestions(suggestions, "temporal_drift", must_reference=["Seventy One"])


def test_temporal_drift_needs_three_links(tmp_path):
    """Link boundary: a stale note with 2 links is skipped, 3 links is flagged."""
    builder = VaultBuilder(tmp_path)
    _stale_hub(builder, "Two Links", 200, "See [[Alpha]] and [[Beta]].")
    _stale_hub(builder, "Three Links", 200)
    ctx = builder.build()

    suggestions = temporal_drift.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "temporal_drift",
        must_reference=["Three Links"],
        must_not_reference=["geist journal", "Two Links"],
    )


def test_temporal_drift_caps_at_three(tmp_path):
    """Cap: five qualifying notes produce exactly three suggestions."""
    ctx = _build(tmp_path, {f"Stale {i}": 100 + i for i in range(5)})

    suggestions = temporal_drift.suggest(ctx)

    assert len(suggestions) == 3
    assert_valid_suggestions(suggestions, "temporal_drift")
    assert len({s.notes[0] for s in suggestions}) == 3


def test_temporal_drift_candidates_are_the_least_recently_modified(tmp_path):
    """In a vault with more than 20 notes, the stale hub is among the 20 oldest
    candidates even though 24 freshly edited notes outnumber it."""
    builder = VaultBuilder(tmp_path)
    _stale_hub(builder, "Old Hub", 200)
    for i in range(24):
        _stale_hub(builder, f"Fresh {i:02d}", 5)
    ctx = builder.build()

    suggestions = temporal_drift.suggest(ctx)

    assert_valid_suggestions(suggestions, "temporal_drift", must_reference=["Old Hub"])
    assert [s.notes for s in suggestions] == [["Old Hub"]]


def test_temporal_drift_excludes_geist_journal(tmp_path):
    """Session notes are always link-heavy and eventually stale; never flag them.

    Both directions, including crowding: 35 session notes that are older than
    the user's stale note must neither be suggested nor push the user's note
    out of the least-recently-modified candidate window.
    """
    builder = VaultBuilder(tmp_path)
    _stale_hub(builder, "Real Stale Hub", 200)
    for i in range(35):
        when = _days_ago(400 + i)
        builder.journal(f"Session {i:02d}", LINKS, created=when, modified=when)
    ctx = builder.build()

    suggestions = temporal_drift.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "temporal_drift",
        must_reference=["Real Stale Hub"],
        must_not_reference=["geist journal", "Session "],
    )


def test_temporal_drift_is_deterministic_for_a_seed(tmp_path):
    hubs = {f"Stale {i}": 100 + i for i in range(5)}

    first = temporal_drift.suggest(_build(tmp_path / "a", hubs))
    second = temporal_drift.suggest(_build(tmp_path / "b", hubs))

    assert len(first) == 3
    assert [s.text for s in first] == [s.text for s in second]
