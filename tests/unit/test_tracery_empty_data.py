"""Tests that Tracery geists handle empty data gracefully.

Ensures that all Tracery geists return empty suggestion lists when
their required vault functions return no results, preventing suggestions
with empty placeholders.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists import DEFAULT_TRACERY_GEISTS
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.tracery import TraceryGeist
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext

TRACERY_DIR = (
    Path(__file__).parent.parent.parent / "src" / "geistfabrik" / "default_geists" / "tracery"
)


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
def isolated_vault(tmp_path: Path) -> Vault:
    """Create vault with isolated notes (no links, no hubs, no orphans with links)."""
    vault_path = tmp_path / "isolated_vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    # Create notes without any links
    (vault_path / "Note A.md").write_text("# Note A\nContent without links")
    (vault_path / "Note B.md").write_text("# Note B\nContent without links")
    (vault_path / "Note C.md").write_text("# Note C\nContent without links")

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
    return VaultContext(isolated_vault, session, seed=42, function_registry=function_registry)


class TestHubExplorerEmptyData:
    """Test hub_explorer geist with no hub notes."""

    def test_hub_explorer_returns_empty_with_no_hubs(self, isolated_vault_context: VaultContext):
        """hub_explorer should return empty list when vault has no hubs."""
        geist_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "tracery"
            / "hub_explorer.yaml"
        )

        geist = TraceryGeist.from_yaml(geist_path, seed=12345)
        suggestions = geist.suggest(isolated_vault_context)

        # Should return empty list, not suggestions with empty placeholders
        assert isinstance(suggestions, list)
        assert len(suggestions) == 0, (
            "hub_explorer should return no suggestions when there are no hubs"
        )


class TestOrphanConnectorEmptyData:
    """Test orphan_connector geist with no orphans."""

    def test_orphan_connector_returns_empty_with_no_orphans(self, tmp_path: Path):
        """orphan_connector should return empty when all notes are linked."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        (vault_path / ".obsidian").mkdir()

        # Create fully connected notes (no orphans)
        (vault_path / "Note A.md").write_text("# Note A\nLinks to [[Note B]]")
        (vault_path / "Note B.md").write_text("# Note B\nLinks to [[Note A]]")

        vault = Vault(vault_path)
        vault.sync()

        session = Session(datetime(2025, 1, 20), vault.db)
        session.compute_embeddings(vault.all_notes())

        context = VaultContext(vault, session, seed=42, function_registry=FunctionRegistry())

        geist_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "tracery"
            / "orphan_connector.yaml"
        )

        geist = TraceryGeist.from_yaml(geist_path, seed=12345)
        suggestions = geist.suggest(context)

        assert isinstance(suggestions, list)
        assert len(suggestions) == 0, (
            "orphan_connector should return no suggestions when there are no orphans"
        )


class TestSemanticNeighboursEmptyData:
    """Test semantic_neighbours geist with insufficient notes."""

    def test_semantic_neighbours_returns_empty_with_one_note(self, tmp_path: Path):
        """semantic_neighbours should return empty when only one note exists."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        (vault_path / ".obsidian").mkdir()

        # Single note - can't have neighbours
        (vault_path / "Only Note.md").write_text("# Only Note\nSolitary content")

        vault = Vault(vault_path)
        vault.sync()

        session = Session(datetime(2025, 1, 20), vault.db)
        session.compute_embeddings(vault.all_notes())

        context = VaultContext(vault, session, seed=42, function_registry=FunctionRegistry())

        geist_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "geistfabrik"
            / "default_geists"
            / "tracery"
            / "semantic_neighbours.yaml"
        )

        geist = TraceryGeist.from_yaml(geist_path, seed=12345)
        suggestions = geist.suggest(context)

        # A lone note has no neighbours, so there is no cluster to describe.
        assert suggestions == []


class TestAllTraceryGeistsWithEmptyVault:
    """Test that all Tracery geists handle empty vaults gracefully."""

    def test_all_tracery_geists_return_empty_with_empty_vault(
        self, empty_vault_context: VaultContext
    ):
        """A geist that draws on the vault has nothing to say about an empty one.

        Geists whose grammar calls a $vault function must return []; a
        vault-free geist (static prompts) may still speak, but never with an
        empty placeholder where a note should be.
        """
        assert DEFAULT_TRACERY_GEISTS, "no bundled Tracery geists discovered"
        speaking: dict[str, list[str]] = {}

        for geist_id in DEFAULT_TRACERY_GEISTS:
            geist_file = TRACERY_DIR / f"{geist_id}.yaml"
            geist = TraceryGeist.from_yaml(geist_file, seed=12345)
            suggestions = geist.suggest(empty_vault_context)
            uses_vault = "$vault." in geist_file.read_text()

            if uses_vault and suggestions:
                speaking[geist_id] = [s.text for s in suggestions]
            for suggestion in suggestions:
                assert suggestion.text == suggestion.text.strip(), (
                    f"{geist_id} has an empty placeholder: {suggestion.text!r}"
                )
                assert "  " not in suggestion.text and " ." not in suggestion.text, (
                    f"{geist_id} has an empty placeholder: {suggestion.text!r}"
                )

        assert speaking == {}, f"vault-backed geists spoke about an empty vault: {speaking}"


class TestTraceryEmptyPlaceholderDetection:
    """Test the _has_empty_placeholder method."""

    def test_detects_double_spaces(self):
        """Should detect double spaces."""
        from geistfabrik.tracery import TraceryGeist

        geist = TraceryGeist("test", {}, count=1, seed=42)

        assert geist._has_empty_placeholder("word  word") is True
        assert geist._has_empty_placeholder("normal text") is False

    def test_detects_space_before_punctuation(self):
        """Should detect space before punctuation."""
        from geistfabrik.tracery import TraceryGeist

        geist = TraceryGeist("test", {}, count=1, seed=42)

        assert geist._has_empty_placeholder("word . word") is True
        assert geist._has_empty_placeholder("word, word") is False
        assert geist._has_empty_placeholder("word . Word") is True

    def test_detects_missing_content_pattern(self):
        """Should detect pattern like 'through . Is'."""
        from geistfabrik.tracery import TraceryGeist

        geist = TraceryGeist("test", {}, count=1, seed=42)

        # The actual failing text from hub_explorer
        assert (
            geist._has_empty_placeholder(
                "Many connections lead through . Is it still clearly defined?"
            )
            is True
        )

        # Valid text should pass
        assert (
            geist._has_empty_placeholder("[[Note]] connects many ideas—what's the common thread?")
            is False
        )
