"""Metric caches belong to exact inputs, even when same-date workers overlap."""

import sqlite3
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch

import numpy as np
import pytest

from geistfabrik.config_loader import GeistFabrikConfig
from geistfabrik.embedding_metrics import EmbeddingMetricsComputer
from geistfabrik.schema import init_db

DATE = "2025-01-15"
PATHS = ["a.md", "b.md"]


def _database(path: Path):
    db = init_db(path)
    db.executemany(
        """INSERT OR IGNORE INTO notes (path, title, content, created, modified, file_mtime)
           VALUES (?, ?, 'original', ?, ?, 1)""",
        [(path, path, DATE, DATE) for path in PATHS],
    )
    db.execute("INSERT OR IGNORE INTO sessions (date, created_at) VALUES (?, ?)", (DATE, DATE))
    db.commit()
    return db


@pytest.fixture
def cheap_metrics(monkeypatch):
    """Keep tests about cache behavior independent of clustering heuristics."""
    monkeypatch.setattr("geistfabrik.embedding_metrics.HAS_SKLEARN", True)
    monkeypatch.setattr(
        EmbeddingMetricsComputer,
        "_compute_basic_metrics",
        lambda self, embeddings: {"avg_similarity": float(embeddings[0, 0])},
    )
    monkeypatch.setattr(
        EmbeddingMetricsComputer,
        "_compute_clustering_metrics",
        lambda self, embeddings, paths: {"n_clusters": int(embeddings[0, 0])},
    )


def test_cache_roundtrip_preserves_complete_result(tmp_path, cheap_metrics):
    with _database(tmp_path / "metrics.db") as db:
        computer = EmbeddingMetricsComputer(db)
        embeddings = np.eye(2, dtype=np.float32)
        expected = computer.compute_metrics(DATE, embeddings, PATHS)
        with patch.object(
            computer, "_compute_basic_metrics", side_effect=AssertionError("cache miss")
        ):
            assert computer.compute_metrics(DATE, embeddings, PATHS) == expected
    db.close()


def test_keybert_results_without_model_identity_are_not_cached(tmp_path, cheap_metrics):
    db = _database(tmp_path / "keybert.db")
    config = GeistFabrikConfig()
    config.clustering.labeling_method = "keybert"
    computer = EmbeddingMetricsComputer(db, config)
    embeddings = np.eye(2, dtype=np.float32)
    with patch.object(
        computer, "_source_digest", side_effect=AssertionError("unusable cache work")
    ) as source_digest:
        computer.compute_metrics(DATE, embeddings, PATHS)
        with patch.object(
            computer, "_compute_basic_metrics", return_value={"vendi_score": 47}
        ) as compute:
            assert computer.compute_metrics(DATE, embeddings, PATHS)["vendi_score"] == 47
            compute.assert_called_once()
        source_digest.assert_not_called()
    assert db.execute("SELECT count(*) FROM embedding_metrics").fetchone() == (0,)
    db.close()


def test_source_digest_memory_is_bounded_by_actual_label_inputs(tmp_path):
    """Cache provenance must not copy entire note bodies that labelers never read."""
    db = init_db(tmp_path / "large-notes.db")
    paths = [f"note-{index}.md" for index in range(16)]
    large_content = "x" * 1_000_000
    db.executemany(
        """INSERT INTO notes (path, title, content, created, modified, file_mtime)
           VALUES (?, ?, ?, ?, ?, 1)""",
        ((path, path, large_content, DATE, DATE) for path in paths),
    )
    db.commit()
    computer = EmbeddingMetricsComputer(db)

    tracemalloc.start()
    try:
        computer._source_digest(np.zeros((len(paths), 2), dtype=np.float32), paths)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        db.close()

    assert peak < 4_000_000


def test_source_digest_matches_python_slicing_across_embedded_nul(tmp_path, cheap_metrics):
    db = _database(tmp_path / "nul-label-input.db")
    db.execute("UPDATE notes SET content = ? WHERE path = 'a.md'", ("prefix\0alpha labels",))
    db.commit()
    computer = EmbeddingMetricsComputer(db)
    embeddings = np.eye(2, dtype=np.float32)
    computer.compute_metrics(DATE, embeddings, PATHS)

    db.execute(
        "UPDATE notes SET content = ? WHERE path = 'a.md'",
        ("prefix\0beta different labels",),
    )
    db.commit()
    with patch.object(
        computer, "_compute_basic_metrics", return_value={"vendi_score": 47}
    ) as compute:
        assert computer.compute_metrics(DATE, embeddings, PATHS)["vendi_score"] == 47
        compute.assert_called_once()
    assert db.execute("SELECT count(*) FROM embedding_metrics").fetchone() == (2,)
    db.close()


@pytest.mark.parametrize(
    "change",
    [
        "bytes",
        "paths",
        "dtype",
        "config",
        "cluster_size",
        "note_text",
        "capability",
        "algorithm",
        "dependency",
    ],
)
def test_same_date_cache_requires_exact_inputs(tmp_path, cheap_metrics, monkeypatch, change):
    db = _database(tmp_path / "metrics.db")
    config = GeistFabrikConfig()
    config.clustering.labeling_method = "tfidf"
    computer = EmbeddingMetricsComputer(db, config)
    embeddings = np.eye(2, dtype=np.float32)
    paths = PATHS.copy()
    computer.compute_metrics(DATE, embeddings, paths)
    assert db.execute("SELECT count(*) FROM embedding_metrics").fetchone() == (1,)
    with patch.object(computer, "_compute_basic_metrics", side_effect=AssertionError("cache miss")):
        computer.compute_metrics(DATE, embeddings, paths)

    if change == "bytes":
        embeddings[0, 0] = 2
    elif change == "paths":
        paths.reverse()
    elif change == "dtype":
        embeddings = embeddings.astype(np.float64)
    elif change == "config":
        config.clustering.n_label_terms += 1
    elif change == "cluster_size":
        config.clustering.min_cluster_size += 1
    elif change == "note_text":
        db.execute("UPDATE notes SET title = 'changed' WHERE path = 'a.md'")
        db.commit()
    elif change == "capability":
        monkeypatch.setattr("geistfabrik.embedding_metrics.HAS_SKDIM", True)
    elif change == "algorithm":
        monkeypatch.setattr("geistfabrik.embedding_metrics.METRICS_ALGORITHM_VERSION", 999)
    else:
        monkeypatch.setattr("geistfabrik.embedding_metrics.version", lambda package: "999")

    with patch.object(
        computer, "_compute_basic_metrics", return_value={"vendi_score": 47}
    ) as compute:
        result = computer.compute_metrics(DATE, embeddings, paths)
        compute.assert_called_once()
        assert result["vendi_score"] == 47
    db.close()


def test_old_worker_cannot_displace_new_same_date_cache(tmp_path, cheap_metrics):
    db_path = tmp_path / "overlapping.db"
    db = _database(db_path)
    old_started = Event()
    release_old = Event()
    older = np.eye(2, dtype=np.float32)
    newer = older * 2

    def old_worker():
        connection = init_db(db_path)
        try:
            computer = EmbeddingMetricsComputer(connection)

            def wait_for_newer(embeddings):
                old_started.set()
                assert release_old.wait(5)
                return {"avg_similarity": float(embeddings[0, 0])}

            with patch.object(computer, "_compute_basic_metrics", side_effect=wait_for_newer):
                return computer.compute_metrics(DATE, older, PATHS, force_recompute=True)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(old_worker)
        try:
            assert old_started.wait(5)
            computer = EmbeddingMetricsComputer(db)
            expected = computer.compute_metrics(DATE, newer, PATHS, force_recompute=True)
        finally:
            release_old.set()
        assert pending.result(timeout=5)["n_clusters"] == 1

    with patch.object(computer, "_compute_basic_metrics", side_effect=AssertionError("cache miss")):
        assert computer.compute_metrics(DATE, newer, PATHS)["n_clusters"] == expected["n_clusters"]
    db.close()


def test_late_old_snapshot_keeps_new_snapshot_cache(tmp_path, cheap_metrics):
    """Even an old input arriving after a newer commit has a separate cache key."""
    db = _database(tmp_path / "late-old-input.db")
    computer = EmbeddingMetricsComputer(db)
    old = np.eye(2, dtype=np.float32)
    new = old * 2
    expected = computer.compute_metrics(DATE, new, PATHS)
    computer.compute_metrics(DATE, old, PATHS)
    with patch.object(computer, "_compute_basic_metrics", side_effect=AssertionError("cache miss")):
        assert computer.compute_metrics(DATE, new, PATHS) == expected
    assert db.execute("SELECT count(*) FROM embedding_metrics").fetchone() == (2,)
    db.close()


def test_label_source_change_during_computation_is_not_cached(tmp_path, cheap_metrics):
    db = _database(tmp_path / "changed-label-source.db")
    computer = EmbeddingMetricsComputer(db)
    embeddings = np.eye(2, dtype=np.float32)

    def mutate_labels(_embeddings):
        db.execute("UPDATE notes SET content = 'new label input'")
        db.commit()
        return {"avg_similarity": 1.0}

    with patch.object(computer, "_compute_basic_metrics", side_effect=mutate_labels):
        computer.compute_metrics(DATE, embeddings, PATHS)

    assert db.execute("SELECT count(*) FROM embedding_metrics").fetchone() == (0,)
    db.close()


def test_metrics_cache_write_failure_rolls_back(tmp_path, cheap_metrics):
    db = _database(tmp_path / "cache-failure.db")
    db.execute("""CREATE TRIGGER reject_metrics BEFORE INSERT ON embedding_metrics
                  BEGIN SELECT RAISE(ABORT, 'injected cache failure'); END""")
    computer = EmbeddingMetricsComputer(db)
    with pytest.raises(sqlite3.IntegrityError, match="injected cache failure"):
        computer.compute_metrics(DATE, np.eye(2, dtype=np.float32), PATHS)

    assert not db.in_transaction
    assert db.execute("SELECT count(*) FROM embedding_metrics").fetchone() == (0,)
    assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    db.close()


def test_metrics_cache_preserves_caller_transaction(tmp_path, cheap_metrics):
    db = _database(tmp_path / "caller-transaction.db")
    db.execute("UPDATE notes SET content = 'uncommitted caller work'")
    computer = EmbeddingMetricsComputer(db)
    with pytest.raises(RuntimeError, match="idle SQLite connection"):
        computer.compute_metrics(DATE, np.eye(2, dtype=np.float32), PATHS)

    assert db.in_transaction
    assert db.execute("SELECT DISTINCT content FROM notes").fetchall() == [
        ("uncommitted caller work",)
    ]
    observer = sqlite3.connect(tmp_path / "caller-transaction.db")
    assert observer.execute("SELECT DISTINCT content FROM notes").fetchall() == [("original",)]
    observer.close()
    db.rollback()
    assert db.execute("SELECT DISTINCT content FROM notes").fetchall() == [("original",)]
    db.close()
