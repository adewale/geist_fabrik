"""Unit tests for the bridge_hunter geist.

bridge_hunter takes semantically similar unlinked pairs (vault.unlinked_pairs,
cosine > 0.5), needs at least 2 of them (journal pairs excluded), and for each
pair finds a 4-note stepping-stone path start -> mid1 -> mid2 -> end through
semantic neighbours. A path whose average consecutive similarity exceeds
SimilarityLevel.MODERATE (0.5) becomes a suggestion; at most 2 are returned.

Fixtures use the bag-of-words test stub: notes that share the same 10 topic
words (plus a unique 2-word title) have cosine ~10/12 = 0.83 with each other.
"""

from datetime import datetime
from itertools import combinations
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import bridge_hunter
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 2
CREATED = datetime(2024, 1, 1)
TOPIC = "tidepool anemone barnacle limpet kelp urchin starfish mussel wrack periwinkle"
GROUP = [
    "Granite Rockpool",
    "Sandy Seashore",
    "Muddy Intertidal",
    "Pebble Shoreline",
    "Coastal Littoral",
]


def _endpoints(text: str) -> tuple[str, str]:
    """Return the (start, end) titles from 'Semantic bridge from [[A]] to [[B]]:'."""
    head = text.split(":", 1)[0]
    start = head.split("[[", 1)[1].split("]]", 1)[0]
    end = head.rsplit("[[", 1)[1].split("]]", 1)[0]
    return start, end


def test_bridge_hunter_finds_stepping_stone_path(tmp_path: Path) -> None:
    """Contract: an unlinked similar pair gets a 4-note path through its neighbours.

    Trigger: 4 unlinked notes sharing TOPIC -> 6 unlinked pairs (>= 2), each
    pair's other two notes are the stepping stones (path strength ~0.9 > 0.5).
    """
    builder = VaultBuilder(tmp_path)
    for title in GROUP[:4]:
        builder.note(title, TOPIC, created=CREATED)
    ctx = builder.build()

    suggestions = bridge_hunter.suggest(ctx)

    assert_valid_suggestions(suggestions, "bridge_hunter", min_count=CAP)
    for s in suggestions:
        # Path is start, two distinct intermediates, end - all planted notes.
        assert len(s.notes) == 4
        assert len(set(s.notes)) == 4
        assert set(s.notes) == set(GROUP[:4])
        assert (s.notes[0], s.notes[-1]) == _endpoints(s.text)
        assert " → ".join(f"[[{t}]]" for t in s.notes) in s.text


def test_bridge_hunter_caps_at_two_distinct_pairs(tmp_path: Path) -> None:
    """Contract: 10 qualifying pairs (5 unlinked notes) yield exactly 2 distinct pairs."""
    builder = VaultBuilder(tmp_path)
    for title in GROUP:
        builder.note(title, TOPIC, created=CREATED)
    ctx = builder.build()

    suggestions = bridge_hunter.suggest(ctx)

    assert_valid_suggestions(suggestions, "bridge_hunter", min_count=CAP)
    assert len(suggestions) == CAP
    pairs = {frozenset(_endpoints(s.text)) for s in suggestions}
    assert len(pairs) == CAP


@pytest.mark.parametrize("unlinked_pairs", [1, 2])
def test_bridge_hunter_needs_two_unlinked_pairs(tmp_path: Path, unlinked_pairs: int) -> None:
    """Contract: fewer than 2 unlinked pairs -> []; exactly 2 -> suggestions.

    Four similar notes; every pair is linked except (A, B) and, in the
    2-pair case, (C, D).
    """
    a, b, c, d = GROUP[:4]
    unlinked = {frozenset((a, b))}
    if unlinked_pairs == 2:
        unlinked.add(frozenset((c, d)))
    links: dict[str, list[str]] = {t: [] for t in (a, b, c, d)}
    for x, y in combinations((a, b, c, d), 2):
        if frozenset((x, y)) not in unlinked:
            links[x].append(y)
    builder = VaultBuilder(tmp_path)
    for title, targets in links.items():
        builder.note(title, TOPIC + " " + " ".join(f"[[{t}]]" for t in targets), created=CREATED)
    ctx = builder.build()
    assert len(ctx.unlinked_pairs(count=20)) == unlinked_pairs

    suggestions = bridge_hunter.suggest(ctx)

    if unlinked_pairs == 1:
        assert suggestions == []
    else:
        assert_valid_suggestions(suggestions, "bridge_hunter", min_count=2)
        assert {frozenset(_endpoints(s.text)) for s in suggestions} == unlinked


def test_bridge_hunter_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are neither endpoints nor stepping stones.

    Six journal notes hold TOPIC under a 1-word title that is itself a topic
    word, so each is MORE similar to a regular note (~0.88) than regular notes
    are to each other (~0.83): unfiltered, they would be the preferred
    stepping stones, and 39 of the 45 unlinked pairs would involve one.
    """
    journal = [word.title() for word in TOPIC.split()[:6]]
    builder = VaultBuilder(tmp_path)
    for title in GROUP[:4]:
        builder.note(title, TOPIC, created=CREATED)
    for title in journal:
        builder.journal(title, TOPIC, created=CREATED)
    ctx = builder.build()

    suggestions = bridge_hunter.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "bridge_hunter",
        min_count=CAP,
        must_not_reference=["geist journal", *journal],
    )
    for s in suggestions:
        assert set(s.notes) <= set(GROUP[:4])
