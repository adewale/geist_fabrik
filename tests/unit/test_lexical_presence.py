"""Exact compact-presence storage at the sync, migration and transaction boundaries."""

import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.config_loader import GeistFabrikConfig
from geistfabrik.lexical_presence import (
    decode_presence,
    ensure_presence,
    presence_terms,
)
from geistfabrik.schema import SCHEMA_VERSION, init_db
from geistfabrik.sqlite_transaction import owned_transaction
from geistfabrik.vault import Vault
from geistfabrik.word_burst_analysis import WordBurstDiagnostics, analyze_word_bursts


def assert_exact_projection(db: sqlite3.Connection) -> None:
    """Retained JSON is the independent oracle, not the compact encoder."""
    terms = dict(presence_terms(db))

    def persisted_terms(blob: bytes) -> set[str]:
        # Read the wire format independently: a paired encoder/decoder endian
        # mistake must not cancel and make the lifecycle oracle pass.
        assert len(blob) % 8 == 0
        ids = [int.from_bytes(blob[i : i + 8], "little") for i in range(0, len(blob), 8)]
        assert decode_presence(blob).tolist() == ids
        return {terms[term_id] for term_id in ids}

    dictionary: Counter[str] = Counter()
    for vector, blob in db.execute("SELECT counts_json, presence FROM lexical_notes"):
        expected = set(json.loads(vector))
        dictionary.update(expected)
        assert blob is not None
        assert persisted_terms(blob) == expected
    assert (
        dict(db.execute("SELECT term, documents FROM lexical_terms WHERE documents > 0"))
        == dictionary
    )
    for vector, blob in db.execute("SELECT terms_json, presence FROM lexical_events"):
        assert blob is not None
        assert persisted_terms(blob) == set(json.loads(vector))


@settings(max_examples=35, deadline=None)
@given(
    maximum=st.integers(1, 3),
    changes=st.lists(
        st.tuples(
            st.integers(0, 3),
            st.one_of(
                st.none(),
                st.lists(
                    st.sampled_from(["aurora", "soil", "repair", "café", "quasar"]),
                    min_size=0,
                    max_size=12,
                ),
            ),
        ),
        min_size=1,
        max_size=14,
    ),
)
def test_presence_matches_exact_json_through_source_lifecycle(maximum, changes):
    """Repeated counts, duplicate bodies, additions and deletion cannot stale IDs."""
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = GeistFabrikConfig()
        config.lexical_analysis.ngram_max = maximum
        with closing(Vault(root, config=config)) as vault:
            known: dict[str, int] = {}
            for number, words in changes:
                source = root / f"note-{number}.md"
                if words is None:
                    source.unlink(missing_ok=True)
                else:
                    source.write_text(
                        "---\ncreated: 2026-01-05\n---\n" + " ".join(words), encoding="utf-8"
                    )
                vault.sync()
                assert_exact_projection(vault.db)
                current = {term: term_id for term_id, term in presence_terms(vault.db)}
                assert all(current[term] == term_id for term, term_id in known.items())
                known = current


def populated_vault(root: Path) -> Vault:
    source = root / "source.md"
    source.write_text("---\ncreated: 2026-01-05\n---\nsoil", encoding="utf-8")
    vault = Vault(root, db_path=root / "vault.db")
    vault.sync()
    source.write_text("---\ncreated: 2026-01-05\n---\nsoil aurora", encoding="utf-8")
    vault.sync()
    return vault


def test_v13_migration_backfills_without_recreating_sources_history_or_saved_data(tmp_path):
    with closing(populated_vault(tmp_path)) as vault:
        with owned_transaction(vault.db, "preserved user data"):
            vault.db.execute(
                "INSERT INTO embeddings VALUES (?, ?, ?, ?)",
                ("source.md", b"exact-embedding-bytes", "migration-fixture", "2026-01-05"),
            )
            vault.db.execute(
                "INSERT INTO session_suggestions VALUES (?, ?, ?, ?, ?, ?)",
                ("2026-01-05", "word_burst", "What if?", "g001", "2026-01-05", "evidence"),
            )
        saved = {
            table: list(vault.db.execute(f"SELECT * FROM {table}"))
            for table in (
                "notes",
                "embeddings",
                "session_suggestions",
                "lexical_meta",
                "lexical_terms",
            )
        }
        current = list(vault.db.execute("SELECT path, counts_json, body_hash FROM lexical_notes"))
        history = list(
            vault.db.execute(
                "SELECT path, terms_json, revisions_json, evidence_hash FROM lexical_events"
            )
        )
        assert history  # Exercise real captured additions, not an empty history migration.
        # Reconstruct the actual v13 surface without a projection or stable-ID table.
        with owned_transaction(vault.db, "legacy fixture"):
            vault.db.execute("DROP TRIGGER lexical_note_presence_invalid")
            vault.db.execute("DROP TRIGGER lexical_event_presence_invalid")
            vault.db.execute("ALTER TABLE lexical_notes DROP COLUMN presence")
            vault.db.execute("ALTER TABLE lexical_events DROP COLUMN presence")
            vault.db.execute("DROP TABLE lexical_presence_terms")
            vault.db.execute("PRAGMA user_version = 13")
    # Remove the file: backfill must work entirely from retained database evidence.
    (tmp_path / "source.md").unlink()
    with closing(init_db(tmp_path / "vault.db")) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
        assert db.execute("SELECT presence FROM lexical_notes").fetchone() == (None,)
        with owned_transaction(db, "legacy compact projection"):
            ensure_presence(db)
        assert_exact_projection(db)
        for table, rows in saved.items():
            assert list(db.execute(f"SELECT * FROM {table}")) == rows
        assert list(db.execute("SELECT path, counts_json, body_hash FROM lexical_notes")) == current
        assert (
            list(
                db.execute(
                    "SELECT path, terms_json, revisions_json, evidence_hash FROM lexical_events"
                )
            )
            == history
        )


def test_projection_backfill_rolls_back_dictionary_and_rows_together(tmp_path):
    for name, body in (("a", "aurora"), ("b", "quasar")):
        (tmp_path / f"{name}.md").write_text(body, encoding="utf-8")
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        with owned_transaction(vault.db, "legacy projection fixture"):
            vault.db.execute("UPDATE lexical_notes SET presence=NULL")
            vault.db.execute("DELETE FROM lexical_presence_terms")
            vault.db.execute(
                "CREATE TRIGGER reject_dictionary BEFORE INSERT ON lexical_presence_terms "
                "WHEN NEW.term = 'quasar' BEGIN SELECT RAISE(ABORT, 'disk fixture failure'); END"
            )
        before = list(vault.db.execute("SELECT * FROM lexical_meta"))
        with pytest.raises(sqlite3.IntegrityError, match="disk fixture failure"):
            with owned_transaction(vault.db, "failed backfill"):
                ensure_presence(vault.db)
        assert list(vault.db.execute("SELECT * FROM lexical_presence_terms")) == []
        assert list(vault.db.execute("SELECT presence FROM lexical_notes")) == [(None,), (None,)]
        assert list(vault.db.execute("SELECT * FROM lexical_meta")) == before
        with owned_transaction(vault.db, "successful backfill"):
            vault.db.execute("DROP TRIGGER reject_dictionary")
            ensure_presence(vault.db)
        assert_exact_projection(vault.db)


def test_direct_json_changes_invalidate_old_projections_and_preserve_captured_terms(tmp_path):
    with closing(populated_vault(tmp_path)) as vault:
        with owned_transaction(vault.db, "direct count mutation"):
            vault.db.execute("UPDATE lexical_notes SET counts_json='{\"soil\":4}'")
            vault.db.execute("UPDATE lexical_events SET terms_json='[\"historical\"]'")
        assert vault.db.execute("SELECT presence FROM lexical_notes").fetchone() == (None,)
        assert vault.db.execute("SELECT presence FROM lexical_events").fetchone() == (None,)
        generation = vault.db.execute(
            "SELECT value FROM lexical_meta WHERE key='generation'"
        ).fetchone()
        with owned_transaction(vault.db, "direct projection repair"):
            ensure_presence(vault.db)
        assert_exact_projection(vault.db)
        assert (
            vault.db.execute("SELECT value FROM lexical_meta WHERE key='generation'").fetchone()
            == generation
        )
        assert "historical" in dict(presence_terms(vault.db)).values()
        assert "historical" not in dict(presence_terms(vault.db, min_documents=1)).values()


def test_policy_reset_rebuilds_projection_and_clears_incompatible_history(tmp_path):
    with closing(populated_vault(tmp_path)) as vault:
        assert vault.db.execute("SELECT count(*) FROM lexical_events").fetchone() == (1,)
        vault.config.lexical_analysis.ngram_max = 3
        vault.sync()
        assert_exact_projection(vault.db)
        assert vault.db.execute("SELECT count(*) FROM lexical_events").fetchone() == (0,)
        assert "soil aurora" in dict(presence_terms(vault.db)).values()


@settings(max_examples=12, deadline=None)
@given(high_id=st.integers(min_value=2**32 + 1, max_value=2**63 - 2))
def test_large_stable_ids_survive_real_sync_without_narrowing(high_id):
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = GeistFabrikConfig()
        config.lexical_analysis.ngram_max = 1
        with closing(Vault(root, config=config)) as vault:
            vault.sync()
            with owned_transaction(vault.db, "retained historical dictionary"):
                vault.db.execute(
                    "INSERT INTO lexical_presence_terms VALUES (?, 'soil')", (high_id,)
                )
            (root / "source.md").write_text("soil quasar", encoding="utf-8")
            vault.sync()
            assert_exact_projection(vault.db)
            assert dict(presence_terms(vault.db)) == {high_id: "soil", high_id + 1: "quasar"}


def test_exhausted_stable_ids_fail_atomically_instead_of_wrapping(tmp_path):
    config = GeistFabrikConfig()
    config.lexical_analysis.ngram_max = 1
    with closing(Vault(tmp_path, config=config)) as vault:
        vault.sync()
        with owned_transaction(vault.db, "last valid dictionary ID"):
            vault.db.execute("INSERT INTO lexical_presence_terms VALUES (?, 'soil')", (2**63 - 1,))
        source = tmp_path / "source.md"
        source.write_text("soil quasar", encoding="utf-8")
        with pytest.raises(OverflowError, match="exhausted SQLite integer IDs"):
            vault.sync()
        assert vault.db.execute("SELECT count(*) FROM notes").fetchone() == (0,)
        assert list(presence_terms(vault.db)) == [(2**63 - 1, "soil")]
        source.write_text("soil", encoding="utf-8")
        vault.sync()
        assert_exact_projection(vault.db)


def test_small_source_edit_does_not_scan_retained_dictionary(tmp_path):
    """A tiny edit must stay bounded when deleted notes left a large vocabulary."""
    source = tmp_path / "source.md"
    source.write_text("soil", encoding="utf-8")
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        with owned_transaction(vault.db, "retained vocabulary"):
            vault.db.executemany(
                "INSERT INTO lexical_presence_terms(term) VALUES (?)",
                (
                    ("archived" + "".join(chr(97 + (i // 26**j) % 26) for j in range(4)),)
                    for i in range(20_000)
                ),
            )
        source.write_text("soil quasar", encoding="utf-8")
        ticks = 0

        def budget_exhausted() -> int:
            nonlocal ticks
            ticks += 1
            return int(ticks > 200)

        # SQLite VM work, not elapsed time: generous for this complete sync's
        # indexed work, insufficient to walk the unrelated 20,000-row lexicon.
        vault.db.set_progress_handler(budget_exhausted, 100)
        try:
            vault.sync()
        finally:
            vault.db.set_progress_handler(None, 0)
        assert_exact_projection(vault.db)


@pytest.mark.parametrize("history_mode", ["dated_cohorts", "observed_additions"])
def test_selected_backfill_leaves_other_populations_lazy_and_preserves_evidence(
    tmp_path, history_mode
):
    cohorts = {
        "selected": "2026-01-12",
        "before": "2025-12-29",
        "future": "2026-01-19",
        "undated": None,
        "after-cutoff": "2026-01-07",
        "before-window": "2026-01-07",
        "empty": "2026-01-07",
        "forward-bin": "2026-01-07",
    }
    for name, cohort in cohorts.items():
        header = f"---\ncreated: {cohort}\n---\n" if cohort else ""
        (tmp_path / f"{name}.md").write_text(header + "soil", encoding="utf-8")
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        for name, cohort in cohorts.items():
            header = f"---\ncreated: {cohort}\n---\n" if cohort else ""
            (tmp_path / f"{name}.md").write_text(header + "soil aurora", encoding="utf-8")
        vault.sync()
        with owned_transaction(vault.db, "legacy populations"):
            vault.db.execute("UPDATE lexical_notes SET presence=NULL")
            vault.db.execute(
                "UPDATE lexical_events SET presence=NULL, bin_start='2026-01-12', "
                "previous_at='2026-01-01T00:00:00+00:00', "
                "observed_at='2026-01-13T00:00:00+00:00'"
            )
            vault.db.execute(
                "UPDATE lexical_events SET observed_at='2026-01-15T00:00:00+00:00' "
                "WHERE path='after-cutoff.md'"
            )
            vault.db.execute(
                "UPDATE lexical_events SET bin_start='2025-12-29' WHERE path='before-window.md'"
            )
            vault.db.execute(
                "UPDATE lexical_events SET bin_start='2026-01-19' WHERE path='forward-bin.md'"
            )
            vault.db.execute(
                "UPDATE lexical_events SET terms_json='[]', "
                "evidence_hash='legacy-empty-observation' "
                "WHERE path='empty.md'"
            )
        before = {
            "notes": list(
                vault.db.execute("SELECT path, counts_json FROM lexical_notes ORDER BY path")
            ),
            "events": list(
                vault.db.execute(
                    "SELECT path, bin_start, terms_json, revisions_json, "
                    "evidence_hash, observed_at "
                    "FROM lexical_events ORDER BY path"
                )
            ),
            "generation": vault.db.execute(
                "SELECT value FROM lexical_meta WHERE key='generation'"
            ).fetchone(),
        }
        vault.config.word_burst.history_mode = history_mode
        vault.config.word_burst.window_weeks = 2
        vault.config.word_burst.min_documents = 1
        vault.config.word_burst.min_populated_bins = 1
        stats = WordBurstDiagnostics()
        analyze_word_bursts(vault, end_day=date(2026, 1, 14), diagnostics=stats)
        assert stats.documents == 2
        assert not stats.cache_hit
        projected_notes = {
            path.removesuffix(".md")
            for (path,) in vault.db.execute(
                "SELECT path FROM lexical_notes WHERE presence IS NOT NULL"
            )
        }
        projected_events = {
            path.removesuffix(".md")
            for (path,) in vault.db.execute(
                "SELECT path FROM lexical_events WHERE presence IS NOT NULL"
            )
        }
        if history_mode == "dated_cohorts":
            assert projected_notes == {
                "selected",
                "after-cutoff",
                "before-window",
                "empty",
                "forward-bin",
            }
            assert projected_events == set()
        else:
            assert projected_notes == set()
            assert projected_events == {"selected", "before", "future", "undated", "empty"}
            assert vault.db.execute(
                "SELECT presence FROM lexical_events WHERE path='empty.md'"
            ).fetchone() == (b"",)
        assert (
            list(vault.db.execute("SELECT path, counts_json FROM lexical_notes ORDER BY path"))
            == before["notes"]
        )
        assert (
            list(
                vault.db.execute(
                    "SELECT path, bin_start, terms_json, revisions_json, "
                    "evidence_hash, observed_at "
                    "FROM lexical_events ORDER BY path"
                )
            )
            == before["events"]
        )
        assert (
            vault.db.execute("SELECT value FROM lexical_meta WHERE key='generation'").fetchone()
            == before["generation"]
        )
        # Completing the remaining projections leaves the selected vectors in
        # place, so the independent wire/JSON oracle also checks their contents.
        with owned_transaction(vault.db, "remaining legacy projection"):
            ensure_presence(vault.db)
        assert_exact_projection(vault.db)


@pytest.mark.parametrize("ids", [[0], [2, 1], [1, 1], [2**63]])
def test_corrupt_projection_is_rejected(ids):
    with pytest.raises(ValueError, match="positive, sorted and unique"):
        decode_presence(np.asarray(ids, dtype="<u8").tobytes())


def test_partial_numeric_id_is_rejected():
    with pytest.raises(ValueError, match="complete uint64"):
        decode_presence(b"\x01")
