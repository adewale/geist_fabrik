"""Tests for the recent_focus geist (absorbs anachronism_detector).

Trigger: non-journal notes modified within 60 days of the session are recent
work (>= 2 needed); 3 of them are sampled and for each the most similar of its
10 nearest neighbours (similarity >= WEAK) not modified for > 60 days becomes
"your older note". If that older note is closer than every other recent note,
the text says so ("resembles ... more than anything else"); otherwise it asks
whether they connect. A creation gap of >= 1 year is stated in whole years.
Under the lexical test stub, shared body vocabulary makes notes neighbours.
"""

from datetime import datetime, timedelta

from geistfabrik.default_geists.code import recent_focus
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

COMPOST = "compost worms soil mulch humus"
CLOSER = (
    "[[Compost Today]], which you've worked on lately, resembles [[Compost Archive]]{gap} "
    "more than anything else you've worked on in the last 60 days. Circling back to an old idea?"
)


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
    assert [(s.text, s.notes) for s in suggestions] == [
        (CLOSER.format(gap=""), ["Compost Today", "Compost Archive"])
    ]


def test_recent_focus_says_closer_than_anything_recent_only_when_measured(tmp_path):
    """Contract: "resembles [[old]] more than anything else you've worked on"
    is said only when no other recently modified note is as similar;
    otherwise the gentler "What if ... connects" question is asked.

    Regression (merged from anachronism_detector): recent_focus never
    compared the older note with the rest of your recent work, so it could
    not tell a note circling back to old thinking from one that sits among
    its current neighbours.
    """
    builder = VaultBuilder(tmp_path / "plan")
    _note(builder, "Compost Today", COMPOST, 2)
    _note(builder, "Compost Plan", COMPOST, 3)  # recent and identical: closer
    _note(builder, "Compost Archive", f"{COMPOST} bins", 200)
    base = builder.build()

    texts = {
        s.text
        for seed in range(10)
        for s in recent_focus.suggest(
            VaultContext(base.vault, base.session, seed=seed, function_registry=FunctionRegistry())
        )
    }

    assert texts == {
        f"What if your recent work on [[{title}]] connects to your older note "
        "[[Compost Archive]]? They're semantically similar - has your thinking evolved?"
        for title in ("Compost Today", "Compost Plan")
    }

    # The other direction: with the other recent note unrelated, it is said.
    alone = VaultBuilder(tmp_path / "alone")
    _note(alone, "Compost Today", COMPOST, 2)
    _note(alone, "Kettle", "boiling water teapot", 3)
    _note(alone, "Compost Archive", f"{COMPOST} bins", 200)
    assert [s.text for s in recent_focus.suggest(alone.build())] == [CLOSER.format(gap="")]


def test_recent_focus_states_the_real_year_gap(tmp_path):
    """Contract: the older note's creation gap is stated in whole years when it
    is at least one year; under a year, no year is claimed.

    Regression (merged from anachronism_detector, which also rounded any gap
    up to "1 year"): recent_focus gave no sense of how old the older note was.
    """
    texts = {}
    for label, created in (
        ("three", datetime(2021, 1, 10)),
        ("one", datetime(2022, 12, 1)),
        ("under", datetime(2023, 9, 1)),
    ):
        builder = VaultBuilder(tmp_path / label)
        builder.note(
            "Compost Today",
            COMPOST,
            created=datetime(2024, 2, 1),
            modified=SESSION_DATE - timedelta(days=2),
        )
        _note(builder, "Kettle", "boiling water teapot", 3)
        builder.note(
            "Compost Archive", COMPOST, created=created, modified=SESSION_DATE - timedelta(days=200)
        )
        texts[label] = [s.text for s in recent_focus.suggest(builder.build())]

    assert texts == {
        "three": [CLOSER.format(gap=" (written 3 years earlier)")],
        "one": [CLOSER.format(gap=" (written 1 year earlier)")],
        "under": [CLOSER.format(gap="")],
    }


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


def test_recent_focus_samples_three_of_all_recent_notes(tmp_path):
    """Contract: three recent notes are sampled per session from everything
    modified in the last 60 days, so any of them can be the starting point.

    Regression: only the three most recently modified notes were ever
    checked ("Recent 3" and "Recent 4" could never appear).
    """
    topics = ["compost worms", "violin bowing", "sourdough starter", "tide pools", "kite string"]
    builder = VaultBuilder(tmp_path)
    for i, topic in enumerate(topics):
        _note(builder, f"Recent {i}", f"{topic} practice notes {topic}", 1 + i)
        _note(builder, f"Archive {i}", f"{topic} {topic} early notes", 300 + i)
    base = builder.build()

    runs = [
        recent_focus.suggest(
            VaultContext(base.vault, base.session, seed=seed, function_registry=FunctionRegistry())
        )
        for seed in range(20)
    ]

    assert {len(run) for run in runs} == {3}
    pairs = {tuple(s.notes) for run in runs for s in run}
    assert pairs == {(f"Recent {i}", f"Archive {i}") for i in range(5)}


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
