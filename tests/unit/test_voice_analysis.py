"""Tests for voice_analysis module (reflective lenses, Layer 1).

Known-answer tests, sad paths, Hypothesis property tests and hostile-input
fuzz cases for the pure-Python linguistic voice analysis.
"""

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.voice_analysis import (
    HEDGES,
    VOICE_METADATA_KEYS,
    compute_voice_metadata,
    count_hedges,
    split_sentences,
    strip_for_analysis,
    tokenize,
)

# Timeout all tests in this module (hostile inputs must stay bounded)
pytestmark = pytest.mark.timeout(30)


def assert_invariants(meta: dict) -> None:
    """Assert all range invariants hold and no value is NaN."""
    assert set(meta.keys()) == VOICE_METADATA_KEYS

    for key, value in meta.items():
        if key == "temporal_orientation":
            assert value in ("past", "present", "future", "mixed")
        else:
            assert isinstance(value, float), f"{key} is {type(value)}"
            assert not math.isnan(value), f"{key} is NaN"
            assert not math.isinf(value), f"{key} is infinite"

    assert 0.0 <= meta["past_tense_ratio"] <= 1.0
    assert 0.0 <= meta["future_tense_ratio"] <= 1.0
    assert 0.0 <= meta["present_tense_ratio"] <= 1.0
    assert 0.0 <= meta["self_focus_ratio"] <= 1.0
    assert 0.0 <= meta["lexical_diversity"] <= 1.0
    assert meta["first_person_singular"] >= 0.0
    assert meta["first_person_plural"] >= 0.0
    assert meta["second_person"] >= 0.0
    assert meta["hedging_ratio"] >= 0.0
    assert meta["question_density"] >= 0.0
    assert meta["modal_density"] >= 0.0
    assert meta["mean_sentence_length"] >= 0.0
    assert meta["sentence_length_variance"] >= 0.0

    # Tense ratios sum to ~1.0 when verbs present, or are all exactly 0.0
    tense_sum = meta["past_tense_ratio"] + meta["future_tense_ratio"] + meta["present_tense_ratio"]
    assert abs(tense_sum - 1.0) < 1e-9 or tense_sum == 0.0


# ============================================================================
# Known-answer tests
# ============================================================================


def test_past_tense_detection() -> None:
    """Regular -ed past tense dominates -> orientation 'past'."""
    meta = compute_voice_metadata("I walked to the store. I bought milk. I returned home.")
    assert meta["past_tense_ratio"] > 0.8
    assert meta["temporal_orientation"] == "past"
    assert meta["future_tense_ratio"] < 0.1
    assert_invariants(meta)


def test_irregular_past_tense() -> None:
    """Irregular verbs (no -ed suffix) must still register as past."""
    meta = compute_voice_metadata("I went home. I saw the error. I thought about it.")
    assert meta["past_tense_ratio"] > 0.6
    assert meta["temporal_orientation"] == "past"
    assert_invariants(meta)


def test_future_tense_detection() -> None:
    """'will' and 'going to' register as future."""
    meta = compute_voice_metadata(
        "Tomorrow I will plan the trip. We will pack early. I am going to enjoy it."
    )
    assert meta["future_tense_ratio"] > 0.4
    assert meta["temporal_orientation"] == "future"
    assert_invariants(meta)


def test_present_tense_detection() -> None:
    """Auxiliaries and -ing forms register as present."""
    meta = compute_voice_metadata(
        "The sky is blue. Birds are singing. Everything is humming along nicely."
    )
    assert meta["present_tense_ratio"] > 0.7
    assert meta["temporal_orientation"] == "present"
    assert_invariants(meta)


def test_hedging_detection() -> None:
    """Hedge words and phrases are detected."""
    meta = compute_voice_metadata("Maybe this works. Perhaps it doesn't. I think it might be okay.")
    assert meta["hedging_ratio"] > 0.5
    assert meta["modal_density"] > 0
    assert_invariants(meta)


def test_multiword_hedges_counted() -> None:
    """Multi-word hedges ('sort of', 'i think') match via the alternation."""
    assert count_hedges("It is sort of done. I think so. In a way, yes.") == 3
    assert count_hedges("Nothing tentative here at all.") == 0


def test_pronoun_patterns() -> None:
    """First-person plural note has low self-focus and zero singular."""
    meta = compute_voice_metadata("We built this together. Our team succeeded. We celebrated.")
    assert meta["first_person_plural"] > 3.0
    assert meta["self_focus_ratio"] < 0.3
    assert meta["first_person_singular"] == 0.0
    assert_invariants(meta)


def test_self_focused_pronouns() -> None:
    """First-person singular note has high self-focus."""
    meta = compute_voice_metadata("I wrote my thoughts. My ideas felt right to me.")
    assert meta["first_person_singular"] > 0.0
    assert meta["first_person_plural"] == 0.0
    assert meta["self_focus_ratio"] == 1.0
    assert_invariants(meta)


def test_question_density() -> None:
    """Question marks per 100 words."""
    meta = compute_voice_metadata("What is this? Why does it matter? How do we know?")
    assert meta["question_density"] > 1.0
    assert_invariants(meta)


def test_lexical_diversity_repeated_words() -> None:
    """Repeating a single word collapses lexical diversity."""
    meta = compute_voice_metadata("word word word word word word word word.")
    assert meta["lexical_diversity"] == pytest.approx(1 / 8)
    assert_invariants(meta)


def test_strip_for_analysis_removes_noise() -> None:
    """Code blocks, inline code, URLs and frontmatter are removed."""
    text = (
        "---\ntitle: Maybe a note\n---\n"
        "Real prose here.\n\n"
        "```python\nmaybe_function()\n```\n"
        "Inline `maybe_code` and a link https://example.com/maybe end.\n"
    )
    stripped = strip_for_analysis(text)
    assert "maybe_function" not in stripped
    assert "maybe_code" not in stripped
    assert "example.com" not in stripped
    assert "title" not in stripped  # frontmatter removed
    assert "Real prose here." in stripped
    # Hedge counting therefore sees no "maybe"
    assert count_hedges(text) == 0


def test_tokenize_keeps_contractions() -> None:
    """Contractions remain single tokens and tokens are lowercased."""
    tokens = tokenize("I Won't STOP")
    assert tokens == ["i", "won't", "stop"]


def test_split_sentences_basic() -> None:
    """Sentences split on terminal punctuation and blank lines."""
    sentences = split_sentences("One here. Two there! Three?\n\nFour paragraph")
    assert len(sentences) == 4


def test_hedges_frozenset_matches_spec() -> None:
    """HEDGES contains the spec's words and is a frozenset."""
    assert isinstance(HEDGES, frozenset)
    for hedge in ("maybe", "sort of", "i think", "presumably", "in a way"):
        assert hedge in HEDGES


# ============================================================================
# Sad paths and boundary values
# ============================================================================


@pytest.mark.parametrize(
    "content",
    [
        "",  # empty
        "   \n\t  \n",  # whitespace only
        "word",  # single word
        "blue sky tall tree",  # no verbs
        "word " * 500,  # one giant sentence (no terminal punctuation)
        "Why? How? When? Where? Who?",  # only questions
        "???",  # punctuation only
    ],
)
def test_sad_paths_never_raise(content: str) -> None:
    """Degenerate inputs produce valid metadata, no exceptions, no NaN."""
    meta = compute_voice_metadata(content)
    assert_invariants(meta)


def test_empty_note_defaults() -> None:
    """Empty content yields zeros, 'mixed' orientation, 0.5 self-focus."""
    meta = compute_voice_metadata("")
    assert meta["past_tense_ratio"] == 0.0
    assert meta["future_tense_ratio"] == 0.0
    assert meta["present_tense_ratio"] == 0.0
    assert meta["temporal_orientation"] == "mixed"
    assert meta["self_focus_ratio"] == 0.5
    assert meta["lexical_diversity"] == 0.0
    assert meta["mean_sentence_length"] == 0.0


def test_no_verbs_gives_zero_ratios() -> None:
    """A verb-free note has all-zero tense ratios (no division by zero)."""
    meta = compute_voice_metadata("blue sky tall tree quiet garden")
    assert meta["past_tense_ratio"] == 0.0
    assert meta["future_tense_ratio"] == 0.0
    assert meta["present_tense_ratio"] == 0.0
    assert meta["temporal_orientation"] == "mixed"


# ============================================================================
# Hostile-input fuzz cases (explicit examples)
# ============================================================================


@pytest.mark.parametrize(
    "content",
    [
        "🎉🎊🚀 ✨ 🤔💭",  # emoji
        "これはテストです。日本語のメモ。改行なしの長い文章です。",  # CJK
        "مرحبا بالعالم. هذه ملاحظة باللغة العربية.",  # RTL Arabic
        "famil‍y: 👩‍👩‍👧‍👦 join‍er",  # zero-width joiners
        "x" * 50_000,  # 50k-char single line
        "a maybe b " * 5_000,  # 50k chars with hedges
        "```\nouter\n```\ninner\n```\nstill\n```",  # nested/sequential code fences
        "```python\nunclosed fence",  # unclosed fence
        "---\nkey: value\n---\nbody\n---\nmore: yaml\n---\n",  # frontmatter-in-body
        "`unclosed inline span",  # unclosed inline code
        "\x00\x01\x02 control chars",  # control characters
    ],
)
def test_hostile_inputs_never_raise(content: str) -> None:
    """Hostile unicode and markdown edge cases never raise; invariants hold."""
    meta = compute_voice_metadata(content)
    assert_invariants(meta)


# ============================================================================
# Property-based tests (Hypothesis)
# ============================================================================


@given(st.text(max_size=5000))
@settings(max_examples=100, deadline=None)
def test_voice_metadata_total_function(content: str) -> None:
    """Never crashes, all ranges hold, tense ratios sum to ~1 or all-zero."""
    meta = compute_voice_metadata(content)
    assert_invariants(meta)


@given(st.text(max_size=2000))
@settings(max_examples=100, deadline=None)
def test_appending_hedge_never_decreases_hedging(content: str) -> None:
    """Metamorphic: adding ' Maybe it is.' adds at least one hedge."""
    before = count_hedges(content)
    after = count_hedges(content + " Maybe it is.")
    assert after >= before + 1


@given(st.text(max_size=2000))
@settings(max_examples=50, deadline=None)
def test_case_invariance(content: str) -> None:
    """Voice metadata is invariant under uppercasing of ASCII text."""
    # Restrict to ASCII to avoid unicode case-folding surprises (e.g. ß -> SS)
    ascii_content = content.encode("ascii", errors="ignore").decode("ascii")
    lower = compute_voice_metadata(ascii_content.lower())
    upper_then_lower = compute_voice_metadata(ascii_content.upper().lower())
    assert lower == upper_then_lower


@given(st.text(max_size=2000))
@settings(max_examples=50, deadline=None)
def test_tokenize_is_total_and_lowercase(content: str) -> None:
    """tokenize never raises and always returns lowercase tokens."""
    tokens = tokenize(content)
    assert isinstance(tokens, list)
    assert all(t == t.lower() for t in tokens)


@given(st.text(max_size=2000))
@settings(max_examples=50, deadline=None)
def test_split_sentences_total(content: str) -> None:
    """split_sentences never raises and returns non-empty fragments."""
    sentences = split_sentences(content)
    assert isinstance(sentences, list)
    assert all(s.strip() for s in sentences)
