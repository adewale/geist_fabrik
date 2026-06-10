"""Unit tests for the 8 reflective lens code geists.

Covers a shared conformance battery (return types, wikilink hygiene,
empty/minimal vault handling, determinism) plus per-geist behaviour
tests against a controlled "voice vault" whose notes deliberately trip
the voice metadata thresholds (temporal orientation, pronouns, hedging,
question density, sentence variance).
"""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import (
    attention_shift,
    self_and_other,
    sentence_variance,
    surprisal,
    temporal_voice,
    this_time_last_year,
    uncertainty_mapper,
    voice_absence,
)
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry
from geistfabrik.models import Suggestion
from geistfabrik.voice_analysis import count_hedges

GEIST_MODULES = [
    attention_shift,
    self_and_other,
    sentence_variance,
    surprisal,
    temporal_voice,
    this_time_last_year,
    uncertainty_mapper,
    voice_absence,
]


def _geist_name(module) -> str:
    return module.__name__.rsplit(".", 1)[-1]


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


# ============================================================================
# Controlled note content (designed to trip voice metadata thresholds)
# ============================================================================

PAST_NOTES = {
    "Past Storm": (
        "Yesterday the storm battered the coast. Waves crashed over the wall "
        "and flooded the road below. The town counted the damage and repaired "
        "what the water wrecked."
    ),
    "Past Mill": (
        "The old mill burned down decades back. Farmers hauled the stones away "
        "and built a barn. The river changed course after the dam failed."
    ),
    "Past Orchard": (
        "She walked through the orchard and picked the last apples. The harvest "
        "ended early because frost arrived in October. Everyone remembered that "
        "cold autumn."
    ),
}

FUTURE_NOTES = {
    "Bridge Vote": (
        "Tomorrow the council will vote on the new bridge. Engineers will survey "
        "the river and crews will start work in spring. The project will take "
        "two years."
    ),
    "Library Opening": (
        "Next month the library will open a new wing. Volunteers will catalogue "
        "donations and the mayor will speak at the launch. Visitors will borrow "
        "books from day one."
    ),
    "North Survey": (
        "Soon the team will travel north for the survey. The route will cross "
        "three rivers and the trek will last ten days. Supplies will arrive by "
        "boat next week."
    ),
}

HEDGY_NOTES = {
    "Hedged Plan": (
        "Maybe the plan works. Perhaps it seems too ambitious. The budget could "
        "possibly stretch further. Apparently the timeline might slip somewhat."
    ),
    "Hedged Essay": (
        "Arguably the essay sort of misses the point. The argument appears weak "
        "and the evidence seems rather thin. Presumably the author kind of "
        "rushed the ending."
    ),
}

WE_NOTES = {
    "Studio Session": (
        "We met at the studio today. We sketched our plans together and we "
        "argued about colour. Our collaboration gives us energy."
    ),
    "Workshop Day": (
        "We hosted the workshop with the whole team. Our guests brought "
        "questions and we shared our tools. Together we built something none "
        "of us expected."
    ),
}

I_NOTES = {
    "Morning Pages": (
        "I wrote in my journal this morning. I noticed my focus drifts when I "
        "skip my walk. My best ideas come to me on the trail."
    ),
    "Draft Night": (
        "I finished my draft late at night. My editor wants changes but I trust "
        "my instincts on this one. I rarely doubt my own voice."
    ),
    "Garden Log": (
        "I planted tomatoes in my garden. I water them every morning and I "
        "track my progress in my notebook. My patience surprises me."
    ),
}

QUESTION_NOTES = {
    "Walkable Cities": (
        "What makes a city walkable? Why do some streets invite strolling? "
        "How wide should a pavement be? Who decides these things?"
    ),
    "Craft Questions": (
        "Where does creativity come from? When does practice become mastery? "
        "Which habits matter most? Whose advice should a beginner trust?"
    ),
    "Progress Questions": (
        "What counts as progress? Why does momentum fade? How does a habit "
        "form? When should a project end?"
    ),
}

_FILLER_WORDS = [
    "market",
    "garden",
    "harbor",
    "temple",
    "castle",
    "village",
    "station",
    "museum",
    "library",
    "forest",
    "kitchen",
    "meadow",
]

FILLER_NOTES = {
    f"Filler {word.title()}": (
        f"The {word} is open today and the staff is busy. "
        f"The light is bright and the room is warm. "
        f"The mood is calm and the pace is steady."
    )
    for word in _FILLER_WORDS
}


def _write_notes(vault_path, notes: dict) -> None:
    for title, body in notes.items():
        (vault_path / f"{title}.md").write_text(f"# {title}\n\n{body}\n")


def _build_vault(vault_path, note_groups: list) -> tuple:
    vault_path.mkdir(exist_ok=True)
    for group in note_groups:
        _write_notes(vault_path, group)
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    session = Session(datetime(2025, 6, 15), vault.db)
    session.compute_embeddings(vault.all_notes())
    return vault, session


def _make_context(vault, session, seed=20250615) -> VaultContext:
    return VaultContext(
        vault=vault,
        session=session,
        seed=seed,
        function_registry=FunctionRegistry(),
    )


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def voice_vault(tmp_path_factory):
    """Vault with controlled voice content (27 notes, >= 25 required).

    3 past-tense, 3 future-tense, 2 high-hedging, 2 "we", 3 "I",
    3 question-dense and 12 neutral present-tense filler notes.
    """
    vault_path = tmp_path_factory.mktemp("voice_vault") / "vault"
    return _build_vault(
        vault_path,
        [
            PAST_NOTES,
            FUTURE_NOTES,
            HEDGY_NOTES,
            WE_NOTES,
            I_NOTES,
            QUESTION_NOTES,
            FILLER_NOTES,
        ],
    )


@pytest.fixture
def empty_vault(tmp_path):
    """Completely empty vault."""
    return _build_vault(tmp_path / "vault", [])


@pytest.fixture
def tiny_vault(tmp_path):
    """Vault with only 3 neutral notes."""
    tiny_notes = dict(list(FILLER_NOTES.items())[:3])
    return _build_vault(tmp_path / "vault", [tiny_notes])


# ============================================================================
# Conformance battery (all 8 geists)
# ============================================================================


@pytest.mark.parametrize("geist", GEIST_MODULES, ids=_geist_name)
def test_returns_suggestion_list_on_voice_vault(geist, voice_vault):
    """Every geist returns a list of well-formed Suggestions."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    suggestions = geist.suggest(context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        assert isinstance(suggestion, Suggestion)
        assert suggestion.geist_id == _geist_name(geist)
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        for ref in suggestion.notes:
            assert isinstance(ref, str)
            assert len(ref) > 0


@pytest.mark.parametrize("geist", GEIST_MODULES, ids=_geist_name)
def test_wikilinks_well_formed(geist, voice_vault):
    """Wikilinks in suggestion text are balanced and not double-bracketed."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    suggestions = geist.suggest(context)

    assert isinstance(suggestions, list)
    for suggestion in suggestions:
        text = suggestion.text
        assert text.count("[[") == text.count("]]")
        assert "[[[[" not in text
        assert "[[]]" not in text


@pytest.mark.parametrize("geist", GEIST_MODULES, ids=_geist_name)
def test_empty_vault_returns_empty(geist, empty_vault):
    """Every geist returns [] on an empty vault."""
    vault, session = empty_vault
    context = _make_context(vault, session)

    suggestions = geist.suggest(context)

    assert isinstance(suggestions, list)
    assert suggestions == []
    assert len(vault.all_notes()) == 0


@pytest.mark.parametrize("geist", GEIST_MODULES, ids=_geist_name)
def test_three_note_vault_no_crash(geist, tiny_vault):
    """Every geist handles a 3-note vault without crashing."""
    vault, session = tiny_vault
    context = _make_context(vault, session)

    suggestions = geist.suggest(context)

    assert isinstance(suggestions, list)
    assert len(vault.all_notes()) == 3
    for suggestion in suggestions:
        assert isinstance(suggestion, Suggestion)


@pytest.mark.parametrize("geist", GEIST_MODULES, ids=_geist_name)
def test_deterministic_output(geist, voice_vault):
    """Same vault + session + seed produces identical suggestions."""
    vault, session = voice_vault

    first = geist.suggest(_make_context(vault, session, seed=777))
    _GLOBAL_REGISTRY.clear()  # Reset before creating second context
    second = geist.suggest(_make_context(vault, session, seed=777))

    assert isinstance(first, list)
    assert isinstance(second, list)
    assert first == second


# ============================================================================
# temporal_voice
# ============================================================================


def test_temporal_voice_pairs_past_and_future(voice_vault):
    """temporal_voice pairs one past-oriented and one future-oriented note."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    past_pool = {
        n.obsidian_link
        for n in context.notes_excluding_journal()
        if context.metadata(n)["temporal_orientation"] == "past"
    }
    future_pool = {
        n.obsidian_link
        for n in context.notes_excluding_journal()
        if context.metadata(n)["temporal_orientation"] == "future"
    }

    # Fixture sanity: the designed notes actually trip the thresholds
    assert set(PAST_NOTES) <= past_pool
    assert set(FUTURE_NOTES) <= future_pool

    suggestions = temporal_voice.suggest(context)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.geist_id == "temporal_voice"
    assert len(suggestion.notes) == 2
    assert suggestion.notes[0] in past_pool
    assert suggestion.notes[1] in future_pool
    assert f"[[{suggestion.notes[0]}]]" in suggestion.text
    assert f"[[{suggestion.notes[1]}]]" in suggestion.text


# ============================================================================
# self_and_other
# ============================================================================


def test_self_and_other_fires_with_i_and_we_notes(voice_vault):
    """self_and_other contrasts the 'I' notes with the 'we' notes."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    suggestions = self_and_other.suggest(context)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.geist_id == "self_and_other"
    # 3 i_notes sampled (all of them) + 2 we_notes sampled (all of them)
    assert len(suggestion.notes) == 5
    assert set(suggestion.notes) == set(I_NOTES) | set(WE_NOTES)
    assert "say 'I'" in suggestion.text
    assert "say 'we'" in suggestion.text
    assert "When do you think alone" in suggestion.text


# ============================================================================
# uncertainty_mapper
# ============================================================================


def test_uncertainty_mapper_picks_hedgy_note_and_counts(voice_vault):
    """uncertainty_mapper names the hedgiest note with hedge/word counts."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    suggestions = uncertainty_mapper.suggest(context)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.geist_id == "uncertainty_mapper"
    assert len(suggestion.notes) == 1
    assert suggestion.notes[0] in HEDGY_NOTES
    assert "What are you not ready to commit to?" in suggestion.text

    # The reported hedge count matches count_hedges() on the actual content
    picked = next(n for n in vault.all_notes() if n.title == suggestion.notes[0])
    assert f"hedges {count_hedges(picked.content)} times" in suggestion.text
    assert f"in {len(picked.content.split())} words" in suggestion.text


# ============================================================================
# surprisal
# ============================================================================


def test_surprisal_references_existing_notes(voice_vault):
    """surprisal returns <= 1 suggestion referencing real vault notes."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    all_links = {n.obsidian_link for n in vault.all_notes()}
    suggestions = surprisal.suggest(context)

    assert len(suggestions) <= 1
    assert len(suggestions) == 1  # 27 notes > k_neighbours + 1, so it fires
    suggestion = suggestions[0]
    assert suggestion.geist_id == "surprisal"
    # 1 surprising note + 3 neighbours
    assert len(suggestion.notes) == 4
    for ref in suggestion.notes:
        assert ref in all_links
    assert "doesn't quite fit" in suggestion.text


def test_surprisal_picks_max_score_note(voice_vault):
    """surprisal names the note with the highest surprisal score."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    scores = context.surprisal_scores()
    assert scores  # non-empty for 27 notes
    top_path = max(scores, key=lambda p: scores[p])
    top_note = context.get_note(top_path)
    assert top_note is not None

    suggestions = surprisal.suggest(context)

    assert len(suggestions) == 1
    assert suggestions[0].notes[0] == top_note.obsidian_link


# ============================================================================
# attention_shift
# ============================================================================


def test_attention_shift_empty_without_old_session(voice_vault):
    """attention_shift returns [] when there is no old-enough session."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    # The only session is the current one — churn data is unavailable
    assert context.neighbour_churn(since_days=180) == {}

    suggestions = attention_shift.suggest(context)

    assert isinstance(suggestions, list)
    assert suggestions == []


# ============================================================================
# this_time_last_year
# ============================================================================


def test_this_time_last_year_finds_anniversary_note(tmp_path):
    """this_time_last_year surfaces a note created ~1 year before the session."""
    vault_path = tmp_path / "vault"
    notes = {
        "Anniversary Note": "A thought captured in the early spring.",
        "Other Note": "A thought from a different season entirely.",
        "Recent Note": "A thought from just a few days back.",
    }
    vault_path.mkdir()
    _write_notes(vault_path, notes)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Session date is 2024-03-15; the anniversary note sits inside the
    # +/- 7 day window around 2023-03-15. The others do not match any window.
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2023, 3, 18, 10, 0).isoformat(), "Anniversary Note"),
    )
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2023, 9, 1, 10, 0).isoformat(), "Other Note"),
    )
    vault.db.execute(
        "UPDATE notes SET created = ? WHERE title = ?",
        (datetime(2024, 3, 10, 10, 0).isoformat(), "Recent Note"),
    )
    vault.db.commit()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())
    context = _make_context(vault, session, seed=20240315)

    suggestions = this_time_last_year.suggest(context)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.geist_id == "this_time_last_year"
    assert suggestion.notes == ["Anniversary Note"]
    assert "Around this time a year ago" in suggestion.text
    assert "[[Anniversary Note]]" in suggestion.text


def test_this_time_last_year_empty_without_anniversaries(voice_vault):
    """No notes near any anniversary window means no suggestion."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    # Notes were created at sync time (today), not 1-3 years before the
    # 2025-06-15 session date, so no window matches.
    suggestions = this_time_last_year.suggest(context)

    assert isinstance(suggestions, list)
    assert suggestions == []
    assert len(vault.all_notes()) >= 25


# ============================================================================
# sentence_variance
# ============================================================================


def test_sentence_variance_fires_on_choppy_note(tmp_path):
    """A single high-variance note among uniform notes is flagged."""
    uniform_sentence = "The quiet {word} square fills with morning light."
    notes = {
        f"Uniform {word.title()}": " ".join([uniform_sentence.format(word=word)] * 3)
        for word in _FILLER_WORDS[:10]
    }
    notes["Choppy Note"] = (
        "Stop. The committee deliberated for eleven hours across two long days "
        "about the proposed water treatment facility and its complicated "
        "funding arrangement before reaching any decision. No. The vote "
        "happened anyway."
    )

    vault, session = _build_vault(tmp_path / "vault", [notes])
    context = _make_context(vault, session)

    suggestions = sentence_variance.suggest(context)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.geist_id == "sentence_variance"
    assert suggestion.notes == ["Choppy Note"]
    assert "choppy" in suggestion.text
    assert "[[Choppy Note]]" in suggestion.text


def test_sentence_variance_empty_below_ten_candidates(tiny_vault):
    """Fewer than 10 substantial notes means no statistics, no suggestion."""
    vault, session = tiny_vault
    context = _make_context(vault, session)

    suggestions = sentence_variance.suggest(context)

    assert isinstance(suggestions, list)
    assert suggestions == []
    assert len(vault.all_notes()) == 3


# ============================================================================
# voice_absence
# ============================================================================


def test_voice_absence_fires_on_missing_future_voice(tmp_path):
    """A 20-note vault with no future-tense notes triggers exactly that absence."""
    # 3 past + 2 we + 3 question + 12 present fillers = 20 notes, no future.
    # Past, we and question voices are all above their thresholds, so only
    # the future absence fires.
    vault, session = _build_vault(
        tmp_path / "vault",
        [PAST_NOTES, WE_NOTES, QUESTION_NOTES, FILLER_NOTES],
    )
    context = _make_context(vault, session)
    assert len(vault.all_notes()) == 20

    suggestions = voice_absence.suggest(context)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.geist_id == "voice_absence"
    assert suggestion.notes == []
    assert "look forward" in suggestion.text
    assert "of your 20 notes" in suggestion.text


def test_voice_absence_returns_at_most_one(voice_vault):
    """voice_absence never returns more than one suggestion."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    suggestions = voice_absence.suggest(context)

    assert isinstance(suggestions, list)
    assert len(suggestions) <= 1
    for suggestion in suggestions:
        assert suggestion.notes == []
        assert suggestion.geist_id == "voice_absence"
