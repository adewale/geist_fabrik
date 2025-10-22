"""Integration tests for all example geists.

These tests verify that all geists in examples/geists/ work correctly
with a real vault. Uses stubs (kepano-obsidian-main test vault), not mocks.

Tests cover:
- All 29 code geists in examples/geists/code/
- All 8 Tracery geists in examples/geists/tracery/

Performance target: All tests should complete in < 15 seconds total
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
# Code Geists Tests (29 geists)
# ============================================================================


# Original 10 geists


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


def test_link_density_analyser_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test link_density_analyser geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("link_density_analyser", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "link_density_analyser"


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


# New ambitious geists (19 total)


def test_columbo_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test columbo geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("columbo", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "columbo"


def test_session_drift_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test session_drift geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("session_drift", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "session_drift"


def test_hermeneutic_instability_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test hermeneutic_instability geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("hermeneutic_instability", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "hermeneutic_instability"


def test_temporal_clustering_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test temporal_clustering geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("temporal_clustering", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "temporal_clustering"


def test_anachronism_detector_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test anachronism_detector geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("anachronism_detector", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "anachronism_detector"


def test_seasonal_patterns_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test seasonal_patterns geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("seasonal_patterns", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "seasonal_patterns"


def test_concept_drift_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test concept_drift geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("concept_drift", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "concept_drift"


def test_convergent_evolution_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test convergent_evolution geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("convergent_evolution", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "convergent_evolution"


def test_divergent_evolution_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test divergent_evolution geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("divergent_evolution", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "divergent_evolution"


def test_island_hopper_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test island_hopper geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("island_hopper", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "island_hopper"


def test_hidden_hub_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test hidden_hub geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("hidden_hub", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "hidden_hub"


def test_bridge_hunter_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test bridge_hunter geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("bridge_hunter", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "bridge_hunter"


def test_density_inversion_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test density_inversion geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("density_inversion", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "density_inversion"


def test_vocabulary_expansion_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test vocabulary_expansion geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("vocabulary_expansion", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "vocabulary_expansion"


def test_assumption_challenger_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test assumption_challenger geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("assumption_challenger", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "assumption_challenger"


def test_pattern_finder_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test pattern_finder geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("pattern_finder", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "pattern_finder"


def test_scale_shifter_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test scale_shifter geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("scale_shifter", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "scale_shifter"


def test_method_scrambler_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test method_scrambler geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("method_scrambler", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "method_scrambler"


def test_antithesis_generator_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test antithesis_generator geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("antithesis_generator", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "antithesis_generator"


# ============================================================================
# Tracery Geists Tests (8 geists)
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
    assert geist.count == 2  # count: 2 in YAML (samples from old/recent pools for variety)

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


def test_semantic_neighbours_tracery_geist(vault_context: VaultContext):
    """Test semantic_neighbours Tracery geist."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "examples"
        / "geists"
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
        # Should reference seed note and neighbor notes
        assert "[[" in suggestion.text


# ============================================================================
# Cross-geist Tests
# ============================================================================


def test_all_geists_are_loadable(geist_executor: GeistExecutor):
    """Test that all example code geists can be loaded without errors."""
    geist_executor.load_geists()

    # We have 29 code geists in examples/geists/code/
    # 10 original + 19 new ambitious geists
    assert len(geist_executor.geists) == 29


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
