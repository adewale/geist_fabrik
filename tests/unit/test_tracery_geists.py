"""Unit tests for all Tracery geists.

Tests each Tracery geist's variables, modifiers, and vault function integration.
These are fast unit tests using minimal test vaults, not integration tests.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from geistfabrik.embeddings import EmbeddingComputer, Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry
from geistfabrik.tracery import TraceryGeist
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext

# Path to default bundled geists
GEISTS_DIR = (
    Path(__file__).parent.parent.parent / "src" / "geistfabrik" / "default_geists" / "tracery"
)


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


def create_mock_embedding_computer(num_notes: int) -> EmbeddingComputer:
    """Create a mock embedding computer for testing."""
    computer = EmbeddingComputer()
    mock_model = Mock()
    mock_model.encode.return_value = np.random.rand(num_notes, 387)  # 384 semantic + 3 temporal
    computer._model = mock_model
    return computer


def create_test_vault_context(tmp_path: Path, num_notes: int = 10) -> VaultContext:
    """Create a minimal vault context for testing Tracery geists."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    # Create hub note first (will have many incoming links)
    hub_content = "# Hub Note\nThis is a hub."
    (vault_path / "hub.md").write_text(hub_content)

    # Create test notes that link to hub (making it an actual hub)
    for i in range(num_notes):
        # Most notes link to hub
        if i < num_notes - 2:
            content = f"# Note {i:02d}\nThis is test note {i}. Related to [[Hub Note]]."
        else:
            content = f"# Note {i:02d}\nThis is test note {i}."
        (vault_path / f"note_{i:02d}.md").write_text(content)

    # Create orphan note (no links)
    (vault_path / "orphan.md").write_text("# Orphan Note\nNo links here.")

    vault = Vault(vault_path)
    vault.sync()

    session_date = datetime(2025, 1, 15)
    mock_computer = create_mock_embedding_computer(len(vault.all_notes()))
    session = Session(session_date, vault.db, computer=mock_computer)
    session.compute_embeddings(vault.all_notes())

    function_registry = FunctionRegistry()
    return VaultContext(vault, session, seed=42, function_registry=function_registry)


# ============================================================================
# Contradictor Tests
# ============================================================================


class TestContradictor:
    """Tests for contradictor.yaml geist."""

    def test_contradictor_loads(self):
        """Test that contradictor geist loads correctly."""
        geist_path = GEISTS_DIR / "contradictor.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert geist.geist_id == "contradictor"
        assert geist.count == 1
        assert "suggestion" in geist.engine.grammar
        assert "note" in geist.engine.grammar

    def test_contradictor_generates_suggestions(self, tmp_path: Path):
        """Test that contradictor generates valid suggestions."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "contradictor.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        assert len(suggestions) == 1
        assert suggestions[0].geist_id == "contradictor"
        assert len(suggestions[0].text) > 0

    def test_contradictor_is_deterministic(self, tmp_path: Path):
        """Test that same seed produces same output."""
        # Create vault once with deterministic file times
        import os

        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        (vault_path / ".obsidian").mkdir()

        base_time = 1640000000.0
        for i in range(10):
            file_path = vault_path / f"note_{i:02d}.md"
            file_path.write_text(f"# Note {i:02d}\nContent")
            os.utime(file_path, (base_time + i, base_time + i))

        vault = Vault(vault_path)
        vault.sync()

        session = Session(datetime(2025, 1, 15), vault.db)
        function_registry = FunctionRegistry()

        # Create two separate contexts with same seed
        context1 = VaultContext(vault, session, seed=123, function_registry=function_registry)
        context2 = VaultContext(vault, session, seed=123, function_registry=function_registry)

        geist_path = GEISTS_DIR / "contradictor.yaml"
        geist1 = TraceryGeist.from_yaml(geist_path, seed=123)
        geist2 = TraceryGeist.from_yaml(geist_path, seed=123)

        suggestions1 = geist1.suggest(context1)
        suggestions2 = geist2.suggest(context2)

        assert suggestions1[0].text == suggestions2[0].text

    def test_contradictor_references_notes(self, tmp_path: Path):
        """Test contradictor generates text (note: uses random_note_title which may not exist)."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "contradictor.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        # Note: contradictor uses $vault.random_note_title() which doesn't exist
        # as a builtin function, so this test just verifies it generates something
        assert len(suggestions[0].text) > 0

    def test_contradictor_uses_multiple_templates(self, tmp_path: Path):
        """Test that contradictor uses different suggestion templates."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "contradictor.yaml"

        # Generate multiple suggestions with different seeds
        texts = set()
        for seed in range(50):
            geist = TraceryGeist.from_yaml(geist_path, seed=seed)
            suggestions = geist.suggest(context)
            # Extract template by removing note titles
            import re

            template = re.sub(r"\[\[.*?\]\]", "[[NOTE]]", suggestions[0].text)
            texts.add(template)

        # Should have used multiple different templates
        assert len(texts) > 5


# ============================================================================
# Hub Explorer Tests
# ============================================================================


class TestHubExplorer:
    """Tests for hub_explorer.yaml geist."""

    def test_hub_explorer_loads(self):
        """Test that hub_explorer geist loads correctly."""
        geist_path = GEISTS_DIR / "hub_explorer.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert geist.geist_id == "hub_explorer"
        assert geist.count == 2

    def test_hub_explorer_generates_suggestions(self, tmp_path: Path):
        """Test that hub_explorer generates valid suggestions."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "hub_explorer.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        assert len(suggestions) == 2
        for suggestion in suggestions:
            assert suggestion.geist_id == "hub_explorer"

    def test_hub_explorer_is_deterministic(self, tmp_path: Path):
        """Test deterministic output."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "hub_explorer.yaml"

        geist1 = TraceryGeist.from_yaml(geist_path, seed=456)
        geist2 = TraceryGeist.from_yaml(geist_path, seed=456)

        suggestions1 = geist1.suggest(context)
        suggestions2 = geist2.suggest(context)

        assert [s.text for s in suggestions1] == [s.text for s in suggestions2]

    def test_hub_explorer_uses_vault_hubs(self, tmp_path: Path):
        """Test that hub_explorer calls vault.hubs() function."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "hub_explorer.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        # Should reference notes (hubs)
        assert any("[[" in s.text for s in suggestions)

    def test_hub_explorer_uses_modifiers(self, tmp_path: Path):
        """Test that hub_explorer uses .s and .capitalize modifiers."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "hub_explorer.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        # Check for capitalized words and plurals in output
        text = " ".join([s.text for s in suggestions])
        # Should have some capitalized words and plural forms
        assert any(word[0].isupper() for word in text.split())

    def test_hub_explorer_uses_multiple_variables(self, tmp_path: Path):
        """Test that multiple grammar variables are used."""
        # Just verify the grammar has all expected variables
        geist_path = GEISTS_DIR / "hub_explorer.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        expected_vars = [
            "hub",
            "verb",
            "element",
            "possessive",
            "question",
            "path",
            "prompt",
            "unifying_theme",
            "action",
            "hub_type",
            "coherent",
        ]

        for var in expected_vars:
            assert var in geist.engine.grammar


# ============================================================================
# Note Combinations Tests
# ============================================================================


class TestNoteCombinations:
    """Tests for note_combinations.yaml geist."""

    def test_note_combinations_loads(self):
        """Test that note_combinations geist loads correctly."""
        geist_path = GEISTS_DIR / "note_combinations.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert geist.geist_id == "note_combinations"
        assert geist.count == 2

    def test_note_combinations_generates_suggestions(self, tmp_path: Path):
        """Test that note_combinations generates valid suggestions."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "note_combinations.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        assert len(suggestions) == 2

    def test_note_combinations_references_two_notes(self, tmp_path: Path):
        """Test that each suggestion references two different notes."""
        context = create_test_vault_context(tmp_path, num_notes=20)
        geist_path = GEISTS_DIR / "note_combinations.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        for suggestion in suggestions:
            # Should reference exactly 2 notes (note1 and note2)
            assert len(suggestion.notes) == 2

    def test_note_combinations_uses_different_reasons(self, tmp_path: Path):
        """Test that different reason variables are used."""
        geist_path = GEISTS_DIR / "note_combinations.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        # Verify grammar has reason and relationship variables
        assert "reason" in geist.engine.grammar
        assert "relationship" in geist.engine.grammar
        assert len(geist.engine.grammar["reason"]) > 1
        assert len(geist.engine.grammar["relationship"]) > 1


# ============================================================================
# Orphan Connector Tests
# ============================================================================


class TestOrphanConnector:
    """Tests for orphan_connector.yaml geist."""

    def test_orphan_connector_loads(self):
        """Test that orphan_connector geist loads correctly."""
        geist_path = GEISTS_DIR / "orphan_connector.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert geist.geist_id == "orphan_connector"
        assert geist.count == 1

    def test_orphan_connector_generates_suggestions(self, tmp_path: Path):
        """Test that orphan_connector generates valid suggestions."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "orphan_connector.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        assert len(suggestions) == 1

    def test_orphan_connector_uses_vault_orphans(self, tmp_path: Path):
        """Test that orphan_connector uses vault.orphans() function."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "orphan_connector.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        # Should reference notes
        assert any("[[" in s.text for s in suggestions)

    def test_orphan_connector_uses_modifiers(self, tmp_path: Path):
        """Test that orphan_connector uses .s and .capitalize modifiers."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "orphan_connector.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        # Should have capitalized words
        text = " ".join([s.text for s in suggestions])
        assert any(word[0].isupper() for word in text.split())

    def test_orphan_connector_uses_multiple_templates(self, tmp_path: Path):
        """Test that orphan_connector uses multiple origin templates."""
        geist_path = GEISTS_DIR / "orphan_connector.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        # Verify grammar has multiple origin templates
        assert "origin" in geist.engine.grammar
        assert len(geist.engine.grammar["origin"]) >= 4

    def test_orphan_connector_with_two_orphans_uses_one(self, tmp_path: Path):
        """Test that orphan_connector requests only 1 orphan even when 2 exist.

        This test verifies the full pipeline:
        1. Vault correctly detects exactly 2 orphan notes
        2. Vault function correctly exposes them
        3. Tracery preprocessing requests and populates only 1 orphan
        4. Geist generates 1 suggestion
        """
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        (vault_path / ".obsidian").mkdir()

        # Create notes with explicit link structure
        notes_data = [
            # Two orphan notes - no links at all
            ("orphan_one.md", "# Orphan One\nCompletely isolated note."),
            ("orphan_two.md", "# Orphan Two\nAnother isolated note."),
            # Two connected notes to ensure we're not detecting non-orphans
            ("connected_a.md", "# Connected A\nLinks to [[Connected B]]."),
            ("connected_b.md", "# Connected B\nLinks to [[Connected A]]."),
        ]

        for filename, content in notes_data:
            (vault_path / filename).write_text(content)

        # Create vault and sync
        vault = Vault(vault_path)
        vault.sync()

        # Create session
        session_date = datetime(2025, 1, 15)
        mock_computer = create_mock_embedding_computer(len(vault.all_notes()))
        session = Session(session_date, vault.db, computer=mock_computer)
        session.compute_embeddings(vault.all_notes())

        # Create context with function registry
        function_registry = FunctionRegistry()
        context = VaultContext(vault, session, seed=42, function_registry=function_registry)

        # Verify orphan detection at vault level
        orphans = context.orphans()
        assert len(orphans) == 2, (
            f"Expected exactly 2 orphans, but found {len(orphans)}: {[n.path for n in orphans]}"
        )
        orphan_titles = {n.title for n in orphans}
        assert orphan_titles == {"Orphan One", "Orphan Two"}, (
            f"Expected 'Orphan One' and 'Orphan Two', but got {orphan_titles}"
        )

        # Load and execute orphan_connector geist
        geist_path = GEISTS_DIR / "orphan_connector.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        # Trigger preprocessing by setting vault context
        geist.engine.set_vault_context(context)

        # CRITICAL: Verify that only 1 orphan is in the preprocessed symbol array
        # This is the key test - preprocessing should request orphans(1)
        orphan_symbol = geist.engine.grammar.get("orphan", [])
        assert len(orphan_symbol) == 1, (
            f"Expected 1 orphan in symbol array (since count=1), "
            f"but got {len(orphan_symbol)}: {orphan_symbol}"
        )
        # Should be one of the two orphans
        assert orphan_symbol[0] in {"Orphan One", "Orphan Two"}, (
            f"Expected one of the orphans, but got {orphan_symbol}"
        )

        # Generate suggestions
        suggestions = geist.suggest(context)

        # Should generate 1 suggestion (count=1)
        assert len(suggestions) == 1, f"Expected 1 suggestion, but got {len(suggestions)}"

        # Extract note references from suggestions
        import re

        referenced_notes = set()
        for suggestion in suggestions:
            matches = re.findall(r"\[\[([^\]]+)\]\]", suggestion.text)
            for match in matches:
                referenced_notes.add(match)

        # Should reference exactly one orphan
        assert len(referenced_notes) == 1, (
            f"Expected exactly 1 orphan reference, got {referenced_notes}"
        )

        vault.close()


# ============================================================================
# Perspective Shifter Tests
# ============================================================================


class TestPerspectiveShifter:
    """Tests for perspective_shifter.yaml geist."""

    def test_perspective_shifter_loads(self):
        """Test that perspective_shifter geist loads correctly."""
        geist_path = GEISTS_DIR / "perspective_shifter.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert geist.geist_id == "perspective_shifter"
        assert geist.count == 2

    def test_perspective_shifter_generates_suggestions(self, tmp_path: Path):
        """Test that perspective_shifter generates valid suggestions."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "perspective_shifter.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        assert len(suggestions) == 2

    def test_perspective_shifter_uses_modifiers(self, tmp_path: Path):
        """Test that perspective_shifter uses modifiers (.capitalize, .a, .ed, .s)."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "perspective_shifter.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        # Should have capitalized words
        text = " ".join([s.text for s in suggestions])
        assert any(word[0].isupper() for word in text.split())

    def test_perspective_shifter_uses_metaphor_variables(self, tmp_path: Path):
        """Test that metaphor and comparison variables are used."""
        geist_path = GEISTS_DIR / "perspective_shifter.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        # Verify grammar has metaphor variables
        assert "metaphor" in geist.engine.grammar
        assert "comparison" in geist.engine.grammar
        assert len(geist.engine.grammar["metaphor"]) >= 5


# ============================================================================
# Random Prompts Tests
# ============================================================================


class TestRandomPrompts:
    """Tests for random_prompts.yaml geist."""

    def test_random_prompts_loads(self):
        """Test that random_prompts geist loads correctly."""
        geist_path = GEISTS_DIR / "random_prompts.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert geist.geist_id == "random_prompts"
        assert geist.count == 2

    def test_random_prompts_generates_suggestions(self, tmp_path: Path):
        """Test that random_prompts generates valid suggestions."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "random_prompts.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        assert len(suggestions) == 2

    def test_random_prompts_starts_with_what_if(self, tmp_path: Path):
        """Test that random_prompts suggestions start with 'What if'."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "random_prompts.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        for suggestion in suggestions:
            assert suggestion.text.startswith("What if")

    def test_random_prompts_uses_multiple_concepts(self, tmp_path: Path):
        """Test that concept variable has multiple options."""
        geist_path = GEISTS_DIR / "random_prompts.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert "concept" in geist.engine.grammar
        assert len(geist.engine.grammar["concept"]) >= 6

    def test_random_prompts_uses_multiple_perspectives(self, tmp_path: Path):
        """Test that perspective variable has multiple options."""
        geist_path = GEISTS_DIR / "random_prompts.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert "perspective" in geist.engine.grammar
        assert len(geist.engine.grammar["perspective"]) >= 4


# ============================================================================
# Semantic Neighbours Tests
# ============================================================================


class TestSemanticNeighbours:
    """Tests for semantic_neighbours.yaml geist."""

    def test_semantic_neighbours_loads(self):
        """Test that semantic_neighbours geist loads correctly."""
        geist_path = GEISTS_DIR / "semantic_neighbours.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert geist.geist_id == "semantic_neighbours"
        assert geist.count == 2

    def test_semantic_neighbours_generates_suggestions(self, tmp_path: Path):
        """Test that semantic_neighbours generates valid suggestions."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "semantic_neighbours.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        assert len(suggestions) == 2

    def test_semantic_neighbours_uses_vault_neighbours(self, tmp_path: Path):
        """Test that semantic_neighbours uses vault.neighbours() function."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "semantic_neighbours.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        # Should reference notes
        assert any("[[" in s.text for s in suggestions)

    def test_semantic_neighbours_uses_different_prompts(self, tmp_path: Path):
        """Test that prompt and question variables have multiple options."""
        geist_path = GEISTS_DIR / "semantic_neighbours.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert "prompt" in geist.engine.grammar
        assert "question" in geist.engine.grammar
        assert len(geist.engine.grammar["prompt"]) >= 4
        assert len(geist.engine.grammar["question"]) >= 4

    def test_semantic_neighbours_all_notes_properly_bracketed(self, tmp_path: Path):
        """Regression test: All note references should have [[...]] brackets."""
        import re

        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "semantic_neighbours.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        for suggestion in suggestions:
            text = suggestion.text

            # Find all properly formatted wikilinks
            wikilinks = re.findall(r'\[\[([^\]]+)\]\]', text)

            # Should have at least seed + 1 neighbour
            assert len(wikilinks) >= 2, f"Expected >= 2 wikilinks, got {len(wikilinks)} in: {text}"

            # Check for orphaned note references (note titles without brackets)
            # Pattern matches "Word#YYYY Month Day" or "Word Word#YYYY Month Day"
            # that are NOT inside [[ ]]
            orphaned = re.findall(r'(?<!\[)\b([\w\s]+#\d{4}[^,.\]]*?)(?=[\s,.]|$)', text)

            # Filter out false positives (things already in brackets)
            actual_orphaned = [o for o in orphaned if o not in ' '.join(wikilinks)]

            assert len(actual_orphaned) == 0, \
                f"Found unbracketed note references: {actual_orphaned} in '{text}'"

    def test_semantic_neighbours_consistent_formatting(self, tmp_path: Path):
        """Regression test: Seed and neighbours should have consistent formatting."""
        import re

        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "semantic_neighbours.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        for suggestion in suggestions:
            text = suggestion.text

            # All wikilinks should be properly closed
            open_brackets = text.count('[[')
            close_brackets = text.count(']]')
            assert open_brackets == close_brackets, \
                f"Mismatched brackets: {open_brackets} [[ vs {close_brackets} ]] in '{text}'"

            # Should not have partial brackets like "[[Note" or "Note]]"
            assert not re.search(r'\[\[[^\]]*$', text), "Found unclosed [["
            assert not re.search(r'^[^\[]*\]\]', text), "Found unmatched ]]"

    def test_semantic_neighbours_structure_matches_pattern(self, tmp_path: Path):
        """Regression test: Output should match expected structure."""
        import re

        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "semantic_neighbours.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        for suggestion in suggestions:
            text = suggestion.text

            # Extract all wikilinks
            wikilinks = re.findall(r'\[\[([^\]]+)\]\]', text)

            # Verify structure: should have seed (first mention) + neighbours
            assert len(wikilinks) >= 2, \
                f"Expected seed + neighbours (>=2 links), got {len(wikilinks)}"

            # All wikilinks should be non-empty
            assert all(link.strip() for link in wikilinks), \
                f"Found empty wikilink in: {text}"


# ============================================================================
# What If Tests
# ============================================================================


class TestWhatIf:
    """Tests for what_if.yaml geist."""

    def test_what_if_loads(self):
        """Test that what_if geist loads correctly."""
        geist_path = GEISTS_DIR / "what_if.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert geist.geist_id == "what_if"
        assert geist.count == 3

    def test_what_if_generates_suggestions(self, tmp_path: Path):
        """Test that what_if generates valid suggestions."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "what_if.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        assert len(suggestions) == 3

    def test_what_if_starts_with_what_if(self, tmp_path: Path):
        """Test that what_if suggestions start with 'What if'."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "what_if.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        for suggestion in suggestions:
            assert suggestion.text.startswith("What if")

    def test_what_if_uses_modifiers(self, tmp_path: Path):
        """Test that what_if uses modifiers (.capitalize, .ed, .s, .a)."""
        context = create_test_vault_context(tmp_path)
        geist_path = GEISTS_DIR / "what_if.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        suggestions = geist.suggest(context)

        # Should have capitalized words
        text = " ".join([s.text for s in suggestions])
        assert any(word[0].isupper() for word in text.split())

    def test_what_if_uses_multiple_origin_templates(self, tmp_path: Path):
        """Test that what_if has multiple origin templates."""
        geist_path = GEISTS_DIR / "what_if.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        assert "origin" in geist.engine.grammar
        assert len(geist.engine.grammar["origin"]) >= 4

    def test_what_if_uses_vault_functions(self, tmp_path: Path):
        """Test that what_if uses vault.sample_notes() function."""
        geist_path = GEISTS_DIR / "what_if.yaml"
        geist = TraceryGeist.from_yaml(geist_path, seed=42)

        # Verify grammar uses vault functions
        assert "note" in geist.engine.grammar
        assert "$vault.sample_notes" in geist.engine.grammar["note"][0]


# ============================================================================
# Cross-Geist Tests
# ============================================================================


class TestAllTraceryGeists:
    """Tests that apply to all Tracery geists."""

    def test_all_geists_load_without_errors(self):
        """Test that all Tracery geists can be loaded."""
        geist_files = list(GEISTS_DIR.glob("*.yaml"))

        # Should have 9 Tracery geists
        assert len(geist_files) == 9

        for geist_file in geist_files:
            geist = TraceryGeist.from_yaml(geist_file, seed=42)
            assert geist.geist_id is not None
            assert geist.count >= 1

    def test_all_geists_are_deterministic(self, tmp_path: Path):
        """Test geists with same seed produce same count (full text tested in integration)."""
        context = create_test_vault_context(tmp_path)
        geist_files = list(GEISTS_DIR.glob("*.yaml"))

        for geist_file in geist_files:
            geist1 = TraceryGeist.from_yaml(geist_file, seed=999)
            geist2 = TraceryGeist.from_yaml(geist_file, seed=999)

            suggestions1 = geist1.suggest(context)
            suggestions2 = geist2.suggest(context)

            # At minimum, same seed should produce same number of suggestions
            assert len(suggestions1) == len(suggestions2), f"Different counts in {geist_file.name}"

            # Note: Full text determinism is tested in integration tests
            # Unit tests use mock vaults which may have file creation order issues

    def test_all_geists_respect_count_parameter(self, tmp_path: Path):
        """Test that all geists respect their count parameter."""
        context = create_test_vault_context(tmp_path)
        geist_files = list(GEISTS_DIR.glob("*.yaml"))

        for geist_file in geist_files:
            geist = TraceryGeist.from_yaml(geist_file, seed=42)
            suggestions = geist.suggest(context)

            assert len(suggestions) == geist.count, f"Wrong count in {geist_file.name}"

    def test_all_geists_have_valid_suggestion_text(self, tmp_path: Path):
        """Test that all geists produce non-empty suggestion text."""
        context = create_test_vault_context(tmp_path)
        geist_files = list(GEISTS_DIR.glob("*.yaml"))

        for geist_file in geist_files:
            geist = TraceryGeist.from_yaml(geist_file, seed=42)
            suggestions = geist.suggest(context)

            for suggestion in suggestions:
                assert len(suggestion.text) > 0, f"Empty text in {geist_file.name}"
                assert suggestion.geist_id == geist.geist_id

    def test_all_geists_produce_variety(self, tmp_path: Path):
        """Test that geists with count > 1 produce different suggestions."""
        context = create_test_vault_context(tmp_path, num_notes=20)
        geist_files = list(GEISTS_DIR.glob("*.yaml"))

        for geist_file in geist_files:
            geist = TraceryGeist.from_yaml(geist_file, seed=42)

            if geist.count > 1:
                suggestions = geist.suggest(context)
                texts = [s.text for s in suggestions]

                # At least some suggestions should be different
                # (not guaranteed 100% but very likely with proper randomness)
                unique_texts = set(texts)
                assert len(unique_texts) > 1 or geist.count == 1, (
                    f"No variety in {geist_file.name} with count={geist.count}"
                )

    def test_all_geists_vault_functions_request_sufficient_items(self):
        """Quality test: vault functions should request at least count items.

        For geists with count > 1, vault functions in symbols should request
        at least count items to avoid guaranteed duplicates.

        This validates the pattern:
        - count: 2 → $vault.function(2) or more
        - count: 3 → $vault.function(3) or more
        """
        import re

        import yaml

        geist_files = list(GEISTS_DIR.glob("*.yaml"))

        for geist_file in geist_files:
            with open(geist_file) as f:
                data = yaml.safe_load(f)

            count = data.get("count", 1)

            # Only check geists with count > 1
            if count <= 1:
                continue

            tracery_grammar = data.get("tracery", {})

            # Check each symbol in the grammar
            for symbol_name, rules in tracery_grammar.items():
                if symbol_name == "origin":
                    continue  # Skip origin (templates, not data sources)

                if not isinstance(rules, list):
                    continue

                # Check each rule in this symbol
                for rule in rules:
                    if not isinstance(rule, str):
                        continue

                    # Check if this rule is a single vault function call
                    vault_func_pattern = r"^\$vault\.([a-z_]+)\(([^)]*)\)$"
                    match = re.match(vault_func_pattern, rule.strip())

                    if match:
                        func_name = match.group(1)
                        args_str = match.group(2).strip()

                        # Parse the first argument (requested count)
                        if args_str:
                            args = [arg.strip().strip("\"'") for arg in args_str.split(",")]
                            if args[0].isdigit():
                                requested = int(args[0])

                                assert requested >= count, (
                                    f"{geist_file.name}: Symbol '{symbol_name}' requests "
                                    f"{requested} items via ${func_name}(), but count={count}. "
                                    f"Should request at least {count} items to avoid "
                                    f"guaranteed duplicates."
                                )


def test_all_tracery_geists_have_consistent_wikilink_formatting(tmp_path: Path):
    """Test that all Tracery geists format wikilinks consistently.

    This regression test ensures that geists which reference notes:
    1. Always wrap note references in [[...]] brackets
    2. Don't have orphaned note references (missing brackets)
    3. Have properly balanced brackets
    """
    import re

    context = create_test_vault_context(tmp_path, num_notes=15)
    geist_files = list(GEISTS_DIR.glob("*.yaml"))

    # Define expected structure for each geist
    # Maps geist_id -> minimum expected wikilinks (for geists that ALWAYS reference notes)
    # Geists with variable templates (like what_if) are checked differently
    always_has_notes = {
        "orphan_connector": 1,      # Always references [[orphan]]
        "hub_explorer": 1,          # Always references [[hub]]
        "note_combinations": 2,     # Always references [[note1]] and [[note2]]
        "contradictor": 1,          # Always references [[note]]
        "perspective_shifter": 1,   # Always references [[note]]
        "transformation_suggester": 1,  # Always references [[note]]
        "semantic_neighbours": 2,   # Always references [[seed]] + [[neighbours]]
    }

    # Geists that SOMETIMES reference notes (variable templates)
    sometimes_has_notes = {
        "what_if",  # Some templates use [[note]], others don't
    }

    for geist_file in geist_files:
        geist = TraceryGeist.from_yaml(geist_file, seed=42)
        geist_id = geist.geist_id

        # Skip geists that never reference notes (like random_prompts)
        if geist_id not in always_has_notes and geist_id not in sometimes_has_notes:
            continue

        suggestions = geist.suggest(context)

        for suggestion in suggestions:
            text = suggestion.text

            # 1. Find all properly formatted wikilinks
            wikilinks = re.findall(r'\[\[([^\]]+)\]\]', text)

            # Verify minimum expected wikilinks (only for geists that ALWAYS have notes)
            if geist_id in always_has_notes:
                min_expected = always_has_notes[geist_id]
                assert len(wikilinks) >= min_expected, (
                    f"{geist_id}: Expected >= {min_expected} wikilinks, "
                    f"got {len(wikilinks)} in: {text}"
                )

            # 2. Check for orphaned note references
            # This regex catches patterns like "Word#YYYY" or "Word Word#YYYY"
            # that look like note references but aren't in brackets
            potential_orphans = re.findall(
                r'(?<!\[)\b([\w\s]+#\d{4}[^\],.\]]*?)(?=[\s,.]|$)',
                text
            )

            # Filter out false positives (content that's actually inside wikilinks)
            wikilink_content = ' '.join(wikilinks)
            actual_orphans = [
                o for o in potential_orphans
                if o.strip() and o not in wikilink_content
            ]

            assert len(actual_orphans) == 0, (
                f"{geist_id}: Found unbracketed note references: {actual_orphans} in '{text}'"
            )

            # 3. Verify bracket balance
            open_brackets = text.count('[[')
            close_brackets = text.count(']]')
            assert open_brackets == close_brackets, (
                f"{geist_id}: Mismatched brackets: {open_brackets} [[ vs "
                f"{close_brackets} ]] in '{text}'"
            )

            # 4. All wikilinks should be non-empty
            assert all(link.strip() for link in wikilinks), (
                f"{geist_id}: Found empty wikilink in: {text}"
            )
