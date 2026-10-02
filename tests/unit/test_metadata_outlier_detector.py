"""Tests for the metadata_outlier_detector geist.

Trigger: >= 10 user notes and a note whose ``word_count`` or ``link_density``
(both built-in metadata; link_density = links / words) is more than 2.0
population standard deviations from the mean. Link density is analysed only
over notes of at least MIN_WORDS_FOR_DENSITY words. At most one suggestion
per metric: 2 in total.

Z-score arithmetic: if k of n notes share one value and the rest share
another, each of the k notes has |z| = sqrt((n - k) / k). One long note among
12 gives sqrt(11) = 3.3 > 2; two among 12 give sqrt(5) = 2.24 > 2; three among
12 give sqrt(3) = 1.73 < 2, whatever the word counts are.

Every title has two words, so the "# <title>" heading adds the same three
words to each count: a SHORT note has 13 words, a LONG one 203, and a
PROSE note (with either 15 links or 15 filler words) 78.
"""

from pathlib import Path

import pytest

from geistfabrik.default_geists.code import metadata_outlier_detector
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

SHORT = "plain words about ordinary things here and there again today"  # 10 words
LONG = " ".join(f"word{i}" for i in range(200))
PROSE = " ".join(f"prose{i}" for i in range(60))
LINKED = PROSE + " " + " ".join(f"[[T{i}]]" for i in range(15))  # 75 words, 15 links
UNLINKED = PROSE + " " + " ".join(f"filler{i}" for i in range(15))  # 75 words, 0 links


def _vault(
    root: Path,
    bodies: dict[str, str],
    *,
    journal: dict[str, str] | None = None,
) -> VaultContext:
    builder = VaultBuilder(root / "vault")
    for title, body in bodies.items():
        builder.note(title, body)
    for title, body in (journal or {}).items():
        builder.journal(title, body)
    return builder.build()


def _plain(count: int, body: str = SHORT) -> dict[str, str]:
    return {f"Note {chr(65 + i)}": body for i in range(count)}


def test_metadata_outlier_detector_names_an_unusually_long_note(tmp_path):
    ctx = _vault(tmp_path, {**_plain(11), "Long Treatise": LONG})

    suggestions = metadata_outlier_detector.suggest(ctx)

    assert_valid_suggestions(
        suggestions, "metadata_outlier_detector", must_reference=["Long Treatise"]
    )
    assert [s.notes for s in suggestions] == [["Long Treatise"]]
    assert suggestions[0].text == (
        "[[Long Treatise]] is unusually detailed (203 words vs median 13). "
        "Does this depth signal importance?"
    )


def test_metadata_outlier_detector_names_an_unusually_short_note(tmp_path):
    """The other side of the median: one 4-word note among 203-word notes."""
    ctx = _vault(tmp_path, {**_plain(11, LONG), "Tiny Stub": "tiny"})

    suggestions = metadata_outlier_detector.suggest(ctx)

    assert_valid_suggestions(suggestions, "metadata_outlier_detector", must_reference=["Tiny Stub"])
    assert suggestions[0].text.startswith(
        "[[Tiny Stub]] is unusually brief (4 words vs median 203)."
    )


def test_metadata_outlier_detector_z_score_threshold(tmp_path):
    """Boundary pair on 2.0 standard deviations: in 12 notes, two long notes
    sit at z = 2.24 (reported); three sit at z = 1.73 (not)."""
    two = _vault(tmp_path / "two", {**_plain(10), "Long 1": LONG, "Long 2": LONG})
    three = _vault(tmp_path / "three", {**_plain(9), **{f"Long {i}": LONG for i in range(3)}})

    assert metadata_outlier_detector.suggest(three) == []
    assert_valid_suggestions(
        metadata_outlier_detector.suggest(two),
        "metadata_outlier_detector",
        must_reference=["Long"],
    )


def test_metadata_outlier_detector_needs_ten_notes(tmp_path):
    """Boundary pair: one long note among 9 notes is ignored (z = 2.83 would
    qualify), among 10 notes (z = 3.0) it is reported."""
    nine = _vault(tmp_path / "nine", {**_plain(8), "Long Treatise": LONG})
    ten = _vault(tmp_path / "ten", {**_plain(9), "Long Treatise": LONG})

    assert metadata_outlier_detector.suggest(nine) == []
    assert_valid_suggestions(
        metadata_outlier_detector.suggest(ten),
        "metadata_outlier_detector",
        must_reference=["Long Treatise"],
    )


@pytest.mark.parametrize(
    ("bodies", "outlier", "text"),
    [
        (
            {**_plain(11, UNLINKED), "Busy Hub": LINKED},
            "Busy Hub",
            "[[Busy Hub]] is unusually dense with links "
            "(15 links in 78 words: 19.2 per 100 words vs median 0.0). "
            "Is this a hub or an over-connected note?",
        ),
        (
            {**_plain(11, LINKED), "Lone Island": UNLINKED},
            "Lone Island",
            "[[Lone Island]] is unusually sparse in links "
            "(0 links in 78 words: 0.0 per 100 words vs median 19.2). "
            "Could this isolated note connect to others?",
        ),
    ],
    ids=["high", "low"],
)
def test_metadata_outlier_detector_link_density_is_built_in(tmp_path, bodies, outlier, text):
    """Contract: the link-density branch fires on a default install.

    Regression: link_density was not built-in metadata, so without a user
    metadata module this branch could never fire. All word counts are equal
    (78), so only the link-density branch can fire.
    """
    ctx = _vault(tmp_path, bodies)

    suggestions = metadata_outlier_detector.suggest(ctx)

    assert_valid_suggestions(suggestions, "metadata_outlier_detector", must_reference=[outlier])
    assert [s.text for s in suggestions] == [text]


def test_metadata_outlier_detector_ignores_link_density_of_short_notes(tmp_path):
    """Contract: density is only compared across notes with some prose.

    One link in a 4-word note is a density of 25 per 100 words; counted, it
    would be the outlier. The positive side is the 78-word hub.
    """
    word_floor = metadata_outlier_detector.MIN_WORDS_FOR_DENSITY
    short = _vault(tmp_path / "short", {**_plain(11, UNLINKED), "Tiny Link": "[[T0]]"})
    hub = _vault(tmp_path / "hub", {**_plain(11, UNLINKED), "Busy Hub": LINKED})
    tiny = next(n for n in short.notes() if n.title == "Tiny Link")
    assert short.metadata(tiny)["word_count"] < word_floor

    assert all("link" not in s.text for s in metadata_outlier_detector.suggest(short))
    assert [s.notes for s in metadata_outlier_detector.suggest(hub)] == [["Busy Hub"]]


def test_metadata_outlier_detector_caps_at_two(tmp_path):
    """Cap: two word-count outliers and one link-density outlier (three
    candidates) yield exactly two suggestions, one per metric."""
    ctx = _vault(
        tmp_path,
        {**_plain(10, UNLINKED), "Long 1": LONG, "Long 2": LONG, "Busy Hub": LINKED},
    )

    suggestions = metadata_outlier_detector.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "metadata_outlier_detector", must_reference=["Busy Hub"])
    assert "unusually detailed" in suggestions[0].text
    assert suggestions[0].notes[0] in {"Long 1", "Long 2"}
    assert suggestions[1].notes == ["Busy Hub"]


def test_metadata_outlier_detector_excludes_geist_journal(tmp_path):
    """Both directions: a session note far longer than anything else is
    neither named nor counted in the statistics; the user's long note is."""
    ctx = _vault(
        tmp_path,
        {**_plain(11), "Long Treatise": LONG},
        journal={"2024-03-14": " ".join(["session"] * 5000)},
    )

    suggestions = metadata_outlier_detector.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "metadata_outlier_detector",
        must_reference=["Long Treatise"],
        must_not_reference=["geist journal", "2024-03-14"],
    )
