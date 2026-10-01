"""Tests for the cluster_evolution_tracker geist.

Trigger: >= 15 user notes, >= 2 sessions, >= 2 current clusters, and a note
whose cluster in the most recent previous session continues (by majority of
its members) as a DIFFERENT current cluster. Up to 3 candidates are collected
and 2 are sampled.

Previous-session labels are written by the production writer: a VaultContext
for the history session runs ``get_clusters()``, exactly as a geist calling it
during that session would have. ``set_session_text`` decides which cluster a
note sat in back then.

Fixture arithmetic (lexical stub, HDBSCAN min_cluster_size=5, min_samples=3):
eight GARDEN notes and eight ROCKET notes share no content words, so they form
two clusters; a mover shares its six topic words with one group and nothing
with the other, so it joins whichever group its text names.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik import Session
from geistfabrik.default_geists.code import cluster_evolution_tracker
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SEED, VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import set_session_text

H0, H1 = datetime(2024, 1, 1), datetime(2024, 2, 1)
CREATED = datetime(2023, 1, 1)
GARDEN = "gardens soil compost seedlings mulch trowel"
ROCKET = "rockets orbit fuel launch thrust nozzle"


def _vault(
    root: Path,
    movers: dict[str, dict[datetime, str]],
    *,
    gardens: int = 8,
    rockets: int = 8,
    history: tuple[datetime, ...] = (H1,),
    journal: dict[str, dict[datetime, str]] | None = None,
) -> VaultContext:
    """``movers`` maps title -> {history date: topic it was about then}; every
    mover is about GARDEN now. History sessions get production cluster labels."""
    builder = VaultBuilder(root)
    for i in range(gardens):
        builder.note(f"Garden {i}", f"{GARDEN} plot{i}", created=CREATED)
    for i in range(rockets):
        builder.note(f"Rocket {i}", f"{ROCKET} stage{i}", created=CREATED)
    for title in movers:
        builder.note(title, f"{GARDEN} wanderer", created=CREATED)
    for title in journal or {}:
        builder.journal(title, f"{GARDEN} wanderer", created=CREATED)
    ctx = builder.build(history=history)

    planted = [("", movers), ("geist journal/", journal or {})]
    for folder, entries in planted:
        for title, texts in entries.items():
            for date, topic in texts.items():
                set_session_text(ctx, f"{folder}{title}.md", date, f"# {title}\n\n{topic} wanderer")
    for date in history:
        VaultContext(ctx.vault, Session(date, ctx.db), seed=SEED).get_clusters()
    return ctx


def test_cluster_evolution_tracker_reports_the_note_that_changed_cluster(tmp_path):
    """Happy path, and the regression for label drift.

    Bug: the geist compared label strings. A label is c-TF-IDF keywords of the
    cluster's members, so when "Mover" joined the garden cluster the garden
    label changed and every Garden note was reported as having "migrated",
    while the actual mover could be sampled away. Only "Mover" moved.
    """
    ctx = _vault(tmp_path, {"Mover": {H1: ROCKET}})

    suggestions = cluster_evolution_tracker.suggest(ctx)

    assert_valid_suggestions(suggestions, "cluster_evolution_tracker", must_reference=["Mover"])
    assert [s.notes for s in suggestions] == [["Mover"]]
    assert suggestions[0].text.startswith("[[Mover]] migrated from 'rocket")
    assert "' cluster to 'garden" in suggestions[0].text


def test_cluster_evolution_tracker_note_that_stayed_is_not_reported(tmp_path):
    """Boundary pair on migration itself: the same vault, but the mover was
    already about GARDEN last session, so nothing moved."""
    stayed = _vault(tmp_path / "stayed", {"Mover": {H1: GARDEN}})
    moved = _vault(tmp_path / "moved", {"Mover": {H1: ROCKET}})

    assert cluster_evolution_tracker.suggest(stayed) == []
    assert_valid_suggestions(
        cluster_evolution_tracker.suggest(moved),
        "cluster_evolution_tracker",
        must_reference=["Mover"],
    )


def test_cluster_evolution_tracker_compares_with_the_most_recent_session(tmp_path):
    """The mover left the rocket cluster before H1, so relative to H1 (the
    previous session) it has not moved; the older H0 move is not re-reported."""
    ctx = _vault(tmp_path, {"Mover": {H0: ROCKET}}, history=(H0, H1))

    assert cluster_evolution_tracker.suggest(ctx) == []


def test_cluster_evolution_tracker_needs_fifteen_notes(tmp_path):
    """Boundary pair: 6 + 7 + 1 mover = 14 notes is too few; 7 + 7 + 1 = 15 fires."""
    fourteen = _vault(tmp_path / "14", {"Mover": {H1: ROCKET}}, gardens=6, rockets=7)
    fifteen = _vault(tmp_path / "15", {"Mover": {H1: ROCKET}}, gardens=7, rockets=7)

    assert len(fourteen.notes()) == 14
    assert cluster_evolution_tracker.suggest(fourteen) == []
    # Only the note count is short: both clusters still form.
    assert len(fourteen.get_clusters()) == 2
    assert_valid_suggestions(
        cluster_evolution_tracker.suggest(fifteen),
        "cluster_evolution_tracker",
        must_reference=["Mover"],
    )


def test_cluster_evolution_tracker_caps_at_two(tmp_path):
    """Cap: four movers (all moved rocket -> garden) produce exactly two
    suggestions, each about a different mover."""
    movers = {f"Mover {i}": {H1: ROCKET} for i in range(4)}
    ctx = _vault(tmp_path, movers)

    suggestions = cluster_evolution_tracker.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "cluster_evolution_tracker")
    reported = {s.notes[0] for s in suggestions}
    assert len(reported) == 2 and reported <= set(movers)


def test_cluster_evolution_tracker_excludes_geist_journal(tmp_path):
    """Both directions: a session note that moved exactly like the user's
    mover is never reported; the user's mover still is."""
    ctx = _vault(
        tmp_path,
        {"Mover": {H1: ROCKET}},
        journal={"2024-02-01": {H1: ROCKET}},
    )

    suggestions = cluster_evolution_tracker.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "cluster_evolution_tracker",
        must_reference=["Mover"],
        must_not_reference=["geist journal", "2024-02-01"],
    )
