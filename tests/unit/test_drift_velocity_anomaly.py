"""Tests for the drift_velocity_anomaly geist.

Trigger: >= 5 sessions and a user note with >= 5 snapshots whose windowed
drift rate (window of 3 consecutive snapshots, rate = 1 - cos(first, last) on
the semantic part) grows by MORE than 0.1 from the first window to the last,
and whose most similar current neighbour has similarity > 0.5. Capped at 2.

Fixture arithmetic (lexical stub, 4 history sessions + the current one):
"Mover" said HOME in the first three snapshots and says AWAY now (and in the
fourth). HOME and AWAY share only the title word, so the first window drifts
1 - cos(HOME, HOME) = 0 and the last window 1 - cos(HOME, AWAY) = 1 - 1/5 = 0.8:
an increase of 0.8 > 0.1. "Destination" shares the four AWAY words with Mover's
current text: cosine 4 / sqrt(5 * 6) = 0.73 > 0.5.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import drift_velocity_anomaly
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import BASE16, set_history

HISTORY = [datetime(2023, m, 1) for m in (9, 10, 11, 12)]
HOME, AWAY = "gardens soil compost mulch", "rockets orbit fuel launch"
STEADY_THEN_FAST = {HISTORY[0]: HOME, HISTORY[1]: HOME, HISTORY[2]: HOME}
DESTINATION = {"Destination": (f"{AWAY} pad", {})}


def _vault(
    root: Path,
    notes: dict[str, tuple[str, dict[datetime, str]]],
    *,
    history: list[datetime] = HISTORY,
    journal: dict[str, tuple[str, dict[datetime, str]]] | None = None,
) -> VaultContext:
    """``notes`` maps title -> (current body, {history date: earlier body})."""
    builder = VaultBuilder(root)
    for title, (body, _) in notes.items():
        builder.note(title, body, created=datetime(2023, 1, 1))
    for title, (body, _) in (journal or {}).items():
        builder.journal(title, body, created=datetime(2023, 1, 1))
    ctx = builder.build(history=history)
    for folder, entries in (("", notes), ("geist journal/", journal or {})):
        for title, (_, texts) in entries.items():
            set_history(
                ctx, f"{folder}{title}.md", {d: f"# {title}\n\n{b}" for d, b in texts.items()}
            )
    return ctx


def test_drift_velocity_anomaly_reports_an_accelerating_note(tmp_path):
    ctx = _vault(tmp_path, {"Mover": (AWAY, STEADY_THEN_FAST), **DESTINATION})

    suggestions = drift_velocity_anomaly.suggest(ctx)

    assert_valid_suggestions(
        suggestions, "drift_velocity_anomaly", must_reference=["Mover", "Destination"]
    )
    assert [s.notes for s in suggestions] == [["Mover", "Destination"]]
    assert suggestions[0].text == (
        "[[Mover]] has been changing more lately: its semantic representation moved "
        "0.00 across its first three recorded sessions and 0.80 across its last three. "
        "It is currently similar to [[Destination]]. What do the source edits show?"
    )


def test_drift_velocity_anomaly_reports_change_per_sessions_not_velocity(tmp_path):
    """Contract: the rates are change across windows of three recorded
    sessions; sessions are irregular, so the text makes no velocity claim.

    Regression: the text said "velocity: 0.00 → 0.80", which reads as change
    per unit time, although a user who invoked daily and then monthly gets
    apparent "acceleration" from session spacing alone.
    """
    ctx = _vault(tmp_path, {"Mover": (AWAY, STEADY_THEN_FAST), **DESTINATION})

    (suggestion,) = drift_velocity_anomaly.suggest(ctx)

    assert "velocity" not in suggestion.text
    assert "across its first three recorded sessions" in suggestion.text


def test_drift_velocity_anomaly_acceleration_threshold(tmp_path):
    """Boundary pair on the 0.1 increase. The first window never moves (BASE16
    three times); the last window adds k new words to the 17 words of
    "# Mover BASE16": drift 1 - sqrt(17 / (17 + k)). k = 3 gives 0.08 (not
    accelerating), k = 5 gives 0.12 (accelerating)."""
    base = {HISTORY[0]: BASE16, HISTORY[1]: BASE16, HISTORY[2]: BASE16}
    peer = {"Peer": (f"{BASE16} zulu", {})}  # similarity to Mover >= 0.8 either way
    slow = _vault(tmp_path / "slow", {"Mover": (f"{BASE16} quebec romeo sierra", base), **peer})
    fast = _vault(
        tmp_path / "fast",
        {"Mover": (f"{BASE16} quebec romeo sierra tango uniform", base), **peer},
    )

    assert drift_velocity_anomaly.suggest(slow) == []
    suggestions = drift_velocity_anomaly.suggest(fast)
    assert_valid_suggestions(suggestions, "drift_velocity_anomaly", must_reference=["Mover"])
    assert [s.notes for s in suggestions] == [["Mover", "Peer"]]


def test_drift_velocity_anomaly_needs_a_similar_neighbour(tmp_path):
    """Boundary pair on the > 0.5 neighbour similarity: a neighbour sharing
    one AWAY word (cosine 1 / sqrt(5 * 5) = 0.2) is not named and the note is
    not reported; one sharing all four (0.73) is."""
    far = _vault(
        tmp_path / "far",
        {"Mover": (AWAY, STEADY_THEN_FAST), "Distant": ("rockets cheese bread wine", {})},
    )
    near = _vault(tmp_path / "near", {"Mover": (AWAY, STEADY_THEN_FAST), **DESTINATION})

    assert drift_velocity_anomaly.suggest(far) == []
    assert_valid_suggestions(
        drift_velocity_anomaly.suggest(near),
        "drift_velocity_anomaly",
        must_reference=["Destination"],
    )


def test_drift_velocity_anomaly_needs_five_sessions(tmp_path):
    """Boundary pair: with 4 sessions (HOME, HOME, HOME, then AWAY now) the two
    windows already show a 0.8 increase, but the geist requires 5 sessions."""
    four = _vault(
        tmp_path / "four", {"Mover": (AWAY, STEADY_THEN_FAST), **DESTINATION}, history=HISTORY[:3]
    )
    five = _vault(tmp_path / "five", {"Mover": (AWAY, STEADY_THEN_FAST), **DESTINATION})

    assert four.session_count() == 4
    assert drift_velocity_anomaly.suggest(four) == []
    assert_valid_suggestions(
        drift_velocity_anomaly.suggest(five), "drift_velocity_anomaly", must_reference=["Mover"]
    )


def test_drift_velocity_anomaly_caps_at_two(tmp_path):
    """Cap: three accelerating notes produce exactly two suggestions."""
    movers = {f"Mover {i}": (AWAY, STEADY_THEN_FAST) for i in range(3)}
    ctx = _vault(tmp_path, {**movers, **DESTINATION})

    suggestions = drift_velocity_anomaly.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "drift_velocity_anomaly")
    assert {s.notes[0] for s in suggestions} < set(movers)
    assert suggestions[0].notes[0] != suggestions[1].notes[0]


def test_drift_velocity_anomaly_excludes_geist_journal(tmp_path):
    """Both directions: the user's accelerating note is reported against a
    user neighbour. A session note with the same trajectory is not reported,
    and a session note quoting Mover's current text verbatim (its most similar
    note) is not offered as the neighbour."""
    ctx = _vault(
        tmp_path,
        {"Mover": (AWAY, STEADY_THEN_FAST), **DESTINATION},
        journal={"2023-12-01": (AWAY, STEADY_THEN_FAST), "2023-11-01": ("Mover " + AWAY, {})},
    )

    suggestions = drift_velocity_anomaly.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "drift_velocity_anomaly",
        must_reference=["Mover", "Destination"],
        must_not_reference=["geist journal", "2023-12-01", "2023-11-01"],
    )
