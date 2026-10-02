"""Unit tests for link_density_analyser geist.

Trigger arithmetic (see the geist source):
- word_count counts whitespace tokens of the whole note, including the
  "# Title" heading (2 tokens for a one-word title) and each [[link]];
- notes under 50 words are skipped;
- "too many links" fires when written links / word_count * 100 > 5, where
  written links exclude embeds and links back to the note itself;
- "needs more connections" fires when word_count > 200, RESOLVED outgoing
  links / word_count * 100 < 0.5, and at most one note links back;
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
    assert by_note["Sparse"] == (
        "What if [[Sparse]] needs more connections? Its 300 words link to "
        "0 other notes in your vault, and 0 notes link back to it."
    )


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
    """The density is of RESOLVED links, so the link targets exist here."""
    builder = VaultBuilder(tmp_path)
    builder.note("Sparse", _body(total_words, links))
    for i in range(links):
        builder.note(f"Target{i}", "Brief plain remark.")
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


def test_sparse_claim_uses_resolved_links_and_backlinks(tmp_path: Path) -> None:
    """Contract: "needs more connections" is judged on the resolved link graph.
    A long note with no outgoing links but several backlinks is connected and
    is not flagged; a long note whose links all point at missing notes is
    flagged, and the text states the resolved counts it measured.

    Regression: the branch used the raw link count alone, so a note linked
    from three others was called "isolated from your knowledge graph", while a
    note with five dangling links (raw density 1.6) was never considered.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Cited", _body(300, 0))
    for i in range(3):
        builder.note(f"Citer {i}", "See [[Cited]] for this.")
    builder.note("Dangling", _body(300, 5))  # Target0..Target4 do not exist

    suggestions = link_density_analyser.suggest(builder.build())

    assert [s.text for s in suggestions] == [
        "What if [[Dangling]] needs more connections? Its 300 words link to "
        "0 other notes in your vault, and 0 notes link back to it."
    ]


def test_embeds_and_self_links_are_not_counted_as_too_many_links(tmp_path: Path) -> None:
    """Contract: "too many links" counts links written to other notes; embeds
    (![[image.png]]) and links back to the note itself ([[#Section]]) are not
    connections and do not make a note "overwhelming".

    Regression: the raw link count included them, so a note with six embedded
    images in 60 words was told it "has too many links".
    """
    builder = VaultBuilder(tmp_path)
    plain = " ".join(f"term{i}" for i in range(46))
    embeds = " ".join(f"![[img{i}.png]]" for i in range(6))
    toc = " ".join(f"[[#Part {i}]]" for i in range(6))
    builder.note("Gallery", f"{plain} {embeds}")
    builder.note("Contents", f"{plain} {toc}")
    builder.note("Dense", _body(60, 6))
    _fillers(builder, 3)

    suggestions = link_density_analyser.suggest(builder.build())

    assert [s.notes for s in suggestions] == [["Dense"]]
