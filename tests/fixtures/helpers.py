"""Shared test helpers for geist tests.

assert_valid_suggestions() is the standard oracle for geist output: it
asserts non-emptiness (vacuous-by-default loops over possibly-empty lists are
how dead geists kept green tests), structural validity, and the journal-
exclusion contract, in one call with clear failure messages.
"""

from collections.abc import Sequence

from geistfabrik.models import Suggestion


def assert_valid_suggestions(
    suggestions: Sequence[Suggestion],
    geist_id: str,
    *,
    min_count: int = 1,
    must_reference: Sequence[str] = (),
    must_not_reference: Sequence[str] = ("geist journal",),
) -> None:
    """Assert a geist's output is non-empty, well-formed, and on-contract.

    Args:
        suggestions: The geist's return value
        geist_id: Expected geist_id on every suggestion
        min_count: Minimum number of suggestions (default 1 - a happy-path
            test runs on a fixture DESIGNED to trigger, so empty output means
            the geist is dead; pass min_count=0 only for tests that are
            explicitly about emptiness)
        must_reference: Substrings at least one suggestion must reference
            (in text or notes) - ties the output to the fixture's content
        must_not_reference: Substrings no suggestion may reference (case-
            insensitive); defaults to the geist-journal exclusion contract
    """
    assert isinstance(suggestions, list), (
        f"geist must return a list, got {type(suggestions).__name__}"
    )
    assert len(suggestions) >= min_count, (
        f"expected >= {min_count} suggestion(s) from a designed-to-trigger "
        f"fixture, got {len(suggestions)} - is the geist dead?"
    )

    for i, s in enumerate(suggestions):
        assert isinstance(s, Suggestion), f"suggestion {i} is {type(s).__name__}"
        assert s.geist_id == geist_id, f"suggestion {i} has geist_id {s.geist_id!r}"
        assert s.text and s.text.strip(), f"suggestion {i} has empty text"
        assert isinstance(s.notes, list), f"suggestion {i} notes is not a list"

        haystacks = [s.text.lower(), *(ref.lower() for ref in s.notes)]
        for banned in must_not_reference:
            assert not any(banned.lower() in h for h in haystacks), (
                f"suggestion {i} references banned content {banned!r}: {s.text[:120]}"
            )

    for required in must_reference:
        assert any(
            required.lower() in s.text.lower()
            or any(required.lower() in ref.lower() for ref in s.notes)
            for s in suggestions
        ), f"no suggestion references expected content {required!r}"
