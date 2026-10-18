"""Independent interval protocol contracts for suggestion novelty."""

from hypothesis import given
from hypothesis import strategies as st

from geistfabrik.evidence_identity import (
    evidence_interval,
    factual_evidence_key,
    interval_evidence_key,
)


@given(st.lists(st.text(), max_size=5), st.dates(), st.dates())
def test_interval_identity_roundtrips_calendar_bounds_with_bounded_payload(namespace, a, b):
    first, last = sorted((a, b))
    key = interval_evidence_key(namespace, first.isoformat(), last.isoformat())
    decoded = evidence_interval(key)
    assert decoded is not None
    assert decoded[1:] == (first, last)
    assert len(key) <= 128


@given(st.text(), st.dates(), st.dates())
def test_same_namespace_keeps_identity_when_calendar_bounds_change(namespace, a, b):
    first, last = sorted((a, b))
    left = evidence_interval(
        interval_evidence_key([namespace], first.isoformat(), first.isoformat())
    )
    right = evidence_interval(
        interval_evidence_key([namespace], first.isoformat(), last.isoformat())
    )
    assert left is not None and right is not None
    assert left[0] == right[0]


@given(st.text())
def test_opaque_nonprotocol_keys_are_not_misinterpreted(text):
    assert evidence_interval("opaque:" + text) is None


@given(st.lists(st.text(), max_size=5), st.lists(st.text(), max_size=5))
def test_factual_identity_is_bounded_stable_and_separates_namespace_from_facts(identity, facts):
    key = factual_evidence_key(identity, facts)
    assert key == factual_evidence_key(list(identity), list(facts))
    assert len(key) <= 128
    assert evidence_interval(key) is None
    assert key != factual_evidence_key(identity, [*facts, "another factual input"])


def test_factual_identity_keeps_tuple_boundaries_and_namespace():
    assert factual_evidence_key(["lens"], ["ab", "c"]) != factual_evidence_key(
        ["lens"], ["a", "bc"]
    )
    assert factual_evidence_key(["lens"], ["body"]) != factual_evidence_key(
        ["other lens"], ["body"]
    )
    assert factual_evidence_key(["lens", "body"], []) != factual_evidence_key(["lens"], ["body"])
