"""Tests for the convergent_evolution geist.

Trigger: a vault of >= 10 non-journal notes containing an UNLINKED pair whose
per-session SEMANTIC similarity over >= 3 shared sessions rises:
mean(second half) - mean(first half) > 0.15 AND last - first > 0.15, and whose
current similarity is >= SimilarityLevel.WEAK (0.35). Capped at 2.

History vectors are injected with ``set_history``: a note's current file
content is its latest snapshot.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import convergent_evolution
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import set_history

H1, H2 = datetime(2023, 10, 1), datetime(2023, 12, 1)
SHARED = "gardens soil compost"
# A "seeker" that used to say ELSEWHERE and now says SHARED has per-session
# similarity to a SHARED note of [0, 0, 0.75] (only the title word differs):
# late mean 0.375 - early mean 0.0 = 0.375 > 0.15.
ELSEWHERE = "rockets orbit fuel"
CONVERGED = {H1: ELSEWHERE, H2: ELSEWHERE}
FILLER_WORDS = [
    "violin bow rosin",
    "sourdough starter flour",
    "tide pools anemone",
    "kite string wind",
    "chess opening gambit",
    "glacier moraine ice",
    "pottery kiln glaze",
    "lantern wick oil",
    "harbour ferry dock",
    "beetle wing shell",
]


def _vault(
    root: Path,
    notes: dict[str, tuple[str, dict[datetime, str]]],
    *,
    fillers: int = 8,
    history: list[datetime] | None = None,
    journal: dict[str, str] | None = None,
) -> VaultContext:
    """``notes`` maps title -> (current body, {history date: earlier body}), plus
    ``fillers`` unrelated constant notes to reach the 10-note minimum."""
    builder = VaultBuilder(root)
    for title, (body, _) in notes.items():
        builder.note(title, body, created=datetime(2023, 1, 1))
    for i in range(fillers):
        builder.note(f"Filler {i}", FILLER_WORDS[i], created=datetime(2023, 1, 1))
    for title, body in (journal or {}).items():
        builder.journal(title, body, created=datetime(2023, 1, 1))
    ctx = builder.build(history=[H1, H2] if history is None else history)
    for title, (_, texts) in notes.items():
        set_history(ctx, f"{title}.md", {d: f"# {title}\n\n{b}" for d, b in texts.items()})
    return ctx


# Topics disjoint from the first 4 fillers, so each seeker converges only with its target.
CAP_TOPICS = ["glacier moraine ice", "pottery kiln glaze", "lantern wick oil"]
PAIR = {"Seeker": (SHARED, CONVERGED), "Target": (SHARED, {})}


def test_convergent_evolution_flags_unlinked_notes_growing_together(tmp_path):
    # 2 planted + 8 filler notes = 10 (the minimum).
    ctx = _vault(tmp_path, PAIR)

    suggestions = convergent_evolution.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "convergent_evolution",
        must_reference=["Seeker", "Target"],
        must_not_reference=["geist journal", "Filler"],
    )
    assert [sorted(s.notes) for s in suggestions] == [["Seeker", "Target"]]
    assert "became more similar across 3 recorded sessions" in suggestions[0].text


def test_convergent_evolution_needs_ten_notes(tmp_path):
    """Boundary pair: 9 notes -> nothing; 10 notes -> flagged."""
    assert convergent_evolution.suggest(_vault(tmp_path / "nine", PAIR, fillers=7)) == []
    assert_valid_suggestions(
        convergent_evolution.suggest(_vault(tmp_path / "ten", PAIR, fillers=8)),
        "convergent_evolution",
    )


def test_convergent_evolution_needs_three_sessions(tmp_path):
    """Boundary pair: 2 recorded sessions -> no trend; 3 -> flagged."""
    two = _vault(
        tmp_path / "two",
        {"Seeker": (SHARED, {H2: ELSEWHERE}), "Target": (SHARED, {})},
        history=[H2],
    )

    assert convergent_evolution.suggest(two) == []
    assert_valid_suggestions(
        convergent_evolution.suggest(_vault(tmp_path / "three", PAIR)), "convergent_evolution"
    )


def test_convergent_evolution_skips_pairs_already_linked(tmp_path):
    """Both directions: of two converging pairs, only the unlinked one is suggested."""
    ctx = _vault(
        tmp_path,
        {
            **PAIR,
            "Linked Seeker": ("beetle wing shell [[Linked Target]]", CONVERGED),
            "Linked Target": ("beetle wing shell", {}),
        },
        fillers=6,
    )

    suggestions = convergent_evolution.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "convergent_evolution",
        must_reference=["Seeker", "Target"],
        must_not_reference=["geist journal", "Linked"],
    )


def test_convergent_evolution_caps_at_two(tmp_path):
    """Cap: three converging pairs produce exactly two suggestions."""
    notes = {}
    for i, topic in enumerate(CAP_TOPICS):
        notes[f"Seeker {i}"] = (topic, CONVERGED)
        notes[f"Target {i}"] = (topic, {})
    ctx = _vault(tmp_path, notes, fillers=4)

    suggestions = convergent_evolution.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "convergent_evolution")
    assert sorted(suggestions[0].notes) != sorted(suggestions[1].notes)


def test_convergent_evolution_excludes_geist_journal(tmp_path):
    """A note edited towards a suggestion quoted in a session note converges with
    that session note; linking to session output is not a useful suggestion.

    Both directions: Seeker/Target is suggested, Seeker/session note is not.
    """
    ctx = _vault(tmp_path, PAIR, journal={"2023-12-01": SHARED})

    suggestions = convergent_evolution.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "convergent_evolution",
        must_reference=["Seeker", "Target"],
        must_not_reference=["geist journal", "2023-12-01"],
    )


def test_convergent_evolution_is_deterministic_for_a_seed(tmp_path):
    notes = {}
    for i, topic in enumerate(CAP_TOPICS):
        notes[f"Seeker {i}"] = (topic, CONVERGED)
        notes[f"Target {i}"] = (topic, {})

    first = convergent_evolution.suggest(_vault(tmp_path / "a", notes, fillers=4))
    second = convergent_evolution.suggest(_vault(tmp_path / "b", notes, fillers=4))

    assert len(first) == 2
    assert [s.text for s in first] == [s.text for s in second]


def test_convergent_evolution_ignores_a_spike_that_fell_back(tmp_path):
    """Contract: convergence needs a net rise (latest over first similarity).

    Regression: only the late-half mean was compared with the early half, so
    similarities [0.0, 0.75, 0.0] (Seeker briefly said SHARED, then went back)
    were reported as "became more similar".
    """
    ctx = _vault(tmp_path, {"Seeker": (ELSEWHERE, {H2: SHARED}), "Target": (SHARED, {})})

    assert convergent_evolution.suggest(ctx) == []


def test_convergent_evolution_needs_the_pair_to_be_similar_now(tmp_path):
    """Contract: a pair that rose from unrelated to still barely related (0.20,
    below SimilarityLevel.WEAK) is not invited to link.

    Regression: similarities [0.0, 0.0, 0.20, 0.20] passed the trend test and
    were reported although the notes are not similar now.
    """
    h0 = datetime(2023, 8, 1)
    barely = "gardens rockets orbit fuel launch"  # shares only "gardens": 0.20
    ctx = _vault(
        tmp_path,
        {
            "Seeker": (barely, {h0: ELSEWHERE, H1: ELSEWHERE, H2: barely}),
            "Target": (SHARED, {}),
        },
        history=[h0, H1, H2],
    )

    assert convergent_evolution.suggest(ctx) == []
