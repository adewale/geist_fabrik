"""Unit tests for pattern_finder geist.

Trigger arithmetic (see the geist source):
- the vault needs >= 15 non-journal notes, otherwise the geist returns [];
- phrase route: 3 consecutive words of prose (frontmatter, code, headings,
  table rows, URLs and punctuation boundaries excluded) longer than 15
  characters, neither starting nor ending with a whole-token stopword, found
  in >= 3 notes of which >= 3 have no link to another note of the group;
- cluster route: a seed plus notes with similarity > 0.80 to it (at most 5
  per cluster, at most 3 clusters), reported when >= 3 notes and no
  internal links;
- output is capped at 2 suggestions.

Fixture vocabulary: phrase-route notes share one long phrase and otherwise
use distinct words, so they are not similar enough to cluster. Cluster-route
notes use identical bags of 3-letter words (similarity ~1.0 under the
lexical stub) whose 3-token windows are <= 15 characters, so the phrase
route ignores them. Fillers use distinct short words and match neither.
"""

from pathlib import Path
from typing import Any

import pytest

from geistfabrik.default_geists.code import pattern_finder
from geistfabrik.models import Note
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEIST = "pattern_finder"
CAP = 2
PHRASE = "velvet copper lantern"
CLUSTER_BODY = "ash elm oak fig yew ivy"


def _fillers(builder: VaultBuilder, count: int) -> None:
    for i in range(count):
        builder.note(f"Filler {i}", f"q{i}a q{i}b q{i}c")


def _phrase_note(builder: VaultBuilder, title: str, index: int, extra: str = "") -> None:
    builder.note(title, f"p{index}x p{index}y {PHRASE} p{index}z {extra}")


def test_phrase_shared_by_three_unlinked_notes_is_reported(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    group = ["Echo A", "Echo B", "Echo C"]
    for i, title in enumerate(group):
        _phrase_note(builder, title, i)
    _fillers(builder, 12)

    suggestions = pattern_finder.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, must_reference=group)
    assert [sorted(s.notes) for s in suggestions] == [group]
    assert f'The phrase "{PHRASE}"' in suggestions[0].text


@pytest.mark.parametrize(("group_size", "fires"), [(2, False), (3, True)])
def test_phrase_needs_three_notes(tmp_path: Path, group_size: int, fires: bool) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(group_size):
        _phrase_note(builder, f"Echo {i}", i)
    _fillers(builder, 15 - group_size)

    suggestions = pattern_finder.suggest(builder.build())

    assert (suggestions != []) is fires


def test_phrase_repeated_within_one_note_is_not_a_pattern(tmp_path: Path) -> None:
    # Regression: phrases were counted once per occurrence, not per note, so
    # one note repeating a phrase three times was reported as "multiple
    # unconnected notes: [[Echo]], [[Echo]], [[Echo]]".
    builder = VaultBuilder(tmp_path)
    builder.note("Echo", f"{PHRASE} p1 {PHRASE} p2 {PHRASE}")
    _fillers(builder, 14)

    assert pattern_finder.suggest(builder.build()) == []


@pytest.mark.parametrize(("linked", "fires"), [(False, True), (True, False)])
def test_linked_phrase_notes_do_not_count_as_isolated(
    tmp_path: Path, linked: bool, fires: bool
) -> None:
    # Four notes share the phrase. Linking A to B leaves only C and D
    # isolated: 2 < 3, so the phrase is no longer an unconnected pattern.
    builder = VaultBuilder(tmp_path)
    for i, title in enumerate(["Echo A", "Echo B", "Echo C", "Echo D"]):
        extra = "[[Echo B]]" if linked and title == "Echo A" else ""
        _phrase_note(builder, title, i, extra)
    _fillers(builder, 11)

    suggestions = pattern_finder.suggest(builder.build())

    assert (suggestions != []) is fires


@pytest.mark.parametrize(("vault_size", "fires"), [(14, False), (15, True)])
def test_minimum_vault_size_boundary(tmp_path: Path, vault_size: int, fires: bool) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        _phrase_note(builder, f"Echo {i}", i)
    _fillers(builder, vault_size - 3)

    suggestions = pattern_finder.suggest(builder.build())

    assert (suggestions != []) is fires


def test_unlinked_semantic_cluster_is_reported(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    group = ["Kiln 1", "Kiln 2", "Kiln 3"]
    for title in group:
        builder.note(title, CLUSTER_BODY)
    _fillers(builder, 12)

    suggestions = pattern_finder.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, must_reference=group)
    assert [sorted(s.notes) for s in suggestions] == [group]
    assert "semantic cluster" in suggestions[0].text


@pytest.mark.parametrize(("cluster_size", "fires"), [(2, False), (3, True)])
def test_cluster_needs_three_notes(tmp_path: Path, cluster_size: int, fires: bool) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(cluster_size):
        builder.note(f"Kiln {i}", CLUSTER_BODY)
    _fillers(builder, 15 - cluster_size)

    suggestions = pattern_finder.suggest(builder.build())

    assert (suggestions != []) is fires


@pytest.mark.parametrize(("linked", "fires"), [(False, True), (True, False)])
def test_internally_linked_cluster_is_not_reported(
    tmp_path: Path, linked: bool, fires: bool
) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Kiln 1", f"{CLUSTER_BODY} [[Kiln 2]]" if linked else CLUSTER_BODY)
    builder.note("Kiln 2", CLUSTER_BODY)
    builder.note("Kiln 3", CLUSTER_BODY)
    _fillers(builder, 12)

    suggestions = pattern_finder.suggest(builder.build())

    assert (suggestions != []) is fires


def _twelve_kilns(tmp_path: Path) -> VaultBuilder:
    builder = VaultBuilder(tmp_path)
    for i in range(12):
        builder.note(f"Kiln {i}", CLUSTER_BODY)
    _fillers(builder, 3)
    return builder


def test_clusters_are_disjoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every note lands in at most one cluster.

    Twelve near-identical notes exceed the 5-note cluster limit, so the
    geist must build a second cluster from what is left (with only 3
    fillers, a second cluster seed is always drawn before the pool shrinks
    to 5). The seed and the
    members of each cluster must leave the unclustered pool; otherwise a note
    reappears in a later cluster (or the seed matches itself and appears
    twice in its own cluster). The spy records each cluster as the geist
    hands it to vault.sample(cluster, count=3) for display, then delegates.
    """
    builder = _twelve_kilns(tmp_path)
    ctx = builder.build()
    clusters: list[list[str]] = []
    real_sample = ctx.sample

    def spy_sample(items: Any, count: int) -> Any:
        if count == 3 and items and all(isinstance(n, Note) for n in items):
            clusters.append([n.title for n in items])
        return real_sample(items, count)

    monkeypatch.setattr(ctx, "sample", spy_sample)

    suggestions = pattern_finder.suggest(ctx)

    assert_valid_suggestions(suggestions, GEIST, min_count=2)
    assert len(clusters) >= 2, f"fixture should form two clusters, got {clusters}"
    for cluster in clusters:
        assert len(cluster) == len(set(cluster)), f"note repeated inside {cluster}"
    flat = [title for cluster in clusters for title in cluster]
    assert len(flat) == len(set(flat)), f"note shared between clusters: {clusters}"
    assert set(flat) <= {f"Kiln {i}" for i in range(12)}


def test_output_is_capped_when_more_patterns_qualify(tmp_path: Path) -> None:
    # Three phrase groups qualify: three suggestions for a cap of 2.
    builder = VaultBuilder(tmp_path)
    phrases = [PHRASE, "saffron glacier harbour", "walnut falcon orchid"]
    for g, phrase in enumerate(phrases):
        for i in range(3):
            builder.note(f"Echo {g}{i}", f"p{g}{i}x p{g}{i}y {phrase} p{g}{i}z")
    _fillers(builder, 6)

    suggestions = pattern_finder.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert len(suggestions) == CAP
    assert len({s.text for s in suggestions}) == CAP


def test_geist_journal_notes_never_join_a_pattern(tmp_path: Path) -> None:
    # Journal notes repeat the regular group's phrase and also form their own
    # three-note phrase group; neither may surface.
    builder = VaultBuilder(tmp_path)
    group = ["Echo A", "Echo B", "Echo C"]
    for i, title in enumerate(group):
        _phrase_note(builder, title, i)
    for i in range(3):
        builder.journal(f"Session Log {i}", f"s{i}x {PHRASE} s{i}y saffron glacier harbour")
    _fillers(builder, 12)

    suggestions = pattern_finder.suggest(builder.build())

    assert_valid_suggestions(
        suggestions, GEIST, must_reference=group, must_not_reference=["Session Log"]
    )


def test_output_does_not_depend_on_hash_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same date + vault = same output, whatever PYTHONHASHSEED a process has.

    Regression: the clustering pool was a set of Notes, so seed choice
    followed string-hash order and varied between processes. Salting
    Note.__hash__ stands in for a different hash seed within one process.
    """
    builder = _twelve_kilns(tmp_path)
    baseline = [s.text for s in pattern_finder.suggest(builder.build())]
    assert baseline

    for salt in ("a", "b", "c", "d"):
        monkeypatch.setattr(Note, "__hash__", lambda self, salt=salt: hash(salt + self.path))
        assert [s.text for s in pattern_finder.suggest(builder.build())] == baseline, salt


def test_markdown_syntax_and_function_word_phrases_are_not_themes(tmp_path: Path) -> None:
    """Contract: a "phrase" is three consecutive words of prose. Code (fenced
    and inline), headings, table rows and phrases that start or end with a
    stopword are never reported as a recurring theme.

    Regression: phrases were whitespace trigrams of raw markdown, so three
    notes sharing a code sample, a template heading, a table row or "for
    large vaults" were reported as e.g. 'The phrase "link in note.links:"'.
    """
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        builder.note(
            f"Spec {i}",
            f"q{i}a q{i}b\n\n"
            "## Success Metrics Overview\n\n"
            "```python\nfor link in note.links:\n    pass\n```\n\n"
            "Call `geistfabrik.vault import Vault` first.\n\n"
            "| Column | Bold assertions here |\n\n"
            f"q{i}c works for large vaults q{i}d\n",
        )
    _fillers(builder, 12)

    suggestions = pattern_finder.suggest(builder.build())

    # The three near-identical notes do form a semantic cluster; the only
    # suggestion is that one, never a phrase.
    assert [s.text.startswith("Found a semantic cluster") for s in suggestions] == [True]


def test_stopwords_match_whole_tokens_not_substrings(tmp_path: Path) -> None:
    """Contract: stopwords are whole tokens, so a phrase whose words merely
    contain one ("understanding" contains "and") is still a theme.

    Regression: the filter was `common in phrase` over the joined string, so
    any phrase containing "the", "and", "with", ... as a substring (other,
    understanding, together, withdrawal) was silently dropped.
    """
    builder = VaultBuilder(tmp_path)
    group = ["Echo A", "Echo B", "Echo C"]
    for i, title in enumerate(group):
        builder.note(title, f"p{i}x understanding together otherwise p{i}z")
    _fillers(builder, 12)

    suggestions = pattern_finder.suggest(builder.build())

    assert [s.text for s in suggestions] == [
        'The phrase "understanding together otherwise" appears in multiple unconnected '
        f"notes: {', '.join(f'[[{n}]]' for n in suggestions[0].notes)}. "
        "Recurring theme you haven't explicitly connected?"
    ]
    assert sorted(suggestions[0].notes) == group
