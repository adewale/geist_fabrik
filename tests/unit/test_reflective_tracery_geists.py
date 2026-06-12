"""Unit tests for the three reflective-lens Tracery geists.

Covers temporal_contrast, questioning_mind, and unexpected_neighbour:
- YAML parses, validates, and id matches filename
- All referenced $vault.* functions are registered built-ins
- No double-bracket bug ([[#symbol#]]) in templates
- End-to-end rendering against a small voice-controlled vault
"""

import re
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from geistfabrik import Vault, VaultContext
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry
from geistfabrik.tracery import TraceryGeist
from geistfabrik.validator import GeistValidator

TRACERY_DIR = (
    Path(__file__).parent.parent.parent / "src" / "geistfabrik" / "default_geists" / "tracery"
)

REFLECTIVE_GEISTS = [
    "temporal_contrast",
    "questioning_mind",
    "unexpected_neighbour",
]

VAULT_FUNCTION_RE = re.compile(r"\$vault\.([a-z_]+)\(")


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


def _yaml_path(geist_id: str) -> Path:
    return TRACERY_DIR / f"{geist_id}.yaml"


# ============================================================================
# Static YAML tests
# ============================================================================


@pytest.mark.parametrize("geist_id", REFLECTIVE_GEISTS)
def test_yaml_exists_and_parses(geist_id: str) -> None:
    """Each reflective Tracery geist YAML exists and parses."""
    path = _yaml_path(geist_id)
    assert path.exists(), f"Missing default Tracery geist: {path}"

    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict)
    assert data["type"] == "geist-tracery"
    assert "tracery" in data
    assert "origin" in data["tracery"]


@pytest.mark.parametrize("geist_id", REFLECTIVE_GEISTS)
def test_yaml_id_matches_filename(geist_id: str) -> None:
    """The id field matches the YAML filename stem."""
    data = yaml.safe_load(_yaml_path(geist_id).read_text())
    assert data["id"] == geist_id


@pytest.mark.parametrize("geist_id", REFLECTIVE_GEISTS)
def test_yaml_passes_validator(geist_id: str) -> None:
    """Each YAML passes the Tracery grammar validator without errors."""
    validator = GeistValidator()
    result = validator.validate_tracery_geist(_yaml_path(geist_id))

    assert not result.has_errors, [
        issue.message for issue in result.issues if issue.severity == "error"
    ]
    assert result.passed


@pytest.mark.parametrize("geist_id", REFLECTIVE_GEISTS)
def test_yaml_loads_as_tracery_geist(geist_id: str) -> None:
    """Each YAML loads via TraceryGeist.from_yaml (anti-pattern check included)."""
    geist = TraceryGeist.from_yaml(_yaml_path(geist_id), seed=42)
    assert geist.geist_id == geist_id
    assert "origin" in geist.engine.grammar


@pytest.mark.parametrize("geist_id", REFLECTIVE_GEISTS)
def test_vault_functions_are_registered_builtins(geist_id: str) -> None:
    """Every $vault.* function referenced in the YAML is a registered built-in."""
    raw = _yaml_path(geist_id).read_text()
    function_names = set(VAULT_FUNCTION_RE.findall(raw))
    assert function_names, f"{geist_id}.yaml references no vault functions"

    registry = FunctionRegistry()
    for name in function_names:
        assert registry.has_function(name), (
            f"{geist_id}.yaml references unregistered vault function: {name}"
        )


@pytest.mark.parametrize("geist_id", REFLECTIVE_GEISTS)
def test_no_double_bracket_bug(geist_id: str) -> None:
    """Templates must use #symbol# as-is, never [[#symbol#]].

    All vault functions return bracketed links already; adding brackets in
    templates would produce [[[[Note]]]].
    """
    raw = _yaml_path(geist_id).read_text()
    assert "[[#" not in raw, f"{geist_id}.yaml adds brackets around a symbol"


# ============================================================================
# Rendering tests
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
    "question_a.md": (
        "# Question A\n\nWhat is this? Why does it matter? How would anyone know? Who decides?"
    ),
    "question_b.md": ("# Question B\n\nWhere did it begin? When does it end? Which path is real?"),
    "filler_a.md": ("# Filler A\n\nNotes about gardening tools and seasonal planting schedules."),
    "filler_b.md": ("# Filler B\n\nReading list for the spring with several novels and essays."),
    "filler_c.md": ("# Filler C\n\nRecipe collection featuring soups, stews and baked goods."),
    "filler_d.md": ("# Filler D\n\nObservations from a long walk through the old town centre."),
    "filler_e.md": ("# Filler E\n\nSketches of birds spotted near the river this winter."),
    "filler_f.md": ("# Filler F\n\nMaintenance log for the bicycle, including parts replaced."),
}


@pytest.fixture
def voice_vault(tmp_path):
    """Small vault with controlled linguistic voices and one computed session."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    for filename, content in VOICE_NOTES.items():
        (vault_path / filename).write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime(2025, 1, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


def _make_context(vault: Vault, session: Session, registry: FunctionRegistry) -> VaultContext:
    return VaultContext(
        vault=vault,
        session=session,
        seed=20250115,
        function_registry=registry,
    )


@pytest.fixture
def voice_context(voice_vault):
    """VaultContext over the voice vault."""
    vault, session = voice_vault
    return _make_context(vault, session, FunctionRegistry())


@pytest.mark.parametrize("geist_id", REFLECTIVE_GEISTS)
def test_geist_renders_bracketed_links(geist_id: str, voice_context: VaultContext) -> None:
    """Executing each geist (as the loader/executor does) yields valid suggestions.

    The fixture vault contains past-focused, future-focused and questioning
    notes, so symbol pre-population should find candidates for every geist.
    """
    geist = TraceryGeist.from_yaml(_yaml_path(geist_id), seed=42)
    suggestions = geist.suggest(voice_context)

    assert isinstance(suggestions, list)
    assert len(suggestions) > 0, f"{geist_id} produced no suggestions on the voice vault"

    for suggestion in suggestions:
        assert suggestion.geist_id == geist_id
        # Vault functions return bracketed links; they must survive rendering
        assert "[[" in suggestion.text, suggestion.text
        assert "]]" in suggestion.text, suggestion.text
        # No unexpanded Tracery symbols remain
        for symbol in ("#origin#", "#provocation#", "#note#", "#past_note#", "#future_note#"):
            assert symbol not in suggestion.text, suggestion.text
        # Note references extracted from the rendered text
        assert len(suggestion.notes) > 0


def test_geists_are_deterministic(voice_vault) -> None:
    """Same vault + same seed produces identical suggestion text."""
    vault, session = voice_vault
    registry = FunctionRegistry()
    for geist_id in REFLECTIVE_GEISTS:
        first = TraceryGeist.from_yaml(_yaml_path(geist_id), seed=42)
        second = TraceryGeist.from_yaml(_yaml_path(geist_id), seed=42)

        texts_first = [s.text for s in first.suggest(_make_context(vault, session, registry))]
        texts_second = [s.text for s in second.suggest(_make_context(vault, session, registry))]

        assert texts_first == texts_second
