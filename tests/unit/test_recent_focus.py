"""Tests for the recent_focus geist.

Trigger: the 5 most recently modified non-journal notes (>= 2 needed); for
each of the top 3, the most similar of its 10 nearest neighbours that has not
been modified for > 60 days becomes "your older note". Under the lexical
test stub, shared body vocabulary makes notes nearest neighbours.
"""

from datetime import timedelta

from geistfabrik.default_geists.code import recent_focus
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

COMPOST = "compost worms soil mulch humus"


def _note(
    builder: VaultBuilder, title: str, body: str, days: int, *, journal: bool = False
) -> None:
    """A note last modified ``days`` before SESSION_DATE."""
    when = SESSION_DATE - timedelta(days=days)
    created = when - timedelta(days=10)
    if journal:
        builder.journal(title, body, created=created, modified=when)
    else:
        builder.note(title, body, created=created, modified=when)


def test_recent_focus_links_recent_note_to_similar_old_note(tmp_path):
    # Trigger arithmetic: "Compost Today" (2 days) and "Kettle" (3 days) are
    # the recent notes; "Compost Archive" shares the compost vocabulary and
    # was last modified 200 days ago (> 60).
    builder = VaultBuilder(tmp_path)
    _note(builder, "Compost Today", COMPOST, 2)
    _note(builder, "Kettle", "boiling water teapot", 3)
    _note(builder, "Compost Archive", COMPOST, 200)
    ctx = builder.build()

    suggestions = recent_focus.suggest(ctx)

    assert_valid_suggestions(suggestions, "recent_focus")
    assert [s.notes for s in suggestions] == [["Compost Today", "Compost Archive"]]
    assert suggestions[0].text.startswith(
        "What if your recent work on [[Compost Today]] connects to your older note "
        "[[Compost Archive]]?"
    )


def test_recent_focus_old_means_more_than_sixty_days(tmp_path):
    """Boundary pair: a 60-day-old twin is not "older", a 61-day-old twin is."""
    results = {}
    for days in (60, 61):
        builder = VaultBuilder(tmp_path / str(days))
        _note(builder, "Compost Today", COMPOST, 2)
        _note(builder, "Kettle", "boiling water teapot", 3)
        _note(builder, "Compost Archive", COMPOST, days)
        results[days] = recent_focus.suggest(builder.build())

    assert results[60] == []
    assert_valid_suggestions(results[61], "recent_focus", must_reference=["Compost Archive"])


def test_recent_focus_picks_the_most_similar_old_note(tmp_path):
    """Two old candidates above the similarity floor (0.71 and 0.50): the closer wins."""
    builder = VaultBuilder(tmp_path)
    _note(builder, "Compost Today", COMPOST, 2)
    _note(builder, "Kettle", "boiling water teapot", 3)
    _note(builder, "Close Archive", COMPOST + " bins", 200)
    _note(builder, "Far Archive", "compost worms soil railway tickets", 200)
    ctx = builder.build()

    suggestions = recent_focus.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "recent_focus",
        must_reference=["Close Archive"],
        must_not_reference=["geist journal", "Far Archive"],
    )


def test_recent_focus_checks_only_the_three_most_recent_notes(tmp_path):
    """Cap: five recent notes each with an old twin -> exactly the 3 newest are used."""
    topics = ["compost worms", "violin bowing", "sourdough starter", "tide pools", "kite string"]
    builder = VaultBuilder(tmp_path)
    for i, topic in enumerate(topics):
        _note(builder, f"Recent {i}", f"{topic} practice notes {topic}", 1 + i)
        _note(builder, f"Archive {i}", f"{topic} {topic} early notes", 300 + i)
    ctx = builder.build()

    suggestions = recent_focus.suggest(ctx)

    assert len(suggestions) == 3
    assert [s.notes[0] for s in suggestions] == ["Recent 0", "Recent 1", "Recent 2"]
    assert [s.notes[1] for s in suggestions] == ["Archive 0", "Archive 1", "Archive 2"]


def test_recent_focus_needs_two_recent_notes(tmp_path):
    """Boundary pair: one recent note (with an old twin) is not yet a focus; two are."""
    one = VaultBuilder(tmp_path / "one")
    _note(one, "Compost Today", COMPOST, 2)
    _note(one, "Compost Archive", COMPOST, 200)
    two = VaultBuilder(tmp_path / "two")
    _note(two, "Compost Today", COMPOST, 2)
    _note(two, "Kettle", "boiling water teapot", 3)
    _note(two, "Compost Archive", COMPOST, 200)

    assert recent_focus.suggest(one.build()) == []
    assert_valid_suggestions(recent_focus.suggest(two.build()), "recent_focus")


def test_recent_focus_excludes_geist_journal(tmp_path):
    """Session notes are neither "recent work" nor "older notes".

    Both directions: twelve session notes modified after every user note must
    not crowd the user's recent notes out, and an old session note that
    matches the recent note even better than the user's archive note must not
    be offered as "your older note".
    """
    builder = VaultBuilder(tmp_path)
    _note(builder, "Compost Today", COMPOST, 20)
    _note(builder, "Kettle", "boiling water teapot", 21)
    _note(builder, "Compost Archive", COMPOST + " garden beds", 200)
    _note(builder, "Old Session", f"Compost Today {COMPOST}", 150, journal=True)
    for i in range(12):
        _note(builder, f"Session {i:02d}", f"suggestions batch {i}", i, journal=True)
    ctx = builder.build()

    suggestions = recent_focus.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "recent_focus",
        must_reference=["Compost Today", "Compost Archive"],
        must_not_reference=["geist journal", "Session"],
    )


def test_recent_focus_does_not_call_unrelated_notes_similar(tmp_path):
    """Regression: in a small vault every note is among the 10 nearest
    neighbours, so an unrelated old note was offered as "semantically similar".
    Recent notes with no vocabulary in common with the old note give nothing.
    """
    builder = VaultBuilder(tmp_path)
    _note(builder, "Compost Today", COMPOST, 2)
    _note(builder, "Kettle", "boiling water teapot", 3)
    _note(builder, "Railway Archive", "timetable platform signal carriage", 200)

    assert recent_focus.suggest(builder.build()) == []


def test_recent_focus_old_notes_are_not_recent_work(tmp_path):
    """Regression: "recent" was simply the 5 latest-modified notes, so in a vault
    untouched for 200 days one old note became "your recent work" and its
    equally old twin "your older note". Nothing modified in 60 days -> nothing.
    """
    builder = VaultBuilder(tmp_path)
    _note(builder, "Compost Draft", COMPOST, 200)
    _note(builder, "Compost Archive", COMPOST, 210)
    _note(builder, "Kettle", "boiling water teapot", 220)

    assert recent_focus.suggest(builder.build()) == []
