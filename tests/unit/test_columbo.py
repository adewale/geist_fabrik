"""Unit tests for the columbo geist.

columbo looks for a note with assertion language whose top-5 semantic
neighbour has similarity > SimilarityLevel.HIGH (0.65) and the opposite
polarity: > 2 "positive" markers (always/all/must/should, substring match)
on one side and > 2 "negative" markers (never/no/not/cannot/but/however/
except) on the other. It returns at most 3 suggestions.

Fixtures use the bag-of-words test stub. A claim and its doubt repeat the
same 12 topic words twice (count 2 per dimension) and differ only in their
marker words, so their cosine is ~0.9 > 0.65. Topic words are checked to
contain no marker substrings, so marker counts are exactly what is planted.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import columbo
from geistfabrik.similarity_analysis import SimilarityLevel
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 3
CREATED = datetime(2024, 1, 1)
POSITIVE = "always must should"  # "always" also contains "all": 4 positive markers
NEGATIVE = "never cannot however except"  # plus "no"/"not" inside "cannot": 6 negative
MARKERS = ["all", "always", "must", "should", "never", "no", "not", "cannot", "but", "however"]
TOPICS = {
    "Beacon": "lighthouse keeper beacon lantern foghorn harbour "
    "tides reef shipwreck gull cliff rocks",
    "Loom": "loom weaving warp weft shuttle heddle yarn tapestry spindle wool dye fibre",
    "Comet": "comet orbit perihelion nucleus coma tail "
    "telescope dust ice sungrazer ecliptic kuiper",
    "Honey": "beehive honeycomb pollen nectar queen drone worker wax apiary swarm smoker frame",
}


def _topic_body(name: str, markers: str) -> str:
    topic = TOPICS[name]
    return f"{topic} {markers} {topic}"


def _add_pair(builder: VaultBuilder, name: str, *, claim: str = POSITIVE) -> tuple[str, str]:
    builder.note(f"{name} Claim", _topic_body(name, claim), created=CREATED)
    builder.note(f"{name} Doubt", _topic_body(name, NEGATIVE), created=CREATED)
    return f"{name} Claim", f"{name} Doubt"


def test_fixture_topics_contain_no_marker_substrings() -> None:
    """Guard for the fixture itself: marker counts must come only from planted words."""
    for name, topic in TOPICS.items():
        text = f"{name} claim doubt {topic}"
        assert not [m for m in MARKERS if m in text], name


def test_columbo_flags_similar_notes_with_opposite_polarity(tmp_path: Path) -> None:
    """Contract: a claim and a near-identical doubt are reported as a contradiction.

    Trigger: 3 notes (>= 3), similarity ~0.9 > 0.65, 4 positive vs 6 negative.
    """
    builder = VaultBuilder(tmp_path)
    claim, doubt = _add_pair(builder, "Beacon")
    builder.note("Loom Filler", TOPICS["Loom"], created=CREATED)
    ctx = builder.build()
    a, b = ctx.resolve_link_target(claim), ctx.resolve_link_target(doubt)
    assert a is not None and b is not None
    assert ctx.similarity(a, b) > SimilarityLevel.HIGH

    suggestions = columbo.suggest(ctx)

    assert_valid_suggestions(suggestions, "columbo", must_reference=[claim, doubt])
    assert all(set(s.notes) == {claim, doubt} for s in suggestions)
    assert "Loom Filler" not in {n for s in suggestions for n in s.notes}


def test_columbo_reports_each_contradiction_once(tmp_path: Path) -> None:
    """Contract: a contradicting pair is one suggestion, not one per direction.

    Both notes pass the claim-language gate, so each finds the other as a
    contradicting neighbour; the pair must still be reported once.
    """
    builder = VaultBuilder(tmp_path)
    _add_pair(builder, "Beacon")
    builder.note("Loom Filler", TOPICS["Loom"], created=CREATED)
    ctx = builder.build()

    suggestions = columbo.suggest(ctx)

    assert_valid_suggestions(suggestions, "columbo")
    assert len(suggestions) == 1


def test_columbo_caps_at_three_distinct_contradictions(tmp_path: Path) -> None:
    """Contract: 4 contradicting pairs -> exactly 3 suggestions, 3 distinct pairs."""
    builder = VaultBuilder(tmp_path)
    pairs = {frozenset(_add_pair(builder, name)) for name in TOPICS}
    ctx = builder.build()

    suggestions = columbo.suggest(ctx)

    assert_valid_suggestions(suggestions, "columbo", min_count=CAP)
    assert len(suggestions) == CAP
    found = {frozenset(s.notes) for s in suggestions}
    assert len(found) == CAP
    assert found <= pairs


@pytest.mark.parametrize(
    ("claim_markers", "fires"),
    [
        ("must should", False),  # 2 positive markers: not > 2
        ("must should all", True),  # 3 positive markers: > 2
    ],
)
def test_columbo_positive_marker_threshold(tmp_path: Path, claim_markers: str, fires: bool) -> None:
    """Contract: the claim side needs MORE than 2 polarity markers."""
    builder = VaultBuilder(tmp_path)
    claim, doubt = _add_pair(builder, "Beacon", claim=claim_markers)
    builder.note("Loom Filler", TOPICS["Loom"], created=CREATED)
    ctx = builder.build()

    suggestions = columbo.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, "columbo", must_reference=[claim, doubt])
    else:
        assert suggestions == []


def test_columbo_ignores_dissimilar_opposites(tmp_path: Path) -> None:
    """Contract: opposite polarity alone is not a contradiction without similarity."""
    builder = VaultBuilder(tmp_path)
    builder.note("Beacon Claim", _topic_body("Beacon", POSITIVE), created=CREATED)
    builder.note("Loom Doubt", _topic_body("Loom", NEGATIVE), created=CREATED)
    builder.note("Comet Filler", TOPICS["Comet"], created=CREATED)
    ctx = builder.build()

    assert columbo.suggest(ctx) == []


def test_columbo_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are never cited as contradictions.

    Three journal notes carry the Beacon doubt text, so unfiltered they would
    contribute most of the candidate contradictions.
    """
    builder = VaultBuilder(tmp_path)
    claim, doubt = _add_pair(builder, "Beacon")
    builder.note("Loom Filler", TOPICS["Loom"], created=CREATED)
    journal = ["Session One", "Session Two", "Session Three"]
    for title in journal:
        builder.journal(title, _topic_body("Beacon", NEGATIVE), created=CREATED)
    ctx = builder.build()

    suggestions = columbo.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "columbo",
        must_reference=[claim, doubt],
        must_not_reference=["geist journal", *journal],
    )
