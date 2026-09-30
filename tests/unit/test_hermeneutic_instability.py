"""Tests for the hermeneutic_instability geist.

Trigger: a non-journal note with >= 3 snapshots whose SEMANTIC vectors over
its last 5 sessions have mean Euclidean distance from their centroid > 0.2,
while the note itself has not been edited for > 60 days. Capped at 2.

History vectors are injected with ``set_history``: a note's current file
content is its latest snapshot. Stub instability values quoted below were
computed from the lexical stub (semantic weight 0.9, title words included).
"""

from datetime import datetime, timedelta
from pathlib import Path

from geistfabrik.default_geists.code import hermeneutic_instability
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import BASE16, set_history

H1, H2 = datetime(2023, 10, 1), datetime(2023, 12, 1)
CURRENT = "violin bow rosin"


def _vault(
    root: Path,
    notes: dict[str, dict[datetime, str]],
    *,
    current: dict[str, str] | None = None,
    history: list[datetime] | None = None,
    unedited_days: int = 200,
    journal: dict[str, dict[datetime, str]] | None = None,
) -> VaultContext:
    """``notes`` maps title -> {history date: earlier body}; current body defaults to CURRENT."""
    current = current or {}
    modified = SESSION_DATE - timedelta(days=unedited_days)
    created = datetime(2022, 1, 1)
    builder = VaultBuilder(root)
    for title in notes:
        builder.note(title, current.get(title, CURRENT), created=created, modified=modified)
    for title in journal or {}:
        builder.journal(title, CURRENT, created=created, modified=modified)
    ctx = builder.build(history=[H1, H2] if history is None else history)
    for folder, entries in (("", notes), ("geist journal/", journal or {})):
        for title, texts in entries.items():
            set_history(
                ctx, f"{folder}{title}.md", {d: f"# {title}\n\n{b}" for d, b in texts.items()}
            )
    return ctx


UNSTABLE = {H1: "gardens soil compost", H2: "rockets orbit fuel"}  # instability 0.57


def test_hermeneutic_instability_flags_unedited_note_with_varying_vectors(tmp_path):
    # Trigger arithmetic: three mutually disjoint bodies -> instability 0.57 > 0.2;
    # unedited for 200 days > 60.
    ctx = _vault(tmp_path, {"Unstable Note": UNSTABLE, "Constant Note": {}})

    suggestions = hermeneutic_instability.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "hermeneutic_instability",
        must_reference=["Unstable Note"],
        must_not_reference=["geist journal", "Constant Note"],
    )
    assert suggestions[0].text == (
        "The semantic representation of [[Unstable Note]] varied across its last 3 recorded "
        "sessions, while the note has not been edited in 200 days. Review the snapshots "
        "before deciding whether the variation is meaningful."
    )


def test_hermeneutic_instability_needs_three_snapshots(tmp_path):
    """Boundary pair: 2 snapshots (1 history session) -> nothing; 3 -> flagged."""
    two = _vault(tmp_path / "two", {"Unstable Note": {H2: "rockets orbit fuel"}}, history=[H2])
    three = _vault(tmp_path / "three", {"Unstable Note": UNSTABLE})

    assert hermeneutic_instability.suggest(two) == []
    assert_valid_suggestions(hermeneutic_instability.suggest(three), "hermeneutic_instability")


def test_hermeneutic_instability_requires_more_than_sixty_unedited_days(tmp_path):
    """Boundary pair: edited 60 days ago -> explained by edits; 61 days -> flagged."""
    at_60 = _vault(tmp_path / "60", {"Unstable Note": UNSTABLE}, unedited_days=60)
    at_61 = _vault(tmp_path / "61", {"Unstable Note": UNSTABLE}, unedited_days=61)

    assert hermeneutic_instability.suggest(at_60) == []
    assert_valid_suggestions(hermeneutic_instability.suggest(at_61), "hermeneutic_instability")


def test_hermeneutic_instability_threshold_boundary(tmp_path):
    """Instability 0.19 (2 words swapped in each session) is ignored; 0.23 (3 words) is flagged."""
    ctx = _vault(
        tmp_path,
        {
            "Slight Wobble": {H1: BASE16, H2: f"{BASE16} quebec romeo"},
            "Real Wobble": {H1: BASE16, H2: f"{BASE16} quebec romeo sierra"},
        },
        current={
            "Slight Wobble": f"{BASE16} sierra tango",
            "Real Wobble": f"{BASE16} tango uniform victor",
        },
    )

    suggestions = hermeneutic_instability.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "hermeneutic_instability",
        must_reference=["Real Wobble"],
        must_not_reference=["geist journal", "Slight Wobble"],
    )


def test_hermeneutic_instability_looks_at_last_five_sessions_only(tmp_path):
    """Six snapshots: a change in the oldest one falls outside the 5-session window.

    "Early Change" differs only in the first of 6 sessions (last 5 identical);
    "Late Change" differs only in the 2nd, which is inside the window
    (instability 0.32).
    """
    dates = [datetime(2023, month, 1) for month in (4, 6, 8, 10, 12)]
    ctx = _vault(
        tmp_path,
        {
            "Early Change": {dates[0]: "gardens soil compost"},
            "Late Change": {dates[1]: "gardens soil compost"},
        },
        history=dates,
    )

    suggestions = hermeneutic_instability.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "hermeneutic_instability",
        must_reference=["Late Change"],
        must_not_reference=["geist journal", "Early Change"],
    )
    assert "its last 5 recorded sessions" in suggestions[0].text


def test_hermeneutic_instability_caps_at_two(tmp_path):
    """Cap: four unstable notes produce exactly two suggestions."""
    ctx = _vault(tmp_path, {f"Unstable {i}": UNSTABLE for i in range(4)})

    suggestions = hermeneutic_instability.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "hermeneutic_instability")
    assert suggestions[0].notes != suggestions[1].notes


def test_hermeneutic_instability_excludes_geist_journal(tmp_path):
    """Both directions: an unstable user note is flagged, an equally unstable
    (rewritten) session note is not."""
    ctx = _vault(tmp_path, {"Unstable Note": UNSTABLE}, journal={"2023-12-01": UNSTABLE})

    suggestions = hermeneutic_instability.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "hermeneutic_instability",
        must_reference=["Unstable Note"],
        must_not_reference=["geist journal", "2023-12-01"],
    )


def test_hermeneutic_instability_is_deterministic_for_a_seed(tmp_path):
    notes = {f"Unstable {i}": UNSTABLE for i in range(4)}

    first = hermeneutic_instability.suggest(_vault(tmp_path / "a", notes))
    second = hermeneutic_instability.suggest(_vault(tmp_path / "b", notes))

    assert len(first) == 2
    assert [s.text for s in first] == [s.text for s in second]
