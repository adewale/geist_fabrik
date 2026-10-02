"""Tests for the concept_drift geist (absorbs session_drift and drift_velocity_anomaly).

Trigger: a non-journal note with >= 3 snapshots whose SEMANTIC drift
1 - cos(first, last) >= 0.2. Among its 5 current nearest neighbours the geist
names the one whose current vector is most aligned with the drift direction
(last - first). Capped at 2. Vectors are content-cached, so the text speaks of
edits: "You've rewritten [[X]] since your session on D", where D is the latest
earlier session whose vector differs from today's by > 0.15, plus "and it has
been changing more lately" when the 3-session windowed drift grew by > 0.1.

History vectors are injected with ``set_history``: a note's current file
content is its latest snapshot.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import concept_drift
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import BASE16, set_history

H1, H2 = datetime(2023, 10, 1), datetime(2023, 12, 1)
GARDEN, ROCKETS = "gardens soil compost", "rockets orbit fuel launch"
# "Drifting Note" said GARDEN in both earlier sessions and says ROCKETS now:
# drift 1 - 2/sqrt(30) = 0.63 (only the title words are shared). The drift
# direction points towards the rocket vocabulary and away from the garden one.
DRIFTED = {H1: GARDEN, H2: GARDEN}


def _vault(
    root: Path,
    notes: dict[str, tuple[str, dict[datetime, str]]],
    *,
    history: list[datetime] | None = None,
    journal: dict[str, tuple[str, dict[datetime, str]]] | None = None,
) -> VaultContext:
    """``notes`` maps title -> (current body, {history date: earlier body})."""
    builder = VaultBuilder(root)
    for title, (body, _) in notes.items():
        builder.note(title, body, created=datetime(2023, 1, 1))
    for title, (body, _) in (journal or {}).items():
        builder.journal(title, body, created=datetime(2023, 1, 1))
    ctx = builder.build(history=[H1, H2] if history is None else history)
    for folder, entries in (("", notes), ("geist journal/", journal or {})):
        for title, (_, texts) in entries.items():
            set_history(
                ctx, f"{folder}{title}.md", {d: f"# {title}\n\n{b}" for d, b in texts.items()}
            )
    return ctx


NEIGHBOURS = {
    "Rocket Note": (f"{ROCKETS} pad", {}),
    "Garden Note": (f"{GARDEN} worms", {}),
}


def test_concept_drift_names_the_neighbour_aligned_with_the_drift(tmp_path):
    ctx = _vault(tmp_path, {"Drifting Note": (ROCKETS, DRIFTED), **NEIGHBOURS})

    suggestions = concept_drift.suggest(ctx)

    assert_valid_suggestions(suggestions, "concept_drift")
    assert [(s.text, s.notes) for s in suggestions] == [
        (
            "You've rewritten [[Drifting Note]] since your session on 2023-12-01. Of its "
            "current neighbours, the edits moved it most toward [[Rocket Note]]. "
            "What were you reaching for?",
            ["Drifting Note", "Rocket Note"],
        )
    ]


def test_concept_drift_dates_the_latest_session_before_the_rewrite(tmp_path):
    """Contract: "since your session on D" names the latest earlier session
    whose vector differs from today's by more than 0.15; a later typo-level
    tweak (drift 0.10) does not move D.

    Regression (merged from session_drift): the text gave only the first and
    last snapshot months ("changed between 2023-10 and 2024-03"), never which
    session the note has been rewritten since.
    """
    tweaked = f"{BASE16} quebec romeo sierra tango"
    ctx = _vault(
        tmp_path,
        {
            "Recent Edit": (ROCKETS, DRIFTED),
            "Earlier Edit": (ROCKETS, {H1: GARDEN, H2: ROCKETS}),
            "Tweaked Note": (tweaked, {H1: "kettle teapot boiling", H2: BASE16}),
            **NEIGHBOURS,
            "Base Note": (f"{BASE16} zulu", {}),
        },
    )

    since = {
        s.notes[0]: s.text.split("since your session on ")[1][:10]
        for seed in range(10)
        for s in concept_drift.suggest(
            VaultContext(ctx.vault, ctx.session, seed=seed, function_registry=FunctionRegistry())
        )
    }

    assert since == {
        "Recent Edit": "2023-12-01",
        "Earlier Edit": "2023-10-01",
        "Tweaked Note": "2023-10-01",
    }


def test_concept_drift_says_when_a_note_is_changing_more_lately(tmp_path):
    """Contract: "and it has been changing more lately" is said only when the
    drift across the last three recorded sessions exceeds the drift across the
    first three by more than 0.1.

    Regression (merged from drift_velocity_anomaly): concept_drift never
    said whether the change was recent; a note that changed only in its
    latest sessions read the same as one that changed long ago and settled.
    """
    history = [datetime(2023, m, 1) for m in (9, 10, 11, 12)]
    home, away = GARDEN, ROCKETS
    ctx = _vault(
        tmp_path,
        {
            # home, home, home, away | away: windows 0.0 -> 0.8
            "Late Mover": (away, {d: home for d in history[:3]}),
            # home, away, away, away | away: windows 0.8 -> 0.0
            "Early Mover": (away, {history[0]: home}),
            **NEIGHBOURS,
        },
        history=history,
    )

    openings = {s.notes[0]: s.text.split(". Of its")[0] for s in concept_drift.suggest(ctx)}

    assert openings == {
        "Late Mover": (
            "You've rewritten [[Late Mover]] since your session on 2023-11-01, "
            "and it has been changing more lately"
        ),
        "Early Mover": "You've rewritten [[Early Mover]] since your session on 2023-09-01",
    }


def test_concept_drift_threshold_boundary(tmp_path):
    """Drift 0.18 (16 words, +9 new) is below 0.2; drift 0.35 (4 words, +8 new) is above."""
    ctx = _vault(
        tmp_path,
        {
            "Mild Note": (
                f"{BASE16} quebec romeo sierra tango uniform victor whiskey xray yankee",
                {H1: BASE16, H2: BASE16},
            ),
            "Wild Note": (
                "alpha bravo charlie delta quebec romeo sierra tango uniform victor whiskey xray",
                {H1: "alpha bravo charlie delta", H2: "alpha bravo charlie delta"},
            ),
            **NEIGHBOURS,
        },
    )

    suggestions = concept_drift.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "concept_drift",
        must_reference=["Wild Note"],
    )
    assert all(s.notes[0] == "Wild Note" for s in suggestions)


def test_concept_drift_needs_three_snapshots(tmp_path):
    """Boundary pair: 2 snapshots -> not enough history; 3 -> flagged."""
    two = _vault(
        tmp_path / "two", {"Drifting Note": (ROCKETS, {H2: GARDEN}), **NEIGHBOURS}, history=[H2]
    )
    three = _vault(tmp_path / "three", {"Drifting Note": (ROCKETS, DRIFTED), **NEIGHBOURS})

    assert concept_drift.suggest(two) == []
    assert_valid_suggestions(
        concept_drift.suggest(three), "concept_drift", must_reference=["Drifting Note"]
    )


def test_concept_drift_caps_at_two(tmp_path):
    """Cap: three drifting notes produce exactly two suggestions."""
    notes = {f"Drifting {i}": (ROCKETS, DRIFTED) for i in range(3)}
    ctx = _vault(tmp_path, {**notes, **NEIGHBOURS})

    suggestions = concept_drift.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "concept_drift")
    assert suggestions[0].notes[0] != suggestions[1].notes[0]


def test_concept_drift_excludes_geist_journal(tmp_path):
    """Both directions: the user's drifting note is reported against a user
    neighbour. A session note that drifted the same way is not reported, and a
    session note that quotes the new text verbatim (so is the MOST aligned
    neighbour) is not offered as the comparison."""
    ctx = _vault(
        tmp_path,
        {"Drifting Note": (ROCKETS, DRIFTED), **NEIGHBOURS},
        journal={"2023-12-02": (ROCKETS, DRIFTED)},
    )

    suggestions = concept_drift.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "concept_drift",
        must_reference=["Drifting Note", "Rocket Note"],
        must_not_reference=["geist journal", "2023-12-02"],
    )


def test_concept_drift_is_deterministic_for_a_seed(tmp_path):
    notes = {f"Drifting {i}": (ROCKETS, DRIFTED) for i in range(3)}

    first = concept_drift.suggest(_vault(tmp_path / "a", {**notes, **NEIGHBOURS}))
    second = concept_drift.suggest(_vault(tmp_path / "b", {**notes, **NEIGHBOURS}))

    assert len(first) == 2
    assert [s.text for s in first] == [s.text for s in second]


def test_concept_drift_skips_a_note_that_moved_away_from_every_neighbour(tmp_path):
    """Contract: the named neighbour lies in the direction of the change
    (positive alignment); if the note moved away from all of them, nothing is
    named.

    Regression: the best of the alignments was named even when negative, so
    "aligns most with [[Garden Note]]" was said of a note that had moved away
    from the garden vocabulary.
    """
    ctx = _vault(
        tmp_path,
        {"Drifting Note": (ROCKETS, DRIFTED), "Garden Note": NEIGHBOURS["Garden Note"]},
    )

    assert concept_drift.suggest(ctx) == []
