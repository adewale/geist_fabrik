"""Unit tests for link_density_analyser geist.

Trigger arithmetic (see the geist source):
- word_count counts whitespace tokens of the whole note, including the
  "# Title" heading (2 tokens for a one-word title) and each [[link]];
- notes under 50 words are skipped;
- "too many links" fires when written links / word_count * 100 > 5, where
  written links exclude embeds and links back to the note itself;
- "needs more connections" fires when word_count > 200, RESOLVED outgoing
  links / word_count * 100 < 0.5, and at most one note links back;
- each density is stated against the median of the same measure over the
  notes of 50+ words; a note on the wrong side of it is not flagged (a
  "too many" note is at or above the median, a sparse one at or below);
- notes with no links in or out (vault.orphans()) are orphan_connector's and
  are skipped;
- three or more sparse notes with at most one resolved link in either
  direction ("isolated") yield one grouped suggestion naming three of them
  (merged in from metadata_driven_discovery); the others are named singly;
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


def _pointer(builder: VaultBuilder, target: str) -> None:
    """A short note (never analysed) giving ``target`` one backlink."""
    builder.note(f"Pointer to {target}", f"See [[{target}]].")


def _fillers(builder: VaultBuilder, count: int) -> None:
    # Under 50 words: skipped by the geist, so they never fire.
    for i in range(count):
        builder.note(f"Filler {i}", "Brief plain remark.")


def test_dense_and_sparse_notes_are_both_flagged(tmp_path: Path) -> None:
    """Contract: each text states the counts it measured and the median of
    the same density over the notes of 50+ words.

    Regression: the densities were stated without any context (the "vs
    median" comparison lived in metadata_outlier_detector, now an example).
    """
    # Dense: 6 links in 60 words = density 10. Sparse: 0 links in 300 words,
    # one backlink. Balanced: 1 link in 100 words = density 1, in neither
    # band. Written densities 10, 0, 1 (median 1.0); no link resolves
    # except the pointer's, so resolved densities are all 0 (median 0.0).
    builder = VaultBuilder(tmp_path)
    builder.note("Dense", _body(60, 6))
    builder.note("Sparse", _body(300, 0))
    _pointer(builder, "Sparse")
    builder.note("Balanced", _body(100, 1))
    _fillers(builder, 6)

    suggestions = link_density_analyser.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=2)
    assert {s.notes[0]: s.text for s in suggestions} == {
        "Dense": (
            "[[Dense]] has 6 links in 60 words (10.0 per 100 words; the median among "
            "your notes of 50+ words is 1.0). Is it a hub spreading through your "
            "vault, or is the density hiding which links matter?"
        ),
        "Sparse": (
            "What if [[Sparse]] needs more connections? Its 300 words link to 0 other "
            "notes in your vault (0.0 per 100 words; the median among your notes of "
            "50+ words is 0.0), and 1 note links back to it."
        ),
    }


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
    """The density is of RESOLVED links, so the link targets exist here; the
    pointer's backlink keeps the 0-link rows from being orphans."""
    builder = VaultBuilder(tmp_path)
    builder.note("Sparse", _body(total_words, links))
    _pointer(builder, "Sparse")
    for i in range(links):
        builder.note(f"Target{i}", "Brief plain remark.")
    _fillers(builder, 3)

    suggestions = link_density_analyser.suggest(builder.build())

    assert [s.notes for s in suggestions] == ([["Sparse"]] if fires else [])


def test_output_is_capped_when_more_notes_qualify(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    planted = [f"Dense {i}" for i in range(6)]
    for title in planted:
        builder.note(title, _body(60, 6))

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
        builder.note(f"Dense {i}", _body(60, 6))

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
        "What if [[Dangling]] needs more connections? Its 300 words link to 0 other "
        "notes in your vault (0.0 per 100 words; the median among your notes of 50+ "
        "words is 0.0), and 0 notes link back to it."
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


def test_long_note_with_no_links_in_or_out_is_left_to_orphan_connector(tmp_path: Path) -> None:
    """Contract: a note with no links in or out is not flagged here; the same
    note with one backlink is.

    Regression: a long unlinked note was named three times in one session,
    by this geist ("needs more connections"), complexity_mismatch
    ("simplify it") and orphan_connector. It is now orphan_connector's alone.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Lonely", _body(300, 0))
    builder.note("Cited Once", _body(300, 0))
    _pointer(builder, "Cited Once")

    suggestions = link_density_analyser.suggest(builder.build())

    assert [s.notes for s in suggestions] == [["Cited Once"]]


def test_note_below_the_median_is_not_called_dense(tmp_path: Path) -> None:
    """Contract: a note over 5 links per 100 words is not "too many" when it
    is below the median density of the notes of 50+ words.

    Regression: the absolute threshold alone decided, so in a link-heavy
    vault (two notes at 20 per 100 words) a note at 6 per 100 was told it
    has too many links, below what is typical there.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("IndexA", _body(60, 12))
    builder.note("IndexB", _body(60, 12))
    builder.note("Moderate", _body(100, 6))

    suggestions = link_density_analyser.suggest(builder.build())

    assert sorted(s.notes[0] for s in suggestions) == ["IndexA", "IndexB"]
    assert {s.text for s in suggestions} == {
        f"[[{title}]] has 12 links in 60 words (20.0 per 100 words; the median among "
        "your notes of 50+ words is 20.0). Is it a hub spreading through your "
        "vault, or is the density hiding which links matter?"
        for title in ("IndexA", "IndexB")
    }


def _isolated(builder: VaultBuilder, title: str, *, dangling: bool = False) -> None:
    """A 300-word note with one backlink, or only links to missing notes."""
    if dangling:
        builder.note(title, _body(300, 2))  # Target0, Target1 do not exist
    else:
        builder.note(title, _body(300, 0))
        _pointer(builder, title)


@pytest.mark.parametrize(
    ("isolated", "expected_shape"),
    [
        (2, [1, 1]),  # too few to group: each named singly
        (3, [3]),  # one group, nobody left over
        (4, [3, 1]),  # one group, the fourth named singly
    ],
)
def test_isolated_sparse_notes_are_grouped_in_threes(
    tmp_path: Path, isolated: int, expected_shape: list[int]
) -> None:
    """Contract: with three or more sparse notes that link to or from at most
    one other note (resolved links only: a note whose links all dangle is
    isolated), one suggestion groups three of them with their word counts;
    no note is named twice.

    Regression: the grouping lived in metadata_driven_discovery (pattern 1),
    which named the same notes as this geist's sparse branch in the same
    session; this geist had no grouping.
    """
    titles = [f"Island{i}" for i in range(isolated)]  # one-word: 2 heading tokens
    builder = VaultBuilder(tmp_path)
    for i, title in enumerate(titles):
        _isolated(builder, title, dangling=i == 0)

    suggestions = link_density_analyser.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST)
    assert [len(s.notes) for s in suggestions] == expected_shape
    named = [ref for s in suggestions for ref in s.notes]
    assert sorted(named) == titles
    groups = [s for s in suggestions if len(s.notes) == 3]
    assert [g.text for g in groups] == [
        "What do these have in common?\n"
        + "\n".join(f"- [[{title}]] (300 words)" for title in g.notes)
        + "\n\nEach is over 200 words and links to or from at most one other note "
        "in your vault. What pattern does this reveal?"
        for g in groups
    ]


def test_connected_sparse_notes_are_not_grouped(tmp_path: Path) -> None:
    """Contract: a sparse note with one backlink AND one resolved outgoing
    link has two connections, so it is never in an "at most one" group.

    Regression: a group claim made without checking each member.
    """
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        builder.note(f"Linked {i}", _body(402, 0) + " [[Hub]]")
        _pointer(builder, f"Linked {i}")
    builder.note("Hub", "Brief plain remark.")

    suggestions = link_density_analyser.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=3)
    assert sorted(s.notes[0] for s in suggestions) == [f"Linked {i}" for i in range(3)]
    assert [len(s.notes) for s in suggestions] == [1, 1, 1]
