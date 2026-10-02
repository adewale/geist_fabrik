"""Designed-to-trigger tests for the claim/hypothesis harvester geists.

These bundle the previously-unused ClaimExtractor/HypothesisExtractor classes
into shipped geists. Every fixture note carries an extractable claim AND
hypothesis, so whichever note random_notes(count=1) lands on, the geist fires -
the non-empty assertion is the point (per GEIST_TESTING_TEMPLATE.md).
"""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from weakref import finalize

import pytest

from geistfabrik import Session, Vault
from geistfabrik.default_geists.code import claim_harvester, hypothesis_harvester
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder

SESSION_DATE = datetime(2024, 3, 15)


def _context(notes: dict[str, str]) -> VaultContext:
    tmp = TemporaryDirectory()
    root = Path(tmp.name)
    for name, content in notes.items():
        (root / name).write_text(content)
    vault = Vault(str(root), ":memory:")
    vault.sync()
    session = Session(SESSION_DATE, vault.db)
    session.compute_embeddings(vault.all_notes())
    ctx = VaultContext(vault, session, seed=20240315)
    finalize(ctx, tmp.cleanup)
    return ctx


CLAIMY = (
    "# {title}\n"
    "Studies show that deliberate practice improves skill acquisition.\n"
    "If you space your reviews, then retention increases over weeks.\n"
)


@pytest.fixture
def claimy_vault():
    return _context({f"note{i}.md": CLAIMY.format(title=f"Note {i}") for i in range(6)})


def test_claim_harvester_fires(claimy_vault):
    suggestions = claim_harvester.suggest(claimy_vault)
    assert suggestions, "every note carries a claim; the geist must fire"
    for s in suggestions:
        assert s.geist_id == "claim_harvester"
        assert "claimed" in s.text.lower()


def test_hypothesis_harvester_fires(claimy_vault):
    suggestions = hypothesis_harvester.suggest(claimy_vault)
    assert suggestions, "every note carries an if/then hypothesis; the geist must fire"
    for s in suggestions:
        assert s.geist_id == "hypothesis_harvester"
        assert "speculates" in s.text.lower()


def test_harvesters_empty_on_plain_prose():
    ctx = _context({"plain.md": "# Plain\nJust a calm description with nothing to extract.\n"})
    assert claim_harvester.suggest(ctx) == []
    assert hypothesis_harvester.suggest(ctx) == []


def _builder_vault(tmp_path, notes: dict[str, str]) -> VaultContext:
    builder = VaultBuilder(tmp_path)
    for title, body in notes.items():
        builder.note(title, body)
    return builder.build()


PLAIN_NOTES = {f"Plain {i}": f"Plain description number {i} of nothing much" for i in range(7)}


def test_claim_harvester_tries_several_notes(tmp_path):
    """Contract: the geist looks past notes without claims before abstaining.

    Regression: it read one random note and abstained when that note had no
    claim (about two thirds of sessions on a real vault).
    """
    ctx = _builder_vault(
        tmp_path, {**PLAIN_NOTES, "Sleep": "Research shows that sleep improves recall."}
    )

    suggestions = claim_harvester.suggest(ctx)

    assert [(s.text, s.notes) for s in suggestions] == [
        (
            'In [[Sleep]] you claimed: "Research shows that sleep improves recall." '
            "Is that still true - and what would change your mind?",
            ["Sleep"],
        )
    ]


def test_hypothesis_harvester_tries_several_notes(tmp_path):
    """Contract: the geist looks past notes without hypotheses before abstaining.

    Regression: it read one random note and abstained when that note had none.
    """
    ctx = _builder_vault(
        tmp_path, {**PLAIN_NOTES, "Caching": "Caching the index might halve startup time."}
    )

    suggestions = hypothesis_harvester.suggest(ctx)

    assert [(s.text, s.notes) for s in suggestions] == [
        (
            '[[Caching]] speculates: "Caching the index might halve startup time." '
            "What is the smallest experiment that would tell you if it holds?",
            ["Caching"],
        )
    ]


def test_claim_harvester_quotes_clean_sentences(tmp_path):
    """Contract: the quoted claim is a whole sentence without Markdown labels.

    Regression: "**Root cause**: ..." (a noun) and "**Value**: "[[X]] shows ..."
    (quoted example output) were harvested, and a real claim was quoted with
    its "**Result**:" label and "**" emphasis.
    """
    ctx = _builder_vault(
        tmp_path,
        {
            "Bench": (
                "**Root cause**: the cache was never invalidated.\n\n"
                '**Value**: "[[Productivity systems]] shows interpretive rhythm."\n\n'
                "**Result**: The benchmark **confirms** a 2.5x speedup."
            )
        },
    )

    suggestions = claim_harvester.suggest(ctx)

    assert [s.text for s in suggestions] == [
        'In [[Bench]] you claimed: "The benchmark confirms a 2.5x speedup." '
        "Is that still true - and what would change your mind?"
    ]


@pytest.mark.timeout(10)
def test_hypothesis_harvester_is_fast_on_a_run_on_sentence() -> None:
    """Regression: the if/then and would/if patterns cost (#if x sentence
    length), so a 400 KB run-on "sentence" took over 30 s (the geist timeout).
    The geist's extractor now skips sentences longer than its LengthFilter
    keeps, which cannot change its output."""
    run_on = "I think " + " ".join(["if soil and roots would maybe"] * 14_000) + " would."
    ctx = _context({"Runon.md": f"# Runon\n\n{run_on}\n\nIf it rains, then the soil softens.\n"})

    suggestions = hypothesis_harvester.suggest(ctx)

    assert [s.text for s in suggestions] == [
        '[[Runon]] speculates: "If it rains, then the soil softens." What is the smallest '
        "experiment that would tell you if it holds?"
    ]
