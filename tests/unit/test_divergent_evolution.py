"""Tests for the divergent_evolution geist.

Trigger: at least 2 linked (source -> target) note pairs exist, and for a
pair the per-session SEMANTIC similarity over >= 3 shared sessions falls:
mean(first half) - mean(second half) > 0.15. Capped at 2.

History vectors are injected with ``set_history``: a note's current file
content is its latest snapshot.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import divergent_evolution
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import set_history

H1, H2 = datetime(2023, 10, 1), datetime(2023, 12, 1)
SHARED = "gardens soil compost"
# A note whose earlier bodies were SHARED and whose current body is NEW has
# per-session similarity to a SHARED note of [0.75, 0.75, 0.0] (the title word
# differs): early mean 0.75 - late mean 0.375 = 0.375 > 0.15.
NEW = "rockets orbit fuel"
DRIFTED = {H1: SHARED, H2: SHARED}


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


def test_divergent_evolution_flags_linked_notes_growing_apart(tmp_path):
    # "Drifter" said SHARED in both earlier sessions and NEW now; "Anchor"
    # still says SHARED. Hub links to both (2 linked pairs).
    ctx = _vault(
        tmp_path,
        {
            "Hub": (SHARED + " [[Drifter]] [[Anchor]]", {}),
            "Drifter": (NEW, DRIFTED),
            "Anchor": (SHARED, {}),
        },
    )

    suggestions = divergent_evolution.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "divergent_evolution",
        must_reference=["Hub", "Drifter"],
        must_not_reference=["geist journal", "Anchor"],
    )
    assert suggestions[0].text.startswith("[[Hub]] and [[Drifter]] are linked, but")
    assert "across 3 recorded sessions" in suggestions[0].text


def test_divergent_evolution_ignores_unlinked_notes_growing_apart(tmp_path):
    """Only linked pairs are candidates: "Loner" diverges from Hub but is not linked."""
    ctx = _vault(
        tmp_path,
        {
            "Hub": (SHARED + " [[Drifter]] [[Anchor]]", {}),
            "Drifter": (NEW, DRIFTED),
            "Anchor": (SHARED, {}),
            "Loner": (NEW, DRIFTED),
        },
    )

    suggestions = divergent_evolution.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "divergent_evolution",
        must_reference=["Drifter"],
        must_not_reference=["geist journal", "Loner"],
    )


def test_divergent_evolution_needs_three_sessions(tmp_path):
    """Boundary pair: 2 recorded sessions -> no trend; 3 -> flagged."""
    notes = {
        "Hub": (SHARED + " [[Drifter]] [[Anchor]]", {}),
        "Drifter": (NEW, {H2: SHARED}),
        "Anchor": (SHARED, {}),
    }
    two = _vault(tmp_path / "two", notes, history=[H2])
    three = _vault(tmp_path / "three", {**notes, "Drifter": (NEW, DRIFTED)})

    assert divergent_evolution.suggest(two) == []
    assert_valid_suggestions(divergent_evolution.suggest(three), "divergent_evolution")


def test_divergent_evolution_needs_two_linked_pairs(tmp_path):
    """Boundary pair: a single (diverging) link is not enough; two links are."""
    one = _vault(
        tmp_path / "one",
        {"Hub": (SHARED + " [[Drifter]]", {}), "Drifter": (NEW, DRIFTED)},
    )
    two = _vault(
        tmp_path / "two",
        {
            "Hub": (SHARED + " [[Drifter]] [[Anchor]]", {}),
            "Drifter": (NEW, DRIFTED),
            "Anchor": (SHARED, {}),
        },
    )

    assert divergent_evolution.suggest(one) == []
    assert_valid_suggestions(divergent_evolution.suggest(two), "divergent_evolution")


def test_divergent_evolution_caps_at_two(tmp_path):
    """Cap: three diverging links produce exactly two suggestions."""
    drifters = [f"Drifter {i}" for i in range(3)]
    notes = {"Hub": (SHARED + " " + " ".join(f"[[{d}]]" for d in drifters), {})}
    notes.update({d: (NEW, DRIFTED) for d in drifters})
    ctx = _vault(tmp_path, notes)

    suggestions = divergent_evolution.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "divergent_evolution")
    assert suggestions[0].notes != suggestions[1].notes


def test_divergent_evolution_excludes_geist_journal(tmp_path):
    """Session notes link to every note they suggest; those links are not the user's.

    Both directions: the user's Hub -> Drifter link is flagged. A session note
    rewritten (--force) from SHARED to NEW text diverges from Anchor, which it
    links to, and from Hub, which links to it; neither link is reported.
    """
    ctx = _vault(
        tmp_path,
        {
            "Hub": (SHARED + " [[Drifter]] [[Anchor]] [[2023-12-01]]", {}),
            "Drifter": (NEW, DRIFTED),
            "Anchor": (SHARED, {}),
        },
        journal={"2023-12-01": (f"{NEW} [[Anchor]]", DRIFTED)},
    )

    suggestions = divergent_evolution.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "divergent_evolution",
        must_reference=["Hub", "Drifter"],
        must_not_reference=["geist journal", "2023-12-01"],
    )


def test_divergent_evolution_is_deterministic_for_a_seed(tmp_path):
    drifters = [f"Drifter {i}" for i in range(3)]
    notes = {"Hub": (SHARED + " " + " ".join(f"[[{d}]]" for d in drifters), {})}
    notes.update({d: (NEW, DRIFTED) for d in drifters})

    first = divergent_evolution.suggest(_vault(tmp_path / "a", notes))
    second = divergent_evolution.suggest(_vault(tmp_path / "b", notes))

    assert len(first) == 2
    assert [s.text for s in first] == [s.text for s in second]
