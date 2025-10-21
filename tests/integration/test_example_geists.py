"""Integration tests for all example geists.

These tests verify that all geists in examples/geists/ work correctly
with a real vault. Uses stubs (kepano-obsidian-main test vault), not mocks.

Tests cover:
- All 10 code geists in examples/geists/code/
- All 7 Tracery geists in examples/geists/tracery/

Performance target: All tests should complete in < 10 seconds total
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik import GeistExecutor, Vault, VaultContext
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.tracery import TraceryGeist


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
    code_geists_dir = Path(__file__).parent.parent.parent / "examples" / "geists" / "code"
    return GeistExecutor(code_geists_dir, timeout=5)


# ============================================================================
# Code Geists Tests (10 geists)
# ============================================================================


def test_temporal_drift_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test temporal_drift geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("temporal_drift", vault_context)

    assert isinstance(suggestions, list)
    # May return empty list if no old notes, but type should be correct
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "temporal_drift"


def test_creative_collision_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test creative_collision geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("creative_collision", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "creative_collision"


def test_bridge_builder_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test bridge_builder geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("bridge_builder", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "bridge_builder"


def test_complexity_mismatch_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test complexity_mismatch geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("complexity_mismatch", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "complexity_mismatch"


def test_question_generator_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test question_generator geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("question_generator", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "question_generator"


def test_link_density_analyzer_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test link_density_analyzer geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("link_density_analyzer", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "link_density_analyzer"


def test_task_archaeology_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test task_archaeology geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("task_archaeology", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "task_archaeology"


def test_concept_cluster_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test concept_cluster geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("concept_cluster", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "concept_cluster"


def test_stub_expander_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test stub_expander geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("stub_expander", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "stub_expander"


def test_recent_focus_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test recent_focus geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("recent_focus", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "recent_focus"


# ============================================================================
# Tracery Geists Tests (7 geists)
# ============================================================================


def test_random_prompts_tracery_geist(vault_context: VaultContext):
    """Test random_prompts Tracery geist."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "examples"
        / "geists"
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
        / "examples"
        / "geists"
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
    geist_path = (
        Path(__file__).parent.parent.parent / "examples" / "geists" / "tracery" / "what_if.yaml"
    )

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


def test_temporal_mirror_tracery_geist(vault_context: VaultContext):
    """Test temporal_mirror Tracery geist (new)."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "examples"
        / "geists"
        / "tracery"
        / "temporal_mirror.yaml"
    )

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "temporal_mirror"
    assert geist.count == 2  # count: 2 in YAML

    suggestions = geist.suggest(vault_context)
    assert isinstance(suggestions, list)
    assert len(suggestions) == 2  # count: 2

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "temporal_mirror"
        # Should reference both old and recent notes
        assert "[[" in suggestion.text
        # Should mention timeframe
        assert "month" in suggestion.text.lower() or "year" in suggestion.text.lower()


def test_orphan_connector_tracery_geist(vault_context: VaultContext):
    """Test orphan_connector Tracery geist."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "examples"
        / "geists"
        / "tracery"
        / "orphan_connector.yaml"
    )

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "orphan_connector"
    assert geist.count == 2

    suggestions = geist.suggest(vault_context)
    assert isinstance(suggestions, list)
    assert len(suggestions) == 2

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
        / "examples"
        / "geists"
        / "tracery"
        / "hub_explorer.yaml"
    )

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "hub_explorer"
    assert geist.count == 2

    suggestions = geist.suggest(vault_context)
    assert isinstance(suggestions, list)
    assert len(suggestions) == 2

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "hub_explorer"
        # Should reference hub notes
        assert "[[" in suggestion.text


def test_semantic_neighbors_tracery_geist(vault_context: VaultContext):
    """Test semantic_neighbors Tracery geist."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "examples"
        / "geists"
        / "tracery"
        / "semantic_neighbors.yaml"
    )

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "semantic_neighbors"
    assert geist.count == 2

    suggestions = geist.suggest(vault_context)
    assert isinstance(suggestions, list)
    assert len(suggestions) == 2

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "semantic_neighbors"
        # Should reference seed note and neighbor notes
        assert "[[" in suggestion.text


# ============================================================================
# Cross-geist Tests
# ============================================================================


def test_all_geists_are_loadable(geist_executor: GeistExecutor):
    """Test that all example code geists can be loaded without errors."""
    geist_executor.load_geists()

    # We have 10 code geists in examples/geists/code/
    assert len(geist_executor.geists) == 10


def test_all_geists_execute_without_crashing(
    vault_context: VaultContext, geist_executor: GeistExecutor
):
    """Test that all geists can execute without throwing exceptions."""
    geist_executor.load_geists()

    for geist_id in geist_executor.geists.keys():
        try:
            suggestions = geist_executor.execute_geist(geist_id, vault_context)
            # Should return a list (might be empty)
            assert isinstance(suggestions, list)
        except Exception as e:
            pytest.fail(f"Geist {geist_id} crashed: {e}")


def test_geist_determinism(vault_context: VaultContext):
    """Test that geists produce deterministic output with same seed."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "examples"
        / "geists"
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
