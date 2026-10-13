"""Observable lexical sync/history/cache contracts and genuine geist firing."""

import json
from collections import Counter
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.config_loader import ConfigError, GeistFabrikConfig
from geistfabrik.default_geists.code.word_burst import suggest
from geistfabrik.embeddings import Session
from geistfabrik.lexical_index import extract_terms
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext
from geistfabrik.word_burst_analysis import WordBurstDiagnostics, analyze_word_bursts


def word(number: int) -> str:
    return "identity" + chr(97 + number // 26) + chr(97 + number % 26)


def planted_vault(root: Path) -> Vault:
    start = date(2026, 1, 5)
    for week in range(12):
        for i in range(10):
            body = f"soil habitat {word(week * 10 + i)}"
            if week in (8, 9) and i < 6:
                body += " aurora"
            (root / f"note-{week}-{i}.md").write_text(
                f"---\ncreated: {start + timedelta(weeks=week)}\n---\n{body}", encoding="utf-8"
            )
    vault = Vault(root)
    vault.sync()
    return vault


def test_geist_fires_with_all_supporting_links_and_honest_population(tmp_path):
    with closing(planted_vault(tmp_path)) as vault:
        with Session(datetime(2026, 3, 29), vault.db) as session:
            output = suggest(VaultContext(vault, session))
        aurora = [item for item in output if "‘aurora’" in item.text]
        assert len(aurora) == 1
        assert len(aurora[0].notes) == 12
        assert "current text grouped by declared dates" in aurora[0].text
        assert "60%" in aurora[0].text


def test_cache_invalidates_on_exposure_and_obeys_exact_cutoffs(tmp_path):
    with closing(planted_vault(tmp_path)) as vault:
        old = analyze_word_bursts(vault, end_day=date(2026, 3, 29))
        stats = WordBurstDiagnostics()
        assert analyze_word_bursts(vault, end_day=date(2026, 3, 29), diagnostics=stats) == old
        assert stats.cache_hit
        assert analyze_word_bursts(vault, end_day=date(2026, 2, 1)) == []
        (tmp_path / "background.md").write_text(
            "---\ncreated: 2026-03-02\n---\nsoil control", encoding="utf-8"
        )
        vault.sync()
        stats = WordBurstDiagnostics()
        new = analyze_word_bursts(vault, end_day=date(2026, 3, 29), diagnostics=stats)
        assert not stats.cache_hit
        before = next(f for f in old if f.term == "aurora")
        after = next(f for f in new if f.term == "aurora")
        assert after.rate < before.rate


def test_declared_cohorts_exclude_filesystem_estimates_and_duplicate_bodies(tmp_path):
    for i in range(80):
        (tmp_path / f"{i}.md").write_text("undated identical prose", encoding="utf-8")
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        stats = WordBurstDiagnostics()
        assert analyze_word_bursts(vault, end_day=date(2026, 10, 13), diagnostics=stats) == []
        assert stats.documents == 0
        for i in range(80):
            (tmp_path / f"{i}.md").write_text(
                "---\ncreated: 2026-10-05\n---\nidentical prose", encoding="utf-8"
            )
        vault.sync()
        stats = WordBurstDiagnostics()
        assert analyze_word_bursts(vault, end_day=date(2026, 10, 13), diagnostics=stats) == []
        assert stats.documents == 1


def freeze(monkeypatch, day: int):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, day, 12, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr("geistfabrik.vault.datetime", Clock)


def test_observed_history_bootstrap_bounds_union_deletion_and_policy_reset(tmp_path, monkeypatch):
    path = tmp_path / "note.md"
    path.write_text("soil", encoding="utf-8")
    with closing(Vault(tmp_path)) as vault:
        freeze(monkeypatch, 5)
        vault.sync()
        assert vault.db.execute("SELECT count(*) FROM lexical_events").fetchone()[0] == 0
        freeze(monkeypatch, 6)
        vault.sync()  # Last confirmed unchanged observation tightens the lower bound.
        freeze(monkeypatch, 7)
        path.write_text("soil aurora", encoding="utf-8")
        vault.sync()
        freeze(monkeypatch, 8)
        path.write_text("soil nebula", encoding="utf-8")
        vault.sync()
        event = vault.db.execute(
            "SELECT terms_json, previous_at, observed_at FROM lexical_events"
        ).fetchone()
        assert set(json.loads(event[0])) == {"aurora", "nebula"}
        assert event[1].startswith("2026-01-06")
        assert event[2].startswith("2026-01-08")
        vault.config.lexical_analysis.ngram_max = 2
        vault.sync()
        assert vault.db.execute("SELECT count(*) FROM lexical_events").fetchone()[0] == 0
        path.unlink()
        vault.sync()
        assert vault.db.execute("SELECT count(*) FROM lexical_notes").fetchone()[0] == 0
        assert vault.db.execute("SELECT count(*) FROM lexical_terms").fetchone()[0] == 0


def test_failed_sync_rolls_back_lexical_capture_and_dictionary(tmp_path, monkeypatch):
    path = tmp_path / "note.md"
    path.write_text("soil", encoding="utf-8")
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        before = list(vault.db.execute("SELECT * FROM lexical_notes"))
        path.write_text("nebula", encoding="utf-8")

        def fail(_self):
            raise RuntimeError("capture failed")

        monkeypatch.setattr("geistfabrik.lexical_index.LexicalIndex.finish", fail)
        with pytest.raises(RuntimeError, match="capture failed"):
            vault.sync()
        assert list(vault.db.execute("SELECT * FROM lexical_notes")) == before
        assert list(vault.db.execute("SELECT term, documents FROM lexical_terms")) == [("soil", 1)]
        note = vault.get_note("note.md")
        assert note is not None and note.content == "soil"


def test_unchanged_sync_and_cached_analysis_do_not_extract_or_decode(tmp_path, monkeypatch):
    with closing(planted_vault(tmp_path)) as vault:
        expected = analyze_word_bursts(vault, end_day=date(2026, 3, 29))
        assert expected

        def forbidden(*args, **kwargs):
            raise AssertionError("unexpected recomputation")

        monkeypatch.setattr("geistfabrik.lexical_index.extract_terms", forbidden)
        monkeypatch.setattr("geistfabrik.word_burst_analysis.detect_bursts", forbidden)
        vault.sync()
        assert analyze_word_bursts(vault, end_day=date(2026, 3, 29)) == expected


def test_code_only_edit_preserves_cache_but_prose_edit_changes_dictionary(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("soil\n```\none\n```", encoding="utf-8")
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        generation = vault.db.execute(
            "SELECT value FROM lexical_meta WHERE key='generation'"
        ).fetchone()
        path.write_text("soil\n```\ntwo\n```", encoding="utf-8")
        vault.sync()
        assert (
            vault.db.execute("SELECT value FROM lexical_meta WHERE key='generation'").fetchone()
            == generation
        )
        path.write_text("soil soil aurora", encoding="utf-8")
        vault.sync()
        assert dict(vault.db.execute("SELECT term,documents FROM lexical_terms")) == {
            "soil": 1,
            "aurora": 1,
        }
        assert json.loads(
            vault.db.execute("SELECT counts_json FROM lexical_notes").fetchone()[0]
        ) == {"soil": 2, "aurora": 1}


def test_completed_and_partial_week_flags(tmp_path):
    with closing(planted_vault(tmp_path)) as vault:
        completed = analyze_word_bursts(vault, end_day=date(2026, 3, 15))
        partial = analyze_word_bursts(vault, end_day=date(2026, 3, 12))
        assert not next(f for f in completed if f.term == "aurora").provisional
        assert next(f for f in partial if f.term == "aurora").provisional


@given(
    st.lists(st.sampled_from(["soil", "aurora", "café", "can't"]), max_size=100), st.integers(1, 3)
)
@settings(max_examples=1000)
def test_extraction_matches_independent_sliding_windows(words, maximum):
    expected = Counter()
    for width in range(1, maximum + 1):
        expected.update(" ".join(words[i : i + width]) for i in range(len(words) - width + 1))
    assert extract_terms(" ".join(words).upper(), ngram_max=maximum) == expected


def test_markdown_regions_and_phrase_boundaries():
    content = (
        "---\ntitle: excluded\n---\nsoil `code` habitat\n> quoted\n"
        "```\nfenced\n```\n    indented\ncafé https://example.com/path nebula\n"
    )
    assert extract_terms(content, ngram_max=2) == Counter(
        {"soil": 1, "habitat": 1, "café": 1, "nebula": 1}
    )


@pytest.mark.parametrize("hidden", ["<!--\nsecret\n-->", "``secret ` code``"])
def test_hidden_multiline_comments_and_nested_backticks_are_excluded(hidden):
    assert extract_terms(f"before {hidden} after") == Counter({"before": 1, "after": 1})


@pytest.mark.parametrize(
    "section,field,value",
    [
        ("word_burst", "s", 1),
        ("word_burst", "gamma", True),
        ("word_burst", "max_states", 0),
        ("lexical_analysis", "ngram_max", 4),
        ("lexical_analysis", "enabled", 1),
        ("word_burst", "history_mode", "git"),
    ],
)
def test_new_config_sections_reject_invalid_values(section, field, value):
    with pytest.raises(ConfigError):
        GeistFabrikConfig.from_dict({section: {field: value}})
