"""Integration tests for all bundled default geists.

These tests verify that all geists in src/geistfabrik/default_geists/ work correctly
with a real vault. Uses stubs (kepano-obsidian-main test vault), not mocks.

Tests cover:
- Every bundled code geist loads and executes cleanly (per the executor's
  execution log, since execute_geist swallows exceptions)
- The harvester geists are deterministic for a fixed seed
- Selected Tracery geists produce well-formed output

Per-geist behaviour is owned by the per-geist unit tests in tests/unit/,
which use fixtures designed to make each geist fire.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik import GeistExecutor, Vault, VaultContext
from geistfabrik.default_geists import CODE_GEIST_COUNT
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.tracery import TraceryGeist
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions


@pytest.fixture(scope="module")
def test_vault_path() -> Path:
    """Get path to test vault."""
    return Path(__file__).parent.parent.parent / "testdata" / "kepano-obsidian-main"


@pytest.fixture(scope="module")
def vault(test_vault_path: Path) -> Vault:
    """Create vault from test data."""
    vault = Vault(str(test_vault_path), ":memory:")
    vault.sync()
    return vault


@pytest.fixture(scope="module")
def session(vault: Vault) -> Session:
    """Create session with embeddings."""
    session_date = datetime(2023, 10, 1)
    session = Session(session_date, vault.db)

    # Compute embeddings for all notes
    notes = vault.all_notes()
    session.compute_embeddings(notes)

    return session


@pytest.fixture(scope="module")
def vault_context(vault: Vault, session: Session) -> VaultContext:
    """Create VaultContext for geist execution."""
    function_registry = FunctionRegistry()
    return VaultContext(
        vault=vault,
        session=session,
        seed=20231001,  # Deterministic seed
        function_registry=function_registry,
    )


@pytest.fixture
def geist_executor(test_vault_path: Path) -> GeistExecutor:
    """Create GeistExecutor for loading code geists."""
    repo_root = Path(__file__).parent.parent.parent
    code_geists_dir = repo_root / "src" / "geistfabrik" / "default_geists" / "code"
    executor = GeistExecutor(code_geists_dir, timeout=5)
    executor.load_geists()
    return executor


# ============================================================================
# Tracery Geists Tests
# ============================================================================


def test_random_prompts_tracery_geist(vault_context: VaultContext):
    """Test random_prompts Tracery geist."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "src"
        / "geistfabrik"
        / "default_geists"
        / "tracery"
        / "random_prompts.yaml"
    )

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "random_prompts"

    suggestions = geist.suggest(vault_context)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "random_prompts"


def test_note_combinations_tracery_geist(vault_context: VaultContext):
    """Test note_combinations Tracery geist."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "src"
        / "geistfabrik"
        / "default_geists"
        / "tracery"
        / "note_combinations.yaml"
    )

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "note_combinations"

    suggestions = geist.suggest(vault_context)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "note_combinations"
        # Should reference vault notes
        assert "[[" in suggestion.text


def test_what_if_tracery_geist(vault_context: VaultContext):
    """Test what_if Tracery geist."""
    repo_root = Path(__file__).parent.parent.parent
    geist_path = repo_root / "src" / "geistfabrik" / "default_geists" / "tracery" / "what_if.yaml"

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "what_if"

    suggestions = geist.suggest(vault_context)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "what_if"
        # Should start with "What if"
        assert suggestion.text.startswith("What if")


def test_orphan_connector_tracery_geist(vault_context: VaultContext):
    """Test orphan_connector Tracery geist."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "src"
        / "geistfabrik"
        / "default_geists"
        / "tracery"
        / "orphan_connector.yaml"
    )

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "orphan_connector"
    assert geist.count == 1

    suggestions = geist.suggest(vault_context)
    assert isinstance(suggestions, list)
    assert len(suggestions) == 1

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "orphan_connector"
        # Should reference orphan notes
        assert "[[" in suggestion.text


def test_hub_explorer_tracery_geist(vault_context: VaultContext):
    """Test hub_explorer Tracery geist."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "src"
        / "geistfabrik"
        / "default_geists"
        / "tracery"
        / "hub_explorer.yaml"
    )

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "hub_explorer"
    assert geist.count == 2

    suggestions = geist.suggest(vault_context)

    # Only notes with at least 3 backlinks are called "central"; each is
    # named at most once, so a vault with one such hub gets one suggestion.
    central = {
        h.link_text for h in vault_context.hubs(5) if len(vault_context.backlinks(h)) >= 3
    }
    assert central
    assert len(suggestions) == min(2, len(central))
    for suggestion in suggestions:
        assert suggestion.geist_id == "hub_explorer"
        assert len(suggestion.notes) == 1 and suggestion.notes[0] in central


def test_semantic_neighbours_tracery_geist(vault_context: VaultContext):
    """Test semantic_neighbours Tracery geist."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "src"
        / "geistfabrik"
        / "default_geists"
        / "tracery"
        / "semantic_neighbours.yaml"
    )

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "semantic_neighbours"
    assert geist.count == 2

    suggestions = geist.suggest(vault_context)
    assert isinstance(suggestions, list)
    assert len(suggestions) == 2

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "semantic_neighbours"

        # Should reference seed note and neighbour notes with proper formatting
        import re

        wikilinks = re.findall(r"\[\[([^\]]+)\]\]", suggestion.text)

        # Should have at least 2 wikilinks (seed + neighbours)
        assert len(wikilinks) >= 2, (
            f"Expected >= 2 wikilinks (seed + neighbours), got {len(wikilinks)} "
            f"in: {suggestion.text}"
        )

        # All wikilinks should be properly formatted (no orphaned note references)
        assert suggestion.text.count("[[") == suggestion.text.count("]]"), (
            f"Mismatched brackets in: {suggestion.text}"
        )

        # Suggestion.notes should match extracted wikilinks
        assert len(suggestion.notes) == len(wikilinks), (
            f"Suggestion.notes has {len(suggestion.notes)} entries but text has "
            f"{len(wikilinks)} wikilinks"
        )


# ============================================================================
# Cross-geist Tests
# ============================================================================


def test_all_geists_are_loadable(geist_executor: GeistExecutor):
    """Test that all bundled default code geists can be loaded without errors."""
    geist_executor.load_geists()

    # Use programmatic count from default_geists/__init__.py (single source of truth)
    assert len(geist_executor.geists) == CODE_GEIST_COUNT


def test_all_geists_execute_without_crashing(
    vault_context: VaultContext, geist_executor: GeistExecutor
):
    """Every bundled code geist runs to completion on a real vault.

    GeistExecutor.execute_geist swallows exceptions and timeouts and returns
    [], so the return value cannot reveal a crash. The execution log can:
    a geist that raises or times out records status "error" instead of
    "success". Regression caught: any bundled geist that crashes, returns a
    non-list, emits malformed suggestions, or exceeds the timeout.
    """
    for geist_id in geist_executor.geists:
        geist_executor.execute_geist(geist_id, vault_context)

    log = geist_executor.get_execution_log()
    failures = {
        entry["geist_id"]: entry.get("error", entry.get("reason", entry["status"]))
        for entry in log
        if entry["status"] != "success"
    }
    assert not failures, f"geists did not execute cleanly: {failures}"
    succeeded = {entry["geist_id"] for entry in log}
    assert succeeded == set(geist_executor.geists)


def test_geist_determinism(vault_context: VaultContext):
    """Test that geists produce deterministic output with same seed."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "src"
        / "geistfabrik"
        / "default_geists"
        / "tracery"
        / "random_prompts.yaml"
    )

    # Create two identical geists with same seed
    geist1 = TraceryGeist.from_yaml(geist_path, seed=12345)
    geist2 = TraceryGeist.from_yaml(geist_path, seed=12345)

    suggestions1 = geist1.suggest(vault_context)
    suggestions2 = geist2.suggest(vault_context)

    # Same seed should produce same suggestions
    assert len(suggestions1) == len(suggestions2)
    for s1, s2 in zip(suggestions1, suggestions2):
        assert s1.text == s2.text


# ============================================================================
# Harvester Family Determinism
# ============================================================================


def _harvestable_vault(root: Path) -> VaultContext:
    """Every note carries four questions, four TODOs and four blockquotes.

    Whichever note a harvester samples, it has more candidates than the
    3-suggestion cap, so both the note choice and the candidate sample are
    exercised by the seeded RNG.
    """
    builder = VaultBuilder(root)
    for i in range(6):
        builder.note(
            f"Garden Log {i}",
            f"Why does bed {i} grow faster in spring rain?\n"
            f"How might soil in plot {i} change over decades?\n"
            f"What would happen if clover covered row {i} entirely?\n"
            f"Where do the earthworms of patch {i} shelter in winter?\n\n"
            f"TODO: measure the soil acidity of bed {i} carefully\n"
            f"TODO: order heritage tomato seeds for plot {i} soon\n"
            f"FIXME: repair the irrigation valve beside row {i}\n"
            f"TODO: sketch a planting map for herb spiral {i}\n\n"
            f"> Garden {i} teaches patience through every slow season.\n\n"
            f"> Plot {i} is autobiography written in soil and water.\n\n"
            f"> Row {i} reminds us that planting means trusting tomorrow.\n\n"
            f"> Patch {i} shows nature never hurries yet finishes everything.\n",
        )
    return builder.build()


@pytest.mark.parametrize("geist_id", ["question_harvester", "todo_harvester", "quote_harvester"])
def test_harvester_is_deterministic_for_a_fixed_seed(
    tmp_path: Path, geist_executor: GeistExecutor, geist_id: str
) -> None:
    """Same vault + same seed gives the same harvested suggestions.

    Two independently built contexts with the same seed must agree on both
    which note is harvested and which of its candidates are sampled.
    Regression caught: a harvester drawing from an unseeded RNG (e.g. the
    global ``random`` module) instead of the VaultContext's seeded one.
    """
    first = geist_executor.execute_geist(geist_id, _harvestable_vault(tmp_path / "a"))
    second = geist_executor.execute_geist(geist_id, _harvestable_vault(tmp_path / "b"))

    assert_valid_suggestions(first, geist_id, min_count=3, must_reference=("Garden Log",))
    assert [(s.text, s.notes) for s in first] == [(s.text, s.notes) for s in second]
