"""Exact public similarity-selection contracts, independent of model inference."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from geistfabrik.models import Link, Note, NoteLinkIndex
from geistfabrik.similarity_analysis import SimilarityFilter, SimilarityProfile
from geistfabrik.vault_context import VaultContext


def note(path: str, links: list[Link] | None = None) -> Note:
    return Note(path, path, "", links or [], [], datetime(2025, 1, 1), datetime(2025, 1, 1))


@pytest.fixture
def semantic_context() -> tuple[Mock, list[Note]]:
    """Two anchors, a shared neighbour, a one-anchor neighbour, and an outsider."""
    notes = [note(name + ".md") for name in ("a", "b", "both", "only_a", "neither")]
    scores = {
        frozenset(("a.md", "b.md")): 0.1,
        frozenset(("a.md", "both.md")): 0.5,
        frozenset(("b.md", "both.md")): 0.8,
        frozenset(("a.md", "only_a.md")): 0.8,
        frozenset(("b.md", "only_a.md")): 0.2,
        frozenset(("a.md", "neither.md")): 0.2,
        frozenset(("b.md", "neither.md")): 0.3,
    }
    context = Mock(spec=VaultContext)
    context.notes.return_value = notes
    context.similarity.side_effect = lambda a, b: scores[frozenset((a.path, b.path))]
    return context, notes


def test_similarity_filters_preserve_order_and_exclude_anchors(semantic_context) -> None:
    context, notes = semantic_context
    a, b, both, only_a, neither = notes
    selector = SimilarityFilter(context)

    assert selector.filter_by_range(a, notes, 0.2, 0.5) == [both, neither]
    assert selector.filter_similar_to_any([a, b], notes, threshold=0.5) == [both, only_a]
    assert selector.filter_similar_to_all([a, b], notes, threshold=0.5) == [both]
    # Dissimilarity is strict: the 0.3 boundary excludes "neither".
    assert selector.filter_dissimilar_to_all([a, b], notes, max_sim=0.3) == []
    assert selector.filter_dissimilar_to_all([a, b], notes, max_sim=0.4) == [neither]
    assert all(call.args[0].path != call.args[1].path for call in context.similarity.call_args_list)


def test_empty_anchors_and_candidates_have_explicit_selection_semantics(semantic_context) -> None:
    context, notes = semantic_context
    selector = SimilarityFilter(context)
    assert selector.filter_similar_to_any([], notes) == []
    assert selector.filter_similar_to_all([], notes) == []
    assert selector.filter_dissimilar_to_all([], notes) == notes
    assert selector.filter_by_range(notes[0], [], 0.0, 1.0) == []
    assert selector.filter_similar_to_any(notes, []) == []
    assert selector.filter_similar_to_all(notes, []) == []
    assert selector.filter_dissimilar_to_all(notes, []) == []
    context.similarity.assert_not_called()


def test_similarity_profile_caches_scores_and_honours_inclusive_bounds(semantic_context) -> None:
    context, notes = semantic_context
    profile = SimilarityProfile(context, notes[0])
    assert profile.count_above(0.5) == 2
    assert profile.count_in_range(0.2, 0.5) == 2
    assert profile.percentile(50) == pytest.approx(0.35)
    assert profile.is_hub(threshold=0.5, min_count=2)
    assert not profile.is_hub(threshold=0.5, min_count=3)
    assert context.similarity.call_count == 4
    empty = SimilarityProfile(context, notes[0], candidates=[])
    assert empty.count_above(0.0) == 0
    assert empty.percentile(50) == 0.0
    assert context.similarity.call_count == 4


def test_bridge_uses_canonical_links_and_requires_two_neighbours() -> None:
    source = note("hub.md")
    left = note("folder/left.md", [Link("right")])
    right = note("folder/right.md")
    unrelated = note("other/right.md")
    context = Mock(spec=VaultContext)
    context.similarity.side_effect = lambda _source, target: 0.8 if target != unrelated else 0.1
    index = NoteLinkIndex.from_notes([source, left, right, unrelated])
    context.has_link.side_effect = lambda a, b: any(
        index.resolve(link.target, a.path) == b.path for link in a.links
    )
    profile = SimilarityProfile(context, source, [source, left, right, unrelated])
    assert not profile.is_bridge()  # Source-local [[right]] resolves to folder/right.md.
    context.has_link.assert_called_once_with(left, right)
    assert profile.is_bridge(unlinked_only=False)
    assert not SimilarityProfile(context, source, [source, left, unrelated]).is_bridge()
    disconnected = note("folder/disconnected.md")
    assert SimilarityProfile(context, source, [left, disconnected]).is_bridge()
