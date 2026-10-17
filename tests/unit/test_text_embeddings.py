"""Exact-text cache lifecycle; deterministic encoder supplies values, not decisions."""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from geistfabrik.text_embeddings import TextEmbeddingCache


def encode(texts):
    return np.asarray([[len(text), sum(map(ord, text))] for text in texts], dtype=np.float64)


@given(texts=st.lists(st.text()), budget=st.integers(min_value=0))
def test_cache_preserves_encoder_values_and_order(texts, budget):
    texts = [text[:1024] for text in texts[:15]]  # Materialized encoder work only.
    cache = TextEmbeddingCache(budget)
    assert np.array_equal(cache.encode(texts, encode), encode(texts))
    assert np.array_equal(cache.encode(texts[::-1], encode), encode(texts[::-1]))


@given(text=st.text())
def test_returned_array_cannot_corrupt_cached_values(text):
    cache = TextEmbeddingCache()
    returned = cache.encode([text], encode)
    returned[:] = -1
    returned.shape = (returned.size,)
    assert np.array_equal(cache.encode([text], encode), encode([text]))


def test_overlapping_batches_encode_only_unique_misses():
    cache = TextEmbeddingCache()
    calls = []

    def observed(texts):
        calls.append(list(texts))
        return encode(texts)

    cache.encode(["a", "b", "a"], observed)
    cache.encode(["b", "c"], observed)
    assert calls == [["a", "b"], ["c"]]


def test_eviction_preserves_recently_used_rows():
    cache = TextEmbeddingCache()
    calls = []

    def observed(texts):
        calls.append(list(texts))
        return encode(texts)

    cache.encode(["a", "b"], observed)
    cache.max_bytes = cache.retained_bytes  # Exactly the observed two-row footprint.
    cache.encode(["a"], observed)
    cache.encode(["c"], observed)
    cache.encode(["a", "b"], observed)
    assert calls == [["a", "b"], ["c"], ["b"]]


@given(budget=st.integers(min_value=0))
def test_budget_reduction_evicts_immediately(budget):
    cache = TextEmbeddingCache()
    cache.encode(["apple", "orange", "pear"], encode)
    cache.max_bytes = budget
    assert cache.retained_bytes <= budget
    assert np.array_equal(cache.encode(["pear"], encode), encode(["pear"]))
    assert cache.retained_bytes <= budget


@pytest.mark.parametrize("budget", [True, -1, 0.5, float("inf")])
def test_invalid_budgets_rejected_at_construction_and_update(budget):
    with pytest.raises(ValueError, match="budget"):
        TextEmbeddingCache(budget)
    cache = TextEmbeddingCache()
    with pytest.raises(ValueError, match="budget"):
        cache.max_bytes = budget


def test_identity_change_invalidates_successful_validation():
    cache = TextEmbeddingCache()
    cache.encode(["same"], encode, identity="model-v1")
    assert np.array_equal(
        cache.encode(["same"], lambda texts: encode(texts) + 10, identity="model-v2"),
        encode(["same"]) + 10,
    )
    cache.clear()
    assert cache.retained_bytes == 0


def test_failed_batch_does_not_publish_partial_cache_rows():
    cache = TextEmbeddingCache()
    with pytest.raises(ValueError, match="finite"):
        cache.encode(["good", "bad"], lambda texts: np.array([[1, 2], [np.nan, 2]]))
    assert cache.retained_bytes == 0
    assert np.array_equal(cache.encode(["good", "bad"], encode), encode(["good", "bad"]))


def test_zero_budget_returns_oversized_rows_without_retaining_them():
    cache = TextEmbeddingCache(0)
    assert np.array_equal(cache.encode(["x", "x"], encode), encode(["x", "x"]))
    assert cache.retained_bytes == 0
