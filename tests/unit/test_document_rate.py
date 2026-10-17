"""Exact prevalence decisions and independently rounded, distinguishable displays."""

from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from geistfabrik.document_rate import DocumentRate, percentage_pair


@st.composite
def rates(draw):
    observations = draw(st.integers(min_value=1))
    return DocumentRate(draw(st.integers(0, observations)), observations)


@given(left=rates(), right=rates())
def test_paired_percentages_preserve_exact_equality_and_order(left, right):
    a, b = (Decimal(value[:-1]) for value in percentage_pair(left, right))
    exact = left.mentions * right.observations - right.mentions * left.observations
    assert (a > b) - (a < b) == (exact > 0) - (exact < 0)


@given(rate=rates(), digits=st.integers(1, 18))
def test_percentage_rounds_like_independent_decimal_arithmetic(rate, digits):
    with localcontext() as context:
        context.prec = 2 * rate.observations.bit_length() + digits + 10
        value = Decimal(rate.mentions) * 100 / Decimal(rate.observations)
        quantum = Decimal(1).scaleb(value.adjusted() - digits + 1)
        expected = value.quantize(quantum, rounding=ROUND_HALF_EVEN)
    assert Decimal(rate.percentage(digits)[:-1]) == expected


@pytest.mark.parametrize(
    "left,right",
    [
        ((67108865, 134217729), (67108864, 134217727)),
        ((4999, 10000), (1, 2)),
        ((1, 10**4500), (2, 10**4500)),
        ((1, 10**4500), (1, 10**4499)),
        ((0, 1), (1, 10**4500)),
    ],
)
def test_distinct_rates_survive_float_and_display_precision_boundaries(left, right):
    a, b = DocumentRate(*left), DocumentRate(*right)
    rendered_a, rendered_b = (Decimal(value[:-1]) for value in percentage_pair(a, b))
    exact = Fraction(*left) - Fraction(*right)
    assert (rendered_a > rendered_b) - (rendered_a < rendered_b) == (exact > 0) - (exact < 0)


@pytest.mark.parametrize(
    "counts", [(True, 2), (1, False), (1.0, 2), (1, 2.0), (-1, 2), (3, 2), (0, 0)]
)
def test_invalid_document_counts_cannot_construct_a_rate(counts):
    with pytest.raises(ValueError):
        DocumentRate(*counts)
