"""Tests for the concept_drift geist.

Trigger: a non-journal note with >= 3 snapshots whose SEMANTIC drift
1 - cos(first, last) >= 0.2. Among its 5 current nearest neighbours the geist
names the one whose current vector is most aligned with the drift direction
(last - first). Capped at 2.

History vectors are injected with ``set_history``: a note's current file
content is its latest snapshot.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import concept_drift
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
    assert [s.notes for s in suggestions] == [["Drifting Note", "Rocket Note"]]
    assert suggestions[0].text.startswith(
        "The semantic representation of [[Drifting Note]] changed between 2023-10 and 2024-03."
    )


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
        journal={"2023-12-01": (ROCKETS, DRIFTED)},
    )

    suggestions = concept_drift.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "concept_drift",
        must_reference=["Drifting Note", "Rocket Note"],
        must_not_reference=["geist journal", "2023-12-01"],
    )


def test_concept_drift_is_deterministic_for_a_seed(tmp_path):
    notes = {f"Drifting {i}": (ROCKETS, DRIFTED) for i in range(3)}

    first = concept_drift.suggest(_vault(tmp_path / "a", {**notes, **NEIGHBOURS}))
    second = concept_drift.suggest(_vault(tmp_path / "b", {**notes, **NEIGHBOURS}))

    assert len(first) == 2
    assert [s.text for s in first] == [s.text for s in second]
