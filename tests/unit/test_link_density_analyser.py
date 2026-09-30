"""Unit tests for link_density_analyser geist.

Trigger arithmetic (see the geist source):
- word_count counts whitespace tokens of the whole note, including the
  "# Title" heading (2 tokens for a one-word title) and each [[link]];
- notes under 50 words are skipped;
- density = links / word_count * 100;
- "too many links" fires when density > 5;
- "needs more connections" fires when density < 0.5 and word_count > 200;
- output is capped at 3 suggestions.
"""

from pathlib import Path

import pytest

from geistfabrik.default_geists.code import link_density_analyser
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEIST = "link_density_analyser"
CAP = 3
HEADING_TOKENS = 2


def _body(total_words: int, links: int) -> str:
    """Body giving the note exactly ``total_words`` tokens, ``links`` of them links."""
    link_tokens = [f"[[Target{i}]]" for i in range(links)]  # one token each
    plain = [f"term{i}" for i in range(total_words - HEADING_TOKENS - links)]
    return " ".join(plain + link_tokens)


def _fillers(builder: VaultBuilder, count: int) -> None:
    # Under 50 words: skipped by the geist, so they never fire.
    for i in range(count):
        builder.note(f"Filler {i}", "Brief plain remark.")


def test_dense_and_sparse_notes_are_both_flagged(tmp_path: Path) -> None:
    # Dense: 6 links in 60 words = density 10. Sparse: 0 links in 300 words.
    # Balanced: 1 link in 100 words = density 1, in neither band.
    builder = VaultBuilder(tmp_path)
    builder.note("Dense", _body(60, 6))
    builder.note("Sparse", _body(300, 0))
    builder.note("Balanced", _body(100, 1))
    _fillers(builder, 6)

    suggestions = link_density_analyser.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=2)
    by_note = {s.notes[0]: s.text for s in suggestions}
    assert set(by_note) == {"Dense", "Sparse"}
    assert "too many links" in by_note["Dense"]
    assert "6 links in 60 words" in by_note["Dense"]
    assert "needs more connections" in by_note["Sparse"]
    assert "0 links in 300 words" in by_note["Sparse"]


@pytest.mark.parametrize(("total_words", "fires"), [(49, False), (50, True)])
def test_short_note_cutoff(tmp_path: Path, total_words: int, fires: bool) -> None:
    # 3 links in ~50 words is density ~6, so only the 50-word cutoff decides.
    builder = VaultBuilder(tmp_path)
    builder.note("Dense", _body(total_words, 3))
    _fillers(builder, 3)

    suggestions = link_density_analyser.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Dense"]] if fires else [])


@pytest.mark.parametrize(("links", "fires"), [(5, False), (6, True)])
def test_too_many_links_density_boundary(tmp_path: Path, links: int, fires: bool) -> None:
    # 100 words: 5 links = density 5.0 (not > 5), 6 links = 6.0.
    builder = VaultBuilder(tmp_path)
    builder.note("Dense", _body(100, links))
    _fillers(builder, 6)

    suggestions = link_density_analyser.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Dense"]] if fires else [])


@pytest.mark.parametrize(
    ("total_words", "links", "fires"),
    [
        (200, 0, False),  # word_count must be > 200
        (201, 0, True),
        (400, 2, False),  # density 0.5 is not < 0.5
        (402, 2, True),  # density 0.4975
    ],
)
def test_too_few_links_boundaries(
    tmp_path: Path, total_words: int, links: int, fires: bool
) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Sparse", _body(total_words, links))
    _fillers(builder, 3)

    suggestions = link_density_analyser.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Sparse"]] if fires else [])


def test_output_is_capped_when_more_notes_qualify(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    planted = [f"Sparse {i}" for i in range(6)]
    for title in planted:
        builder.note(title, " ".join(f"term{j}" for j in range(300)))

    suggestions = link_density_analyser.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert len(suggestions) == CAP
    referenced = [ref for s in suggestions for ref in s.notes]
    assert len(set(referenced)) == CAP
    assert set(referenced) <= set(planted)


def test_geist_journal_notes_are_never_flagged(tmp_path: Path) -> None:
    # Journal session notes are link-dense (every suggestion is a wikilink),
    # exactly like the regular "Dense" note.
    builder = VaultBuilder(tmp_path)
    builder.note("Dense", _body(60, 6))
    for i in range(4):
        builder.journal(f"Session Log {i}", _body(60, 6))
    _fillers(builder, 6)

    suggestions = link_density_analyser.suggest(builder.build())

    assert_valid_suggestions(
        suggestions, GEIST, must_reference=["Dense"], must_not_reference=["Session Log"]
    )


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        builder.note(f"Sparse {i}", " ".join(f"term{j}" for j in range(300)))

    first = [s.text for s in link_density_analyser.suggest(builder.build())]
    second = [s.text for s in link_density_analyser.suggest(builder.build())]

    assert first
    assert first == second
