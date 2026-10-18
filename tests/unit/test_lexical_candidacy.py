"""Question eligibility is bounded presentation policy, never a corpus filter."""

import unicodedata
from contextlib import closing
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from geistfabrik.config_loader import GeistFabrikConfig
from geistfabrik.default_geists.code.word_burst import suggest
from geistfabrik.embeddings import Session
from geistfabrik.lexical_candidacy import ENGLISH_FUNCTION_WORDS, is_question_lens
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext
from geistfabrik.word_burst_analysis import analyze_word_bursts


@pytest.mark.parametrize(
    "term",
    [
        "of",
        "of a",
        "for",
        "but",
        "with",
        "without",
        "under",
        "our",
        "ours",
        "they are",
        "isn't",
        "IT’S",
        "we’re",
        "because of the",
        "ＯＦ Ａ",
        "ſo",
        "",
        " ",
        "...",
        "of-a",
        "of.a",
        "theory. of mind",
        "mind\nrepair",
        "mind\u2028repair",
        "mind\u2029repair",
        "mind\rrepair",
        "mind\vrepair",
        "mind\frepair",
        "mind\x85repair",
        "mind\x00repair",
        "mind_thing",
        "123",
        "\u0301",
        "four content words here",
        "a" * 101,
    ],
)
def test_grammatical_or_nonlexical_expressions_are_not_question_lenses(term: str) -> None:
    assert not is_question_lens(term)


@pytest.mark.parametrize(
    "term",
    [
        "theory of mind",
        "repair cafe",
        "supported practice",
        "without prejudice",
        "of interest",
        "the system",
        "fire",
        "bill",
        "detail",
        "interest",
        "system",
        "offer",
        "format",
        "otherworldly",
        "understand",
        "together",
        "aurora",
        "quasar",
        "café",
        "cafe\u0301",
        "naïve",
        "Straße",
        "İstanbul",
        "東京",
        "नमस्ते",
        "don't panic",
        "worker’s rights",
        "de la",
        "ＭＩＮＤ",
        "x" * 100,
    ],
)
def test_content_words_and_phrases_remain_eligible(term: str) -> None:
    assert is_question_lens(term)


def _fullwidth(value: str) -> str:
    return "".join(
        chr(ord(character) + 0xFEE0) if "!" <= character <= "~" else character
        for character in value
    )


@given(
    words=st.lists(st.sampled_from(sorted(ENGLISH_FUNCTION_WORDS)), min_size=1, max_size=3),
    style=st.integers(min_value=0, max_value=3),
)
def test_grammatical_sequences_stay_ineligible_under_case_and_compatibility_forms(
    words: list[str], style: int
) -> None:
    phrase = " ".join(words)
    variant = [phrase, phrase.upper(), phrase.title(), _fullwidth(phrase)][style]
    assert not is_question_lens(variant)


@given(
    suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=12),
    surround=st.lists(st.sampled_from(sorted(ENGLISH_FUNCTION_WORDS)), max_size=2),
    insertion=st.integers(min_value=0, max_value=2),
)
def test_a_content_token_is_not_lost_to_grammatical_substring_or_surrounding_words(
    suffix: str, surround: list[str], insertion: int
) -> None:
    # A generated unfamiliar lexical word should fail open; grammatical prefixes
    # and suffixes do not justify a substring-based exclusion.
    content = "offerlexeme" + suffix + "with"
    words = list(surround)
    words.insert(min(insertion, len(words)), content)
    phrase = " ".join(words)
    assert is_question_lens(phrase)
    assert is_question_lens(_fullwidth(phrase.upper()))


@given(term=st.sampled_from(["café", "Straße", "İstanbul", "नमस्ते", "東京"]))
def test_eligible_unicode_terms_keep_casefold_and_normalization_equivalence(term: str) -> None:
    assert is_question_lens(term)
    assert is_question_lens(unicodedata.normalize("NFKD", term).upper())
    assert is_question_lens(unicodedata.normalize("NFKC", term.casefold()))


@pytest.fixture
def burst_vault(tmp_path: Path):
    """Real analysis contains grammatical and content episodes on the same text."""
    start = date(2026, 1, 5)
    for week in range(12):
        for index in range(10):
            identity = f"identity{chr(97 + week)}{chr(97 + index)}"
            body = f"soil habitat {identity}"
            if week in (8, 9) and index < 6:
                body += " of a theory of mind"
            (tmp_path / f"note-{week}-{index}.md").write_text(
                f"---\ncreated: {start + timedelta(weeks=week)}\n---\n{body}", encoding="utf-8"
            )
    config = GeistFabrikConfig()
    config.lexical_analysis.ngram_max = 3
    with closing(Vault(tmp_path, config=config)) as vault:
        vault.sync()
        yield vault


def test_question_gate_leaves_dictionary_counts_and_all_model_episodes_unchanged(burst_vault):
    vault = burst_vault
    findings = analyze_word_bursts(vault, end_day=date(2026, 3, 29))
    assert {"of", "of a", "theory of mind"} <= {finding.term for finding in findings}
    exact_dictionary = vault.db.execute(
        "SELECT term,documents FROM lexical_terms ORDER BY term"
    ).fetchall()
    all_evidence = [finding.to_dict() for finding in findings]
    with Session(datetime(2026, 3, 29), vault.db) as session:
        output = suggest(VaultContext(vault, session))
    assert output
    assert any("‘theory of mind’" in item.text for item in output)
    assert all("‘of a’" not in item.text and "‘of’" not in item.text for item in output)
    assert (
        vault.db.execute("SELECT term,documents FROM lexical_terms ORDER BY term").fetchall()
        == exact_dictionary
    )
    assert [
        finding.to_dict() for finding in analyze_word_bursts(vault, end_day=date(2026, 3, 29))
    ] == all_evidence


@pytest.mark.parametrize("direction", ["rising", "declining"])
def test_candidacy_runs_before_grouping_and_sampling_in_both_directions(
    burst_vault, monkeypatch: pytest.MonkeyPatch, direction: str
) -> None:
    vault = burst_vault
    original = next(
        finding
        for finding in analyze_word_bursts(vault, end_day=date(2026, 3, 29))
        if finding.term == "theory of mind"
    )
    # A one-question budget makes every ineligible sampled invitation observable.
    vault.config.word_burst.max_suggestions = 1
    findings = [
        replace(
            original,
            term=term,
            direction=direction,
            reference=original.baseline,
            reference_start="2026-01-05",
            reference_end="2026-03-01",
        )
        for term in ["of", "of a", "for", "but", "with", "theory of mind"]
    ]
    with Session(datetime(2026, 3, 29), vault.db) as session:
        context = VaultContext(vault, session)
        monkeypatch.setattr(context, "word_bursts", lambda: findings)
        output = suggest(context)
    assert len(output) == 1
    assert "‘theory of mind’" in output[0].text
    assert ("earlier period" in output[0].text) is (direction == "declining")


def test_only_grammatical_episodes_abstain_without_reading_sources(
    burst_vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault = burst_vault
    original = next(iter(analyze_word_bursts(vault, end_day=date(2026, 3, 29))))
    with Session(datetime(2026, 3, 29), vault.db) as session:
        context = VaultContext(vault, session)
        monkeypatch.setattr(context, "word_bursts", lambda: [replace(original, term="of a")])

        def no_source_read(path: str):
            pytest.fail(f"An ineligible episode read its source: {path}")

        monkeypatch.setattr(context, "get_note", no_source_read)
        assert suggest(context) == []
        assert "content-bearing word or phrase" in context.execution_diagnostics["word_burst"]
