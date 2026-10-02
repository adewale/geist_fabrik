"""Known-answer tests for the three reflective-lens Tracery geists.

temporal_contrast, questioning_mind and unexpected_neighbour draw on the
voice metadata (tense, question density) and on surprisal. The fixture gives
each lens exactly the notes it should find, so every rendered link can be
checked against the designed answer. Shared Tracery contracts (validator,
count, determinism, bracketed links that resolve) are owned by
tests/unit/test_tracery_geists.py for every bundled geist.
"""

import re
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.tracery import TraceryGeist
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

TRACERY_DIR = (
    Path(__file__).parent.parent.parent / "src" / "geistfabrik" / "default_geists" / "tracery"
)
_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")

# Every note but "Bicycle Log" shares the garden vocabulary, so under the
# lexical stub "Bicycle Log" is the one note unlike its neighbourhood.
SHARED = "Garden soil compost seedlings."
PAST = {
    "Past A": "I walked to the store. I bought milk. I returned home. I cooked dinner.",
    "Past B": "She wrote letters. He painted walls. They travelled far away.",
}
FUTURE = {
    "Future A": "Tomorrow I will start. I will plan the trip. It will work well.",
    "Future B": "We will launch soon. The team will grow. It will succeed.",
}
QUESTIONS = {
    "Question A": "What is this? Why does it matter? How would anyone know? Who decides?",
    "Question B": "Where did it begin? When does it end? Which path is real?",
}
FILLER = {
    "Filler A": "Notes about gardening tools and seasonal planting schedules.",
    "Filler B": "Reading list for the spring with several novels and essays.",
    "Filler C": "Recipe collection featuring soups, stews and breads.",
    "Filler D": "Observations from a long walk through the old town centre.",
    "Filler E": "Sketches of birds near the river this winter.",
}
ODD_ONE_OUT = "Bicycle Log"


@pytest.fixture
def voice_context(tmp_path: Path) -> VaultContext:
    builder = VaultBuilder(tmp_path)
    for i, (title, body) in enumerate({**PAST, **FUTURE, **QUESTIONS, **FILLER}.items()):
        builder.note(title, f"{body} {SHARED}", created=datetime(2024, 1, 1 + i))
    builder.note(
        ODD_ONE_OUT,
        "Maintenance chain derailleur sprocket spokes.",
        created=datetime(2024, 2, 1),
    )
    return builder.build()


def _links(geist_id: str, context: VaultContext, seeds: range = range(20)) -> list[list[str]]:
    """Render the geist under several seeds; return each suggestion's links."""
    rendered = []
    for seed in seeds:
        geist = TraceryGeist.from_yaml(TRACERY_DIR / f"{geist_id}.yaml", seed=seed)
        suggestions = geist.suggest(context)
        assert_valid_suggestions(suggestions, geist_id)
        for suggestion in suggestions:
            links = _WIKILINK.findall(suggestion.text)
            assert suggestion.notes == links, suggestion.text
            rendered.append(links)
    return rendered


def test_temporal_contrast_names_one_past_tense_note(voice_context: VaultContext) -> None:
    """Every suggestion names exactly one past-tense note.

    (Updated: the two past-with-future templates were removed; see
    test_temporal_contrast_fires_without_a_future_focused_note.)
    """
    rendered = _links("temporal_contrast", voice_context)

    assert len(rendered) == 20
    assert all(len(links) == 1 and links[0] in PAST for links in rendered), rendered


def test_temporal_contrast_fires_without_a_future_focused_note(tmp_path: Path) -> None:
    """Contract: a vault with a past-tense note but no future-focused note still gets a prompt.

    Regression: two templates also drew $vault.future_focused_notes(1). A
    future-focused note needs future_tense_ratio > 0.4, which real prose
    almost never reaches, and an empty vault-function pool silences the whole
    geist, so temporal_contrast was silent in every real-run session even
    though its past-note template needed no future note.
    """
    builder = VaultBuilder(tmp_path)
    for i, (title, body) in enumerate({**PAST, **FILLER}.items()):
        builder.note(title, f"{body} {SHARED}", created=datetime(2024, 1, 1 + i))
    context = builder.build()
    assert context.call_function("future_focused_notes", 1) == []

    suggestions = TraceryGeist.from_yaml(TRACERY_DIR / "temporal_contrast.yaml", seed=3).suggest(
        context
    )

    assert len(suggestions) == 1
    (past,) = suggestions[0].notes
    assert past in PAST
    assert suggestions[0].text == (
        f"[[{past}]] is in past tense. What would it say if you rewrote it looking forward?"
    )


def test_questioning_mind_names_a_question_dense_note(voice_context: VaultContext) -> None:
    rendered = _links("questioning_mind", voice_context)

    assert {link for links in rendered for link in links} <= set(QUESTIONS)


def test_unexpected_neighbour_names_the_note_unlike_its_neighbourhood(
    voice_context: VaultContext,
) -> None:
    rendered = _links("unexpected_neighbour", voice_context, seeds=range(5))

    assert rendered == [[ODD_ONE_OUT]] * 5
