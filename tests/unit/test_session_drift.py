"""Tests for the session_drift geist.

Trigger: a non-journal note whose SEMANTIC vector in its two latest recorded
sessions differs by drift = 1 - cos > 0.15. The text depends on whether the
note was edited in the last 30 days. Output is capped at 3.

History vectors are injected with ``set_session_text``: a note's current
file content is its latest snapshot.
"""

from datetime import datetime, timedelta
from pathlib import Path

from geistfabrik.default_geists.code import session_drift
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import BASE16, set_history

EARLY, PREVIOUS = datetime(2023, 11, 1), datetime(2024, 1, 10)
OLD_TEXT, NEW_TEXT = "gardens soil compost", "rockets orbit fuel"


def _vault(
    root: Path,
    notes: dict[str, dict[datetime, str]],
    *,
    current: dict[str, str] | None = None,
    edited_days_ago: int = 100,
    journal: dict[str, dict[datetime, str]] | None = None,
) -> VaultContext:
    """``notes`` maps title -> {history date: earlier body}; current body is NEW_TEXT."""
    current = current or {}
    modified = SESSION_DATE - timedelta(days=edited_days_ago)
    builder = VaultBuilder(root)
    for title in notes:
        builder.note(
            title, current.get(title, NEW_TEXT), created=datetime(2023, 1, 1), modified=modified
        )
    for title in journal or {}:
        builder.journal(title, NEW_TEXT, created=datetime(2023, 1, 1), modified=modified)
    ctx = builder.build(history=[EARLY, PREVIOUS])
    for title, history in notes.items():
        set_history(ctx, f"{title}.md", {d: f"# {title}\n\n{body}" for d, body in history.items()})
    for title, history in (journal or {}).items():
        set_history(
            ctx,
            f"geist journal/{title}.md",
            {d: f"# {title}\n\n{body}" for d, body in history.items()},
        )
    return ctx


def test_session_drift_flags_vector_change_since_previous_session(tmp_path):
    # Trigger arithmetic: previous snapshot embeds OLD_TEXT, current NEW_TEXT;
    # only the title words are shared -> drift 0.6 > 0.15. Unedited 100 days.
    ctx = _vault(
        tmp_path, {"Shifting Note": {EARLY: OLD_TEXT, PREVIOUS: OLD_TEXT}, "Steady Note": {}}
    )

    suggestions = session_drift.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "session_drift",
        must_reference=["Shifting Note"],
        must_not_reference=["geist journal", "Steady Note"],
    )
    assert "The note has not been edited in 100 days" in suggestions[0].text


def test_session_drift_does_not_point_at_unstored_snapshots(tmp_path):
    """Contract: the suggestion only asks for what the user can do: reread the note.

    Regression: it said "revisit the snapshots", but only embedding vectors
    are stored per session, never earlier versions of the text, so there is
    nothing for the user to revisit.
    """
    ctx = _vault(tmp_path, {"Shifting Note": {EARLY: OLD_TEXT, PREVIOUS: OLD_TEXT}})

    suggestions = session_drift.suggest(ctx)

    assert [s.text for s in suggestions] == [
        "The semantic representation of [[Shifting Note]] differs between its two "
        "latest recorded sessions. The note has not been edited in 100 days; reread "
        "it and decide what, if anything, changed in its meaning."
    ]


def test_session_drift_mentions_recent_edits_within_thirty_days(tmp_path):
    """Text boundary: edited 30 days ago -> "Recent edits"; 31 days -> "not been edited"."""
    history = {"Shifting Note": {EARLY: OLD_TEXT, PREVIOUS: OLD_TEXT}}
    at_30 = session_drift.suggest(_vault(tmp_path / "30", history, edited_days_ago=30))
    at_31 = session_drift.suggest(_vault(tmp_path / "31", history, edited_days_ago=31))

    assert_valid_suggestions(at_30, "session_drift")
    assert_valid_suggestions(at_31, "session_drift")
    assert "Recent edits may explain the change" in at_30[0].text
    assert "has not been edited in 31 days" in at_31[0].text


def test_session_drift_threshold_boundary(tmp_path):
    """Drift 0.10 (16 shared words + 4 new) is ignored; drift 0.19 (+9 new) is flagged."""
    below = f"{BASE16} quebec romeo sierra tango"
    above = f"{BASE16} quebec romeo sierra tango uniform victor whiskey xray yankee"
    ctx = _vault(
        tmp_path,
        {"Small Shift": {PREVIOUS: BASE16}, "Big Shift": {PREVIOUS: BASE16}},
        current={"Small Shift": below, "Big Shift": above},
    )

    suggestions = session_drift.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "session_drift",
        must_reference=["Big Shift"],
        must_not_reference=["geist journal", "Small Shift"],
    )


def test_session_drift_compares_only_the_two_latest_sessions(tmp_path):
    """A change between the two OLDER sessions is not drift "between its two latest"."""
    ctx = _vault(
        tmp_path, {"Settled Note": {EARLY: OLD_TEXT}, "Shifting Note": {PREVIOUS: OLD_TEXT}}
    )

    suggestions = session_drift.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "session_drift",
        must_reference=["Shifting Note"],
        must_not_reference=["geist journal", "Settled Note"],
    )


def test_session_drift_needs_two_snapshots(tmp_path):
    """Boundary: with only the current session there is nothing to compare."""
    builder = VaultBuilder(tmp_path)
    builder.note("Lonely Note", NEW_TEXT, created=datetime(2023, 1, 1))

    assert session_drift.suggest(builder.build()) == []


def test_session_drift_caps_at_three(tmp_path):
    """Cap: five drifting notes produce exactly three suggestions."""
    ctx = _vault(tmp_path, {f"Shifting {i}": {PREVIOUS: OLD_TEXT} for i in range(5)})

    suggestions = session_drift.suggest(ctx)

    assert len(suggestions) == 3
    assert_valid_suggestions(suggestions, "session_drift")
    assert len({s.notes[0] for s in suggestions}) == 3


def test_session_drift_excludes_geist_journal(tmp_path):
    """A rewritten (--force) session note also changes vector; it is output, not a note.

    Both directions: the drifting user note is flagged, the equally drifting
    session note is not.
    """
    ctx = _vault(
        tmp_path,
        {"Shifting Note": {PREVIOUS: OLD_TEXT}},
        journal={"2024-01-10": {PREVIOUS: OLD_TEXT}},
    )

    suggestions = session_drift.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "session_drift",
        must_reference=["Shifting Note"],
        must_not_reference=["geist journal", "2024-01-10"],
    )


def test_session_drift_is_deterministic_for_a_seed(tmp_path):
    history = {f"Shifting {i}": {PREVIOUS: OLD_TEXT} for i in range(5)}

    first = session_drift.suggest(_vault(tmp_path / "a", history))
    second = session_drift.suggest(_vault(tmp_path / "b", history))

    assert len(first) == 3
    assert [s.text for s in first] == [s.text for s in second]
