"""Tests for the eight reflective-lens vault functions.

Contract: every function returns a list of bracketed Obsidian links
([[Note]]), returns [] gracefully when no candidates exist, and is
deterministic for the same seed.
"""

import re
from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry

pytestmark = pytest.mark.timeout(60)

BRACKETED_LINK_RE = re.compile(r"^\[\[.+\]\]$")

REFLECTIVE_FUNCTIONS = [
    "past_focused_notes",
    "future_focused_notes",
    "self_focused_notes",
    "we_notes",
    "uncertain_notes",
    "questioning_notes",
    "surprising_notes",
    "attention_shifted_notes",
]

# Voice-metadata functions: (notes designed to qualify, notes of an opposite
# voice that must not). Voice scoring itself is owned by test_voice_analysis.py.
VOICE_CASES = {
    "past_focused_notes": ({"Past A", "Past B"}, {"Future A", "Future B", "Question A"}),
    "future_focused_notes": ({"Future A", "Future B"}, {"Past A", "Past B", "We A"}),
    "self_focused_notes": ({"Self A", "Self B"}, {"We A", "We B", "Question A"}),
    "we_notes": ({"We A", "We B"}, {"Self A", "Self B", "Past A"}),
    "uncertain_notes": ({"Hedgy A", "Hedgy B"}, {"Past A", "Future A", "Question A"}),
    "questioning_notes": ({"Question A", "Question B"}, {"Hedgy A", "Past A", "Future A"}),
}
VOICE_FUNCTIONS = list(VOICE_CASES)


# ============================================================================
# Fixtures
# ============================================================================

VOICE_NOTES = {
    "past_a.md": (
        "# Past A\n\nI walked to the store. I bought milk. I returned home. I cooked dinner."
    ),
    "past_b.md": ("# Past B\n\nShe wrote letters. He painted walls. They travelled far away."),
    "future_a.md": (
        "# Future A\n\nTomorrow I will start. I will plan the trip. It will work well."
    ),
    "future_b.md": ("# Future B\n\nWe will launch soon. The team will grow. It will succeed."),
    "hedgy_a.md": (
        "# Hedgy A\n\nMaybe this works. Perhaps it could help. "
        "I think it might be fine. Presumably so."
    ),
    "hedgy_b.md": (
        "# Hedgy B\n\nApparently it seems plausible. Sort of unclear, arguably. "
        "Possibly, probably, roughly right."
    ),
    "we_a.md": (
        "# We A\n\nWe built this together. Our team succeeded. "
        "We shipped our product. We celebrated."
    ),
    "we_b.md": ("# We B\n\nWe gathered around. Us against the odds. Our shared plan held."),
    "self_a.md": (
        "# Self A\n\nI wrote my thoughts today. My ideas felt right to me. "
        "I trust myself completely."
    ),
    "self_b.md": ("# Self B\n\nI walked alone. My mind raced. I sorted my notes by myself."),
    "question_a.md": (
        "# Question A\n\nWhat is this? Why does it matter? How would anyone know? Who decides?"
    ),
    "question_b.md": ("# Question B\n\nWhere did it begin? When does it end? Which path is real?"),
}


def _make_voice_vault(tmp_path) -> Vault:
    """Build a vault with a controlled mix of linguistic voices."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    for filename, content in VOICE_NOTES.items():
        (vault_path / filename).write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    return vault


@pytest.fixture
def voice_vault(tmp_path):
    """Voice fixture vault with one computed session."""
    vault = _make_voice_vault(tmp_path)
    session = Session(datetime(2025, 1, 15), vault.db)
    session.compute_embeddings(vault.all_notes())
    return vault, session


@pytest.fixture
def empty_vault(tmp_path):
    """Empty vault with one computed session."""
    vault_path = tmp_path / "empty_vault"
    vault_path.mkdir()
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    session = Session(datetime(2025, 1, 15), vault.db)
    session.compute_embeddings(vault.all_notes())
    return vault, session


def _context(vault: Vault, session: Session, registry: FunctionRegistry) -> VaultContext:
    return VaultContext(
        vault=vault,
        session=session,
        seed=20250115,
        function_registry=registry,
    )


# ============================================================================
# Contract tests
# ============================================================================


@pytest.mark.parametrize("name", VOICE_FUNCTIONS)
def test_voice_functions_select_the_designed_notes(voice_vault, name: str) -> None:
    """Each voice lens returns bracketed links to its designed notes, not to opposite voices."""
    vault, session = voice_vault
    registry = FunctionRegistry()
    context = _context(vault, session, registry)
    expected, excluded = VOICE_CASES[name]

    result = registry.call(name, context, len(VOICE_NOTES))

    assert all(BRACKETED_LINK_RE.match(entry) for entry in result), result
    # The fixture's file names differ from the titles, so links read
    # [[past_a|Past A]]: compare the displayed titles.
    titles = {entry[2:-2].split("|")[-1] for entry in result}
    assert expected <= titles, f"{name} missed designed notes: {sorted(expected - titles)}"
    assert not titles & excluded, f"{name} picked opposite voices: {sorted(titles & excluded)}"


def test_attention_shifted_notes_no_history_returns_empty(voice_vault) -> None:
    """With a single (current) session there is no history -> []."""
    vault, session = voice_vault
    registry = FunctionRegistry()
    context = _context(vault, session, registry)

    result = registry.call("attention_shifted_notes", context)
    assert result == []


def test_attention_shifted_notes_with_history(tmp_path) -> None:
    """min_churn is an inclusive floor and count caps the result.

    Both sessions embed the same text, so every note's neighbourhood is
    unchanged (churn 0.0): a floor of 0.0 admits all notes, capped at count,
    and any positive floor admits none.
    """
    vault = _make_voice_vault(tmp_path)
    notes = vault.all_notes()

    old_session = Session(datetime(2024, 6, 1), vault.db)
    old_session.compute_embeddings(notes)

    new_session = Session(datetime(2025, 1, 15), vault.db)
    new_session.compute_embeddings(notes)

    registry = FunctionRegistry()
    context = _context(vault, new_session, registry)

    result = registry.call("attention_shifted_notes", context, 6, 0.0, 5)
    assert len(result) == 5
    assert all(BRACKETED_LINK_RE.match(entry) for entry in result), result
    assert registry.call("attention_shifted_notes", context, 6, 0.01, 5) == []


def test_all_functions_empty_vault(empty_vault) -> None:
    """All eight functions return [] on an empty vault, without raising."""
    vault, session = empty_vault
    registry = FunctionRegistry()
    context = _context(vault, session, registry)

    for name in REFLECTIVE_FUNCTIONS:
        result = registry.call(name, context)
        assert result == [], name


def test_functions_deterministic_for_same_seed(voice_vault) -> None:
    """Same vault + same seed -> identical results for every function."""
    vault, session = voice_vault
    registry = FunctionRegistry()

    context_a = _context(vault, session, registry)
    context_b = _context(vault, session, registry)

    for name in REFLECTIVE_FUNCTIONS:
        result_a = registry.call(name, context_a)
        result_b = registry.call(name, context_b)
        assert result_a == result_b, name


def test_count_parameter_caps_results(voice_vault) -> None:
    """The count argument is honoured exactly when enough candidates exist."""
    vault, session = voice_vault
    registry = FunctionRegistry()
    context = _context(vault, session, registry)

    for name in VOICE_FUNCTIONS:
        assert len(registry.call(name, context, 1)) == 1, name
    assert len(registry.call("surprising_notes", context, 2)) == 2
