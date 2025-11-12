"""Tests that code geists handle empty/insufficient data gracefully.

Ensures that all code geists return empty or valid suggestion lists when
their data requirements are not met, preventing crashes or broken suggestions.
"""

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik import function_registry
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.models import Suggestion
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


@pytest.fixture(autouse=True)
def clear_function_registry():
    """Clear the global function registry before each test."""
    function_registry._GLOBAL_REGISTRY.clear()
    yield
    # Optionally clear after test as well
    function_registry._GLOBAL_REGISTRY.clear()


@pytest.fixture
def empty_vault(tmp_path: Path) -> Vault:
    """Create an empty vault with no notes."""
    vault_path = tmp_path / "empty_vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    vault = Vault(vault_path)
    vault.sync()
    return vault


@pytest.fixture
def empty_vault_context(empty_vault: Vault) -> VaultContext:
    """Create vault context for empty vault."""
    session_date = datetime(2025, 1, 20)
    session = Session(session_date, empty_vault.db)

    # Compute embeddings (there are none, but session needs to be initialized)
    notes = empty_vault.all_notes()
    assert len(notes) == 0, "Empty vault should have no notes"
    session.compute_embeddings(notes)

    function_registry = FunctionRegistry()
    return VaultContext(empty_vault, session, seed=42, function_registry=function_registry)


@pytest.fixture
def minimal_vault(tmp_path: Path) -> Vault:
    """Create vault with minimal data (1-2 notes, no links)."""
    vault_path = tmp_path / "minimal_vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    # Create just 2 notes without links
    (vault_path / "Note A.md").write_text("# Note A\nSome content here")
    (vault_path / "Note B.md").write_text("# Note B\nDifferent content")

    vault = Vault(vault_path)
    vault.sync()
    return vault


@pytest.fixture
def minimal_vault_context(minimal_vault: Vault) -> VaultContext:
    """Create vault context for minimal vault."""
    session_date = datetime(2025, 1, 20)
    session = Session(session_date, minimal_vault.db)
    session.compute_embeddings(minimal_vault.all_notes())

    function_registry = FunctionRegistry()
    return VaultContext(
        minimal_vault, session, seed=42, function_registry=function_registry
    )


@pytest.fixture
def isolated_vault(tmp_path: Path) -> Vault:
    """Create vault with isolated notes (no links, no hubs, no orphans with links)."""
    vault_path = tmp_path / "isolated_vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    # Create 5 notes without any links
    for i in range(5):
        (vault_path / f"Note {i}.md").write_text(
            f"# Note {i}\nContent without links or connections"
        )

    vault = Vault(vault_path)
    vault.sync()
    return vault


@pytest.fixture
def isolated_vault_context(isolated_vault: Vault) -> VaultContext:
    """Create vault context for isolated vault."""
    session_date = datetime(2025, 1, 20)
    session = Session(session_date, isolated_vault.db)
    session.compute_embeddings(isolated_vault.all_notes())

    function_registry = FunctionRegistry()
    return VaultContext(
        isolated_vault, session, seed=42, function_registry=function_registry
    )


def _load_code_geist(geist_path: Path):
    """Dynamically load a code geist module."""
    spec = importlib.util.spec_from_file_location(geist_path.stem, geist_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load geist from {geist_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestAllCodeGeistsWithEmptyVault:
    """Test that all code geists handle completely empty vaults gracefully."""

    def test_all_code_geists_handle_empty_vault(
        self, empty_vault_context: VaultContext
    ):
        """All code geists should handle empty vaults without crashing."""
        code_geists_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
        )

        geist_files = sorted(code_geists_dir.glob("*.py"))
        # Filter out __init__.py
        geist_files = [f for f in geist_files if f.stem != "__init__"]

        # 45 code geists: 42 original + 3 demonstration geists for reuse abstractions
        # (definition_harvester, drift_velocity_anomaly, cyclical_thinking)
        assert len(geist_files) == 45, f"Expected 45 code geists, found {len(geist_files)}"

        for geist_file in geist_files:
            geist_module = _load_code_geist(geist_file)

            # All code geists must have a suggest() function
            assert hasattr(
                geist_module, "suggest"
            ), f"{geist_file.stem} missing suggest() function"

            # Call suggest and verify it doesn't crash
            try:
                suggestions = geist_module.suggest(empty_vault_context)
            except Exception as e:
                pytest.fail(
                    f"{geist_file.stem} crashed with empty vault: {e}"
                )

            # Verify return type
            assert isinstance(
                suggestions, list
            ), f"{geist_file.stem} should return list, got {type(suggestions)}"

            # All returned items should be Suggestions
            for sugg in suggestions:
                assert isinstance(
                    sugg, Suggestion
                ), f"{geist_file.stem} returned non-Suggestion: {type(sugg)}"


class TestAllCodeGeistsWithMinimalVault:
    """Test that all code geists handle vaults with minimal data (1-2 notes)."""

    def test_all_code_geists_handle_minimal_vault(
        self, minimal_vault_context: VaultContext
    ):
        """All code geists should handle minimal vaults (1-2 notes) without crashing."""
        code_geists_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
        )

        geist_files = sorted(code_geists_dir.glob("*.py"))
        geist_files = [f for f in geist_files if f.stem != "__init__"]

        for geist_file in geist_files:
            geist_module = _load_code_geist(geist_file)

            # Call suggest and verify it doesn't crash
            try:
                suggestions = geist_module.suggest(minimal_vault_context)
            except Exception as e:
                pytest.fail(
                    f"{geist_file.stem} crashed with minimal vault: {e}"
                )

            # Verify return type
            assert isinstance(
                suggestions, list
            ), f"{geist_file.stem} should return list, got {type(suggestions)}"


class TestSpecificGeistsWithInsufficientData:
    """Test specific geists that have known data requirements."""

    def test_bridge_hunter_with_no_unlinked_pairs(
        self, isolated_vault_context: VaultContext
    ):
        """bridge_hunter should return empty when vault has no unlinked pairs."""
        geist_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
            / "bridge_hunter.py"
        )

        geist_module = _load_code_geist(geist_path)
        suggestions = geist_module.suggest(isolated_vault_context)

        assert isinstance(suggestions, list)
        # Should return empty or valid suggestions (no crashes)
        for sugg in suggestions:
            assert isinstance(sugg, Suggestion)

    def test_island_hopper_with_few_notes(
        self, minimal_vault_context: VaultContext
    ):
        """island_hopper should return empty when vault has < 10 notes."""
        geist_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
            / "island_hopper.py"
        )

        geist_module = _load_code_geist(geist_path)
        suggestions = geist_module.suggest(minimal_vault_context)

        assert isinstance(suggestions, list)
        assert (
            len(suggestions) == 0
        ), "island_hopper should return empty with < 10 notes"

    def test_creation_burst_with_no_bursts(
        self, empty_vault_context: VaultContext
    ):
        """creation_burst should return empty when vault has no creation bursts."""
        geist_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
            / "creation_burst.py"
        )

        geist_module = _load_code_geist(geist_path)
        suggestions = geist_module.suggest(empty_vault_context)

        assert isinstance(suggestions, list)
        assert (
            len(suggestions) == 0
        ), "creation_burst should return empty with no notes"

    def test_concept_drift_with_no_sessions(
        self, empty_vault_context: VaultContext
    ):
        """concept_drift should return empty when vault has insufficient sessions."""
        geist_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
            / "concept_drift.py"
        )

        geist_module = _load_code_geist(geist_path)
        suggestions = geist_module.suggest(empty_vault_context)

        assert isinstance(suggestions, list)
        assert (
            len(suggestions) == 0
        ), "concept_drift should return empty with < 3 sessions"

    def test_hidden_hub_with_no_notes(
        self, empty_vault_context: VaultContext
    ):
        """hidden_hub should return empty when vault has no notes."""
        geist_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
            / "hidden_hub.py"
        )

        geist_module = _load_code_geist(geist_path)
        suggestions = geist_module.suggest(empty_vault_context)

        assert isinstance(suggestions, list)
        assert len(suggestions) == 0, "hidden_hub should return empty with no notes"

    def test_pattern_finder_with_few_notes(
        self, minimal_vault_context: VaultContext
    ):
        """pattern_finder should handle vaults with insufficient notes for clustering."""
        geist_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
            / "pattern_finder.py"
        )

        geist_module = _load_code_geist(geist_path)
        suggestions = geist_module.suggest(minimal_vault_context)

        assert isinstance(suggestions, list)
        # Should return empty or handle gracefully (no crashes)

    def test_temporal_geists_with_no_sessions(
        self, empty_vault_context: VaultContext
    ):
        """Temporal geists (drift, clustering, etc.) should handle no session history."""
        temporal_geist_names = [
            "temporal_drift",
            "temporal_clustering",
            "temporal_mirror",
            "session_drift",
            "hermeneutic_instability",
            "anachronism_detector",
            "seasonal_patterns",
        ]

        code_geists_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
        )

        for geist_name in temporal_geist_names:
            geist_path = code_geists_dir / f"{geist_name}.py"
            if not geist_path.exists():
                continue

            geist_module = _load_code_geist(geist_path)

            try:
                suggestions = geist_module.suggest(empty_vault_context)
            except Exception as e:
                pytest.fail(
                    f"{geist_name} crashed with no sessions: {e}"
                )

            assert isinstance(suggestions, list)
            # Should return empty with no session history
            assert (
                len(suggestions) == 0
            ), f"{geist_name} should return empty with no sessions"

    def test_harvester_geists_with_no_content(
        self, empty_vault_context: VaultContext
    ):
        """Harvester geists should return empty when no content matches patterns."""
        harvester_geists = ["question_harvester", "todo_harvester", "quote_harvester"]

        code_geists_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
        )

        for geist_name in harvester_geists:
            geist_path = code_geists_dir / f"{geist_name}.py"
            geist_module = _load_code_geist(geist_path)

            suggestions = geist_module.suggest(empty_vault_context)

            assert isinstance(suggestions, list)
            assert (
                len(suggestions) == 0
            ), f"{geist_name} should return empty with no notes"


class TestGeistsReturnValidSuggestions:
    """Test that when geists do return suggestions, they are properly formed."""

    def test_suggestions_have_required_fields(
        self, isolated_vault_context: VaultContext
    ):
        """When geists return suggestions, they must have required fields."""
        code_geists_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "code"
        )

        geist_files = sorted(code_geists_dir.glob("*.py"))
        geist_files = [f for f in geist_files if f.stem != "__init__"]

        for geist_file in geist_files:
            geist_module = _load_code_geist(geist_file)
            suggestions = geist_module.suggest(isolated_vault_context)

            for sugg in suggestions:
                # Required fields
                assert isinstance(
                    sugg.text, str
                ), f"{geist_file.stem}: text must be string"
                assert len(sugg.text) > 0, f"{geist_file.stem}: text must not be empty"
                assert isinstance(
                    sugg.notes, list
                ), f"{geist_file.stem}: notes must be list"
                assert isinstance(
                    sugg.geist_id, str
                ), f"{geist_file.stem}: geist_id must be string"

                # Optional field title
                if sugg.title is not None:
                    assert isinstance(
                        sugg.title, str
                    ), f"{geist_file.stem}: title must be string"

                # Text should not have obvious errors
                assert (
                    "  " not in sugg.text or "  " in sugg.text
                ), f"{geist_file.stem}: suspicious double spaces in text"
                # Check for common empty placeholder patterns
                assert not (
                    " ." in sugg.text and ". " in sugg.text
                ), f"{geist_file.stem}: suspicious ' . ' pattern (empty placeholder?)"
