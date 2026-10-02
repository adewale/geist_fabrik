"""Tests for the creation_burst geist.

Trigger: notes_grouped_by_creation_date(min_per_day=3, exclude_journal=True)
returns at least one day with >= 3 non-journal notes created on it. The geist
samples ONE such day and returns one suggestion naming the day, the count and
(up to 8 of) its notes; 6+ notes ask "What was special about that day?",
3-5 ask "What were you circling around that day?". Days with more than
max(20, 25% of the vault) notes (bulk imports) and days after the session date
are not bursts. When burst notes were rewritten since the first session that
recorded them (semantic drift >= 0.05), one sentence names up to 3 of them.
"""

import re
from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import creation_burst
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import BASE16, set_session_text

EXTRA9 = "quebec romeo sierra tango uniform victor whiskey xray yankee"

BURST_DAY = datetime(2024, 2, 10, 9, 0)
OTHER_DAY = datetime(2024, 1, 5, 9, 0)
LARGE_QUESTION = "What was special about that day?"
# Regression: the 3-5 note question was "Does today feel generative?", which
# asked about today in a suggestion about a past day.
SMALL_QUESTION = "What were you circling around that day?"


def _burst_vault(root: Path, counts: dict[datetime, int]) -> VaultContext:
    """One note per slot; ``counts`` maps a creation day to its note count."""
    builder = VaultBuilder(root)
    for day, count in counts.items():
        for i in range(count):
            builder.note(f"Burst {day:%m%d} {i}", f"Idea {i} from {day:%B}.", created=day)
    return builder.build()


def test_creation_burst_fires_on_three_notes_created_the_same_day(tmp_path):
    # Trigger arithmetic: 3 notes share BURST_DAY (== min_per_day=3).
    ctx = _burst_vault(tmp_path, {BURST_DAY: 3})

    suggestions = creation_burst.suggest(ctx)

    assert_valid_suggestions(suggestions, "creation_burst", must_reference=["Burst 0210 0"])
    [suggestion] = suggestions
    assert suggestion.text.startswith("On 2024-02-10, you created 3 notes in one day:")
    assert sorted(suggestion.notes) == [f"Burst 0210 {i}" for i in range(3)]
    assert SMALL_QUESTION in suggestion.text


def test_creation_burst_two_notes_on_a_day_is_not_a_burst(tmp_path):
    # Boundary partner of the test above: 2 < min_per_day=3.
    ctx = _burst_vault(tmp_path, {BURST_DAY: 2, OTHER_DAY: 2})

    assert creation_burst.suggest(ctx) == []


def test_creation_burst_question_switches_at_six_notes(tmp_path):
    """5 notes is a small burst, 6 is a large one (the count >= 6 boundary)."""
    five = creation_burst.suggest(_burst_vault(tmp_path / "five", {BURST_DAY: 5}))
    six = creation_burst.suggest(_burst_vault(tmp_path / "six", {BURST_DAY: 6}))

    assert_valid_suggestions(five, "creation_burst")
    assert_valid_suggestions(six, "creation_burst")
    assert SMALL_QUESTION in five[0].text and LARGE_QUESTION not in five[0].text
    assert LARGE_QUESTION in six[0].text and SMALL_QUESTION not in six[0].text


def test_creation_burst_lists_eight_links_then_counts_the_rest(tmp_path):
    """Display cap: 10 notes show 8 wikilinks plus "and 2 more"; notes keeps all 10."""
    ctx = _burst_vault(tmp_path, {BURST_DAY: 10})

    [suggestion] = creation_burst.suggest(ctx)

    assert suggestion.text.count("[[") == 8
    assert ", and 2 more." in suggestion.text
    assert sorted(suggestion.notes) == sorted(f"Burst 0210 {i}" for i in range(10))


def test_creation_burst_returns_one_suggestion_for_one_sampled_day(tmp_path):
    """Several burst days still produce exactly one suggestion, about one day only."""
    ctx = _burst_vault(tmp_path, {BURST_DAY: 3, OTHER_DAY: 4})

    suggestions = creation_burst.suggest(ctx)

    assert len(suggestions) == 1
    notes = set(suggestions[0].notes)
    day_one = {f"Burst 0210 {i}" for i in range(3)}
    day_two = {f"Burst 0105 {i}" for i in range(4)}
    assert notes in (day_one, day_two)


def test_creation_burst_ignores_geist_journal_notes(tmp_path):
    """Journal notes neither form a burst nor count towards one.

    Day A: 3 regular notes (a real burst). Day B: 3 journal notes only (not a
    burst). Day C: 2 regular + 2 journal notes (not a burst: 2 < 3 regular).
    """
    day_a, day_b, day_c = BURST_DAY, OTHER_DAY, datetime(2023, 12, 1, 9, 0)
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        builder.note(f"Regular {i}", "Real work.", created=day_a)
        builder.journal(f"2024-01-0{i + 1}", "Session output.", created=day_b)
    for i in range(2):
        builder.note(f"Almost {i}", "Almost a burst.", created=day_c)
        builder.journal(f"2023-12-0{i + 1}", "Session output.", created=day_c)
    ctx = builder.build()

    suggestions = creation_burst.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "creation_burst",
        must_reference=["Regular 0"],
        must_not_reference=["geist journal", "2024-01-0", "2023-12-0", "Almost"],
    )
    assert sorted(suggestions[0].notes) == ["Regular 0", "Regular 1", "Regular 2"]


def test_creation_burst_virtual_notes_use_deeplinks(tmp_path):
    """Journal-file entries count by their heading date and link as File#heading.

    Three date-collection files each have a 2024-03-15 entry, plus one regular
    note created that day: a 4-note burst. Every other heading date has at most
    two entries, so it is not a burst. Virtual entries must be listed as distinct
    deeplinks ("Work Journal#2024-03-15"), not three copies of "2024-03-15".
    """
    builder = VaultBuilder(tmp_path)
    for name, other_day in (("Work", 16), ("Personal", 16), ("Research", 14)):
        (tmp_path / f"{name} Journal.md").write_text(
            f"## 2024-03-15\n\n{name} thoughts.\n\n## 2024-03-{other_day}\n\nMore {name} notes.\n"
        )
    builder.note("Regular Note", "Some content.", created=datetime(2024, 3, 15, 10, 0))
    ctx = builder.build(session_date=datetime(2024, 3, 20))

    suggestions = creation_burst.suggest(ctx)

    assert_valid_suggestions(suggestions, "creation_burst")
    [suggestion] = suggestions
    expected = [
        "Personal Journal#2024-03-15",
        "Regular Note",
        "Research Journal#2024-03-15",
        "Work Journal#2024-03-15",
    ]
    assert sorted(suggestion.notes) == expected
    assert suggestion.text.startswith("On 2024-03-15, you created 4 notes in one day:")
    for link in expected:
        assert f"[[{link}]]" in suggestion.text


def test_creation_burst_ignores_bulk_import_days(tmp_path):
    """Contract: a day on which more than max(20, 25% of the vault) notes were
    "created" is an import artefact, not a burst; 20 notes still count.

    Regression: a clone or sync stamps every file with one date, and the geist
    reported "On 2026-10-02, you created 77 notes in one day".
    """
    imported = creation_burst.suggest(_burst_vault(tmp_path / "21", {BURST_DAY: 21}))
    [burst] = creation_burst.suggest(_burst_vault(tmp_path / "20", {BURST_DAY: 20}))

    assert imported == []
    assert burst.text.startswith("On 2024-02-10, you created 20 notes in one day:")


def test_creation_burst_ignores_days_after_the_session(tmp_path):
    """Contract: on a replay, a burst after the session date has not happened yet;
    one on the session date itself is reported.

    Regression: replaying 2024-03-15 reported a burst dated 2024-04-01.
    """
    future = creation_burst.suggest(_burst_vault(tmp_path / "future", {datetime(2024, 4, 1): 3}))
    [same_day] = creation_burst.suggest(
        _burst_vault(tmp_path / "same", {datetime(2024, 3, 15, 8, 0): 3})
    )

    assert future == []
    assert same_day.text.startswith("On 2024-03-15, you created 3 notes in one day:")


# --- Rewritten since (merged from burst_evolution) ---------------------------
# Stub drift with title words: "Tweak" +1 word on 18 words = 0.03 (< 0.05,
# trivial), "Moderate" 0.18, "Rewritten" 0.60. HISTORY is one earlier session.

HISTORY = datetime(2023, 9, 1)
EVOLVED_DAY = datetime(2023, 6, 10, 9, 0)


def _evolved_burst(root: Path, notes: dict[str, tuple[str, str]]) -> VaultContext:
    """``notes``: title -> (body at HISTORY, current body), all created EVOLVED_DAY."""
    builder = VaultBuilder(root)
    for title, (_, current) in notes.items():
        builder.note(title, current, created=EVOLVED_DAY)
    ctx = builder.build(history=[HISTORY])
    for title, (earlier, _) in notes.items():
        set_session_text(ctx, f"{title}.md", HISTORY, f"# {title}\n\n{earlier}")
    return ctx


def _rewritten(text: str) -> str:
    """The "Since your first session ..." sentence, or "" when absent."""
    match = re.search(r" (Since your first session with them [^.]*\.)", text)
    return match.group(1) if match else ""


def test_creation_burst_names_burst_notes_rewritten_since(tmp_path):
    """Contract: one sentence names the burst-day notes whose text was
    rewritten since the first session that recorded them (drift >= 0.05);
    unchanged and trivially tweaked notes are not named.

    Regression (merged from burst_evolution): creation_burst never said
    which of a burst day's notes you went back to.
    """
    ctx = _evolved_burst(
        tmp_path,
        {
            "Stable Note": ("steady unchanging text", "steady unchanging text"),
            "Tweak Note": (BASE16, f"{BASE16} quebec"),
            "Moderate Note": (BASE16, f"{BASE16} {EXTRA9}"),
            "Rewritten Note": ("gardens soil compost", "rockets orbit fuel"),
        },
    )

    [suggestion] = creation_burst.suggest(ctx)

    named = re.findall(r"\[\[([^\]]+)\]\]", _rewritten(suggestion.text))
    assert sorted(named) == ["Moderate Note", "Rewritten Note"]
    assert _rewritten(suggestion.text) == (
        f"Since your first session with them (2023-09-01), you have rewritten "
        f"[[{named[0]}]] and [[{named[1]}]]."
    )
    assert suggestion.text.endswith(f"{_rewritten(suggestion.text)} {SMALL_QUESTION}")


def test_creation_burst_says_nothing_about_rewrites_when_none_happened(tmp_path):
    """Contract: the rewrite sentence appears only if true: with session
    history but no edited note, the suggestion is the plain burst question.
    (Guard for the merged-in branch; burst_evolution once reported an
    all-unchanged group as a table of 0.00 distances.)
    """
    notes = {f"Steady {i}": (f"steady text {i}", f"steady text {i}") for i in range(3)}

    [suggestion] = creation_burst.suggest(_evolved_burst(tmp_path, notes))

    assert "rewritten" not in suggestion.text
    assert suggestion.text.endswith(f". {SMALL_QUESTION}")


def test_creation_burst_names_three_rewrites_then_counts_the_rest(tmp_path):
    """Contract: at most three rewritten notes are named, the rest counted.

    Regression: no rewrite sentence existed.
    """
    notes = {f"Changed {i}": ("gardens soil compost", f"rockets orbit fuel {i}x") for i in range(5)}

    [suggestion] = creation_burst.suggest(_evolved_burst(tmp_path, notes))

    sentence = _rewritten(suggestion.text)
    assert sentence.startswith(
        "Since your first session with them (2023-09-01), you have rewritten [[Changed "
    )
    assert sentence.endswith(" and 2 more.")
    assert sentence.count("[[") == 3
