"""Tests for the anachronism_detector geist.

Trigger: >= 30 non-journal notes, of which >= 5 are recent (created within
90 days of the session) and >= 5 old (created more than 365 days before).
Two findings, capped at 2 overall:
- a recent note whose best match among (up to 10 sampled) old notes beats its
  average similarity to other recent notes by > 0.15;
- an old note whose best recent match has similarity > 0.80.

Every filler note below has its own vocabulary (similarity ~0 to the rest),
while "Echo" repeats "Origin"'s 8-word body: similarity 8/9 = 0.89.
"""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from geistfabrik.default_geists.code import anachronism_detector
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions
from tests.stubs import lexical_embedding

RECENT, MIDDLE, OLD = datetime(2024, 2, 1), datetime(2023, 6, 1), datetime(2021, 5, 1)
IDEA = "lantern harbour ferry gulls tide ropes fog bells"
IDEAS = [
    IDEA,
    "violin rosin bowing scales etude sonata vibrato bridge",
    "kiln glaze clay wheel slip bisque raku trim",
]
_RESERVED = lexical_embedding(" ".join([*IDEAS, "echo origin"]))


def _filler_words(prefix: str, start: int, count: int) -> str:
    """``count`` made-up words whose stub vectors are orthogonal to every idea,
    so fillers never match Echo/Origin by a hash collision."""
    words: list[str] = []
    i = start * 50
    while len(words) < count:
        word = f"{prefix}{chr(97 + i // 26 % 26)}{chr(97 + i % 26)}"
        i += 1
        if abs(float(np.dot(lexical_embedding(word), _RESERVED))) < 1e-6:
            words.append(word)
    return " ".join(words)


def _builder(
    root: Path,
    *,
    recent: int = 5,
    old: int = 5,
    middle: int = 18,
    echoes: int = 1,
    echo_created: datetime = RECENT,
    origin_created: datetime = OLD,
) -> VaultBuilder:
    """Fillers plus ``echoes`` Echo/Origin pairs (Origin old, Echo recent)."""
    builder = VaultBuilder(root)
    for kind, count, when in (
        ("Recent", recent, RECENT),
        ("Old", old, OLD),
        ("Mid", middle, MIDDLE),
    ):
        for i in range(count):
            builder.note(f"{kind} {i}", _filler_words(kind.lower(), i, 3), created=when)
    for i in range(echoes):
        suffix = "" if i == 0 else f" {'ii' if i == 1 else 'iii'}"
        builder.note(f"Origin{suffix}", IDEAS[i], created=origin_created)
        builder.note(f"Echo{suffix}", IDEAS[i], created=echo_created)
    return builder


def test_anachronism_detector_finds_recent_note_echoing_old_thinking(tmp_path):
    # Trigger arithmetic: 30 notes = 6 recent (5 fillers + Echo), 6 old
    # (5 fillers + Origin), 18 middle. Echo vs Origin 0.89 > avg recent ~0 + 0.15,
    # and > 0.80 from Origin's side.
    ctx = _builder(tmp_path, middle=18).build()

    suggestions = anachronism_detector.suggest(ctx)

    assert_valid_suggestions(suggestions, "anachronism_detector", min_count=2)
    texts = sorted(s.text for s in suggestions)
    assert texts == [
        "[[Echo]] (written recently) semantically resembles [[Origin]] from 3 years ago more "
        "than it resembles your current thinking. Circling back to old ideas?",
        "[[Origin]] from 3 years ago feels remarkably contemporary—it's very similar to your "
        "recent [[Echo]]. Some ideas are timeless?",
    ]


def test_anachronism_detector_needs_thirty_notes(tmp_path):
    """Boundary pair: 29 notes -> nothing; 30 -> flagged."""
    assert anachronism_detector.suggest(_builder(tmp_path / "29", middle=17).build()) == []
    assert_valid_suggestions(
        anachronism_detector.suggest(_builder(tmp_path / "30", middle=18).build()),
        "anachronism_detector",
    )


def test_anachronism_detector_needs_five_recent_and_five_old(tmp_path):
    """Boundary pairs: 4 recent (or 4 old) notes -> nothing; 5 -> flagged."""
    four_recent = _builder(tmp_path / "r4", recent=3, middle=20).build()
    four_old = _builder(tmp_path / "o4", old=3, middle=20).build()
    five_each = _builder(tmp_path / "55", recent=4, old=4, middle=20).build()

    assert anachronism_detector.suggest(four_recent) == []
    assert anachronism_detector.suggest(four_old) == []
    assert_valid_suggestions(anachronism_detector.suggest(five_each), "anachronism_detector")


def test_anachronism_detector_age_windows(tmp_path):
    """Recent means created within 90 days; old means more than 365 days ago.

    With Echo 91 days old it is neither recent nor old; with Origin 364 days
    old it is not old; either way the pair is not an anachronism. At 89 and
    366 days the pair is found.
    """
    day = timedelta(days=1)
    not_recent = _builder(tmp_path / "a", echo_created=SESSION_DATE - 91 * day, recent=6).build()
    not_old = _builder(tmp_path / "b", origin_created=SESSION_DATE - 364 * day, old=6).build()
    both = _builder(
        tmp_path / "c",
        echo_created=SESSION_DATE - 89 * day,
        origin_created=SESSION_DATE - 366 * day,
    ).build()

    assert anachronism_detector.suggest(not_recent) == []
    assert anachronism_detector.suggest(not_old) == []
    assert_valid_suggestions(
        anachronism_detector.suggest(both), "anachronism_detector", must_reference=["Echo"]
    )


def test_anachronism_detector_caps_at_two(tmp_path):
    """Cap: three Echo/Origin pairs yield six findings; exactly two are returned."""
    ctx = _builder(tmp_path, echoes=3, recent=5, old=5, middle=14).build()

    suggestions = anachronism_detector.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "anachronism_detector")


def test_anachronism_detector_excludes_geist_journal(tmp_path):
    """A recent session note that quotes an old note is output, not the user
    circling back. Both directions, across seeds: Echo/Origin is found and the
    session note never appears (neither as the recent side nor as a match)."""
    builder = _builder(tmp_path)
    builder.journal("2024-03-10", IDEA, created=datetime(2024, 3, 10))
    ctx = builder.build()

    for seed in range(6):
        seeded = VaultContext(
            ctx.vault, ctx.session, seed=seed, function_registry=FunctionRegistry()
        )
        assert_valid_suggestions(
            anachronism_detector.suggest(seeded),
            "anachronism_detector",
            must_reference=["Echo", "Origin"],
            must_not_reference=["geist journal", "2024-03-10"],
        )


def test_anachronism_detector_is_deterministic_for_a_seed(tmp_path):
    first = anachronism_detector.suggest(_builder(tmp_path / "a", echoes=3, middle=14).build())
    second = anachronism_detector.suggest(_builder(tmp_path / "b", echoes=3, middle=14).build())

    assert len(first) == 2
    assert [s.text for s in first] == [s.text for s in second]
