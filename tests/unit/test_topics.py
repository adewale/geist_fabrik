"""Automatic topics preserve authorship, source evidence and atomic reads."""

import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

import geistfabrik.topics as topics_module
from geistfabrik.config_loader import GeistFabrikConfig
from geistfabrik.embeddings import Session
from geistfabrik.schema import SCHEMA_VERSION, get_schema_version, init_db
from geistfabrik.topics import (
    MAX_TOPIC_CHARS,
    MAX_TOPICS,
    TopicIndex,
    TopicIndexIncompleteError,
    extract_topics,
    topic_key,
    topic_prose,
)
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


@pytest.fixture
def topic_vault(tmp_path: Path) -> Iterator[Vault]:
    (tmp_path / "cakes.md").write_text(
        "---\ntags: [authored]\n---\n# Chocolate cake\n\nChocolate cake needs cocoa."
    )
    vault = Vault(tmp_path)
    vault.sync()
    yield vault
    vault.close()


def test_normalization_preserves_distinct_subjects() -> None:
    assert topic_key("  CAFÉ\t  Culture ") == "café culture"
    assert topic_key("Cafe\u0301 Culture") == "café culture"
    assert topic_key("cake") != topic_key("cakes")
    assert topic_key("topic-name") != topic_key("topic name")


def test_real_extraction_is_deterministic_bounded_and_source_grounded() -> None:
    source = "---\ntags: [authored]\n---\n# Chocolate cake\n\nChocolate cake needs cocoa."
    tags = extract_topics(source)
    assert tags == extract_topics(source)
    assert "chocolate cake" in {tag.key for tag in tags}
    assert 0 < len(tags) <= MAX_TOPICS == 5
    for tag in tags:
        assert source[tag.start : tag.end] == tag.text
        assert tag.line == source[: tag.start].count("\n") + 1
        assert tag.key == topic_key(tag.label)
        assert tag.score >= 0
        assert tag.provenance


@pytest.mark.parametrize(
    "source",
    [
        "---\ntitle: Hidden subject\ntags: [hidden]\n---\n",
        "```python\nsecret_subject = 1\n```\n",
        "> ```python\n> secret_subject = 1\n> ```\n",
        "    secret_subject = 1\n",
        "<!-- hidden ` topic -->\n",
        "%% hidden ` topic %%\n",
        "`hidden <!-- topic`\n",
        "`hidden %% topic`\n",
        "``hidden\nmultiline subject``\n",
        "[hidden]: https://example.test 'Hidden subject'\n",
        "![hidden](https://example.test/image.png)\n",
        "![[Hidden subject]]\n",
        "https://example.test/hidden_subject #authored\n",
    ],
)
def test_nonprose_never_becomes_topics(source: str) -> None:
    assert extract_topics(source) == []
    assert len(topic_prose(source)) == len(source)


def test_visible_link_labels_retain_exact_source_offsets() -> None:
    source = (
        "# Urban gardens\n\n[Urban gardens](https://example.test 'Hidden subject') "
        "and [[Private destination|seed libraries]].\n\n"
        "[hidden-id]: https://example.test 'Secret title'\n"
    )
    prose = topic_prose(source)
    assert "Urban gardens" in prose
    assert "seed libraries" in prose
    for hidden in ["https", "Hidden subject", "Private destination", "hidden-id", "Secret title"]:
        assert hidden not in prose
    assert "urban gardens" in {tag.key for tag in extract_topics(source)}


def test_comments_and_inline_code_own_their_delimiters() -> None:
    source = (
        "<!-- hidden ` title -->\n# Public gardens\n"
        "`hidden %% title`\n%% hidden ` title %%\n"
        "Public gardens support local wildlife.\n"
    )
    prose = topic_prose(source)
    assert "Public gardens" in prose
    assert "hidden" not in prose
    assert "public gardens" in {tag.key for tag in extract_topics(source)}


def test_primary_heading_survives_secondary_heading_budget() -> None:
    source = (
        "# Urban gardens\n\nUrban gardens support local wildlife.\n"
        "## Introduction\n## Background\n## Methods\n## Results\n## Discussion\n## References\n"
    )
    keys = {tag.key for tag in extract_topics(source)}
    assert "urban gardens" in keys
    assert not keys.intersection({"introduction", "background", "methods", "references"})


@pytest.mark.parametrize("subject", ["Use cases", "Climate changes", "Game over"])
def test_subject_words_are_not_hard_rejected(subject: str) -> None:
    assert topic_key(subject) in {tag.key for tag in extract_topics(f"# {subject}\n")}


def test_singleton_topic_and_authored_tags_are_independent(topic_vault: Vault) -> None:
    index = TopicIndex(topic_vault.db)
    assert index.paths("Chocolate cake") == ["cakes.md"]
    assert index.state("cakes.md").status == "complete"
    assert ("chocolate cake", 1) in index.catalog()
    note = topic_vault.get_note("cakes.md")
    assert note is not None and note.tags == ["authored"]
    assert index.catalog() == sorted(index.catalog())


def test_incremental_edit_delete_and_rebuild_match(topic_vault: Vault) -> None:
    index = TopicIndex(topic_vault.db)
    path = topic_vault.vault_path / "cakes.md"
    path.write_text("# Urban gardens\n\nUrban gardens need sunlight.")
    topic_vault.sync()
    assert index.paths("chocolate cake") == []
    assert index.paths("urban gardens") == ["cakes.md"]
    previous = (index.catalog(), index.tags("cakes.md"))
    topic_vault.sync(rebuild_topics=True)
    assert previous == (index.catalog(), index.tags("cakes.md"))
    path.unlink()
    topic_vault.sync()
    assert index.catalog() == []
    assert topic_vault.db.execute("SELECT * FROM note_topics").fetchall() == []


def test_unchanged_note_uses_cache_and_rebuild_reextracts(
    topic_vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0
    original = topics_module.extract_topics

    def counted(content: str, extractor=None):
        nonlocal calls
        calls += 1
        return original(content, extractor)

    monkeypatch.setattr(topics_module, "extract_topics", counted)
    topic_vault.sync()
    assert calls == 0
    topic_vault.sync(rebuild_topics=True)
    assert calls == 1


def test_extraction_failure_is_incomplete_and_retried(
    topic_vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    index = TopicIndex(topic_vault.db)
    original = topics_module.extract_topics

    def broken(_content: str, extractor=None):
        raise ValueError("extractor unavailable")

    monkeypatch.setattr(topics_module, "extract_topics", broken)
    topic_vault.sync(rebuild_topics=True)
    state = index.state("cakes.md")
    assert state.status == "error" and state.error
    with pytest.raises(TopicIndexIncompleteError):
        index.catalog()
    with pytest.raises(TopicIndexIncompleteError):
        index.tags("cakes.md")
    monkeypatch.setattr(topics_module, "extract_topics", original)
    topic_vault.sync()
    assert index.state("cakes.md").status == "complete"
    assert index.paths("chocolate cake") == ["cakes.md"]


def test_oversized_note_is_explicit_error(topic_vault: Vault) -> None:
    (topic_vault.vault_path / "cakes.md").write_text("a" * (MAX_TOPIC_CHARS + 1))
    topic_vault.sync()
    assert TopicIndex(topic_vault.db).state("cakes.md").status == "error"


def test_boundaries_are_enforced_even_when_filter_disabled(tmp_path: Path) -> None:
    for path in [
        "public.md",
        "Private/secret.md",
        "geist journal/generated.md",
        "_geistfabrik/x.md",
    ]:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# Rare subject\n\nRare subject.")
    config = GeistFabrikConfig()
    config.filtering.boundary_enabled = False
    config.filtering.exclude_paths = ["Private/"]
    vault = Vault(tmp_path, config=config)
    try:
        vault.sync()
        index = TopicIndex(vault.db, config.filtering.exclude_paths)
        assert index.paths("rare subject") == ["public.md"]
        assert index.state("Private/secret.md").status == "excluded"
        assert index.state("geist journal/generated.md").status == "excluded"
        config.filtering.exclude_paths = ["Private/", "public.md"]
        vault.sync()
        assert TopicIndex(vault.db, config.filtering.exclude_paths).catalog() == []
        assert vault.db.execute("SELECT * FROM note_topics").fetchall() == []
    finally:
        vault.close()


def test_invalid_utf8_new_old_recovery_and_deletion(topic_vault: Vault) -> None:
    index = TopicIndex(topic_vault.db)
    bad = topic_vault.vault_path / "unparsed.md"
    bad.write_bytes(b"\xff\xfe")
    old = topic_vault.vault_path / "cakes.md"
    old.write_bytes(b"\xff\xfe")
    topic_vault.sync()
    assert index.state("unparsed.md").status == "error"
    assert index.state("cakes.md").status == "error"
    with pytest.raises(TopicIndexIncompleteError):
        index.paths("chocolate cake")
    old.write_text("# Urban gardens\n")
    bad.unlink()
    topic_vault.sync()
    assert index.state("cakes.md").status == "complete"
    assert index.paths("urban gardens") == ["cakes.md"]
    assert topic_vault.db.execute("SELECT * FROM topic_source_errors").fetchall() == []


def test_parser_rejection_cannot_disappear_as_empty(
    topic_vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    import geistfabrik.markdown_parser as markdown

    monkeypatch.setattr(markdown, "MAX_NOTE_LINKS", 1)
    (topic_vault.vault_path / "unparsed.md").write_text("[[one]] [[two]]")
    topic_vault.sync()
    index = TopicIndex(topic_vault.db)
    assert index.state("unparsed.md").status == "error"
    with pytest.raises(TopicIndexIncompleteError):
        index.catalog()


def test_dated_entries_preserve_source_and_author_tags(tmp_path: Path) -> None:
    source = (
        "---\ntags: [authored]\n---\n## 2025-01-01\n[[Urban gardens]]\n"
        "## 2025-01-02\n[[Chocolate cake]]\n"
    )
    path = tmp_path / "diary.md"
    path.write_text(source)
    vault = Vault(tmp_path)
    try:
        vault.sync()
        notes = vault.all_notes()
        assert len(notes) == 2
        assert all(note.is_virtual for note in notes)
        index = TopicIndex(vault.db)
        garden_paths = index.paths("urban gardens")
        cake_paths = index.paths("chocolate cake")
        assert len(garden_paths) == len(cake_paths) == 1
        assert garden_paths != cake_paths
        assert all(note.tags == ["authored"] for note in notes)
        assert path.read_text() == source
    finally:
        vault.close()


def test_storage_failure_rolls_back_note_and_topic_publication(
    topic_vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_note = topic_vault.get_note("cakes.md")
    assert old_note is not None
    old_content = old_note.content
    before = TopicIndex(topic_vault.db).catalog()
    (topic_vault.vault_path / "cakes.md").write_text("# Urban gardens\n")

    def fail(_self, **_kwargs):
        raise sqlite3.OperationalError("storage failure")

    monkeypatch.setattr(TopicIndex, "synchronize", fail)
    with pytest.raises(sqlite3.OperationalError, match="storage failure"):
        topic_vault.sync()
    assert not topic_vault.db.in_transaction
    stored_note = topic_vault.get_note("cakes.md")
    assert stored_note is not None and stored_note.content == old_content
    assert TopicIndex(topic_vault.db).catalog() == before


@pytest.mark.parametrize("previous_version", [10, 15])
def test_upgrade_preserves_raw_notes_and_is_idempotent(
    tmp_path: Path, previous_version: int
) -> None:
    path = tmp_path / "state.db"
    db = init_db(path)
    db.execute(
        "INSERT INTO notes (path,title,content,created,modified,file_mtime) VALUES (?,?,?,?,?,?)",
        ("old.md", "Old", "Source", "2025-01-01", "2025-01-01", 0),
    )
    db.execute("INSERT INTO tags VALUES ('old.md','authored')")
    for table in [
        "note_topics",
        "note_topic_state",
        "topic_source_errors",
        "topic_source_identity",
        "topics",
    ]:
        db.execute(f"DROP TABLE {table}")
    db.execute(f"PRAGMA user_version={previous_version}")
    db.commit()
    db.close()
    for _ in range(2):
        db = init_db(path)
        try:
            assert get_schema_version(db) == SCHEMA_VERSION == 16
            assert db.execute("SELECT content FROM notes").fetchall() == [("Source",)]
            assert db.execute("SELECT tag FROM tags").fetchall() == [("authored",)]
            assert TopicIndex(db).state("old.md").status == "pending"
        finally:
            db.close()


@pytest.mark.parametrize("query", ["tags", "catalog", "paths"])
def test_wal_queries_keep_validation_and_membership_in_one_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, query: str
) -> None:
    source = tmp_path / "note.md"
    source.write_text("# Chocolate cake\n")
    reader = Vault(tmp_path, tmp_path / "wal.db")
    reader.db.execute("PRAGMA journal_mode=WAL")
    reader.sync()
    writer = Vault(tmp_path, tmp_path / "wal.db")
    fired = False
    method_name = "state" if query == "tags" else "require_complete"
    original = getattr(TopicIndex, method_name)

    def after_validation(self, *args, **kwargs):
        nonlocal fired
        result = original(self, *args, **kwargs)
        if self.db is reader.db and not fired:
            fired = True
            source.write_text("# Urban gardens\n")
            writer.sync()
        return result

    monkeypatch.setattr(TopicIndex, method_name, after_validation)
    try:
        index = TopicIndex(reader.db)
        if query == "tags":
            assert "chocolate cake" in {tag.key for tag in index.tags("note.md")}
        elif query == "catalog":
            assert ("chocolate cake", 1) in index.catalog()
        else:
            assert index.paths("chocolate cake") == ["note.md"]
        assert fired
        assert index.paths("chocolate cake") == []
        assert index.paths("urban gardens") == ["note.md"]
    finally:
        writer.close()
        reader.close()


def test_context_topics_metadata_and_deterministic_functions(topic_vault: Vault) -> None:
    from geistfabrik.function_registry import FunctionRegistry

    session = Session(datetime(2025, 1, 3), topic_vault.db)
    first = VaultContext(topic_vault, session, seed=17)
    second = VaultContext(topic_vault, session, seed=17)
    note = first.get_note("cakes.md")
    assert note is not None
    assert "chocolate cake" in {tag.key for tag in first.topics_for_note(note)}
    assert [note.path for note in first.notes_for_topic("Chocolate cake")] == ["cakes.md"]
    metadata = first.metadata(note)
    assert metadata["derived_topics_status"] == "complete"
    assert "chocolate cake" in metadata["derived_topics"]
    assert note.tags == ["authored"]
    registry = FunctionRegistry()
    assert registry.call("topic_notes", first, "Chocolate cake", 1) == registry.call(
        "topic_notes", second, "Chocolate cake", 1
    )
    assert registry.call("topic_notes", first, "Chocolate cake", 1) == ["[[cakes|Chocolate cake]]"]
    assert "Chocolate cake" in registry.call("note_topics", first, "[[cakes]]")


def test_context_membership_and_returned_body_share_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "note.md"
    source.write_text("# Chocolate cake\n")
    reader = Vault(tmp_path, tmp_path / "wal.db")
    reader.db.execute("PRAGMA journal_mode=WAL")
    reader.sync()
    writer = Vault(tmp_path, tmp_path / "wal.db")
    original = TopicIndex.paths
    changed = False

    def paths_then_change(self, topic):
        nonlocal changed
        result = original(self, topic)
        if self.db is reader.db and not changed:
            changed = True
            source.write_text("# Urban gardens\n")
            writer.sync()
        return result

    monkeypatch.setattr(TopicIndex, "paths", paths_then_change)
    try:
        context = VaultContext(reader, Session(datetime(2025, 1, 3), reader.db))
        notes = context.notes_for_topic("chocolate cake")
        assert changed and len(notes) == 1
        assert notes[0].content == "# Chocolate cake\n"
        stored_note = reader.get_note("note.md")
        assert stored_note is not None and stored_note.content == "# Urban gardens\n"
    finally:
        writer.close()
        reader.close()


def test_cache_version_mismatch_is_pending_until_sync(topic_vault: Vault) -> None:
    index = TopicIndex(topic_vault.db)
    topic_vault.db.execute("UPDATE note_topic_state SET algorithm_digest='obsolete'")
    topic_vault.db.commit()
    assert index.state("cakes.md").status == "pending"
    with pytest.raises(TopicIndexIncompleteError):
        index.tags("cakes.md")
    topic_vault.sync()
    assert index.state("cakes.md").status == "complete"
    assert index.paths("chocolate cake") == ["cakes.md"]


def test_empty_complete_and_unknown_pending_are_distinct(topic_vault: Vault) -> None:
    (topic_vault.vault_path / "empty.md").write_text("")
    topic_vault.sync()
    index = TopicIndex(topic_vault.db)
    assert index.state("empty.md").status == "complete"
    assert index.tags("empty.md") == []
    assert index.state("missing.md").status == "pending"
    with pytest.raises(TopicIndexIncompleteError):
        index.tags("missing.md")


def test_read_snapshot_preserves_borrowed_transaction(topic_vault: Vault) -> None:
    index = TopicIndex(topic_vault.db)
    topic_vault.db.execute("BEGIN")
    try:
        with index.read_snapshot():
            assert index.paths("chocolate cake") == ["cakes.md"]
        assert topic_vault.db.in_transaction
    finally:
        topic_vault.db.rollback()
    with index.read_snapshot():
        assert topic_vault.db.in_transaction
    assert not topic_vault.db.in_transaction


def test_unreadable_new_source_and_exclusion_manifest(
    topic_vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = topic_vault.vault_path / "unreadable.md"
    path.write_text("# Private subject\n")
    original = Path.open

    def guarded_open(self: Path, *args, **kwargs):
        if self == path:
            raise PermissionError("denied")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    topic_vault.sync()
    assert TopicIndex(topic_vault.db).state("unreadable.md").status == "error"
    with pytest.raises(TopicIndexIncompleteError):
        TopicIndex(topic_vault.db).catalog()
    topic_vault.config.filtering.exclude_paths = ["unreadable.md"]
    topic_vault.sync()
    index = TopicIndex(topic_vault.db, ["unreadable.md"])
    assert index.state("unreadable.md").status == "excluded"
    assert index.paths("chocolate cake") == ["cakes.md"]
    assert topic_vault.db.execute("SELECT * FROM topic_source_errors").fetchall() == []


class _CandidateExtractor:
    def extract_keywords(self, _text: str) -> list[tuple[str, float]]:
        return [
            ("rare topic", 0.1),
            ("invented subject", 0.01),
            ("topic topic", 0.001),
            ("1234", 0.001),
            ("rare", float("nan")),
            ("topic", -1.0),
        ]


def test_candidate_validation_rejects_unobserved_and_invalid_scores() -> None:
    tags = extract_topics("A rare topic appears here. topic topic 1234", _CandidateExtractor())
    assert [tag.key for tag in tags] == ["rare topic"]
    assert tags[0].text == "rare topic"


class _JoinedExtractor:
    def extract_keywords(self, _text: str) -> list[tuple[str, float]]:
        return [("red blue", 0.01)]


class _SeparatedCosts:
    def extract_keywords(self, text: str) -> list[tuple[str, float]]:
        return [("alpha", 0.1), ("beta", 0.11), ("gamma", 1.0)]


def test_budget_does_not_pad_a_large_statistical_cost_gap() -> None:
    tags = extract_topics("alpha beta gamma", _SeparatedCosts())
    assert [tag.key for tag in tags] == ["alpha", "beta"]


class _WeakSingleton:
    def extract_keywords(self, text: str) -> list[tuple[str, float]]:
        return [("rare topic", 2.0)]


def test_cost_gap_abstention_has_no_absolute_or_corpus_frequency_floor() -> None:
    tags = extract_topics("rare topic", _WeakSingleton())
    assert [tag.key for tag in tags] == ["rare topic"]


class _EarlyCostGap:
    def extract_keywords(self, text: str) -> list[tuple[str, float]]:
        return [("alpha", 0.000001), ("beta", 0.0001)]


def test_statistical_abstention_does_not_suppress_later_authored_evidence() -> None:
    tags = extract_topics("alpha beta [[Rare topic]]", _EarlyCostGap())
    assert [tag.key for tag in tags] == ["alpha", "rare topic"]


class _PhraseAfterGap:
    def extract_keywords(self, text: str) -> list[tuple[str, float]]:
        return [("alpha", 0.1), ("beta", 0.11), ("gamma", 1.0), ("rare topic", 2.0)]


def test_word_padding_abstention_preserves_phrase_evidence_after_a_gap() -> None:
    tags = extract_topics("alpha beta gamma rare topic", _PhraseAfterGap())
    assert [tag.key for tag in tags] == ["alpha", "beta", "rare topic"]


@pytest.mark.parametrize("source", ["red\n\nblue", "red\n- blue", "red\n## blue"])
def test_labels_cannot_join_distinct_prose_blocks(source: str) -> None:
    assert "red blue" not in {tag.key for tag in extract_topics(source, _JoinedExtractor())}


def test_topic_upgrade_preserves_existing_lexical_evidence(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    db = init_db(path)
    db.execute(
        "INSERT INTO notes(path,title,content,created,modified,file_mtime) VALUES (?,?,?,?,?,?)",
        ("old.md", "Old", "Original prose", "2026-01-01", "2026-01-01", 0),
    )
    db.execute(
        "INSERT INTO lexical_notes(path,raw_hash,body_hash,provenance,counts_json,observed_at) "
        "VALUES (?,?,?,?,?,?)",
        ("old.md", "raw", "body", "declared", '{"original":1}', "2026-01-01"),
    )
    db.execute(
        "INSERT INTO lexical_events(path,bin_start,previous_at,observed_at,terms_json,"
        "revisions_json,evidence_hash) VALUES (?,?,?,?,?,?,?)",
        ("old.md", "2025-12-29", "2026-01-01", "2026-01-02", '{"original":1}', "[]", "keep"),
    )
    db.execute("INSERT INTO word_burst_cache VALUES ('keep','{}','{}')")
    tables = ("notes", "lexical_notes", "lexical_events", "word_burst_cache")
    before = {table: db.execute(f"SELECT * FROM {table}").fetchall() for table in tables}
    for table in (
        "note_topics",
        "note_topic_state",
        "topic_source_errors",
        "topic_source_identity",
        "topics",
    ):
        db.execute(f"DROP TABLE {table}")
    db.execute("PRAGMA user_version=15")
    db.commit()
    db.close()
    for _ in range(2):
        db = init_db(path)
        try:
            assert get_schema_version(db) == 16
            after = {table: db.execute(f"SELECT * FROM {table}").fetchall() for table in tables}
            assert after == before
        finally:
            db.close()
