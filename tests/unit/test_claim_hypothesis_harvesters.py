"""Designed-to-trigger tests for the claim/hypothesis harvester geists.

These bundle the previously-unused ClaimExtractor/HypothesisExtractor classes
into shipped geists. Every fixture note carries an extractable claim AND
hypothesis, so whichever note random_notes(count=1) lands on, the geist fires -
the non-empty assertion is the point (per GEIST_TESTING_TEMPLATE.md).
"""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from geistfabrik import Session, Vault
from geistfabrik.default_geists.code import claim_harvester, hypothesis_harvester
from geistfabrik.vault_context import VaultContext

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
    ctx._tmp = tmp  # type: ignore[attr-defined]  # keep alive
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


def test_harvesters_empty_vault():
    ctx = _context({"only.md": "# Only\nshort"})
    # Single short note: extractors find nothing, geists abstain (no crash).
    assert isinstance(claim_harvester.suggest(ctx), list)
    assert isinstance(hypothesis_harvester.suggest(ctx), list)
