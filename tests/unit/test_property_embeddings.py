"""Property-based tests for cosine similarity invariants."""

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from geistfabrik.config import SEMANTIC_DIM, TOTAL_DIM
from geistfabrik.embeddings import cosine_similarity

# Timeout all tests in this module
pytestmark = pytest.mark.timeout(10)

DIM = TOTAL_DIM  # persisted vectors include semantic and temporal dimensions

# Use hypothesis.extra.numpy for efficient array generation
_float_elements = st.floats(
    min_value=-1.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False,
    allow_subnormal=False,
    width=32,
)


@st.composite
def _nonzero_array(draw: st.DrawFn, dimension: int = DIM) -> np.ndarray:
    """Construct a bounded nonzero vector without rejecting zero-filled draws."""
    vector = draw(arrays(dtype=np.float32, shape=(dimension,), elements=_float_elements)).copy()
    pivot = draw(st.integers(min_value=0, max_value=dimension - 1))
    vector[pivot] = draw(st.sampled_from([-1.0, -0.5, 0.5, 1.0]))
    return vector


def _normalized_array() -> st.SearchStrategy[np.ndarray]:
    """Generate a normalised DIM-dimensional vector using hypothesis numpy arrays."""
    return _nonzero_array().map(lambda v: v / np.linalg.norm(v))


@st.composite
def embedding_pairs(draw: st.DrawFn) -> tuple[np.ndarray, np.ndarray]:
    """Cover both production dimensions and small vectors with readable shrinks."""
    dimension = draw(st.sampled_from([1, 3, SEMANTIC_DIM, TOTAL_DIM]))
    return draw(_nonzero_array(dimension)), draw(_nonzero_array(dimension))


normalized = _normalized_array()

_pbt_settings = settings(max_examples=50)
_positive_scale = st.one_of(
    st.integers(min_value=-30, max_value=3).map(lambda exponent: float(10.0**exponent)),
    st.floats(min_value=0.125, max_value=8.0, width=32),
)


@given(pair=embedding_pairs())
@_pbt_settings
def test_nonunit_vectors_match_scalar_cosine_reference(
    pair: tuple[np.ndarray, np.ndarray],
) -> None:
    """General vectors agree with an independent double-precision scalar oracle."""
    a, b = pair
    dot = math.fsum(float(x) * float(y) for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(math.fsum(float(x) ** 2 for x in a))
    norm_b = math.sqrt(math.fsum(float(x) ** 2 for x in b))
    assert cosine_similarity(a, b) == pytest.approx(dot / (norm_a * norm_b), abs=1e-5)


@given(
    pair=embedding_pairs(),
    scale_a=_positive_scale,
    scale_b=_positive_scale,
)
@_pbt_settings
def test_positive_rescaling_preserves_cosine(
    pair: tuple[np.ndarray, np.ndarray], scale_a: float, scale_b: float
) -> None:
    """Magnitude changes must not change cosine for unnormalised production inputs."""
    a, b = pair
    assert cosine_similarity(a * scale_a, b * scale_b) == pytest.approx(
        cosine_similarity(a, b), abs=1e-5
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


@given(
    invalid=st.sampled_from([np.float32("nan"), np.float32("inf"), np.float32("-inf")]),
    invalid_on_left=st.booleans(),
    zero_peer=st.booleans(),
    fast_path=st.booleans(),
)
def test_nonfinite_components_are_rejected_before_other_shortcuts(
    invalid: np.float32,
    invalid_on_left: bool,
    zero_peer: bool,
    fast_path: bool,
) -> None:
    """Invalid embeddings never become plausible scores or zero-vector results."""
    from geistfabrik import embeddings

    previous_fast_path = embeddings.SKLEARN_OPTIMIZATIONS["fast_path"]
    try:
        embeddings.SKLEARN_OPTIMIZATIONS["fast_path"] = fast_path
        invalid_vector = np.array([1.0, invalid], dtype=np.float32)
        peer = np.zeros(2, dtype=np.float32) if zero_peer else np.ones(2, dtype=np.float32)
        left, right = (invalid_vector, peer) if invalid_on_left else (peer, invalid_vector)
        with pytest.raises(ValueError, match="finite"):
            cosine_similarity(left, right)
    finally:
        embeddings.SKLEARN_OPTIMIZATIONS["fast_path"] = previous_fast_path


def test_original_embedding_shapes_must_match() -> None:
    """Equal element counts do not make differently shaped embeddings compatible."""
    with pytest.raises(ValueError, match="shapes must match"):
        cosine_similarity(np.ones((1, 2)), np.ones(2))


def test_large_finite_vectors_do_not_overflow_to_a_false_unit_score() -> None:
    """Scale-safe normalization handles finite float64 values near their limit."""
    large = np.array([1e308, 1e308])
    orthogonal = np.array([1e308, -1e308])
    assert cosine_similarity(large, orthogonal) == pytest.approx(0.0, abs=1e-12)


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


@given(exponent=st.integers(min_value=-44, max_value=-7))
@_pbt_settings
def test_tiny_nonzero_vector_has_unit_self_similarity(exponent: int) -> None:
    """Float32 magnitudes below sklearn's cutoff remain mathematically non-zero."""
    value = np.float32(10.0**exponent)
    if value == 0:
        return
    vector = np.array([value], dtype=np.float32)
    assert cosine_similarity(vector, vector) == pytest.approx(1.0, abs=1e-12)


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
def test_interpolation_similarity_to_b_increases(a: np.ndarray, b: np.ndarray, t: float) -> None:
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
