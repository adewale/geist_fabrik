"""Observable lexical sync/history/cache contracts and genuine geist firing."""

import json
import os
import time
import unicodedata
from collections import Counter
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.config_loader import ConfigError, GeistFabrikConfig
from geistfabrik.default_geists.code.word_burst import suggest
from geistfabrik.document_rate import DocumentRate
from geistfabrik.embeddings import EmbeddingComputer, Session
from geistfabrik.evidence_identity import interval_evidence_key
from geistfabrik.filtering import SuggestionFilter
from geistfabrik.geist_executor import GeistExecutor
from geistfabrik.geist_status import GeistStatusStore
from geistfabrik.journal_writer import JournalWriter
from geistfabrik.lexical_index import LexicalIndex, extract_terms, lexical_excerpt
from geistfabrik.models import Suggestion
from geistfabrik.schema import SCHEMA_VERSION, migrate_schema
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


@pytest.mark.parametrize("direction", ["rising", "declining"])
def test_geist_rendering_preserves_small_exact_prevalence_changes(tmp_path, monkeypatch, direction):
    """Renderer transport, independent of the detector's existing likelihood proof."""
    with closing(planted_vault(tmp_path)) as vault:
        finding = next(
            f for f in analyze_word_bursts(vault, end_day=date(2026, 3, 29)) if f.term == "aurora"
        )
        finding = replace(
            finding,
            direction=direction,
            prevalence=DocumentRate(5000, 10000)
            if direction == "rising"
            else DocumentRate(4999, 10000),
            baseline=DocumentRate(9999, 20000),
            reference=DocumentRate(1, 2),
            reference_start="2026-01-05",
            reference_end="2026-03-01",
        )
        with Session(datetime(2026, 3, 29), vault.db) as session:
            context = VaultContext(vault, session)
            monkeypatch.setattr(context, "word_bursts", lambda: [finding])
            output = suggest(context)
        assert len(output) == 1
        if direction == "rising":
            assert "50% of observations, compared with 49.995% across" in output[0].text
        else:
            assert "49.99% of observations, compared with 50% during" in output[0].text


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
        assert set(json.loads(event[0])) == {"aurora", "nebula", "soil aurora", "soil nebula"}
        assert event[1].startswith("2026-01-06")
        assert event[2].startswith("2026-01-08")
        vault.config.word_burst.history_mode = "observed_additions"
        early, late = WordBurstDiagnostics(), WordBurstDiagnostics()
        analyze_word_bursts(vault, end_day=date(2026, 1, 7), diagnostics=early)
        analyze_word_bursts(vault, end_day=date(2026, 1, 8), diagnostics=late)
        assert early.documents == 0 and late.documents == 1
        vault.config.lexical_analysis.ngram_max = 3
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
        assert row is not None and json.loads(row[0]) == ["aurora", "soil aurora"]


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
        vault.sync()
        stats = WordBurstDiagnostics()
        assert analyze_word_bursts(vault, end_day=date(2026, 3, 29), diagnostics=stats) == expected
        assert stats.cache_hit and stats.decoded == 0


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
            "soil soil": 1,
            "soil aurora": 1,
        }
        assert json.loads(
            vault.db.execute("SELECT counts_json FROM lexical_notes").fetchone()[0]
        ) == {"soil": 2, "aurora": 1, "soil soil": 1, "soil aurora": 1}


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
    st.lists(
        st.sampled_from(["soil", "aurora", "café", "can't", "İstanbul", "ǰ", "ΐ", "किताब"]),
        max_size=100,
    ),
    st.integers(1, 3),
)
@settings(max_examples=1000, deadline=None)
def test_extraction_matches_independent_sliding_windows(words, maximum):
    words = [unicodedata.normalize("NFKC", word.casefold()) for word in words]
    expected = Counter()
    for width in range(1, maximum + 1):
        expected.update(" ".join(words[i : i + width]) for i in range(len(words) - width + 1))
    content = " ".join(words).upper()
    assert extract_terms(content, ngram_max=maximum) == expected


def test_markdown_regions_and_phrase_boundaries():
    content = (
        "---\ntitle: excluded\n---\nsoil `code` habitat\n> quoted\n"
        "```\nfenced\n```\n    indented\ncafé https://example.com/path nebula\n"
    )
    assert extract_terms(content, ngram_max=2) == Counter(
        {"soil": 1, "habitat": 1, "café": 1, "nebula": 1}
    )


@pytest.mark.parametrize(
    "content",
    [
        "    <!--\n    hide\n    --> phantom",
        "    <!--\n    --> [visible](secret)",
        "```\n<!--\n--> phantom\n```",
    ],
)
def test_hidden_comments_cannot_admit_code_as_visible_prose(content):
    assert extract_terms(content) == Counter()
    assert lexical_excerpt(content, "phantom") is None


def test_comment_contents_cannot_start_a_fence_or_admit_frontmatter():
    assert extract_terms("<!--\n```\n-->\nvisible") == Counter({"visible": 1})
    assert extract_terms("---\rtitle: hidden\r---\rvisible") == Counter({"visible": 1})


@given(prefix=st.sampled_from(["", "- ", "1. ", "- - ", "1. - "]), quote=st.booleans())
def test_parser_owned_blockquotes_respect_the_quote_policy(prefix, quote):
    content = prefix + "> quotedphantom [visible](secret)\n\nordinary"
    expected = Counter({"ordinary": 1})
    if quote:
        expected.update({"quotedphantom": 1, "visible": 1})
    assert extract_terms(content, include_quotes=quote) == expected


@pytest.mark.parametrize("footnote", [False, True])
@pytest.mark.parametrize(
    "link,definition",
    [
        (
            "[Visible guide][hiddenreference]",
            '[hiddenreference]: https://example.com "Secret title"',
        ),
        ("[Visible guide][]", "[visible guide]: https://example.com"),
        ("[Visible guide]", "[visible guide]:\n  <https://example.com>\n  'Secret title'"),
        ("[Visible guide][HIDDENREFERENCE]", "> [hiddenreference]: https://example.com"),
        (r"[Visible \[guide\]][hiddenreference]", "[hiddenreference]: https://example.com"),
        ("![Visible guide][hiddenreference]", "[hiddenreference]: https://example.com"),
        ("[Visible guide][secret`code`id]", "[secret`code`id]: /hidden"),
        ("[Visible guide][secret<!-- hidden -->id]", "[secret<!-- hidden -->id]: /hidden"),
        ('[Visible guide](path "secret) hidden")', ""),
        ("[Visible guide](https://example.com/path(secret)hidden)", ""),
        ('[Visible guide](\n /hidden\n "secret title"\n)', ""),
        ('![Visible guide](path "secret) hidden")', ""),
    ],
)
def test_reference_links_keep_only_visible_prose_and_excerpts(link, definition, footnote):
    content = ("[^1]: " if footnote else "") + f"Read {link}.\n\n{definition}"
    assert extract_terms(content, ngram_max=2) == Counter(
        {"read": 1, "visible": 1, "guide": 1, "read visible": 1, "visible guide": 1}
    )
    assert lexical_excerpt(content, "hiddenreference") is None
    assert lexical_excerpt(content, "secret") is None
    assert lexical_excerpt(content, "visible guide") == (
        "Read Visible [guide" if "\\[" in link else "Read Visible guide"
    )


@pytest.mark.parametrize("image", ["", "!"])
def test_reference_only_footnote_retains_visible_body(image):
    content = f"[^1]: {image}[visible][hiddenid]\n\n[hiddenid]: /secret"
    assert extract_terms(content) == Counter({"visible": 1})
    assert lexical_excerpt(content, "hiddenid") is None


@given(
    words=st.lists(
        st.sampled_from(["soil", "café", "habitat", "nebula", "İstanbul", "ǰ", "ΐ"]),
        min_size=1,
        max_size=15,
    ),
    form=st.sampled_from(["full", "collapsed", "shortcut"]),
    first=st.booleans(),
    separate=st.booleans(),
    maximum=st.integers(1, 3),
)
@settings(max_examples=200, deadline=None)
def test_reference_prose_matches_visible_word_windows(words, form, first, separate, maximum):
    links, definitions = [], []
    for visible in words if separate else [" ".join(words)]:
        identifier = "hiddenreference" if form == "full" else visible
        links.append(
            f"[{visible}]"
            + (f"[{identifier}]" if form == "full" else "[]" if form == "collapsed" else "")
        )
        definitions.append(
            f'[{identifier.upper()}]:\n  <https://example.com/hiddendestination>\n  "Hidden title"'
        )
    link, definition = " ".join(links), "\n\n".join(definitions)
    content = definition + "\n\n" + link if first else link + "\n\n" + definition
    words = [unicodedata.normalize("NFKC", word.casefold()) for word in words]
    expected = Counter(
        " ".join(words[i : i + width])
        for width in range(1, maximum + 1)
        for i in range(len(words) - width + 1)
    )
    assert extract_terms(content, ngram_max=maximum) == expected
    assert all(lexical_excerpt(content, term) is not None for term in expected)


@pytest.mark.parametrize(
    "content",
    [
        "visible\n    hidden code",
        "visible\u2028other",
        "small &amp; reversible",
        "<section>\nvisible prose\n</section>",
        "before [[target|visible]] after",
        "[^footnote]: soil",
    ],
)
def test_unused_reference_definition_preserves_other_prose_boundaries(content):
    assert extract_terms(content + "\n\n[unused]: /destination", ngram_max=3) == extract_terms(
        content, ngram_max=3
    )


def test_reference_definition_cannot_capture_a_wikilink_alias():
    content = "before [[target|visible]] after\n\n[target|visible]: /destination"
    assert extract_terms(content) == Counter({"before": 1, "visible": 1, "after": 1})
    assert lexical_excerpt(content, "target") is None


@pytest.mark.parametrize("boundary", ["\n\n", "\n```\nhidden code\n```\n", "\n# Heading\n"])
def test_reference_recognition_cannot_cross_block_boundaries(boundary):
    content = f"[visible{boundary}other][hiddenid]\n\n[hiddenid]: /destination"
    expected = Counter({"visible": 1, "other": 1, "hiddenid": 1})
    if "Heading" in boundary:
        expected["heading"] = 1
    assert extract_terms(content) == expected


@pytest.mark.parametrize("separator", ["\n", "\r\n", "\r", "\n\r"])
@pytest.mark.parametrize("prefix", ["", "\x00"])
def test_reference_source_mapping_preserves_line_endings_and_nulls(separator, prefix):
    content = prefix + "[visible][hiddenid]" + separator * 2 + "[hiddenid]: /destination"
    assert extract_terms(content) == Counter({"visible": 1})


@pytest.mark.parametrize("indent", ["  ", "\t", " \t", "\t "])
def test_reference_list_indentation_cannot_introduce_hidden_vocabulary(indent):
    content = f"- [visible][secret]\n{indent}continuation\n\n[secret]: /hidden"
    assert extract_terms(content, ngram_max=2) == Counter(
        {"visible": 1, **({"continuation": 1} if indent == "  " else {})}
    )
    assert lexical_excerpt(content, "secret") is None


@pytest.mark.parametrize("word", ["İstanbul", "ǰ", "ΐ", "a\u0307", "किताब"])
def test_unicode_words_have_identical_count_and_excerpt_boundaries(word):
    normalized = unicodedata.normalize("NFKC", unicodedata.normalize("NFKC", word).casefold())
    assert extract_terms(word + " orchards", ngram_max=2) == Counter(
        {normalized: 1, "orchards": 1, normalized + " orchards": 1}
    )
    assert lexical_excerpt(word + " orchards", normalized + " orchards") is not None


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="host timezone probe needs POSIX tzset")
def test_declared_calendar_cohort_is_independent_of_host_timezone(tmp_path):
    previous = os.environ.get("TZ")
    try:
        for zone in ("UTC", "Europe/Helsinki", "America/Los_Angeles"):
            os.environ["TZ"] = zone
            time.tzset()
            root = tmp_path / zone.replace("/", "_")
            root.mkdir()
            (root / "note.md").write_text("---\ncreated: 2026-01-05T00:30:00+02:00\n---\norchards")
            with closing(Vault(root)) as vault:
                vault.sync()
                assert vault.db.execute("SELECT cohort_day FROM lexical_notes").fetchone() == (
                    "2026-01-05",
                )
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        time.tzset()


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
    actions=st.lists(
        st.tuples(
            st.integers(0, 3),
            st.one_of(
                st.none(), st.lists(st.sampled_from(["soil", "aurora", "habitat"]), max_size=12)
            ),
        ),
        max_size=30,
    ),
    maximum=st.integers(1, 3),
)
@settings(max_examples=100, deadline=None)
def test_dictionary_document_counts_match_independent_edit_delete_model(actions, maximum):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        model: dict[int, list[str]] = {}
        config = GeistFabrikConfig()
        config.lexical_analysis.ngram_max = maximum
        with closing(Vault(root, config=config)) as vault:
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
                    expected.update(
                        {
                            " ".join(body[i : i + width])
                            for width in range(1, maximum + 1)
                            for i in range(len(body) - width + 1)
                        }
                    )
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
        assert vault.db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
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
            "existing prose": 1,
        }


@pytest.mark.parametrize("mode", ["dated_cohorts", "observed_additions"])
def test_one_geist_reports_rising_and_disappearing_phrases_through_real_history(
    tmp_path, monkeypatch, mode
):
    start = date(2026, 1, 5)
    for week in range(12):
        for i in range(10):
            (tmp_path / f"note-{week}-{i}.md").write_text(
                f"---\ncreated: {start + timedelta(weeks=week)}\n---\n{word(week * 10 + i)}\n"
            )
    config = GeistFabrikConfig()
    config.lexical_analysis.ngram_max = 3
    with closing(Vault(tmp_path, config=config)) as vault:
        freeze(monkeypatch, 1)
        vault.sync()  # Discovery never fabricates additions.
        for week in range(12):
            observed = datetime.combine(start + timedelta(weeks=week), datetime.min.time(), UTC)

            class Clock(datetime):
                @classmethod
                def now(cls, tz=None):
                    return observed.astimezone(tz)

            monkeypatch.setattr("geistfabrik.vault.datetime", Clock)
            for i in range(10):
                phrase = (
                    "small reversible experiments"
                    if week < 4 and i < 6
                    else "deliberate commitments"
                    if week >= 8 and i < 6
                    else "steady background"
                )
                path = tmp_path / f"note-{week}-{i}.md"
                path.write_text(path.read_text() + phrase)
            vault.sync()
        vault.config.word_burst.history_mode = mode
        if mode == "observed_additions":
            for path in tmp_path.glob("note-*.md"):
                path.write_text(path.read_text().replace("small reversible experiments", ""))
            vault.sync()
            assert (
                vault.db.execute(
                    "SELECT documents FROM lexical_terms WHERE term='small reversible experiments'"
                ).fetchone()
                is None
            )
        findings = analyze_word_bursts(vault, end_day=date(2026, 3, 29))
        decline = next(
            f
            for f in findings
            if f.term == "small reversible experiments" and f.direction == "declining"
        )
        assert (decline.start, decline.end, decline.rate, decline.reference_rate) == (
            "2026-02-02",
            "2026-03-29",
            0,
            0.6,
        )
        assert len(decline.support_paths) == 24
        assert any(f.term == "deliberate commitments" and f.direction == "rising" for f in findings)
        executor = GeistExecutor(tmp_path / "geists", status_store=GeistStatusStore(vault.db))
        executor.register_geist("word_burst", Path(suggest.__code__.co_filename), suggest)
        with Session(datetime(2026, 3, 29), vault.db) as session:
            output = executor.execute_geist("word_burst", VaultContext(vault, session))
        assert executor.execution_log[-1]["status"] == "success"
        assert any(
            "earlier period" in item.text and "small reversible experiments" in item.text
            for item in output
        )
        assert any(
            "deliberate commitments" in item.text and "across the window" in item.text
            for item in output
        )
        assert all(item.evidence_key is not None for item in output)


@pytest.mark.parametrize("separator", ["\n", ". ", "! ", "? ", "; ", " `hidden` "])
def test_phrase_extraction_and_excerpts_cannot_bridge_removed_or_sentence_regions(separator):
    content = f"small{separator}experiments"
    assert "small experiments" not in extract_terms(content, ngram_max=3)
    assert lexical_excerpt(content, "small experiments") is None


def test_excerpt_uses_visible_current_prose_with_original_case():
    content = (
        "`Small Reversible Experiments`\n> Small Reversible Experiments\n\n"
        "Try **Small Reversible Experiments** before committing."
    )
    assert (
        lexical_excerpt(content, "small reversible experiments")
        == "Try **Small Reversible Experiments** before committing"
    )


@pytest.mark.parametrize("continuation", ["", "    indented lazy continuation\n"])
def test_quote_continuation_cannot_enter_phrase_signal_or_current_excerpt(continuation):
    content = "> quoted start\n" + continuation + "lazy secret phrase\n\nvisible prose"
    assert extract_terms(content, ngram_max=3) == Counter(
        {"visible": 1, "prose": 1, "visible prose": 1}
    )
    assert lexical_excerpt(content, "secret phrase") is None


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\x85", "\v", "\f", "\r"])
def test_quote_exclusion_keeps_source_line_numbering_across_unicode_separators(separator):
    content = f"visible{separator}other\n> secret quoted signal\nlazy quoted continuation"
    assert "secret" not in extract_terms(content, ngram_max=3)
    assert lexical_excerpt(content, "quoted signal") is None


@pytest.mark.parametrize("break_line", ["---", "***", "___", "- - -", "* * *"])
def test_thematic_break_ends_quote_exclusion(break_line):
    content = f"> quoted paragraph\n{break_line}\nvisible original prose"
    assert "visible original prose" in extract_terms(content, ngram_max=3)
    assert lexical_excerpt(content, "original prose") == "visible original prose"


def test_saved_episode_suppresses_changed_wording_and_clipped_dates_but_not_return(tmp_path):
    identity = ["word_burst", "dated_cohorts", "rising", "small experiments"]
    original = Suggestion(
        text="An earlier question",
        notes=["A"],
        geist_id="word_burst",
        evidence_key=interval_evidence_key(identity, "2026-01-05", "2026-01-25"),
    )
    with closing(Vault(tmp_path)) as vault:
        writer = JournalWriter(tmp_path, vault.db)
        writer.write_session(datetime(2026, 1, 26), [original])
        # Exercise the actual persisted identity, not rows invented by a fixture.
        rewritten = Suggestion(
            text="Entirely different wording and links",
            notes=["B"],
            geist_id="word_burst",
            evidence_key=interval_evidence_key(identity, "2026-01-12", "2026-01-25"),
        )
        returned = Suggestion(
            text="A later recurrence",
            notes=["C"],
            geist_id="word_burst",
            evidence_key=interval_evidence_key(identity, "2026-02-02", "2026-02-08"),
        )
        # Text matching cannot catch the rewritten wording; episode overlap must.
        pipeline = SuggestionFilter(
            vault.db, EmbeddingComputer(), config={"novelty": {"method": "text_match"}}
        )
        assert pipeline.filter_novelty([rewritten, returned], datetime(2026, 2, 9)) == [returned]
        assert pipeline.filter_novelty([rewritten], datetime(2026, 1, 26)) == [rewritten]


@pytest.mark.parametrize("directions", [[], ["rising", "rising"], ["falling"], [True], "rising"])
def test_direction_configuration_rejects_empty_duplicate_and_unknown_modes(directions):
    with pytest.raises(ConfigError, match="directions"):
        GeistFabrikConfig.from_dict({"word_burst": {"directions": directions}})


def test_date_only_edit_preserves_dictionary_without_vocabulary_sized_writes(tmp_path):
    path = tmp_path / "note.md"
    body = " ".join(word(i) for i in range(500))
    path.write_text("---\ncreated: 2026-01-05\n---\n" + body)
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        dictionary = dict(vault.db.execute("SELECT term,documents FROM lexical_terms"))
        before = vault.db.total_changes
        path.write_text("---\ncreated: 2026-01-12\n---\n" + body)
        vault.sync()
        # A chronology edit updates bounded note/index metadata, not every
        # frequency row. SQLite counts real writes including trigger work.
        assert vault.db.total_changes - before < 30
        assert dict(vault.db.execute("SELECT term,documents FROM lexical_terms")) == dictionary
        assert vault.db.execute("SELECT cohort_day FROM lexical_notes").fetchone() == (
            "2026-01-12",
        )


def test_v11_episode_migration_preserves_lexical_history_and_saved_questions(tmp_path, monkeypatch):
    path = tmp_path / "note.md"
    path.write_text("existing prose")
    db_path = tmp_path / "_geistfabrik/vault.db"
    with closing(Vault(tmp_path, db_path=db_path)) as vault:
        freeze(monkeypatch, 5)
        vault.sync()
        freeze(monkeypatch, 6)
        path.write_text("existing prose\nnew additions")
        vault.sync()
        JournalWriter(tmp_path, vault.db).write_session(
            datetime(2026, 1, 6), [Suggestion("Earlier question", ["note"], "word_burst")]
        )
        history = list(vault.db.execute("SELECT * FROM lexical_events"))
        assert history
        # Frozen v11 suggestion DDL; retain the genuinely captured lexical rows.
        vault.db.execute("ALTER TABLE session_suggestions RENAME TO newer_suggestions")
        vault.db.execute(
            "CREATE TABLE session_suggestions (session_date TEXT NOT NULL, geist_id TEXT NOT NULL, "
            "suggestion_text TEXT NOT NULL, block_id TEXT NOT NULL, created_at TEXT NOT NULL, "
            "PRIMARY KEY(session_date, block_id))"
        )
        vault.db.execute(
            "INSERT INTO session_suggestions SELECT session_date, geist_id, suggestion_text, "
            "block_id, created_at FROM newer_suggestions"
        )
        vault.db.execute("DROP TABLE newer_suggestions")
        vault.db.execute("PRAGMA user_version=11")
        vault.db.commit()
    with closing(Vault(tmp_path, db_path=db_path)) as migrated:
        assert list(migrated.db.execute("SELECT * FROM lexical_events")) == history
        assert migrated.db.execute(
            "SELECT suggestion_text, evidence_key FROM session_suggestions"
        ).fetchall() == [("Earlier question", None)]
        assert migrated.db.execute("PRAGMA user_version").fetchone() == (12,)
