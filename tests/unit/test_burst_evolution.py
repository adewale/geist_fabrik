"""Tests for the burst_evolution geist.

Trigger: a burst day (>= 3 non-journal notes created that day) on which >= 3
notes have >= 2 session snapshots. For each such note the geist reports
drift = 1 - cos(first snapshot, last snapshot) over the SEMANTIC dimensions,
labelled small (< 0.10) / moderate (< 0.25) / large (< 0.40) / very large.
One suggestion, listing at most 7 notes, highest drift first.

History vectors are injected with ``set_session_text`` (see
tests/fixtures/temporal.py): the note's current file content is the last
snapshot, the injected text is what it said in the earlier session.
"""

import re
from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import burst_evolution
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import BASE16, set_session_text

BURST_DAY = datetime(2023, 6, 10, 9, 0)
HISTORY = datetime(2023, 9, 1)  # one earlier session -> 2 snapshots per note
# Session 2024-03-15 is 279 days after BURST_DAY -> "9 months later".

EXTRA9 = "quebec romeo sierra tango uniform victor whiskey xray yankee"
BASE4 = "alpha bravo charlie delta"
EXTRA8 = "quebec romeo sierra tango uniform victor whiskey xray"

# title -> (earlier body, current body). Stub drift (title words included):
# Stable 0.0, Moderate 0.18, Large 0.35, Rewritten 0.60.
NOTES = {
    "Stable Note": ("steady unchanging text", "steady unchanging text"),
    "Moderate Note": (BASE16, f"{BASE16} {EXTRA9}"),
    "Large Note": (BASE4, f"{BASE4} {EXTRA8}"),
    "Rewritten Note": ("gardens soil compost", "rockets orbit fuel"),
}


def _burst(
    root: Path,
    notes: dict[str, tuple[str, str]],
    *,
    day: datetime = BURST_DAY,
    history: bool = True,
    builder: VaultBuilder | None = None,
) -> VaultContext:
    builder = builder or VaultBuilder(root)
    for title, (_, current) in notes.items():
        builder.note(title, current, created=day)
    ctx = builder.build(history=[HISTORY] if history else [])
    if history:
        for title, (earlier, _) in notes.items():
            set_session_text(ctx, f"{title}.md", HISTORY, f"# {title}\n\n{earlier}")
    return ctx


def _lines(text: str) -> list[tuple[str, float, str]]:
    return [
        (title, float(drift), label)
        for title, drift, label in re.findall(
            r"- \[\[([^\]]+)\]\]: ([\d.]+) semantic distance \(([a-z ]+)\)", text
        )
    ]


def test_burst_evolution_reports_measured_drift_per_burst_note(tmp_path):
    ctx = _burst(tmp_path, NOTES)

    suggestions = burst_evolution.suggest(ctx)

    assert_valid_suggestions(suggestions, "burst_evolution", must_reference=list(NOTES))
    [suggestion] = suggestions
    assert suggestion.text.startswith("On 2023-06-10, you created 4 notes. 9 months later:\n")
    lines = _lines(suggestion.text)
    assert [(title, label) for title, _, label in lines] == [
        ("Rewritten Note", "very large change"),
        ("Large Note", "large change"),
        ("Moderate Note", "moderate change"),
        ("Stable Note", "small change"),
    ]
    assert lines[-1][1] == 0.0
    # Average drift 0.28 is mid-range: the stable note is named as the anchor.
    assert "[[Stable Note]] have the smallest measured changes" in suggestion.text
    assert sorted(suggestion.notes) == sorted(NOTES)


def test_burst_evolution_ignores_calendar_only_movement(tmp_path):
    """Unchanged notes drift 0 even though every session adds a new calendar tail."""
    unchanged = {f"Steady {i}": ("same words here", "same words here") for i in range(3)}
    ctx = _burst(tmp_path, unchanged)

    [suggestion] = burst_evolution.suggest(ctx)

    assert [drift for _, drift, _ in _lines(suggestion.text)] == [0.0, 0.0, 0.0]
    assert "This group has a low average representation change." in suggestion.text


def test_burst_evolution_low_average_observation(tmp_path):
    # Stub drift per note is 0.10 (17 words kept, 4 added), mean < 0.15.
    nudged = {f"Low {i}": (BASE16, f"{BASE16} quebec romeo sierra tango") for i in range(3)}
    ctx = _burst(tmp_path, nudged)

    [suggestion] = burst_evolution.suggest(ctx)

    assert [label for _, _, label in _lines(suggestion.text)] == ["moderate change"] * 3
    assert "This group has a low average representation change." in suggestion.text


def test_burst_evolution_high_average_observation(tmp_path):
    # Stub drift per note is 0.67 ("rewrite" is the only word kept), mean > 0.45.
    rewritten = {f"Rewrite {i}": ("gardens soil", "rockets orbit") for i in range(3)}
    ctx = _burst(tmp_path, rewritten)

    [suggestion] = burst_evolution.suggest(ctx)

    assert "This group has a high average representation change." in suggestion.text


def test_burst_evolution_needs_a_second_snapshot(tmp_path):
    """Boundary pair: 1 snapshot per note -> no drift to report; 2 -> reported."""
    assert burst_evolution.suggest(_burst(tmp_path / "one", NOTES, history=False)) == []
    assert_valid_suggestions(
        burst_evolution.suggest(_burst(tmp_path / "two", NOTES)), "burst_evolution"
    )


def test_burst_evolution_needs_three_notes_on_the_day(tmp_path):
    """Boundary pair: 2 notes with history is not a burst; 3 is."""
    two = dict(list(NOTES.items())[:2])
    three = dict(list(NOTES.items())[:3])

    assert burst_evolution.suggest(_burst(tmp_path / "two", two)) == []
    assert_valid_suggestions(
        burst_evolution.suggest(_burst(tmp_path / "three", three)), "burst_evolution"
    )


def test_burst_evolution_lists_at_most_seven_notes(tmp_path):
    """Display cap: a 9-note burst lists 7 drift lines but references all 9 notes."""
    nine = {f"Idea {i}": (f"early words {i}", f"early words {i}") for i in range(9)}
    ctx = _burst(tmp_path, nine)

    [suggestion] = burst_evolution.suggest(ctx)

    assert len(_lines(suggestion.text)) == 7
    assert sorted(suggestion.notes) == sorted(nine)


def test_burst_evolution_ignores_geist_journal(tmp_path):
    """Journal notes neither form a burst nor count towards one.

    Day A: 3 regular notes (a burst). Day B: 2 regular notes plus 3 session
    notes, all with history (not a burst). Whatever day order a seed samples,
    only day A is reported, and no session note is listed.
    """
    day_b = datetime(2023, 7, 1, 9, 0)
    builder = VaultBuilder(tmp_path)
    for i in range(2):
        builder.note(f"Near Miss {i}", "near miss words", created=day_b)
    for i in range(3):
        builder.journal(f"Session {i}", "session output words", created=day_b)
    ctx = _burst(tmp_path, dict(list(NOTES.items())[:3]), builder=builder)

    for seed in range(6):
        seeded = VaultContext(
            ctx.vault, ctx.session, seed=seed, function_registry=FunctionRegistry()
        )
        suggestions = burst_evolution.suggest(seeded)
        assert_valid_suggestions(
            suggestions,
            "burst_evolution",
            must_reference=["Stable Note"],
            must_not_reference=["geist journal", "Session", "Near Miss"],
        )
