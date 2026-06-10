"""Property-based tests for cosine similarity invariants."""

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from geistfabrik.embeddings import cosine_similarity

# Timeout all tests in this module
pytestmark = pytest.mark.timeout(10)

DIM = 384  # sentence-transformers embedding dimension

# Use hypothesis.extra.numpy for efficient array generation
_float_elements = st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)


def _normalized_array() -> st.SearchStrategy[np.ndarray]:
    """Generate a normalised DIM-dimensional vector using hypothesis numpy arrays."""
    return arrays(
        dtype=np.float32, shape=(DIM,), elements=_float_elements
    ).filter(lambda v: np.linalg.norm(v) > 0.01).map(
        lambda v: v / np.linalg.norm(v)
    )


normalized = _normalized_array()

_pbt_settings = settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.large_base_example],
)


@given(a=normalized, b=normalized)
@_pbt_settings
def test_symmetry(a: np.ndarray, b: np.ndarray) -> None:
    """cosine_similarity(a, b) == cosine_similarity(b, a)."""
    assert abs(cosine_similarity(a, b) - cosine_similarity(b, a)) < 1e-5


@given(v=normalized)
@_pbt_settings
def test_self_similarity_is_one(v: np.ndarray) -> None:
    """cosine_similarity(v, v) ~ 1.0 for normalised vectors."""
    sim = cosine_similarity(v, v)
    assert 0.99 < sim <= 1.0 + 1e-6


@given(a=normalized, b=normalized)
@_pbt_settings
def test_bounded(a: np.ndarray, b: np.ndarray) -> None:
    """Result is always in [-1, 1]."""
    sim = cosine_similarity(a, b)
    assert -1.0 - 1e-6 <= sim <= 1.0 + 1e-6


@given(v=normalized)
@_pbt_settings
def test_zero_vector_gives_zero(v: np.ndarray) -> None:
    """cosine_similarity(zero, anything) == 0.0."""
    zero = np.zeros(DIM, dtype=np.float32)
    assert cosine_similarity(zero, v) == 0.0
    assert cosine_similarity(v, zero) == 0.0


def test_orthogonal_vectors() -> None:
    """Orthogonal unit vectors have similarity ~ 0."""
    a = np.zeros(DIM, dtype=np.float32)
    b = np.zeros(DIM, dtype=np.float32)
    a[0] = 1.0
    b[1] = 1.0
    assert abs(cosine_similarity(a, b)) < 0.01


def test_identical_vectors() -> None:
    """Identical normalised vectors have similarity ~ 1."""
    v = np.random.default_rng(42).standard_normal(DIM).astype(np.float32)
    v = v / np.linalg.norm(v)
    assert cosine_similarity(v, v) > 0.999


def test_opposite_vectors() -> None:
    """Opposite vectors have similarity ~ -1."""
    v = np.random.default_rng(42).standard_normal(DIM).astype(np.float32)
    v = v / np.linalg.norm(v)
    sim = cosine_similarity(v, -v)
    assert sim < -0.99


@given(
    a=normalized,
    b=normalized,
    t=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@_pbt_settings
def test_interpolation_similarity_to_b_increases(
    a: np.ndarray, b: np.ndarray, t: float
) -> None:
    """Interpolating from a toward b should not decrease similarity to b."""
    mid = (1.0 - t) * a + t * b
    norm = np.linalg.norm(mid)
    if norm < 1e-6:
        return  # degenerate case: a and b cancel out
    mid = mid / norm

    sim_mid_b = cosine_similarity(mid, b)
    sim_a_b = cosine_similarity(a, b)
    # mid is closer to b than a is, within float tolerance
    assert sim_mid_b >= sim_a_b - 0.02
