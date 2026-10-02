"""Tests for temporal_analysis: numpy cosine helpers and preloaded trajectories.

The trajectory helpers used to call sklearn's cosine_similarity once per
snapshot pair; its input validation cost ~0.6 ms a call, so cyclical_thinking
took ~13 s on a 4,000-note vault. They now use one numpy matrix-vector product
per trajectory (cosine_to_rows), and the finders load every trajectory with a
single SELECT. These tests pin both changes to the old results: a reference
implementation with sklearn per pair and one query per note is kept here.
"""

import random
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from geistfabrik import temporal_analysis
from geistfabrik.models import Note
from geistfabrik.temporal_analysis import (
    CYCLE_HIGH_SIMILARITY,
    CYCLE_LOW_SIMILARITY,
    EmbeddingTrajectoryCalculator,
    TemporalPatternFinder,
    cosine,
    cosine_to_rows,
    semantic_component,
)
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder
from tests.fixtures.temporal import set_history

HISTORY = [datetime(2023, m, 1) for m in (7, 8, 9, 10, 11, 12)]
WORDS = (
    "gardens soil compost mulch rockets orbit fuel launch tides harbour "
    "sails rigging violin cello sonata fugue"
).split()


def _sk(a: np.ndarray, b: np.ndarray) -> float:
    return float(sklearn_cosine(a.reshape(1, -1), b.reshape(1, -1))[0, 0])


# ---------------------------------------------------------------------------
# cosine_to_rows: same numbers as sklearn
# ---------------------------------------------------------------------------


def test_cosine_known_answers() -> None:
    assert cosine(np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])) == pytest.approx(0.0)
    assert cosine(np.array([1.0, 2.0, 3.0]), np.array([2.0, 4.0, 6.0])) == pytest.approx(1.0)
    assert cosine(np.array([1.0, 2.0]), np.array([-1.0, -2.0])) == pytest.approx(-1.0)
    # sklearn leaves a zero vector at zero, so its similarity is 0, not NaN.
    assert cosine(np.zeros(3), np.array([1.0, 2.0, 3.0])) == 0.0
    assert cosine(np.array([1.0, 2.0, 3.0]), np.zeros(3)) == 0.0


def test_cosine_to_rows_matches_sklearn_within_1e6() -> None:
    rng = np.random.default_rng(42)
    for size in (2, 3, 384, 387):
        reference = rng.normal(size=size).astype(np.float32)
        rows = [rng.normal(size=size).astype(np.float32) for _ in range(20)]
        rows.append(np.zeros(size, dtype=np.float32))
        rows.append(reference * 3)
        expected = sklearn_cosine(reference.reshape(1, -1), np.vstack(rows))[0]

        np.testing.assert_allclose(cosine_to_rows(reference, rows), expected, atol=1e-6)


def test_cosine_to_rows_rejects_what_sklearn_rejected() -> None:
    assert cosine_to_rows(np.ones(3), []).shape == (0,)
    with pytest.raises(ValueError):
        cosine_to_rows(np.array([1.0, np.nan]), [np.ones(2)])
    with pytest.raises(ValueError):
        cosine_to_rows(np.ones(2), [np.array([np.inf, 1.0])])
    with pytest.raises(ValueError):
        cosine_to_rows(np.ones(2), [np.ones(3)])


# ---------------------------------------------------------------------------
# Trajectory helpers and finders: same results as the per-pair sklearn code
# ---------------------------------------------------------------------------


def _vault(root: Path) -> VaultContext:
    """Twelve notes with varied six-session histories (some cycle, some drift)."""
    rng = random.Random(7)
    builder = VaultBuilder(root)
    titles = [f"Note {i:02d}" for i in range(12)]
    for title in titles:
        builder.note(title, " ".join(WORDS[:4]), created=datetime(2023, 1, 1))
    ctx = builder.build(history=HISTORY)
    for i, title in enumerate(titles):
        if i < 3:  # home, away, home, away, home, home: two returns
            texts = {d: " ".join(WORDS[4:8]) for d in (HISTORY[1], HISTORY[3])}
        else:
            texts = {d: " ".join(rng.sample(WORDS, rng.randint(2, 8))) for d in HISTORY}
        set_history(ctx, f"{title}.md", {d: f"# {title}\n\n{b}" for d, b in texts.items()})
    return ctx


def _reference_snapshots(vault: VaultContext, note: Note) -> list[tuple[datetime, np.ndarray]]:
    """One query per note (the former loading path)."""
    return EmbeddingTrajectoryCalculator(vault, note)._load_snapshots()


def _reference_cycling(vault: VaultContext, notes: list[Note], min_cycles: int) -> list[Note]:
    cycling = []
    for note in notes:
        snapshots = _reference_snapshots(vault, note)
        if len(snapshots) < 2 * min_cycles + 1:
            continue
        first = semantic_component(snapshots[0][1])
        cycles, state = 0, "high"
        for _, emb in snapshots[1:]:
            sim = _sk(first, semantic_component(emb))
            if state == "high" and sim < CYCLE_LOW_SIMILARITY:
                state = "low"
            elif state == "low" and sim > CYCLE_HIGH_SIMILARITY:
                state, cycles = "high", cycles + 1
        if cycles >= min_cycles:
            cycling.append(note)
    return cycling


def _reference_drift(snapshots: list[tuple[datetime, np.ndarray]]) -> float:
    return 1.0 - _sk(semantic_component(snapshots[0][1]), semantic_component(snapshots[-1][1]))


def test_finders_match_the_per_pair_sklearn_reference(tmp_path: Path) -> None:
    ctx = _vault(tmp_path)
    notes = ctx.notes()
    finder = TemporalPatternFinder(ctx)

    expected_cycling = _reference_cycling(ctx, notes, min_cycles=2)
    # The fixture must exercise both outcomes, or equality proves little.
    assert 0 < len(expected_cycling) < len(notes)
    assert finder.find_cycling_notes(notes, min_cycles=2) == expected_cycling

    drifts = {n.path: _reference_drift(_reference_snapshots(ctx, n)) for n in notes}
    min_drift = float(np.median(list(drifts.values())))
    high = finder.find_high_drift_notes(notes, min_drift=min_drift)
    expected_high = [n for n in notes if drifts[n.path] >= min_drift]
    assert 0 < len(expected_high) < len(notes)
    assert [n for n, _ in high] == expected_high
    for note, vector in high:
        np.testing.assert_allclose(
            vector, EmbeddingTrajectoryCalculator(ctx, note).drift_direction_vector(), atol=1e-12
        )

    direction = high[0][1]
    aligned = finder.find_aligned_with_direction(notes, direction, min_alignment=0.3)
    expected_aligned = [
        n for n in notes if EmbeddingTrajectoryCalculator(ctx, n).drift_alignment(direction) >= 0.3
    ]
    assert expected_aligned and aligned == expected_aligned


def test_trajectory_helpers_match_sklearn_within_1e6(tmp_path: Path) -> None:
    ctx = _vault(tmp_path)
    notes = ctx.notes()
    for note, other in zip(notes, notes[1:]):
        calc = EmbeddingTrajectoryCalculator(ctx, note)
        snaps = [semantic_component(e) for _, e in calc.snapshots()]
        other_snaps = [
            semantic_component(e) for _, e in EmbeddingTrajectoryCalculator(ctx, other).snapshots()
        ]

        assert calc.total_drift() == pytest.approx(_reference_drift(calc.snapshots()), abs=1e-6)
        assert calc.windowed_drift_rates(3) == pytest.approx(
            [1.0 - _sk(snaps[i], snaps[i + 2]) for i in range(len(snaps) - 2)], abs=1e-6
        )
        mid = len(snaps) // 2
        early, late = calc.early_late_split()
        assert early == pytest.approx(np.mean([_sk(s, snaps[-1]) for s in snaps[:mid]]), abs=1e-6)
        assert late == pytest.approx(np.mean([_sk(s, snaps[-1]) for s in snaps[mid:-1]]), abs=1e-6)
        assert calc.similarity_with_trajectory(
            EmbeddingTrajectoryCalculator(ctx, other)
        ) == pytest.approx([_sk(a, b) for a, b in zip(snaps, other_snaps)], abs=1e-6)


def test_preloaded_trajectories_equal_per_note_loading(tmp_path: Path) -> None:
    ctx = _vault(tmp_path)
    notes = ctx.notes()
    missing = Note(
        path="Not stored.md",
        title="Not stored",
        content="",
        links=[],
        tags=[],
        created=datetime(2023, 1, 1),
        modified=datetime(2023, 1, 1),
    )

    calcs = list(TemporalPatternFinder(ctx)._preloaded_calculators([*notes, notes[0], missing]))

    # One calculator per distinct path; a note without snapshots gets none.
    assert sorted(c.note.path for c in calcs) == sorted([n.path for n in notes] + [missing.path])
    for calc in calcs:
        expected = _reference_snapshots(ctx, calc.note)
        assert [d for d, _ in calc.snapshots()] == [d for d, _ in expected]
        for (_, got), (_, want) in zip(calc.snapshots(), expected):
            np.testing.assert_array_equal(got, want)
    assert [c.snapshots() for c in calcs if c.note.path == missing.path] == [[]]


def test_find_cycling_notes_uses_one_query_and_one_product_per_trajectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: one sklearn call per snapshot pair and one query per note.

    Structural rather than wall-clock: with S sessions and N notes the old
    code made N * (S - 1) cosine calls and N trajectory queries.
    """
    ctx = _vault(tmp_path)
    notes = ctx.notes()
    products: list[int] = []
    real = temporal_analysis.cosine_to_rows

    def counting(reference: np.ndarray, rows: list[np.ndarray]) -> np.ndarray:
        products.append(len(rows))
        return real(reference, rows)

    monkeypatch.setattr(temporal_analysis, "cosine_to_rows", counting)
    statements: list[str] = []
    ctx.db.set_trace_callback(statements.append)
    try:
        cycling = TemporalPatternFinder(ctx).find_cycling_notes(notes, min_cycles=2)
    finally:
        ctx.db.set_trace_callback(None)

    assert cycling
    # One product per note, covering all its later snapshots at once.
    assert products == [len(HISTORY)] * len(notes)
    assert sum("session_embeddings" in s for s in statements) == 1
