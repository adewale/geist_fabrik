"""Tests for the temporal_drift geist.

Trigger: any non-journal note with staleness > 0.7 that at least 2 other
user notes link to (backlinks; journal links don't count). Built-in staleness
is ``round(1 - 1 / (1 + days_since_modified / 30), 3)``, so 70 days gives
exactly 0.7 (not stale enough) and 71 days gives 0.703. Output is capped at 3.

Fixtures make a note "well-connected" by adding two freshly edited "Reader"
notes (5 days old, never stale themselves) that link to it.
"""

from datetime import datetime, timedelta
from pathlib import Path

from geistfabrik.default_geists.code import temporal_drift
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

LINKS = "See [[Alpha]], [[Beta]] and [[Gamma]]."


def _days_ago(days: int) -> datetime:
    return SESSION_DATE - timedelta(days=days)


def _stale_note(builder: VaultBuilder, title: str, days: int, body: str = LINKS) -> None:
    when = _days_ago(days)
    builder.note(title, body, created=when - timedelta(days=30), modified=when)


def _readers(builder: VaultBuilder, targets: list[str], count: int = 2) -> None:
    """``count`` fresh notes, each linking to every target."""
    links = " ".join(f"[[{t}]]" for t in targets)
    for i in range(count):
        _stale_note(builder, f"Reader {i}", 5, f"Notes that cite {links}.")


def _build(root: Path, hubs: dict[str, int]) -> VaultContext:
    builder = VaultBuilder(root)
    for title, days in hubs.items():
        _stale_note(builder, title, days)
    _readers(builder, list(hubs))
    return builder.build()


def test_temporal_drift_flags_stale_linked_to_note(tmp_path):
    """Contract: the text states how many notes link to the stale note.

    Regression: it said "it has N links", counting raw outgoing links.
    """
    # Trigger arithmetic: 200 days unmodified -> staleness 0.87 > 0.7; 2 backlinks.
    ctx = _build(tmp_path, {"Stale Hub": 200})

    suggestions = temporal_drift.suggest(ctx)

    assert_valid_suggestions(suggestions, "temporal_drift", must_reference=["Stale Hub"])
    assert [(s.text, s.notes) for s in suggestions] == [
        (
            "What if [[Stale Hub]] needs updating? It's been 200 days since you modified it, "
            "but 2 notes link to it - might your thinking have evolved?",
            ["Stale Hub"],
        )
    ]


def test_temporal_drift_staleness_boundary_is_71_days(tmp_path):
    """70 days -> staleness 0.7 (not > 0.7); 71 days -> 0.703."""
    assert temporal_drift.suggest(_build(tmp_path / "a", {"Seventy": 70})) == []

    suggestions = temporal_drift.suggest(_build(tmp_path / "b", {"Seventy One": 71}))

    assert_valid_suggestions(suggestions, "temporal_drift", must_reference=["Seventy One"])


def test_temporal_drift_needs_two_backlinks(tmp_path):
    """Contract: well-connected means at least 2 user notes link to it.

    Regression: "well-connected" was >= 3 raw outgoing links. (Replaces the
    3-outgoing-links boundary test.)
    """
    builder = VaultBuilder(tmp_path)
    _stale_note(builder, "One Backlink", 200)
    _stale_note(builder, "Two Backlinks", 200)
    _stale_note(builder, "Reader 0", 5, "Cites [[One Backlink]] and [[Two Backlinks]].")
    _stale_note(builder, "Reader 1", 5, "Cites [[Two Backlinks]].")
    ctx = builder.build()

    suggestions = temporal_drift.suggest(ctx)

    assert [s.notes for s in suggestions] == [["Two Backlinks"]]


def test_temporal_drift_ignores_outgoing_links_and_links_in_code(tmp_path):
    """Contract: outgoing links, however many, don't make a note well-connected.

    Regression: a stale note whose "75 links" were ``[[{note}]]`` f-strings in
    a code sample (0 real connections) was called well-connected, as was one
    linking to notes that don't exist.
    """
    builder = VaultBuilder(tmp_path)
    code = "```python\n" + "\n".join(f'print(f"[[{{note{i}}}]]")' for i in range(10)) + "\n```"
    _stale_note(builder, "Code Sample", 300, code)
    _stale_note(builder, "Link Lister", 300, "[[Trips]] [[Kyoto]] [[Japan]] " + LINKS)
    _stale_note(builder, "Alpha", 5, "Fresh.")
    _stale_note(builder, "Beta", 5, "Fresh.")
    _stale_note(builder, "Gamma", 5, "Fresh.")
    ctx = builder.build()

    assert temporal_drift.suggest(ctx) == []


def test_temporal_drift_caps_at_three(tmp_path):
    """Cap: five qualifying notes produce exactly three suggestions."""
    ctx = _build(tmp_path, {f"Stale {i}": 100 + i for i in range(5)})

    suggestions = temporal_drift.suggest(ctx)

    assert len(suggestions) == 3
    assert_valid_suggestions(suggestions, "temporal_drift")
    assert len({s.notes[0] for s in suggestions}) == 3


def test_temporal_drift_scans_every_stale_note(tmp_path):
    """Contract: every stale note is a candidate, not just the 20 oldest.

    Regression: only the 20 least recently modified notes were considered,
    so 24 older (but unlinked) notes hid a stale note that 2 notes link to.
    """
    builder = VaultBuilder(tmp_path)
    _stale_note(builder, "Linked Hub", 200)
    for i in range(24):
        _stale_note(builder, f"Ancient {i:02d}", 400 + i, "Unlinked old thought.")
    _readers(builder, ["Linked Hub"])
    ctx = builder.build()

    suggestions = temporal_drift.suggest(ctx)

    assert [s.notes for s in suggestions] == [["Linked Hub"]]


def test_temporal_drift_excludes_geist_journal(tmp_path):
    """Session notes are always link-heavy and eventually stale; never flag them,
    and never count their links as backlinks.

    35 session notes older than the user's stale note, all linking to it and
    to each other, must neither be suggested nor make an otherwise unlinked
    note look well-connected.
    """
    builder = VaultBuilder(tmp_path)
    _stale_note(builder, "Real Stale Hub", 200)
    _stale_note(builder, "Journal Favourite", 200)
    _readers(builder, ["Real Stale Hub"])
    for i in range(35):
        when = _days_ago(400 + i)
        builder.journal(
            f"Session {i:02d}",
            f"[[Journal Favourite]] [[Session {(i + 1) % 35:02d}]] [[Real Stale Hub]]",
            created=when,
            modified=when,
        )
    ctx = builder.build()

    suggestions = temporal_drift.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "temporal_drift",
        must_reference=["Real Stale Hub"],
        must_not_reference=["geist journal", "Session ", "Journal Favourite"],
    )
    assert "but 2 notes link to it" in suggestions[0].text


def test_temporal_drift_is_deterministic_for_a_seed(tmp_path):
    hubs = {f"Stale {i}": 100 + i for i in range(5)}

    first = temporal_drift.suggest(_build(tmp_path / "a", hubs))
    second = temporal_drift.suggest(_build(tmp_path / "b", hubs))

    assert len(first) == 3
    assert [s.text for s in first] == [s.text for s in second]
