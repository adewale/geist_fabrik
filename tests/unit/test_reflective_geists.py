"""Unit tests for the 8 reflective lens code geists.

Covers a shared conformance battery (well-formed output, wikilink hygiene,
3-note vault handling, determinism), run for each geist on a vault designed
to make it fire, plus per-geist behaviour tests against a controlled "voice
vault" whose notes deliberately trip the voice metadata thresholds
(temporal orientation, pronouns, hedging, question density, sentence
variance). Empty-vault behaviour is owned by test_code_geists_empty_data.py.
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
from tests.fixtures.helpers import assert_valid_suggestions

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


def _set_created(vault, title: str, created: datetime) -> None:
    vault.db.execute("UPDATE notes SET created = ? WHERE title = ?", (created.isoformat(), title))
    vault.db.commit()


def _build_anniversary_vault(vault_path, created: datetime) -> tuple:
    """Three notes; only "Anniversary Note" can fall in a 1-3 year window.

    The session date is 2024-03-15, so the 1-year window is 2023-03-08 to
    2023-03-22 inclusive. The other two notes sit outside every window.
    """
    vault_path.mkdir()
    _write_notes(
        vault_path,
        {
            "Anniversary Note": "A thought captured in the early spring.",
            "Other Note": "A thought from a different season entirely.",
            "Recent Note": "A thought from just a few days back.",
        },
    )
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    _set_created(vault, "Anniversary Note", created)
    _set_created(vault, "Other Note", datetime(2023, 9, 1, 10, 0))
    _set_created(vault, "Recent Note", datetime(2024, 3, 10, 10, 0))
    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())
    return vault, session


ALPHA_WORDS = "quartz lichen harbour violin saffron glacier"
BETA_WORDS = "meadow lantern cobalt thistle walnut falcon"


def _build_shifted_vault(vault_path) -> tuple:
    """A note whose vocabulary moved from one topic group to another.

    Ten "Alpha" notes share one vocabulary and ten "Beta" notes another. In
    the historical session (2024-06-01, over 180 days before the current
    one) "Pivot" used the Alpha words, so its 10 nearest neighbours were the
    Alpha notes; it was then rewritten with the Beta words, so its current
    neighbours are the Beta notes: churn 1.0 > 0.6.
    """
    vault_path.mkdir()
    for i in range(10):
        _write_notes(vault_path, {f"Alpha {i}": f"{ALPHA_WORDS} a{i}x"})
        _write_notes(vault_path, {f"Beta {i}": f"{BETA_WORDS} b{i}x"})
    _write_notes(vault_path, {"Pivot": ALPHA_WORDS})
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    Session(datetime(2024, 6, 1), vault.db).compute_embeddings(vault.all_notes())

    _write_notes(vault_path, {"Pivot": BETA_WORDS})
    vault.sync()
    session = Session(datetime(2025, 6, 15), vault.db)
    session.compute_embeddings(vault.all_notes())
    return vault, session


def _build_voiceless_vault(vault_path) -> tuple:
    """20 neutral present-tense notes: no past, no future, no "we" and no
    questions, so all four voice_absence checks fire (and the pick among
    them is a seeded sample)."""
    fillers = {
        f"Plain {i}": f"The room {i} is quiet today. The desk is tidy. The lamp is on."
        for i in range(20)
    }
    return _build_vault(vault_path, [fillers])


def _build_choppy_vault(vault_path) -> tuple:
    """Ten uniform notes plus one note mixing very short and very long sentences."""
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
    return _build_vault(vault_path, [notes])


def _firing_vault(geist, voice_vault, tmp_path) -> tuple:
    """A vault on which ``geist`` is designed to fire (see each builder)."""
    name = _geist_name(geist)
    if name == "attention_shift":
        return _build_shifted_vault(tmp_path / "vault")
    if name == "this_time_last_year":
        return _build_anniversary_vault(tmp_path / "vault", datetime(2023, 3, 18, 10, 0))
    if name == "voice_absence":
        return _build_voiceless_vault(tmp_path / "vault")
    if name == "sentence_variance":
        return _build_choppy_vault(tmp_path / "vault")
    return voice_vault


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
def test_returns_well_formed_suggestions_when_firing(geist, voice_vault, tmp_path):
    """On its designed-to-trigger vault every geist fires with well-formed
    output that references only real notes."""
    vault, session = _firing_vault(geist, voice_vault, tmp_path)
    context = _make_context(vault, session)
    real_notes = {n.link_text for n in vault.all_notes()}

    suggestions = geist.suggest(context)

    assert_valid_suggestions(suggestions, _geist_name(geist))
    for suggestion in suggestions:
        assert set(suggestion.notes) <= real_notes


@pytest.mark.parametrize("geist", GEIST_MODULES, ids=_geist_name)
def test_wikilinks_well_formed(geist, voice_vault, tmp_path):
    """Wikilinks in suggestion text are balanced, not double-bracketed, and
    every referenced note is linked in the text."""
    vault, session = _firing_vault(geist, voice_vault, tmp_path)
    context = _make_context(vault, session)

    suggestions = geist.suggest(context)

    assert suggestions, "fixture is designed to trigger"
    for suggestion in suggestions:
        text = suggestion.text
        assert text.count("[[") == text.count("]]")
        assert "[[[[" not in text
        assert "[[]]" not in text
        for ref in suggestion.notes:
            assert f"[[{ref}]]" in text


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
def test_deterministic_output(geist, voice_vault, tmp_path):
    """Same vault + session + seed produces identical, non-empty suggestions."""
    vault, session = _firing_vault(geist, voice_vault, tmp_path)

    first = geist.suggest(_make_context(vault, session, seed=777))
    _GLOBAL_REGISTRY.clear()  # Reset before creating second context
    second = geist.suggest(_make_context(vault, session, seed=777))

    assert first
    assert first == second


# ============================================================================
# temporal_voice
# ============================================================================


def test_temporal_voice_pairs_past_and_future(voice_vault):
    """temporal_voice pairs one past-oriented and one future-oriented note."""
    vault, session = voice_vault
    context = _make_context(vault, session)

    past_pool = {
        n.link_text
        for n in context.notes_excluding_journal()
        if context.metadata(n)["temporal_orientation"] == "past"
    }
    future_pool = {
        n.link_text
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

    all_links = {n.link_text for n in vault.all_notes()}
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
    assert suggestions[0].notes[0] == top_note.link_text


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

    assert suggestions == []


def test_attention_shift_names_the_note_whose_neighbours_moved(tmp_path):
    vault, session = _build_shifted_vault(tmp_path / "vault")
    context = _make_context(vault, session)

    suggestions = attention_shift.suggest(context)

    assert_valid_suggestions(suggestions, "attention_shift")
    assert len(suggestions) == 1
    pivot, *moved = suggestions[0].notes
    assert pivot == "Pivot"
    departed, arrived = moved[:3], moved[3:]
    assert departed and all(t.startswith("Alpha") for t in departed)
    assert arrived and all(t.startswith("Beta") for t in arrived)


# ============================================================================
# this_time_last_year
# ============================================================================


@pytest.mark.parametrize(
    ("created", "fires"),
    [
        (datetime(2023, 3, 8, 10, 0), True),  # 7 days before the anniversary
        (datetime(2023, 3, 22, 10, 0), True),  # 7 days after
        (datetime(2023, 3, 7, 10, 0), False),  # 8 days before: outside
        (datetime(2023, 3, 23, 10, 0), False),  # 8 days after: outside
    ],
)
def test_this_time_last_year_window_boundaries(tmp_path, created, fires):
    """A note created within +/- 7 days of a 1-year anniversary is resurfaced."""
    vault, session = _build_anniversary_vault(tmp_path / "vault", created)
    context = _make_context(vault, session, seed=20240315)

    suggestions = this_time_last_year.suggest(context)

    if not fires:
        assert suggestions == []
        return
    assert_valid_suggestions(suggestions, "this_time_last_year")
    assert [s.notes for s in suggestions] == [["Anniversary Note"]]
    assert "Around this time a year ago" in suggestions[0].text


# ============================================================================
# sentence_variance
# ============================================================================


def test_sentence_variance_fires_on_choppy_note(tmp_path):
    """A single high-variance note among uniform notes is flagged."""
    vault, session = _build_choppy_vault(tmp_path / "vault")
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


def test_voice_absence_names_exactly_one_of_several_absences(tmp_path):
    """With four voices missing, voice_absence still names exactly one."""
    vault, session = _build_voiceless_vault(tmp_path / "vault")
    context = _make_context(vault, session)

    suggestions = voice_absence.suggest(context)

    assert_valid_suggestions(suggestions, "voice_absence")
    assert len(suggestions) == 1
    assert suggestions[0].notes == []
    assert suggestions[0].text.startswith("Only 0 of your 20 notes")
