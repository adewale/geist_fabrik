"""Durable factual memory, with an independent calendar-set overlap oracle."""

import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

from hypothesis import given
from hypothesis import strategies as st

from geistfabrik.default_geists.code import uncertainty_mapper
from geistfabrik.evidence_identity import factual_evidence_key, interval_evidence_key
from geistfabrik.filtering import SuggestionFilter
from geistfabrik.journal_writer import JournalWriter
from geistfabrik.models import Note, Suggestion


def _filter(db):
    encoder = MagicMock()
    encoder.compute_batch_semantic.side_effect = AssertionError("old facts need no encoding")
    return SuggestionFilter(db, encoder, config={"novelty": {"method": "text_match"}})


def _history_db():
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE session_suggestions (session_date TEXT, geist_id TEXT, "
        "suggestion_text TEXT, block_id TEXT, created_at TEXT, evidence_key TEXT)"
    )
    db.execute(
        "CREATE INDEX idx_session_suggestions_evidence "
        "ON session_suggestions(geist_id, evidence_key, session_date)"
    )
    return db


def _save(db, key, *, geist="word_burst", when="2024-01-01", text="An earlier question"):
    db.execute(
        "INSERT INTO session_suggestions VALUES (?, ?, ?, ?, ?, ?)",
        (when, geist, text, "^saved", "now", key),
    )


def _candidate(key, *, geist="word_burst", text="Completely changed wording"):
    return Suggestion(text, ["Note"], geist, evidence_key=key)


def test_saved_episode_survives_novelty_expiry_and_allows_a_disjoint_return(test_db, tmp_path):
    """Use the actual write path, then replay more than a year later."""
    identity = ["word_burst", "dated_cohorts", "rising", "small experiments"]
    original = _candidate(interval_evidence_key(identity, "2024-01-01", "2024-01-21"))
    writer = JournalWriter(tmp_path, test_db)
    writer.write_session(datetime(2024, 1, 22), [original])
    exact = _candidate(original.evidence_key, text="A different question about the same finding")
    clipped = _candidate(interval_evidence_key(identity, "2024-01-15", "2024-01-28"))
    returned = _candidate(interval_evidence_key(identity, "2025-01-06", "2025-01-12"))
    assert _filter(test_db).filter_novelty([exact, clipped, returned], datetime(2025, 2, 1)) == [
        returned
    ]


def test_factual_identity_uses_full_input_not_just_counts_and_does_not_blacklist_text(test_db):
    old = factual_evidence_key(["uncertainty_mapper", "note.md"], ["Perhaps the lake is deep."])
    changed = factual_evidence_key(["uncertainty_mapper", "note.md"], ["Perhaps the lake is wide."])
    assert old != changed
    _save(test_db, old, geist="uncertainty_mapper", text="The same hedge count and question")
    repeated = _candidate(old, geist="uncertainty_mapper", text="A new wording")
    revised = _candidate(
        changed, geist="uncertainty_mapper", text="The same hedge count and question"
    )
    playful = _candidate(None, geist="playful", text="The same hedge count and question")
    assert _filter(test_db).filter_novelty([repeated, revised, playful], datetime(2025, 1, 1)) == [
        revised,
        playful,
    ]


def test_uncertainty_mapper_identity_tracks_full_content_even_when_question_is_unchanged(test_db):
    def result(body):
        note = Note("Plan.md", "Plan", body, [], [], datetime(2024, 1, 1), datetime(2024, 1, 1))
        context = MagicMock()
        context.notes.return_value = [note]
        context.sample.side_effect = lambda values, _size: values[:1]
        return uncertainty_mapper.suggest(context)[0]

    original = result("The plan might work out well in the end. " * 16)
    unchanged = result("The plan might work out well in the end. " * 16)
    revised = result("The boat might work out well in the end. " * 16)
    assert original.text == revised.text  # Same note, hedges and word count.
    assert original.evidence_key == unchanged.evidence_key
    assert original.evidence_key != revised.evidence_key
    _save(test_db, original.evidence_key, geist=original.geist_id, text=original.text)
    assert _filter(test_db).filter_novelty([unchanged, revised], datetime(2025, 1, 1)) == [revised]


def test_playful_text_revisits_keep_the_short_window_policy(test_db):
    playful = _candidate(None, geist="playful", text="What if these notes traded places?")
    _save(test_db, None, geist="playful", when="2025-01-01", text=playful.text)
    pipeline = _filter(test_db)
    assert pipeline.filter_novelty([playful], datetime(2025, 1, 2)) == []
    assert pipeline.filter_novelty([playful], datetime(2025, 3, 3)) == [playful]


def test_evidence_replay_excludes_same_day_and_future_sessions(test_db):
    key = interval_evidence_key(["observation"], "2024-01-01", "2024-01-10")
    _save(test_db, key, when="2026-01-01")
    candidate = _candidate(key)
    pipeline = _filter(test_db)
    assert pipeline.filter_novelty([candidate], datetime(2025, 1, 1)) == [candidate]
    assert pipeline.filter_novelty([candidate], datetime(2026, 1, 1)) == [candidate]
    assert pipeline.filter_novelty([candidate], datetime(2026, 1, 2)) == []


def test_durable_filter_previews_do_not_persist_new_observations(test_db, tmp_path):
    old = _candidate(factual_evidence_key(["facts"], ["old body"]))
    JournalWriter(tmp_path, test_db).write_session(datetime(2024, 1, 1), [old])
    fresh = _candidate(factual_evidence_key(["facts"], ["changed body"]))
    saved_rows = list(test_db.execute("SELECT * FROM session_suggestions"))
    journal = tmp_path / "geist journal/2024-01-01.md"
    saved_text = journal.read_bytes()
    changes = test_db.total_changes
    pipeline = _filter(test_db)
    for _ in range(2):
        assert pipeline.filter_novelty([old, fresh], datetime(2025, 1, 1)) == [fresh]
    assert test_db.total_changes == changes
    assert list(test_db.execute("SELECT * FROM session_suggestions")) == saved_rows
    assert journal.read_bytes() == saved_text


@given(
    st.lists(
        st.tuples(st.integers(0, 60), st.integers(0, 14), st.booleans(), st.booleans()), max_size=30
    ),
    st.integers(0, 60),
    st.integers(0, 14),
)
def test_interval_history_matches_independent_day_set_oracle(history, start, length):
    """Do not reproduce the endpoint-comparison implementation as the oracle."""
    epoch = date(2023, 1, 1)
    candidate_days = set(range(start, start + length + 1))
    expected_seen = any(
        same_identity and same_geist and candidate_days.intersection(range(a, a + size + 1))
        for a, size, same_identity, same_geist in history
    )

    def key(a, size, same=True):
        return interval_evidence_key(
            ["same" if same else "other"],
            (epoch + timedelta(days=a)).isoformat(),
            (epoch + timedelta(days=a + size)).isoformat(),
        )

    with closing(_history_db()) as db:
        for a, size, same_identity, same_geist in history:
            _save(db, key(a, size, same_identity), geist="word_burst" if same_geist else "other")
        candidate = _candidate(key(start, length))
        assert _filter(db).filter_novelty([candidate], datetime(2025, 1, 1)) == (
            [] if expected_seen else [candidate]
        )


def test_malformed_interval_history_stays_opaque_and_cannot_suppress_an_episode(test_db):
    key = interval_evidence_key(["same"], "2024-01-01", "2024-01-10")
    prefix = key.rsplit(":", 2)[0]
    _save(test_db, prefix + ":2024-01-01:not-a-date")
    candidate = _candidate(key)
    assert _filter(test_db).filter_novelty([candidate], datetime(2025, 1, 1)) == [candidate]


def test_exact_and_interval_lookups_use_the_migrated_covering_index(test_db):
    key = interval_evidence_key(["same"], "2024-01-01", "2024-01-10")
    _save(test_db, interval_evidence_key(["same"], "2024-01-02", "2024-01-10"))
    queries = []
    test_db.set_trace_callback(queries.append)
    assert _filter(test_db).filter_novelty([_candidate(key)], datetime(2025, 1, 1)) == []
    test_db.set_trace_callback(None)
    evidence_queries = [query for query in queries if "AND evidence_key" in query]
    assert evidence_queries
    for query in evidence_queries:
        plan = test_db.execute("EXPLAIN QUERY PLAN " + query).fetchall()
        assert any("SEARCH session_suggestions USING COVERING INDEX " in row[3] for row in plan)


def test_final_boundary_rejects_template_aliases_and_physical_sources_even_when_disabled(test_db):
    rows = [
        ("Templates/Outline.md", "Outline", False, None, None),
        ("Work/Outline.md", "Outline", False, None, None),
        ("templates/Lower.md", "Lower", False, None, None),
        ("Nested/Templates/Nested.md", "Nested", False, None, None),
        ("Private/Personal.md", "Personal", False, None, None),
        ("Templates/Diary.md/2024-01-01", "2024-01-01", True, "Templates/Diary.md", "2024-01-01"),
    ]
    test_db.executemany(
        "INSERT INTO notes (path, title, content, created, modified, file_mtime, "
        "is_virtual, source_file, entry_date) "
        "VALUES (?, ?, '', '2024-01-01', '2024-01-01', 0, ?, ?, ?)",
        rows,
    )
    targets = [
        "Templates/Outline",
        "Outline",
        "Work/Outline",
        "Lower",
        "Nested",
        "Personal",
        "Templates/Diary#2024-01-01",
    ]
    candidates = [Suggestion("What might this suggest?", [target], "custom") for target in targets]
    pipeline = SuggestionFilter(
        test_db,
        MagicMock(),
        config={"boundary": {"enabled": False, "exclude_paths": ["Private/"]}},
    )
    assert pipeline.filter_boundary(candidates) == candidates[2:6]
    pipeline.config["boundary"]["enabled"] = True
    assert pipeline.filter_boundary(candidates) == candidates[2:5]
