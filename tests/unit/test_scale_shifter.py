"""Unit tests for the scale_shifter geist.

scale_shifter needs >= 20 non-journal notes. It scores each note by counting
the distinct abstract words (theory, principle, framework, ...) and concrete
words (example, instance, specific, ...) that occur in it as whole words
(plurals included):
  - abstract note (>= 3 abstract, <= 1 concrete): "zoom in" to a neighbour
    with similarity >= 0.5 and >= 2 concrete words, more concrete than
    abstract;
  - concrete note (>= 3 concrete, <= 1 abstract): "zoom out" to a neighbour
    with similarity >= 0.5 and >= 2 abstract words, more abstract than
    concrete;
  - cross-scale: an abstract and a concrete note with similarity > 0.6 that
    are not linked.
Each pair of notes is suggested at most once; at most 2 suggestions.

Fixtures use the bag-of-words test stub: notes on one topic repeat the same
8 topic words twice (cosine ~0.85 between them); topic and filler words are
checked to contain no scale-word substrings, so scores are exactly what is
planted.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import scale_shifter
from geistfabrik.similarity_analysis import SimilarityLevel
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 2
MIN_NOTES = 20
CREATED = datetime(2024, 1, 1)
ABSTRACT = "theory principle framework"
CONCRETE = "example instance specific"
SCALE_WORDS = (
    "theory principle concept framework paradigm model pattern system structure abstract "
    "general universal category class example case instance specific particular detail "
    "concrete actual practical real individual tangible implementation"
).split()
# Title and filler words other than the planted "Theory"/"Example" markers.
NEUTRAL_TITLE_WORDS = ["thinking", "visit", "session", "filler", "loose", "idle"]
TOPICS = {
    "Orchard": "orchard pruning grafting apple blossom cider rootstock scion",
    "Glacier": "glacier moraine crevasse icefall serac firn cirque tarn",
    "Violin": "violin bowing rosin fingerboard vibrato luthier spruce purfling",
}


def _body(topic: str, markers: str) -> str:
    return f"{TOPICS[topic]} {markers} {TOPICS[topic]}"


def _add_fillers(builder: VaultBuilder, count: int) -> None:
    for i in range(count):
        builder.note(f"Filler {i}", f"filler{i} loose{i} idle{i}", created=CREATED)


def test_fixture_words_contain_no_scale_substrings() -> None:
    """Guard for the fixture itself: scores must come only from planted scale words."""
    vocabulary = " ".join(TOPICS.values()).split() + NEUTRAL_TITLE_WORDS
    assert not [(v, w) for v in vocabulary for w in SCALE_WORDS if w in v]


def test_scale_shifter_links_abstract_and_concrete_notes_on_one_topic(tmp_path: Path) -> None:
    """Contract: an abstract note and a concrete note on the same topic are paired.

    Trigger: 20 notes; "Orchard Theory" scores 3 abstract/0 concrete,
    "Orchard Example" 3 concrete/0 abstract, cosine ~0.85 (> 0.6, unlinked).
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Orchard Theory", _body("Orchard", ABSTRACT), created=CREATED)
    builder.note("Orchard Example", _body("Orchard", CONCRETE), created=CREATED)
    _add_fillers(builder, MIN_NOTES - 2)
    ctx = builder.build()

    suggestions = scale_shifter.suggest(ctx)

    assert_valid_suggestions(
        suggestions, "scale_shifter", must_reference=["Orchard Theory", "Orchard Example"]
    )
    for s in suggestions:
        assert set(s.notes) == {"Orchard Theory", "Orchard Example"}


def test_scale_shifter_caps_at_two_suggestions(tmp_path: Path) -> None:
    """Contract: 3 topics x (zoom in, zoom out, cross-scale) -> exactly 2 distinct suggestions."""
    builder = VaultBuilder(tmp_path)
    for topic in TOPICS:
        builder.note(f"{topic} Theory", _body(topic, ABSTRACT), created=CREATED)
        builder.note(f"{topic} Example", _body(topic, CONCRETE), created=CREATED)
    _add_fillers(builder, MIN_NOTES - 2 * len(TOPICS))
    ctx = builder.build()

    suggestions = scale_shifter.suggest(ctx)

    assert_valid_suggestions(suggestions, "scale_shifter", min_count=CAP)
    assert len(suggestions) == CAP
    assert len({s.text for s in suggestions}) == CAP


@pytest.mark.parametrize(("abstract_words", "fires"), [(2, False), (3, True)])
def test_scale_shifter_abstract_threshold(tmp_path: Path, abstract_words: int, fires: bool) -> None:
    """Contract: a note needs >= 3 abstract words to be treated as abstract.

    Its concrete neighbour has only 2 concrete words: enough to be a zoom-in
    target, not enough to be a concrete note itself, so the abstract note is
    the only possible trigger.
    """
    builder = VaultBuilder(tmp_path)
    markers = " ".join(ABSTRACT.split()[:abstract_words])
    builder.note("Orchard Thinking", _body("Orchard", markers), created=CREATED)
    builder.note("Orchard Visit", _body("Orchard", "instance specific"), created=CREATED)
    _add_fillers(builder, MIN_NOTES - 2)
    ctx = builder.build()

    suggestions = scale_shifter.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, "scale_shifter", must_reference=["Orchard Visit"])
        assert "What if you zoomed in?" in suggestions[0].text
    else:
        assert suggestions == []


@pytest.mark.parametrize(("total_notes", "fires"), [(MIN_NOTES - 1, False), (MIN_NOTES, True)])
def test_scale_shifter_needs_twenty_notes(tmp_path: Path, total_notes: int, fires: bool) -> None:
    """Contract: a qualifying pair is ignored in a 19-note vault, used in a 20-note one."""
    builder = VaultBuilder(tmp_path)
    builder.note("Orchard Theory", _body("Orchard", ABSTRACT), created=CREATED)
    builder.note("Orchard Example", _body("Orchard", CONCRETE), created=CREATED)
    _add_fillers(builder, total_notes - 2)
    ctx = builder.build()

    suggestions = scale_shifter.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, "scale_shifter")
    else:
        assert suggestions == []


def test_scale_shifter_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are never offered as the other scale.

    Three abstract notes can only zoom in (their one regular concrete
    neighbour has 2 concrete words, so no zoom-out or cross-scale). Four
    journal notes on the same topic also have 2 concrete words: unfiltered,
    they are 4 of the 5 zoom-in targets for every abstract note.
    """
    builder = VaultBuilder(tmp_path)
    abstract = [f"Orchard Theory {c}" for c in "ABC"]
    for title in abstract:
        builder.note(title, _body("Orchard", ABSTRACT), created=CREATED)
    builder.note("Orchard Visit", _body("Orchard", "instance specific"), created=CREATED)
    journal = [f"Session {c}" for c in "ABCD"]
    for title in journal:
        builder.journal(title, _body("Orchard", "instance specific"), created=CREATED)
    _add_fillers(builder, MIN_NOTES - 4)
    ctx = builder.build()

    suggestions = scale_shifter.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "scale_shifter",
        min_count=CAP,
        must_reference=["Orchard Visit"],
        must_not_reference=["geist journal", *journal],
    )


def test_scale_words_match_whole_words_only(tmp_path: Path) -> None:
    """Contract: scale words are matched as whole words, so "because",
    "really" and "actually" are not the concrete words "case", "real" and
    "actual".

    Regression: substring matching gave this abstract note a concrete score
    of 3, so it was classed as neither abstract nor concrete and the zoom-in
    to its concrete neighbour never happened.
    """
    builder = VaultBuilder(tmp_path)
    builder.note(
        "Orchard Theory",
        _body("Orchard", f"{ABSTRACT} because really actually"),
        created=CREATED,
    )
    builder.note("Orchard Visit", _body("Orchard", "instance specific"), created=CREATED)
    _add_fillers(builder, MIN_NOTES - 2)

    suggestions = scale_shifter.suggest(builder.build())

    assert [s.text for s in suggestions] == [
        "[[Orchard Theory]] operates at a high level of abstraction. What if you "
        "zoomed in? [[Orchard Visit]] might be a more concrete instance of the same ideas."
    ]


def test_broader_framework_must_be_more_abstract_and_pairs_are_deduped(
    tmp_path: Path,
) -> None:
    """Contract: the note offered as a "broader framework" leans abstract by
    the same measure (more abstract than concrete words), and a pair of notes
    is suggested once, not once per route.

    Regression: any neighbour with 2 abstract words qualified, so "Orchard
    Survey" (2 abstract, 3 concrete words) was offered as the broader
    framework for "Orchard Example"; and the Glacier pair was emitted by
    the zoom loop and again by the cross-scale loop, filling both slots.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Orchard Example", _body("Orchard", CONCRETE), created=CREATED)
    builder.note(
        "Orchard Survey",
        _body("Orchard", "theory principle example instance specific"),
        created=CREATED,
    )
    builder.note("Glacier Theory", _body("Glacier", ABSTRACT), created=CREATED)
    builder.note("Glacier Example", _body("Glacier", CONCRETE), created=CREATED)
    _add_fillers(builder, MIN_NOTES - 4)

    suggestions = scale_shifter.suggest(builder.build())

    assert [sorted(s.notes) for s in suggestions] == [["Glacier Example", "Glacier Theory"]]


def test_zoom_partner_needs_moderate_similarity(tmp_path: Path) -> None:
    """Contract: a zoom partner must be at least moderately similar (>= 0.5),
    not merely one of the 10 nearest notes.

    Regression: neighbours had no similarity floor, so an abstract note
    sharing 3 of 8 topic words (similarity ~0.46) was offered as the
    broader framework for a concrete note, and vice versa.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Orchard Example", _body("Orchard", CONCRETE), created=CREATED)
    part = " ".join(TOPICS["Orchard"].split()[:3])
    builder.note(
        "Partial Theory",
        f"{part} {ABSTRACT} zinc wax oat rye elk gnu {part}",
        created=CREATED,
    )
    _add_fillers(builder, MIN_NOTES - 2)
    ctx = builder.build()
    example, partial = (
        next(n for n in ctx.notes() if n.title == title)
        for title in ("Orchard Example", "Partial Theory")
    )
    assert 0.3 < ctx.similarity(example, partial) < SimilarityLevel.MODERATE

    assert scale_shifter.suggest(ctx) == []
