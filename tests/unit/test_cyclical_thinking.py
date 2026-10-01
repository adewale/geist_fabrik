"""Tests for the cyclical_thinking geist.

Trigger: >= 5 sessions and a user note whose semantic similarity to its FIRST
snapshot goes low -> high (threshold 0.7) at least twice across the later
snapshots. Up to 5 cycling notes become candidates and 2 are sampled.

Fixture arithmetic (lexical stub): HOME and AWAY share only the note's title
words. For "Cycler" (1 title word + 4 HOME words vs 1 + 4 AWAY words) the
cosine of a HOME snapshot with an AWAY one is 1/5 = 0.2 (< 0.7, "low"), and of
two HOME snapshots 1.0 ("high"). The current snapshot is the file content
(HOME); history snapshots are rewritten with ``set_history``.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import cyclical_thinking
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import set_history

HISTORY = [datetime(2023, m, 1) for m in (9, 10, 11, 12)] + [datetime(2024, 1, 1)]
HOME, AWAY = "gardens soil compost mulch", "rockets orbit fuel launch"
# First snapshot HOME, then AWAY, HOME, AWAY, HOME, and HOME now:
# similarities to the first are low, high, low, high, high -> two low->high cycles.
TWO_CYCLES = {HISTORY[1]: AWAY, HISTORY[3]: AWAY}
ONE_CYCLE = {HISTORY[1]: AWAY}


def _vault(
    root: Path,
    notes: dict[str, dict[datetime, str]],
    *,
    history: list[datetime] = HISTORY,
    journal: dict[str, dict[datetime, str]] | None = None,
) -> VaultContext:
    """``notes`` maps title -> {history date: earlier body}; current body is HOME."""
    builder = VaultBuilder(root)
    for title in notes:
        builder.note(title, HOME, created=datetime(2023, 1, 1))
    for title in journal or {}:
        builder.journal(title, HOME, created=datetime(2023, 1, 1))
    ctx = builder.build(history=history)
    for folder, entries in (("", notes), ("geist journal/", journal or {})):
        for title, texts in entries.items():
            set_history(
                ctx, f"{folder}{title}.md", {d: f"# {title}\n\n{b}" for d, b in texts.items()}
            )
    return ctx


def test_cyclical_thinking_reports_a_note_that_returned_twice(tmp_path):
    ctx = _vault(tmp_path, {"Cycler": TWO_CYCLES})

    suggestions = cyclical_thinking.suggest(ctx)

    assert_valid_suggestions(suggestions, "cyclical_thinking", must_reference=["Cycler"])
    assert [s.notes for s in suggestions] == [["Cycler"]]
    assert suggestions[0].text.startswith(
        "[[Cycler]] shows cyclical thinking—returning to similar semantic states "
        "across sessions (2023-09 to 2024-03)."
    )


def test_cyclical_thinking_needs_two_cycles(tmp_path):
    """Boundary pair: one low->high return is not a cycle pattern; two are."""
    one = _vault(tmp_path / "one", {"Cycler": ONE_CYCLE})
    two = _vault(tmp_path / "two", {"Cycler": TWO_CYCLES})

    assert cyclical_thinking.suggest(one) == []
    assert_valid_suggestions(
        cyclical_thinking.suggest(two), "cyclical_thinking", must_reference=["Cycler"]
    )


def test_cyclical_thinking_fires_with_five_sessions(tmp_path):
    """Regression for an off-by-one in the history guard.

    Bug: the geist required 6 sessions "for 2 cycles", but two cycles need only
    5 snapshots (first state, then low, high, low, high), so a note that cycled
    twice in 5 sessions was never reported. (Fewer than 5 snapshots cannot hold
    two cycles at all, so there is no 4-session counterpart to test.)
    """
    # Four history sessions HOME, AWAY, HOME, AWAY, then HOME now.
    ctx = _vault(tmp_path, {"Cycler": TWO_CYCLES}, history=HISTORY[:4])

    assert ctx.session_count() == 5
    assert_valid_suggestions(
        cyclical_thinking.suggest(ctx), "cyclical_thinking", must_reference=["Cycler"]
    )


def test_cyclical_thinking_caps_at_two(tmp_path):
    """Cap: three cycling notes produce exactly two suggestions."""
    ctx = _vault(tmp_path, {f"Cycler {i}": TWO_CYCLES for i in range(3)})

    suggestions = cyclical_thinking.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "cyclical_thinking")
    assert suggestions[0].notes != suggestions[1].notes


def test_cyclical_thinking_excludes_geist_journal(tmp_path):
    """Both directions: a session note with the same cycling history is never
    reported; the user's cycling note is."""
    ctx = _vault(tmp_path, {"Cycler": TWO_CYCLES}, journal={"2023-12-01": TWO_CYCLES})

    suggestions = cyclical_thinking.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "cyclical_thinking",
        must_reference=["Cycler"],
        must_not_reference=["geist journal", "2023-12-01"],
    )
