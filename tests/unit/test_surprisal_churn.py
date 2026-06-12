"""Tests for VaultContext surprisal and neighbour churn (reflective lenses).

Differential tests (blocked vs naive reference), known-answer tests,
churn properties, and integration-style tests on real tmp_path vaults.
"""

from datetime import datetime

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik import Vault, VaultContext
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry
from geistfabrik.vault_context import (
    ChurnResult,
    _jaccard_churn,
    _surprisal_blocked,
    _surprisal_naive,
    _topk_neighbour_sets,
)

pytestmark = pytest.mark.timeout(60)


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


def _random_embeddings(n: int, d: int, seed: int) -> dict[str, np.ndarray]:
    """Build a dict of n random d-dimensional embeddings (Gaussian, no ties)."""
    rng = np.random.default_rng(seed)
    return {f"note{i:04d}.md": rng.standard_normal(d).astype(np.float32) for i in range(n)}


# ============================================================================
# Differential tests: blocked vs naive reference
# ============================================================================


@pytest.mark.parametrize("n", [10, 23, 64, 200])
@pytest.mark.parametrize("seed", [0, 1, 42])
def test_blocked_matches_naive_on_random_matrices(n: int, seed: int) -> None:
    """The fast blocked path agrees with the readable naive reference."""
    embeddings = _random_embeddings(n, d=16, seed=seed)
    k = 5

    fast = _surprisal_blocked(embeddings, k_neighbours=k)
    slow = _surprisal_naive(embeddings, k_neighbours=k)

    assert fast.keys() == slow.keys()
    assert len(fast) == n
    for path in fast:
        assert abs(fast[path] - slow[path]) < 1e-5, path


def test_blocked_matches_naive_across_block_boundaries() -> None:
    """Small block sizes (forcing multiple blocks) do not change results."""
    embeddings = _random_embeddings(50, d=16, seed=7)
    k = 5

    blocked_small = _surprisal_blocked(embeddings, k_neighbours=k, block_size=7)
    blocked_big = _surprisal_blocked(embeddings, k_neighbours=k, block_size=1024)
    slow = _surprisal_naive(embeddings, k_neighbours=k)

    assert blocked_small.keys() == slow.keys()
    for path in slow:
        assert abs(blocked_small[path] - slow[path]) < 1e-5
        assert abs(blocked_big[path] - slow[path]) < 1e-5


def test_surprisal_too_few_notes_returns_empty() -> None:
    """Fewer than k_neighbours + 1 notes -> {} from both implementations."""
    embeddings = _random_embeddings(5, d=16, seed=3)
    assert _surprisal_blocked(embeddings, k_neighbours=10) == {}
    assert _surprisal_naive(embeddings, k_neighbours=10) == {}
    assert _surprisal_blocked({}, k_neighbours=10) == {}


# ============================================================================
# Known-answer tests
# ============================================================================


def test_identical_points_have_zero_surprisal_outlier_high() -> None:
    """A point identical to its neighbours ~0; orthogonal outlier ~1."""
    d = 8
    e1 = np.zeros(d)
    e1[0] = 1.0
    e2 = np.zeros(d)
    e2[1] = 1.0

    embeddings: dict[str, np.ndarray] = {f"same{i}.md": e1.copy() for i in range(6)}
    embeddings["outlier.md"] = e2

    scores = _surprisal_blocked(embeddings, k_neighbours=3)

    for i in range(6):
        assert scores[f"same{i}.md"] < 0.01
    assert scores["outlier.md"] > 0.9

    # All values clipped to [0, 2]
    assert all(0.0 <= s <= 2.0 for s in scores.values())


def test_surprisal_handles_zero_vectors() -> None:
    """Zero-norm embeddings never cause division by zero."""
    embeddings = _random_embeddings(12, d=16, seed=9)
    embeddings["zero.md"] = np.zeros(16, dtype=np.float32)

    scores = _surprisal_blocked(embeddings, k_neighbours=3)
    assert "zero.md" in scores
    assert 0.0 <= scores["zero.md"] <= 2.0
    assert all(np.isfinite(s) for s in scores.values())


# ============================================================================
# Churn properties
# ============================================================================


sets_of_paths = st.sets(st.text(min_size=1, max_size=8), max_size=12)


@given(old=sets_of_paths, new=sets_of_paths)
@settings(max_examples=200, deadline=None)
def test_jaccard_churn_properties(old: set, new: set) -> None:
    """Churn is bounded, zero on identical sets, and symmetric."""
    churn = _jaccard_churn(old, new)
    assert 0.0 <= churn <= 1.0
    assert _jaccard_churn(old, old) == 0.0
    assert _jaccard_churn(old, new) == _jaccard_churn(new, old)


def test_jaccard_churn_known_answers() -> None:
    """Known-answer churn values."""
    assert _jaccard_churn(set(), set()) == 0.0  # both empty -> 0.0
    assert _jaccard_churn({"a"}, {"b"}) == 1.0  # disjoint -> 1.0
    assert _jaccard_churn({"a", "b"}, {"b", "c"}) == pytest.approx(1.0 - 1 / 3)


def test_topk_neighbour_sets_basics() -> None:
    """Top-k sets exclude self, have size k, and respect blocking."""
    embeddings = _random_embeddings(20, d=16, seed=11)
    paths = sorted(embeddings)
    matrix = np.stack([embeddings[p] for p in paths])

    sets_default = _topk_neighbour_sets(matrix, paths, k=4)
    sets_blocked = _topk_neighbour_sets(matrix, paths, k=4, block_size=3)

    assert sets_default == sets_blocked
    for path, neighbours in sets_default.items():
        assert path not in neighbours  # self excluded
        assert len(neighbours) == 4

    # k larger than n - 1 is capped
    sets_capped = _topk_neighbour_sets(matrix, paths, k=100)
    for path, neighbours in sets_capped.items():
        assert len(neighbours) == 19

    # Degenerate inputs
    assert _topk_neighbour_sets(np.zeros((0, 4)), [], k=3) == {}
    single = _topk_neighbour_sets(np.ones((1, 4)), ["only.md"], k=3)
    assert single == {"only.md": set()}


# ============================================================================
# Integration-style tests on a real vault
# ============================================================================


def _make_vault(tmp_path, n_notes: int = 12) -> Vault:
    """Create a synced vault with n_notes varied notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    topics = [
        "machine learning and neural networks",
        "gardening tips for spring vegetables",
        "philosophy of mind and consciousness",
        "sourdough bread baking techniques",
        "distributed systems and consensus",
        "watercolour painting for beginners",
        "the history of ancient Rome",
        "trail running in the mountains",
        "quantum computing fundamentals",
        "jazz improvisation and music theory",
        "sustainable architecture and design",
        "marine biology and coral reefs",
        "medieval manuscripts and calligraphy",
        "chess openings and endgame strategy",
    ]
    for i in range(n_notes):
        topic = topics[i % len(topics)]
        (vault_path / f"note{i:02d}.md").write_text(
            f"# Note {i}\n\nThis note number {i} explores {topic} in detail."
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    return vault


def _context_for(vault: Vault, session: Session) -> VaultContext:
    """Build a VaultContext with a fresh function registry."""
    return VaultContext(
        vault=vault,
        session=session,
        seed=20250115,
        function_registry=FunctionRegistry(),
    )


def test_surprisal_scores_on_real_vault(tmp_path) -> None:
    """surprisal_scores works end-to-end and is session-cached."""
    vault = _make_vault(tmp_path, n_notes=14)
    session = Session(datetime(2025, 1, 15), vault.db)
    session.compute_embeddings(vault.all_notes())
    context = _context_for(vault, session)

    scores = context.surprisal_scores(k_neighbours=5)

    assert len(scores) == 14
    note_paths = {n.path for n in vault.all_notes()}
    assert set(scores.keys()) == note_paths
    assert all(0.0 <= s <= 2.0 for s in scores.values())

    # Session-scoped cache returns the same object
    assert context.surprisal_scores(k_neighbours=5) is scores


def test_surprisal_scores_tiny_vault_returns_empty(tmp_path) -> None:
    """Fewer notes than k_neighbours + 1 -> {} (graceful degradation)."""
    vault = _make_vault(tmp_path, n_notes=4)
    session = Session(datetime(2025, 1, 15), vault.db)
    session.compute_embeddings(vault.all_notes())
    context = _context_for(vault, session)

    assert context.surprisal_scores(k_neighbours=10) == {}


def test_neighbour_churn_with_two_sessions(tmp_path) -> None:
    """Churn computed between two sessions more than since_days apart."""
    vault = _make_vault(tmp_path, n_notes=10)
    notes = vault.all_notes()

    old_session = Session(datetime(2024, 10, 1), vault.db)
    old_session.compute_embeddings(notes)

    new_session = Session(datetime(2025, 1, 15), vault.db)
    new_session.compute_embeddings(notes)

    context = _context_for(vault, new_session)

    # 2024-10-01 is 106 days before 2025-01-15: since_days=90 finds it
    churn_map = context.neighbour_churn(since_days=90, k=3)

    assert churn_map  # notes exist in both epochs
    note_paths = {n.path for n in notes}
    for path, result in churn_map.items():
        assert path in note_paths
        assert isinstance(result, ChurnResult)
        assert 0.0 <= result.churn <= 1.0
        assert result.departed == sorted(result.departed)
        assert result.arrived == sorted(result.arrived)
        assert all(isinstance(p, str) for p in result.departed + result.arrived)

    # Session-scoped cache, keyed by (since_days, k)
    assert context.neighbour_churn(since_days=90, k=3) is churn_map

    # k larger than the vault: every note's neighbours are "all others"
    # in both epochs, so churn is exactly 0
    full_churn = context.neighbour_churn(since_days=90, k=50)
    assert full_churn
    assert all(r.churn == 0.0 for r in full_churn.values())


def test_neighbour_churn_fallback_to_oldest_session(tmp_path) -> None:
    """No session as old as since_days -> falls back to the oldest session
    when it is at least 30 days older than the current session."""
    vault = _make_vault(tmp_path, n_notes=8)
    notes = vault.all_notes()

    old_session = Session(datetime(2024, 11, 20), vault.db)
    old_session.compute_embeddings(notes)

    new_session = Session(datetime(2025, 1, 15), vault.db)
    new_session.compute_embeddings(notes)

    context = _context_for(vault, new_session)

    # No session 180 days back, but oldest (56 days old) is >= 30 days old
    churn_map = context.neighbour_churn(since_days=180, k=3)
    assert churn_map
    assert all(isinstance(r, ChurnResult) for r in churn_map.values())


def test_neighbour_churn_single_session_returns_empty(tmp_path) -> None:
    """Only the current session exists -> {} (graceful degradation)."""
    vault = _make_vault(tmp_path, n_notes=8)
    session = Session(datetime(2025, 1, 15), vault.db)
    session.compute_embeddings(vault.all_notes())
    context = _context_for(vault, session)

    assert context.neighbour_churn(since_days=180) == {}


def test_neighbour_churn_recent_history_returns_empty(tmp_path) -> None:
    """Oldest session less than 30 days older than current -> {}."""
    vault = _make_vault(tmp_path, n_notes=8)
    notes = vault.all_notes()

    old_session = Session(datetime(2025, 1, 5), vault.db)
    old_session.compute_embeddings(notes)

    new_session = Session(datetime(2025, 1, 15), vault.db)
    new_session.compute_embeddings(notes)

    context = _context_for(vault, new_session)

    # No session 180 days back; oldest is only 10 days old -> {}
    assert context.neighbour_churn(since_days=180) == {}
