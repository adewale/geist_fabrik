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
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry

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

# Functions whose candidates come from voice metadata in the fixture vault
VOICE_FUNCTIONS = [
    "past_focused_notes",
    "future_focused_notes",
    "self_focused_notes",
    "we_notes",
    "uncertain_notes",
    "questioning_notes",
]


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


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


def test_all_functions_registered() -> None:
    """All eight reflective-lens functions are built-ins."""
    registry = FunctionRegistry()
    for name in REFLECTIVE_FUNCTIONS:
        assert registry.has_function(name), name


def test_voice_functions_return_bracketed_links(voice_vault) -> None:
    """Voice-metadata functions return non-empty lists of [[links]]."""
    vault, session = voice_vault
    registry = FunctionRegistry()
    context = _context(vault, session, registry)

    for name in VOICE_FUNCTIONS:
        result = registry.call(name, context)
        assert isinstance(result, list), name
        assert len(result) > 0, f"{name} found no candidates in the voice vault"
        for entry in result:
            assert isinstance(entry, str), name
            assert BRACKETED_LINK_RE.match(entry), f"{name} returned unbracketed entry: {entry}"


def test_surprising_notes_returns_bracketed_links(voice_vault) -> None:
    """surprising_notes returns top-k bracketed links (12 notes >= k+1)."""
    vault, session = voice_vault
    registry = FunctionRegistry()
    context = _context(vault, session, registry)

    result = registry.call("surprising_notes", context)
    assert isinstance(result, list)
    assert 0 < len(result) <= 5
    for entry in result:
        assert BRACKETED_LINK_RE.match(entry), entry


def test_attention_shifted_notes_no_history_returns_empty(voice_vault) -> None:
    """With a single (current) session there is no history -> []."""
    vault, session = voice_vault
    registry = FunctionRegistry()
    context = _context(vault, session, registry)

    result = registry.call("attention_shifted_notes", context)
    assert result == []


def test_attention_shifted_notes_with_history(tmp_path) -> None:
    """With an old session and min_churn=0.0, returns bracketed links."""
    vault = _make_voice_vault(tmp_path)
    notes = vault.all_notes()

    old_session = Session(datetime(2024, 6, 1), vault.db)
    old_session.compute_embeddings(notes)

    new_session = Session(datetime(2025, 1, 15), vault.db)
    new_session.compute_embeddings(notes)

    registry = FunctionRegistry()
    context = _context(vault, new_session, registry)

    result = registry.call("attention_shifted_notes", context, 6, 0.0, 5)
    assert isinstance(result, list)
    assert 0 < len(result) <= 5
    for entry in result:
        assert BRACKETED_LINK_RE.match(entry), entry


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


def test_k_parameter_limits_results(voice_vault) -> None:
    """The k parameter caps the number of returned links."""
    vault, session = voice_vault
    registry = FunctionRegistry()
    context = _context(vault, session, registry)

    for name in VOICE_FUNCTIONS:
        result = registry.call(name, context, 1)
        assert len(result) <= 1, name

    result = registry.call("surprising_notes", context, 2)
    assert len(result) <= 2


def test_candidates_match_expected_voices(voice_vault) -> None:
    """Spot-check that the controlled fixture notes appear as candidates."""
    vault, session = voice_vault
    registry = FunctionRegistry()
    context = _context(vault, session, registry)

    questioning = registry.call("questioning_notes", context, 12)
    assert any("Question" in entry for entry in questioning)

    uncertain = registry.call("uncertain_notes", context, 12)
    assert any("Hedgy" in entry for entry in uncertain)

    future = registry.call("future_focused_notes", context, 12)
    assert any("Future" in entry for entry in future)

    we = registry.call("we_notes", context, 12)
    assert any("We" in entry for entry in we)
