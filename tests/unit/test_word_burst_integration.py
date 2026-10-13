"""Observable lexical sync/history/cache contracts and genuine geist firing."""

import json
from collections import Counter
from contextlib import closing
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.config_loader import ConfigError, GeistFabrikConfig
from geistfabrik.default_geists.code.word_burst import suggest
from geistfabrik.embeddings import Session
from geistfabrik.geist_executor import GeistExecutor
from geistfabrik.geist_status import GeistStatusStore
from geistfabrik.lexical_index import LexicalIndex, extract_terms
from geistfabrik.schema import migrate_schema
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


@pytest.mark.parametrize("private_tail", [False, True])
def test_large_episode_passes_executor_and_checks_evidence_beyond_output_limit(
    tmp_path, private_tail
):
    with closing(planted_vault(tmp_path)) as vault:
        original = (tmp_path / "note-8-0.md").read_bytes()
        for i in range(110):
            (tmp_path / f"copy-{i:03d}.md").write_bytes(original)
        if private_tail:
            (tmp_path / "z-private").mkdir()
            (tmp_path / "z-private/hidden.md").write_bytes(original)
            vault.config.filtering.exclude_paths = ["z-private/"]
        vault.sync()
        evidence = next(
            f for f in analyze_word_bursts(vault, end_day=date(2026, 3, 29)) if f.term == "aurora"
        )
        assert len(evidence.support_paths) > 100
        if private_tail:
            assert evidence.support_paths.index("z-private/hidden.md") >= 100
        status_store = GeistStatusStore(vault.db)
        executor = GeistExecutor(tmp_path / "geists", status_store=status_store)
        executor.register_geist("word_burst", Path(suggest.__code__.co_filename), suggest)
        with Session(datetime(2026, 3, 29), vault.db) as session:
            for _ in range(3):
                output = executor.execute_geist("word_burst", VaultContext(vault, session))
                assert bool(output) is not private_tail
                assert all(len(item.notes) <= 100 for item in output)
                assert executor.execution_log[-1]["status"] == "success"
        assert status_store.load() == {}


def test_file_exclusion_survives_journal_reclassification(tmp_path):
    source = tmp_path / "private-journal.md"
    source.write_text("---\ncreated: 2026-01-05\n---\nsecret aurora", encoding="utf-8")
    config = GeistFabrikConfig()
    config.lexical_analysis.exclude_paths = ["private*.md"]
    with closing(Vault(tmp_path, config=config)) as vault:
        vault.sync()
        assert vault.db.execute("SELECT counts_json FROM lexical_notes").fetchone()[0] == "{}"
        source.write_text(
            "## 2026-01-05\nsecret aurora\n## 2026-01-12\nsecret nebula", encoding="utf-8"
        )
        vault.sync()
        rows = vault.db.execute("SELECT path, counts_json FROM lexical_notes").fetchall()
        assert len(rows) == 2 and all(vector == "{}" for _, vector in rows)
        assert vault.db.execute("SELECT count(*) FROM lexical_terms").fetchone()[0] == 0
        source.write_text(source.read_text() + " comet", encoding="utf-8")
        vault.sync()
        assert vault.db.execute("SELECT count(*) FROM lexical_events").fetchone()[0] == 0


@pytest.mark.parametrize(
    "relative", [r"Templates\example.md", r"_geistfabrik\output.md", r"geist journal\2026-01-05.md"]
)
def test_windows_source_paths_obey_lexical_exclusions(tmp_path, relative):
    (tmp_path / "note.md").write_text("excludedsecret", encoding="utf-8")
    # Persist the native Windows spelling in the same DB input used by capture.
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        vault.db.execute("DELETE FROM lexical_notes")
        vault.db.execute("UPDATE notes SET path=?", (relative,))
        vault.db.commit()
        # Run capture inside its existing production ownership boundary.
        from geistfabrik.sqlite_transaction import owned_transaction

        with owned_transaction(vault.db, "Windows path capture"):
            index = LexicalIndex(vault.db, vault.config.lexical_analysis, datetime.now(UTC))
            row = vault.db.execute(
                "SELECT path,title,content,created,modified,is_virtual,source_file,entry_date "
                "FROM notes"
            ).fetchone()
            index.sync_note(vault._build_note_from_row(row, [], []))
        assert vault.db.execute("SELECT counts_json FROM lexical_notes").fetchone()[0] == "{}"


def test_skipped_source_does_not_tighten_observation_bound(tmp_path, monkeypatch):
    path = tmp_path / "note.md"
    path.write_text("soil", encoding="utf-8")
    with closing(Vault(tmp_path)) as vault:
        freeze(monkeypatch, 5)
        vault.sync()
        freeze(monkeypatch, 6)
        path.write_bytes(b"soil aurora\xff")
        assert vault.sync() == 0
        freeze(monkeypatch, 7)
        path.write_text("soil aurora", encoding="utf-8")
        vault.sync()
        previous, observed = vault.db.execute(
            "SELECT previous_at, observed_at FROM lexical_events"
        ).fetchone()
        assert previous.startswith("2026-01-05") and observed.startswith("2026-01-07")


def test_hardlinked_skipped_journal_cannot_borrow_another_sources_confirmation(
    tmp_path, monkeypatch
):
    source = tmp_path / "A.md"
    source.write_text("## 2026-01-05\nsoil\n## 2026-01-12\nhabitat", encoding="utf-8")
    (tmp_path / "B.md").hardlink_to(source)
    config = GeistFabrikConfig()
    config.date_collection.exclude_files = ["A.md"]
    with closing(Vault(tmp_path, config=config)) as vault:
        freeze(monkeypatch, 5)
        vault.sync()
        first = vault.db.execute(
            "SELECT value FROM lexical_meta WHERE key='last_sync_at'"
        ).fetchone()
        source.write_text("## 2026-01-05\nnovel\n" * 10001, encoding="utf-8")
        freeze(monkeypatch, 6)
        vault.sync()
        assert (
            vault.db.execute("SELECT value FROM lexical_meta WHERE key='last_sync_at'").fetchone()
            == first
        )
        ordinary = vault.get_note("A.md")
        skipped = vault.get_note("B.md/2026-01-05")
        assert ordinary is not None and ordinary.content.startswith("## 2026-01-05\nnovel")
        assert skipped is not None and skipped.content == "soil"


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
        vault.config.word_burst.history_mode = "observed_additions"
        early, late = WordBurstDiagnostics(), WordBurstDiagnostics()
        analyze_word_bursts(vault, end_day=date(2026, 1, 7), diagnostics=early)
        analyze_word_bursts(vault, end_day=date(2026, 1, 8), diagnostics=late)
        assert early.documents == 0 and late.documents == 1
        vault.config.lexical_analysis.ngram_max = 2
        vault.sync()
        assert vault.db.execute("SELECT count(*) FROM lexical_events").fetchone()[0] == 0
        path.unlink()
        vault.sync()
        assert vault.db.execute("SELECT count(*) FROM lexical_notes").fetchone()[0] == 0
        assert vault.db.execute("SELECT count(*) FROM lexical_terms").fetchone()[0] == 0


def test_same_timestamp_observations_still_capture_positive_changes(tmp_path, monkeypatch):
    path = tmp_path / "note.md"
    path.write_text("soil", encoding="utf-8")
    freeze(monkeypatch, 5)
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        path.write_text("soil aurora", encoding="utf-8")
        vault.sync()
        row = vault.db.execute("SELECT terms_json FROM lexical_events").fetchone()
        assert row is not None and json.loads(row[0]) == ["aurora"]


def test_edit_during_lexical_capture_is_retried_before_commit(tmp_path, monkeypatch):
    path = tmp_path / "note.md"
    path.write_text("soil", encoding="utf-8")
    original = LexicalIndex.finish
    changed = False

    def finish(index):
        nonlocal changed
        original(index)
        if not changed:
            path.write_text("aurora", encoding="utf-8")
            changed = True

    monkeypatch.setattr(LexicalIndex, "finish", finish)
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        note = vault.get_note("note.md")
        assert note is not None and note.content == "aurora"
        assert dict(vault.db.execute("SELECT term,documents FROM lexical_terms")) == {"aurora": 1}


def test_observation_timestamp_follows_source_reads(tmp_path, monkeypatch):
    (tmp_path / "note.md").write_text("soil", encoding="utf-8")

    class Clock(datetime):
        day = 11

        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, cls.day, 12, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr("geistfabrik.vault.datetime", Clock)
    original = Vault._sync_discovered_files

    def sync_sources(vault, files):
        Clock.day = 12
        return original(vault, files)

    monkeypatch.setattr(Vault, "_sync_discovered_files", sync_sources)
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        assert (
            vault.db.execute("SELECT observed_at FROM lexical_notes")
            .fetchone()[0]
            .startswith("2026-01-12")
        )


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


def test_duplicate_observations_preserve_episode_values_and_include_evidence_paths(tmp_path):
    with closing(planted_vault(tmp_path)) as vault:
        before = next(
            f for f in analyze_word_bursts(vault, end_day=date(2026, 3, 29)) if f.term == "aurora"
        )
        (tmp_path / "copy.md").write_bytes((tmp_path / "note-8-0.md").read_bytes())
        vault.sync()
        after = next(
            f for f in analyze_word_bursts(vault, end_day=date(2026, 3, 29)) if f.term == "aurora"
        )
        assert (after.rate, after.baseline_rate, after.gain, after.start, after.end) == (
            before.rate,
            before.baseline_rate,
            before.gain,
            before.start,
            before.end,
        )
        assert set(after.support_paths) == set(before.support_paths) | {"copy.md"}


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


@given(
    st.lists(
        st.tuples(
            st.integers(0, 3),
            st.one_of(
                st.none(), st.lists(st.sampled_from(["soil", "aurora", "habitat"]), max_size=12)
            ),
        ),
        max_size=30,
    )
)
@settings(max_examples=100, deadline=None)
def test_dictionary_document_counts_match_independent_edit_delete_model(actions):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        model: dict[int, list[str]] = {}
        with closing(Vault(root)) as vault:
            for i, words in actions:
                path = root / f"note-{i}.md"
                if words is None:
                    path.unlink(missing_ok=True)
                    model.pop(i, None)
                else:
                    path.write_text(" ".join(words), encoding="utf-8")
                    model[i] = words
                vault.sync()
                expected = Counter()
                for body in model.values():
                    expected.update(set(body))
                assert dict(vault.db.execute("SELECT term,documents FROM lexical_terms")) == dict(
                    expected
                )


@pytest.mark.parametrize("mode", ["dated_cohorts", "observed_additions"])
@pytest.mark.parametrize("cutoff", [date.min, date.max])
def test_calendar_boundary_cutoffs_abstain_without_overflow(tmp_path, mode, cutoff):
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        vault.config.word_burst.history_mode = mode
        assert analyze_word_bursts(vault, end_day=cutoff) == []


def test_schema_v10_upgrade_preserves_note_and_embedding_bytes(tmp_path):
    (tmp_path / "note.md").write_text("existing prose", encoding="utf-8")
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        vault.db.execute(
            "INSERT INTO embeddings VALUES ('note.md', ?, 'old', '2026-01-01')",
            (b"existing bytes",),
        )
        for table in (
            "lexical_events",
            "lexical_notes",
            "lexical_terms",
            "word_burst_cache",
            "lexical_meta",
        ):
            vault.db.execute(f"DROP TABLE {table}")
        vault.db.execute("PRAGMA user_version=10")
        vault.db.commit()
        migrate_schema(vault.db)
        assert vault.db.execute("PRAGMA user_version").fetchone()[0] == 11
        assert (
            vault.db.execute("SELECT content FROM notes WHERE path='note.md'").fetchone()[0]
            == "existing prose"
        )
        assert (
            vault.db.execute(
                "SELECT embedding FROM embeddings WHERE note_path='note.md'"
            ).fetchone()[0]
            == b"existing bytes"
        )
        vault.sync()
        assert dict(vault.db.execute("SELECT term,documents FROM lexical_terms")) == {
            "existing": 1,
            "prose": 1,
        }
