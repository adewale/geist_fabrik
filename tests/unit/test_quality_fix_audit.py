"""Storage lifecycle proof missing from the individual quality-fix owners."""

from contextlib import closing
from datetime import datetime
from unittest.mock import MagicMock

from geistfabrik.evidence_identity import interval_evidence_key
from geistfabrik.filtering import SuggestionFilter
from geistfabrik.journal_writer import JournalWriter
from geistfabrik.models import Suggestion
from geistfabrik.schema import SCHEMA_VERSION, init_db


def test_saved_episode_memory_survives_v12_migration_and_a_second_reopen(tmp_path):
    """Upgrade a real saved question, then exercise durable novelty after expiry.

    Existing migration proof preserves NULL evidence; existing history proof
    starts from a fresh schema. This protects their storage/lifecycle boundary
    without duplicating interval arithmetic or dictionary-cache assertions.
    """
    identity = ["word_burst", "dated_cohorts", "rising", "small experiments"]
    key = interval_evidence_key(identity, "2024-01-01", "2024-01-21")
    saved = Suggestion("What connects these experiments?", ["Plan"], "word_burst", evidence_key=key)
    db_path = tmp_path / "vault.db"
    with closing(init_db(db_path)) as db:
        JournalWriter(tmp_path, db).write_session(datetime(2024, 1, 22), [saved])
        # Materialize the known v12 derived structure independently of what
        # the current initializer creates. Keep the actual writer's key/rows.
        db.execute("DROP TABLE word_burst_cache")
        db.execute(
            "CREATE TABLE word_burst_cache (cache_key TEXT PRIMARY KEY, result_json TEXT NOT NULL)"
        )
        db.execute("DROP INDEX IF EXISTS idx_session_suggestions_evidence")
        db.execute("PRAGMA user_version = 12")
        db.commit()
    journal = tmp_path / "geist journal/2024-01-22.md"
    original_text = journal.read_bytes()

    with closing(init_db(db_path)) as upgraded:
        assert upgraded.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
        assert upgraded.execute("SELECT evidence_key FROM session_suggestions").fetchall() == [
            (key,)
        ]

    with closing(init_db(db_path)) as reopened:
        repeated = Suggestion(
            "A differently worded question", ["Plan"], "word_burst", evidence_key=key
        )
        overlap = Suggestion(
            "A clipped view of that episode",
            ["Plan"],
            "word_burst",
            evidence_key=interval_evidence_key(identity, "2024-01-15", "2024-01-28"),
        )
        returned = Suggestion(
            "A genuinely later return",
            ["Plan"],
            "word_burst",
            evidence_key=interval_evidence_key(identity, "2025-01-06", "2025-01-12"),
        )
        filtering = SuggestionFilter(
            reopened, MagicMock(), config={"novelty": {"method": "text_match"}}
        )
        assert filtering.filter_novelty([repeated, overlap, returned], datetime(2025, 2, 1)) == [
            returned
        ]
    assert journal.read_bytes() == original_text
