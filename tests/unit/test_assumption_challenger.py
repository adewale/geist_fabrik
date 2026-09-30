"""Unit tests for assumption_challenger geist.

Trigger arithmetic (see the geist source):
- the vault needs >= 10 non-journal notes, otherwise the geist returns [];
- causal trigger: a note with >= 3 distinct causal markers ("because",
  "therefore", "thus", ...) and fewer than 2 outgoing links;
- certainty trigger: a note with >= 2 assumption phrases ("obviously",
  "clearly", ...) whose semantic neighbour has >= 2 hedging phrases
  ("maybe", "perhaps", ...). Under the bag-of-words test stub, shared
  content words make the two notes neighbours;
- output is capped at 3 suggestions.
"""

from pathlib import Path

import pytest

from geistfabrik.default_geists.code import assumption_challenger
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEIST = "assumption_challenger"
CAP = 3
CAUSAL_BODY = "Growth happens because of soil, therefore roots spread, and thus it leads to fruit."


def _fillers(builder: VaultBuilder, count: int) -> None:
    for i in range(count):
        builder.note(f"Filler {i}", f"Plain remark number {i} about pebbles.")


def _causal_vault(
    tmp_path: Path, *, total_notes: int, causal_body: str = CAUSAL_BODY
) -> VaultContext:
    builder = VaultBuilder(tmp_path)
    builder.note("Causal Claim", causal_body)
    _fillers(builder, total_notes - 1)
    return builder.build()


def test_causal_claims_without_links_are_challenged(tmp_path: Path) -> None:
    ctx = _causal_vault(tmp_path, total_notes=12)

    suggestions = assumption_challenger.suggest(ctx)

    assert_valid_suggestions(suggestions, GEIST, must_reference=["Causal Claim"])
    assert [s.notes for s in suggestions] == [["Causal Claim"]]
    assert "causal claims" in suggestions[0].text


def test_certain_note_is_paired_with_hedging_neighbour(tmp_path: Path) -> None:
    # The two notes share "orchard", "pruning" and "yield", so under the
    # lexical stub the hedging note is the certain note's nearest neighbour.
    builder = VaultBuilder(tmp_path)
    builder.note("Certain Orchard", "Obviously orchard pruning clearly raises yield.")
    builder.note("Hedging Orchard", "Maybe orchard pruning perhaps raises yield.")
    _fillers(builder, 10)
    ctx = builder.build()

    suggestions = assumption_challenger.suggest(ctx)

    assert_valid_suggestions(suggestions, GEIST)
    assert [s.notes for s in suggestions] == [["Certain Orchard", "Hedging Orchard"]]
    assert "seem certain" in suggestions[0].text


def test_certain_note_without_hedging_neighbour_is_not_paired(tmp_path: Path) -> None:
    # Control for the pairing test: a single hedging phrase is below the
    # >= 2 threshold, so certainty alone must not produce a suggestion.
    builder = VaultBuilder(tmp_path)
    builder.note("Certain Orchard", "Obviously orchard pruning clearly raises yield.")
    builder.note("Hedging Orchard", "Maybe orchard pruning raises yield.")
    _fillers(builder, 10)

    assert assumption_challenger.suggest(builder.build()) == []


@pytest.mark.parametrize(("total_notes", "fires"), [(9, False), (10, True)])
def test_minimum_vault_size_boundary(tmp_path: Path, total_notes: int, fires: bool) -> None:
    ctx = _causal_vault(tmp_path, total_notes=total_notes)

    suggestions = assumption_challenger.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, GEIST, must_reference=["Causal Claim"])
    else:
        assert suggestions == []


@pytest.mark.parametrize(
    ("causal_body", "fires"),
    [
        ("Growth happens because of soil, therefore roots spread.", False),
        (CAUSAL_BODY, True),
    ],
)
def test_causal_marker_count_boundary(tmp_path: Path, causal_body: str, fires: bool) -> None:
    ctx = _causal_vault(tmp_path, total_notes=12, causal_body=causal_body)

    suggestions = assumption_challenger.suggest(ctx)

    assert (suggestions != []) is fires


@pytest.mark.parametrize(("link_count", "fires"), [(1, True), (2, False)])
def test_causal_note_link_count_boundary(tmp_path: Path, link_count: int, fires: bool) -> None:
    links = " ".join(f"[[Filler {i}]]" for i in range(link_count))
    ctx = _causal_vault(tmp_path, total_notes=12, causal_body=f"{CAUSAL_BODY} {links}")

    suggestions = assumption_challenger.suggest(ctx)

    assert (suggestions != []) is fires


def test_output_is_capped_when_more_notes_qualify(tmp_path: Path) -> None:
    # Six causal notes qualify: twice the cap of 3.
    builder = VaultBuilder(tmp_path)
    planted = [f"Causal {i}" for i in range(6)]
    for title in planted:
        builder.note(title, CAUSAL_BODY)
    _fillers(builder, 6)

    suggestions = assumption_challenger.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert len(suggestions) == CAP
    referenced = [ref for s in suggestions for ref in s.notes]
    assert len(set(referenced)) == CAP, "cap must not be filled by repeats"
    assert set(referenced) <= set(planted)


def test_geist_journal_is_excluded_both_as_subject_and_as_neighbour(tmp_path: Path) -> None:
    # Journal session notes carry causal claims and hedging language that
    # would trigger both branches; only the regular causal note may appear.
    builder = VaultBuilder(tmp_path)
    builder.note("Causal Claim", CAUSAL_BODY)
    builder.note("Certain Orchard", "Obviously orchard pruning clearly raises yield.")
    for i in range(4):
        builder.journal(f"Session Echo {i}", CAUSAL_BODY)
    builder.journal("Session Doubt", "Maybe orchard pruning perhaps raises yield.")
    _fillers(builder, 8)

    suggestions = assumption_challenger.suggest(builder.build())

    assert_valid_suggestions(
        suggestions,
        GEIST,
        must_reference=["Causal Claim"],
        must_not_reference=["Session Echo", "Session Doubt"],
    )


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(6):
        builder.note(f"Causal {i}", CAUSAL_BODY)
    _fillers(builder, 6)

    first = [s.text for s in assumption_challenger.suggest(builder.build())]
    second = [s.text for s in assumption_challenger.suggest(builder.build())]

    assert first
    assert first == second
