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
from geistfabrik.voice_analysis import count_hedges, strip_for_analysis, tokenize
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


def _long_prose(extra: str = "", sentences: int = 22) -> str:
    """About 240 words of pronoun-free, present-tense prose plus ``extra``.

    Long enough that a single pronoun, "will" or "?" in ``extra`` is a low
    per-100-word rate (about 0.4), so tests can tell "says it once" from
    "says it a lot".
    """
    body = " ".join(["The quiet path is wide and the old stone wall is warm."] * sentences)
    return f"{body} {extra}".strip()


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
    """20 neutral present-tense notes: no past, no future and no questions,
    so all three voice_absence checks fire (and the pick among them is a
    seeded sample)."""
    fillers = {
        f"Plain {i}": f"The room {i} is quiet today. The desk is tidy. The lamp is on."
        for i in range(20)
    }
    return _build_vault(vault_path, [fillers])


UNIFORM_SENTENCE = "The quiet {word} square fills with morning light."
LONG_SENTENCE = (
    "The committee deliberated for eleven hours across two long days about the "
    "proposed water treatment facility and its complicated funding arrangement."
)


def _choppy_body(burst: str = "Stop.") -> str:
    """Eleven sentences alternating one-word bursts with 21-word stretches."""
    return " ".join([burst, LONG_SENTENCE] * 5 + [burst])


def _uniform_notes(count: int = 10) -> dict:
    """Notes of ten identical 8-word sentences (zero spread)."""
    return {
        f"Uniform {word.title()}": " ".join([UNIFORM_SENTENCE.format(word=word)] * 10)
        for word in _FILLER_WORDS[:count]
    }


def _build_choppy_vault(vault_path) -> tuple:
    """Ten uniform notes plus one note mixing very short and very long sentences."""
    notes = _uniform_notes()
    notes["Choppy Note"] = _choppy_body()
    return _build_vault(vault_path, [notes])


# Long-form hedgy notes: uncertainty_mapper only considers notes of at least
# 5 sentences and 80 words (the voice-vault HEDGY_NOTES are 4 sentences).
LONG_HEDGY_NOTES = {title: " ".join([body] * 4) for title, body in HEDGY_NOTES.items()}


def _build_hedgy_vault(vault_path) -> tuple:
    """Two long, heavily hedged notes among twelve plain fillers."""
    return _build_vault(vault_path, [LONG_HEDGY_NOTES, FILLER_NOTES])


def _build_surprisal_vault(vault_path) -> tuple:
    """Long notes (>= 50 words) with graded surprisal, plus one near-empty note.

    Fourteen "Cluster" notes share 40 words. Six "Odd" notes share fewer of
    them (40 down to 15) and add 40 words of their own, so they are more
    surprising than any Cluster note. "Tiny Aside" has two words nobody else
    uses, so it is the most surprising note of all, but it is near-empty.
    """
    shared = [f"soil{j}" for j in range(40)]
    notes = {
        f"Cluster {i:02d}": " ".join(shared + [f"leaf{i}x{j}" for j in range(15)])
        for i in range(14)
    }
    for k in range(6):
        notes[f"Odd {k}"] = " ".join(shared[: 40 - 5 * k] + [f"odd{k}x{j}" for j in range(40)])
    notes["Tiny Aside"] = "Quasar nebula."
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
    if name == "uncertainty_mapper":
        return _build_hedgy_vault(tmp_path / "vault")
    if name == "surprisal":
        return _build_surprisal_vault(tmp_path / "vault")
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


def test_self_and_other_ignores_a_single_stray_i(tmp_path):
    """Contract: an "I" note uses the first person singular at >= 1 per 100
    words, not merely more often than "we".

    Regression: self_focus_ratio alone qualified a note, so one "I" (from
    "Did I implement...", a quoted example or a code variable) in a long
    technical note made it an "I" note.
    """
    stray = {f"Spec {i}": _long_prose("Did I implement the parser correctly?") for i in range(3)}
    vault, session = _build_vault(tmp_path / "vault", [stray, WE_NOTES, FILLER_NOTES])
    context = _make_context(vault, session)
    assert all(
        context.voice(n).self_focus_ratio == 1.0
        for n in context.notes()
        if n.title.startswith("Spec")
    )

    assert self_and_other.suggest(context) == []


def test_self_and_other_does_not_claim_no_we_notes_when_some_say_we(tmp_path):
    """Contract: the rarity sentence counts every note that says "we" at all.

    Regression: the "You have no 'we' notes" branch fired whenever no note
    reached 2 "we" per 100 words, even when many notes said "we" (29 of 77 in
    the real run). Three of 18 notes saying "we" once is not rare (>= 5%), so
    the geist abstains.
    """
    occasional_we = {
        f"Team Note {i}": _long_prose("Later we compare the results.") for i in range(3)
    }
    vault, session = _build_vault(tmp_path / "vault", [I_NOTES, occasional_we, FILLER_NOTES])
    context = _make_context(vault, session)
    assert len(context.notes()) == 18

    assert self_and_other.suggest(context) == []


@pytest.mark.parametrize(
    ("we_notes", "rarity"),
    [
        ({}, "None of your 20 notes say 'we'."),
        (
            {"Team Note": _long_prose("Later we compare the results.")},
            "Only 1 of your 21 notes says 'we' at all.",
        ),
    ],
)
def test_self_and_other_states_the_true_we_count(tmp_path, we_notes, rarity):
    """Contract: when "we" is rare (< 5% of notes), the count stated is the
    number of notes that say "we"/"us"/"our" at all.

    Regression: the text said "You have no 'we' notes" whatever the count.
    """
    extra_fillers = {f"Extra {i}": _long_prose() for i in range(5)}
    vault, session = _build_vault(
        tmp_path / "vault", [I_NOTES, we_notes, FILLER_NOTES, extra_fillers]
    )
    context = _make_context(vault, session)

    suggestions = self_and_other.suggest(context)

    assert_valid_suggestions(suggestions, "self_and_other")
    assert len(suggestions) == 1
    assert sorted(suggestions[0].notes) == sorted(I_NOTES)
    titles = ", ".join(f"[[{t}]]" for t in suggestions[0].notes)
    assert suggestions[0].text == (
        f"These notes say 'I': {titles}. {rarity} Who could you be thinking with?"
    )


# ============================================================================
# uncertainty_mapper
# ============================================================================


def test_uncertainty_mapper_picks_hedgy_note_and_counts(tmp_path):
    """uncertainty_mapper names a hedgy note with true hedge/word counts.

    Updated: the word count is now the prose word count (frontmatter, code
    and URLs stripped, as the hedges are), not whitespace tokens of the raw
    file, and the fixture notes are long enough to pass the length minimum.
    """
    vault, session = _build_hedgy_vault(tmp_path / "vault")
    context = _make_context(vault, session)

    suggestions = uncertainty_mapper.suggest(context)

    assert_valid_suggestions(suggestions, "uncertainty_mapper")
    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert len(suggestion.notes) == 1
    assert suggestion.notes[0] in LONG_HEDGY_NOTES
    picked = next(n for n in vault.all_notes() if n.title == suggestion.notes[0])
    words = len(tokenize(strip_for_analysis(picked.content)))
    assert suggestion.text == (
        f"[[{picked.title}]] hedges {count_hedges(picked.content)} times in {words} words. "
        "What are you not ready to commit to?"
    )


def test_uncertainty_mapper_ignores_one_line_notes(tmp_path):
    """Contract: only notes with >= 5 sentences and >= 80 words compete, and
    they are ranked by hedges per 100 words.

    Regression: hedges per sentence with no minimum length let a one-liner
    ("Maybe we could perhaps call Bob.", 1.5 per sentence) beat a long note
    that hedges in every sentence (0.94 per sentence).
    """
    steady = " ".join(["The plan might work out well in the end."] * 16)
    vault, session = _build_vault(
        tmp_path / "vault",
        [
            {"Quick Thought": "Maybe we could perhaps call Bob.", "Steady Doubt": steady},
            FILLER_NOTES,
        ],
    )
    context = _make_context(vault, session)

    suggestions = uncertainty_mapper.suggest(context)

    assert [(s.text, s.notes) for s in suggestions] == [
        (
            "[[Steady Doubt]] hedges 16 times in 146 words. What are you not ready to commit to?",
            ["Steady Doubt"],
        )
    ]


def test_uncertainty_mapper_month_may_and_rather_are_not_hedges(tmp_path):
    """Contract: capitalised "May" (the month) and "rather than" are not hedges.

    Regression: "The release shipped in May ... speed rather than polish"
    counted two hedges per sentence, so a confident release log was named as
    the vault's most uncertain note.
    """
    log = " ".join(["The release shipped in May and the team chose speed rather than polish."] * 8)
    vault, session = _build_vault(tmp_path / "vault", [{"Release Log": log}, FILLER_NOTES])
    context = _make_context(vault, session)
    note = next(n for n in context.notes() if n.title == "Release Log")
    assert count_hedges(note.content) == 0

    assert uncertainty_mapper.suggest(context) == []


def test_uncertainty_mapper_samples_among_the_top_three(tmp_path):
    """Contract: the named note is sampled from the three most hedged notes,
    never a lower-ranked one.

    Regression: a fixed argmax named the same note every session.
    """
    hedge = "The plan might work out well in the end."
    plain = "The plan works out well in the end."
    notes = {f"Doubt {n}": " ".join([hedge] * n + [plain] * (16 - n)) for n in (16, 14, 12, 10)}
    vault, session = _build_vault(tmp_path / "vault", [notes, FILLER_NOTES])

    picked = {
        tuple(s.notes)
        for seed in range(30)
        for s in uncertainty_mapper.suggest(_make_context(vault, session, seed=seed))
    }

    assert picked == {("Doubt 16",), ("Doubt 14",), ("Doubt 12",)}


# ============================================================================
# surprisal
# ============================================================================


def test_surprisal_references_existing_notes(tmp_path):
    """surprisal returns 1 suggestion: a note plus its 3 nearest neighbours."""
    vault, session = _build_surprisal_vault(tmp_path / "vault")
    context = _make_context(vault, session)

    all_links = {n.link_text for n in vault.all_notes()}
    suggestions = surprisal.suggest(context)

    assert_valid_suggestions(suggestions, "surprisal")
    assert len(suggestions) == 1  # 21 notes > k_neighbours + 1, so it fires
    suggestion = suggestions[0]
    # 1 surprising note + 3 neighbours
    assert len(suggestion.notes) == 4
    assert set(suggestion.notes) <= all_links
    assert "doesn't quite fit" in suggestion.text


def test_surprisal_skips_near_empty_notes_and_samples_the_top_five(tmp_path):
    """Contract: notes under 50 prose words never compete; the named note is
    sampled from the five most surprising remaining notes.

    Regression: a fixed argmax over all notes always named the same note,
    typically a near-empty one ("Product usage analysis", 18 words, in both
    real-run sessions), and so did unexpected_neighbour. (Replaces
    test_surprisal_picks_max_score_note, which encoded the argmax.)
    """
    vault, session = _build_surprisal_vault(tmp_path / "vault")
    scores = _make_context(vault, session).surprisal_scores()
    by_title = {n.title: scores[n.path] for n in vault.all_notes()}
    # Fixture sanity: the near-empty note is the most surprising of all; the
    # next five are Odd notes, and a sixth Odd note ranks just below them.
    assert max(by_title, key=by_title.__getitem__) == "Tiny Aside"
    ranked = sorted(
        (t for t in by_title if t != "Tiny Aside"), key=by_title.__getitem__, reverse=True
    )
    top_five = ranked[:5]
    assert all(t.startswith("Odd") for t in ranked[:6])

    picked = {
        s.notes[0]
        for seed in range(30)
        for s in surprisal.suggest(_make_context(vault, session, seed=seed))
    }

    assert picked == set(top_five)


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
    """A single high-spread note among uniform notes is flagged."""
    vault, session = _build_choppy_vault(tmp_path / "vault")
    context = _make_context(vault, session)

    suggestions = sentence_variance.suggest(context)

    assert [(s.text, s.notes) for s in suggestions] == [
        (
            "[[Choppy Note]] has unusually choppy sentences — short bursts mixed "
            "with long stretches. Were you working something out when you wrote this?",
            ["Choppy Note"],
        )
    ]


def test_sentence_variance_ignores_tables_headings_and_tight_lists(tmp_path):
    """Contract: table rows and headings are not sentences, and each list
    item is its own sentence.

    Regression: a markdown table (or a tight bullet list) was one 200-token
    "sentence", so a structured ledger had by far the largest raw variance
    and was named as "choppy" every session, ahead of genuinely choppy prose.
    """
    rows = "\n".join(
        f"| item {i} | specification section {i} | implemented and verified in release {i} |"
        for i in range(12)
    )
    bullets = "\n".join(f"- {UNIFORM_SENTENCE.format(word=w)[:-1]}" for w in _FILLER_WORDS)
    ledger = (
        "## Status\n\n"
        + " ".join([UNIFORM_SENTENCE.format(word="ledger")] * 4)
        + f"\n\n{rows}\n\n### Items\n{bullets}\n"
    )
    notes = _uniform_notes()
    notes["Choppy Note"] = _choppy_body()
    notes["Status Ledger"] = ledger
    vault, session = _build_vault(tmp_path / "vault", [notes])

    picked = {
        tuple(s.notes)
        for seed in range(10)
        for s in sentence_variance.suggest(_make_context(vault, session, seed=seed))
    }

    assert picked == {("Choppy Note",)}


def test_sentence_variance_samples_among_outliers(tmp_path):
    """Contract: when several notes are outliers, the session seed picks one.

    Regression: a fixed argmax named the same note every session.
    """
    notes = _uniform_notes()
    notes["Choppy Note"] = _choppy_body()
    notes["Halting Note"] = _choppy_body("Wait.")
    vault, session = _build_vault(tmp_path / "vault", [notes])

    picked = {
        tuple(s.notes)
        for seed in range(20)
        for s in sentence_variance.suggest(_make_context(vault, session, seed=seed))
    }

    assert picked == {("Choppy Note",), ("Halting Note",)}


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
    """A 20-note vault with no future-tense words triggers exactly that absence.

    3 past + 2 we + 3 question + 12 present fillers = 20 notes, none using
    'will' or 'going to'. Past and question voices are present, so only the
    future absence fires. (Updated: the text used to say "look forward",
    counting the near-unreachable "future" orientation; it now states what
    is counted.)
    """
    vault, session = _build_vault(
        tmp_path / "vault",
        [PAST_NOTES, WE_NOTES, QUESTION_NOTES, FILLER_NOTES],
    )
    context = _make_context(vault, session)
    assert len(vault.all_notes()) == 20

    suggestions = voice_absence.suggest(context)

    assert [(s.text, s.notes) for s in suggestions] == [
        (
            "Only 0 of your 20 notes use the future tense ('will', 'going to'). "
            "What are you anticipating that you haven't written about?",
            [],
        )
    ]


def test_voice_absence_counts_notes_that_use_each_voice_at_all(tmp_path):
    """Contract: "Only N of your T notes use the future tense / contain
    questions" counts notes with ANY future marker / question mark, and
    voice_absence never makes the "we" claim (self_and_other owns it).

    Regression: the future count was notes whose verbs were > 40% future
    (almost none), questions needed > 0.5 per 100 words, and "say 'we'"
    needed > 1 per 100 words, so a vault where notes do say "will", ask
    questions and say nothing about "we" got a false "Only 0 of your 20
    notes ..." sentence.
    """
    future_once = {f"Plan {i}": _long_prose("The gardener will rest after noon.") for i in range(2)}
    question_once = {f"Puzzle {i}": _long_prose("Why does the wall lean north?") for i in range(2)}
    fillers = dict(list(FILLER_NOTES.items())[:10])
    fillers.update({f"Extra {i}": _long_prose() for i in range(3)})
    vault, session = _build_vault(
        tmp_path / "vault", [PAST_NOTES, future_once, question_once, fillers]
    )
    context = _make_context(vault, session)
    assert len(context.notes()) == 20
    # Fixture sanity: the old thresholds counted none of these notes.
    assert not any(context.voice(n).temporal_orientation == "future" for n in context.notes())
    assert not any(context.voice(n).question_density > 0.5 for n in context.notes())

    assert voice_absence.suggest(context) == []


def test_voice_absence_names_exactly_one_of_several_absences(tmp_path):
    """With four voices missing, voice_absence still names exactly one."""
    vault, session = _build_voiceless_vault(tmp_path / "vault")
    context = _make_context(vault, session)

    suggestions = voice_absence.suggest(context)

    assert_valid_suggestions(suggestions, "voice_absence")
    assert len(suggestions) == 1
    assert suggestions[0].notes == []
    assert suggestions[0].text.startswith("Only 0 of your 20 notes")
