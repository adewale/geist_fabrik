"""Integration tests for all bundled default geists.

These tests verify that all geists in src/geistfabrik/default_geists/ work correctly
with a real vault. Uses stubs (kepano-obsidian-main test vault), not mocks.

Tests cover:
- All 42 code geists in src/geistfabrik/default_geists/code/
- All 9 Tracery geists in src/geistfabrik/default_geists/tracery/

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
    repo_root = Path(__file__).parent.parent.parent
    code_geists_dir = repo_root / "src" / "geistfabrik" / "default_geists" / "code"
    executor = GeistExecutor(code_geists_dir, timeout=5)
    executor.load_geists()
    return executor


# ============================================================================
# Code Geists Tests (35 geists)
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


def test_temporal_mirror_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test temporal_mirror geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("temporal_mirror", vault_context)

    assert isinstance(suggestions, list)
    # Should return 1 suggestion or empty if insufficient notes
    assert len(suggestions) <= 1
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "temporal_mirror"
        # Should reference exactly 2 notes (one from each period)
        assert len(suggestion.notes) == 2
        # Should mention period numbers
        assert "period" in suggestion.text.lower()


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


def test_creation_burst_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test creation_burst geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("creation_burst", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "creation_burst"


def test_burst_evolution_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test burst_evolution geist returns valid suggestions."""
    geist_executor.load_geists()
    suggestions = geist_executor.execute_geist("burst_evolution", vault_context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "burst_evolution"


# ============================================================================
# Tracery Geists Tests (10 geists)
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
        wikilinks = re.findall(r'\[\[([^\]]+)\]\]', suggestion.text)

        # Should have at least 2 wikilinks (seed + neighbours)
        assert len(wikilinks) >= 2, (
            f"Expected >= 2 wikilinks (seed + neighbours), got {len(wikilinks)} "
            f"in: {suggestion.text}"
        )

        # All wikilinks should be properly formatted (no orphaned note references)
        assert suggestion.text.count("[[") == suggestion.text.count("]]"), \
            f"Mismatched brackets in: {suggestion.text}"

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

    # We have 45 code geists (42 existing + 3 new demonstration geists)
    # New geists from reuse abstractions implementation:
    #   - definition_harvester (content extraction)
    #   - drift_velocity_anomaly (temporal analysis)
    #   - cyclical_thinking (temporal patterns)
    # Note: congruence_mirror was removed from main
    assert len(geist_executor.geists) == 45


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
# Harvester Family Tests (3 geists)
# ============================================================================


def test_question_harvester_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test question_harvester geist extracts questions from random notes."""
    suggestions = geist_executor.execute_geist("question_harvester", vault_context)

    assert isinstance(suggestions, list)
    # May return 0-3 suggestions depending on whether random note has questions
    assert 0 <= len(suggestions) <= 3

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "question_harvester"
        # Should have "From [[...]]:" prefix
        assert "From [[" in suggestion.text
        # Should have temporal framing
        assert "What if you revisited this question now?" in suggestion.text
        # Should reference exactly 1 note
        assert len(suggestion.notes) == 1


def test_question_harvester_deterministic(
    vault_context: VaultContext, geist_executor: GeistExecutor
):
    """Test question_harvester is deterministic (same seed = same results)."""
    # Run twice with same vault context (same seed)
    suggestions_1 = geist_executor.execute_geist("question_harvester", vault_context)
    suggestions_2 = geist_executor.execute_geist("question_harvester", vault_context)

    # Should return identical results
    assert len(suggestions_1) == len(suggestions_2)
    for s1, s2 in zip(suggestions_1, suggestions_2):
        assert s1.text == s2.text
        assert s1.notes == s2.notes


def test_todo_harvester_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test todo_harvester geist extracts TODO markers from random notes."""
    suggestions = geist_executor.execute_geist("todo_harvester", vault_context)

    assert isinstance(suggestions, list)
    # May return 0-3 suggestions depending on whether random note has TODOs
    assert 0 <= len(suggestions) <= 3

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "todo_harvester"
        # Should have "From [[...]]:" prefix
        assert "From [[" in suggestion.text
        # Should have temporal framing
        assert "What if you tackled this now?" in suggestion.text
        # Should reference exactly 1 note
        assert len(suggestion.notes) == 1


def test_todo_harvester_deterministic(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test todo_harvester is deterministic (same seed = same results)."""
    # Run twice with same vault context (same seed)
    suggestions_1 = geist_executor.execute_geist("todo_harvester", vault_context)
    suggestions_2 = geist_executor.execute_geist("todo_harvester", vault_context)

    # Should return identical results
    assert len(suggestions_1) == len(suggestions_2)
    for s1, s2 in zip(suggestions_1, suggestions_2):
        assert s1.text == s2.text
        assert s1.notes == s2.notes


def test_quote_harvester_geist(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test quote_harvester geist extracts blockquotes from random notes."""
    suggestions = geist_executor.execute_geist("quote_harvester", vault_context)

    assert isinstance(suggestions, list)
    # May return 0-3 suggestions depending on whether random note has quotes
    assert 0 <= len(suggestions) <= 3

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "quote_harvester"
        # Should have "From [[...]]:" prefix
        assert "From [[" in suggestion.text
        # Should have temporal framing
        assert "What if you reflected on this again?" in suggestion.text
        # Should reference exactly 1 note
        assert len(suggestion.notes) == 1


def test_quote_harvester_deterministic(vault_context: VaultContext, geist_executor: GeistExecutor):
    """Test quote_harvester is deterministic (same seed = same results)."""
    # Run twice with same vault context (same seed)
    suggestions_1 = geist_executor.execute_geist("quote_harvester", vault_context)
    suggestions_2 = geist_executor.execute_geist("quote_harvester", vault_context)

    # Should return identical results
    assert len(suggestions_1) == len(suggestions_2)
    for s1, s2 in zip(suggestions_1, suggestions_2):
        assert s1.text == s2.text
        assert s1.notes == s2.notes
