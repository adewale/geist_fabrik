"""Unit tests for method_scrambler geist.

Trigger arithmetic (see the geist source):
- the vault needs >= 10 non-journal notes, otherwise the geist returns [];
- route 1: each sampled note with >= 2 non-journal candidates (its first 3
  outgoing links plus its 5 nearest neighbours) yields one SCAMPER prompt;
- route 2: each of vault.unlinked_pairs() (similarity > 0.5, no link) may
  yield a substitute/combine/adapt prompt;
- output is capped at 3 suggestions.

Under the bag-of-words test stub, notes sharing words are similar and notes
with disjoint vocabulary are not.
"""

from itertools import combinations
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import method_scrambler
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEIST = "method_scrambler"
CAP = 3
TOPICS = [
    "quartz lichen harbour",
    "violin saffron glacier",
    "meadow lantern cobalt",
    "thistle anchor walnut",
    "falcon ember tundra",
    "orchid basalt ferry",
    "pepper canyon mosaic",
    "silver marsh kettle",
    "tiger velvet summit",
    "copper willow nectar",
]


def _topic_notes(builder: VaultBuilder, count: int) -> list[str]:
    titles = [f"Topic {i}" for i in range(count)]
    for title, words in zip(titles, TOPICS, strict=False):
        builder.note(title, words)
    return titles


def test_prompts_pair_two_distinct_vault_notes(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    titles = _topic_notes(builder, 10)

    suggestions = method_scrambler.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    for s in suggestions:
        note, other = s.notes
        assert note != other
        assert {note, other} <= set(titles)
        assert s.text.startswith("What if you")
        assert f"[[{note}]]" in s.text and f"[[{other}]]" in s.text


@pytest.mark.parametrize(("count", "fires"), [(9, False), (10, True)])
def test_minimum_vault_size_boundary(tmp_path: Path, count: int, fires: bool) -> None:
    builder = VaultBuilder(tmp_path)
    _topic_notes(builder, count)

    suggestions = method_scrambler.suggest(builder.build())

    assert (suggestions != []) is fires


def test_output_is_capped_when_more_prompts_qualify(tmp_path: Path) -> None:
    # Every one of the 10 notes has >= 2 neighbour candidates, so route 1
    # alone produces 10 prompts for a cap of 3.
    builder = VaultBuilder(tmp_path)
    _topic_notes(builder, 10)

    suggestions = method_scrambler.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert len(suggestions) == CAP
    assert len({s.text for s in suggestions}) == CAP


def test_geist_journal_is_excluded_from_both_routes(tmp_path: Path) -> None:
    # Each journal note joins two topics (similarity > 0.5 to both topic
    # notes, and higher to journal notes sharing a topic); every topic
    # appears in 6 journal notes. Were journal notes visible, every topic
    # note's 5 nearest neighbours would be journal notes (route 1) and every
    # unlinked pair above 0.5 would involve one (route 2). "Session Linker" is
    # a journal note shaped like "Linker": it must not be a prompt's subject.
    builder = VaultBuilder(tmp_path)
    titles = _topic_notes(builder, 10)
    builder.note("Linker", "zephyr [[Topic 0]] [[Topic 1]]")
    builder.journal("Session Linker", "mistral [[Topic 2]] [[Topic 3]]")
    pairs = [(i, j) for i, j in combinations(range(10), 2) if (j - i) in (1, 2, 3, 7, 8, 9)]
    for k, (i, j) in enumerate(pairs):
        builder.journal(f"Session Log {k}", f"{TOPICS[i]} {TOPICS[j]}")

    suggestions = method_scrambler.suggest(builder.build())

    assert_valid_suggestions(
        suggestions,
        GEIST,
        must_not_reference=["Session Log", "Session Linker"],
    )
    assert all(set(s.notes) <= {"Linker", *titles} for s in suggestions)


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    _topic_notes(builder, 10)

    first = [s.text for s in method_scrambler.suggest(builder.build())]
    second = [s.text for s in method_scrambler.suggest(builder.build())]

    assert first
    assert first == second


def test_output_does_not_depend_on_hash_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same date + vault = same output, whatever PYTHONHASHSEED a process has.

    Regression: candidates were deduplicated through a set of Notes, so the
    order fed to vault.sample followed string-hash order. Salting
    Note.__hash__ stands in for a different hash seed within one process.
    """
    from geistfabrik.models import Note

    builder = VaultBuilder(tmp_path)
    _topic_notes(builder, 10)
    baseline = [s.text for s in method_scrambler.suggest(builder.build())]
    assert baseline

    for salt in ("a", "b", "c", "d", "e", "f"):
        monkeypatch.setattr(Note, "__hash__", lambda self, salt=salt: hash(salt + self.path))
        assert [s.text for s in method_scrambler.suggest(builder.build())] == baseline, salt
