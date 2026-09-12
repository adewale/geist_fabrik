"""Replay boundaries, canonical cluster history, and small-vault statistics."""

from contextlib import closing
from datetime import datetime
from unittest.mock import Mock, patch

import numpy as np
import pytest

from geistfabrik import Session, Vault, VaultContext
from geistfabrik.clustering_analysis import ClusterAnalyser
from geistfabrik.config_loader import GeistFabrikConfig
from geistfabrik.default_geists.code import cluster_mirror
from geistfabrik.embedding_metrics import EmbeddingMetricsComputer
from geistfabrik.schema import init_db
from geistfabrik.stats import StatsCollector
from geistfabrik.temporal_analysis import EmbeddingTrajectoryCalculator, TemporalSemanticQuery


@pytest.fixture
def replay_context(tmp_path):
    for index in range(6):
        (tmp_path / f"note-{index}.md").write_text(f"# Note {index}\nTopic {index}")
    with closing(Vault(tmp_path)) as vault:
        vault.config.clustering.labeling_method = "tfidf"
        vault.config.clustering.min_cluster_size = 2
        vault.sync()
        sessions = []
        for month in (1, 2, 3, 4, 12):
            session = Session(datetime(2024, month, 1), vault.db)
            session.compute_embeddings(vault.all_notes())
            sessions.append(session)
        yield VaultContext(vault, sessions[3]), sessions


def test_replay_bounds_every_history_reader_and_parses_trajectory_dates(replay_context):
    context, sessions = replay_context
    note = context.notes()[0]
    expected_dates = [datetime(2024, month, 1) for month in (1, 2, 3, 4)]
    calculator = EmbeddingTrajectoryCalculator(context, note)
    assert [when for when, _ in calculator.snapshots()] == expected_dates
    assert context.session_count() == 4
    assert context.recent_session_ids(count=10) == [s.session_id for s in sessions[3::-1]]
    assert context.session_dates_for_note(note) == [d.strftime("%Y-%m-%d") for d in expected_dates]
    assert [row[1] for row in context.session_embeddings_by_session()] == [
        d.strftime("%Y-%m-%d") for d in reversed(expected_dates)
    ]
    # Explicit IDs cannot bypass the replay boundary; an empty selection stays empty.
    assert EmbeddingTrajectoryCalculator(context, note, [sessions[-1].session_id]).snapshots() == []
    assert EmbeddingTrajectoryCalculator(context, note, []).snapshots() == []
    # This reaches the seasonal date.month consumer, which used to receive strings.
    assert set(TemporalSemanticQuery(context).drift_direction_by_period(note)) == {
        "winter",
        "spring",
    }


def test_cluster_history_rejects_future_and_incompatible_config(replay_context):
    context, sessions = replay_context
    note = context.notes()[0]
    prior = VaultContext(context.vault, sessions[0])
    prior.persist_cluster_labels({note.path: "old topics"})
    assert context.previous_cluster_label_for_note(note, sessions[0].session_id) == "old topics"
    future = VaultContext(context.vault, sessions[-1])
    future.persist_cluster_labels({note.path: "future topics"})
    assert context.previous_cluster_label_for_note(note, sessions[-1].session_id) is None
    context.vault.config.clustering.min_cluster_size = 3
    assert context.previous_cluster_label_for_note(note, sessions[0].session_id) is None


def test_stats_drift_uses_requested_replay_date(replay_context):
    context, _sessions = replay_context
    collector = StatsCollector(context.vault, context.vault.config)
    result = collector.get_temporal_drift("2024-04-01", days_back=15)
    assert result is not None
    assert result["current_date"] == "2024-04-01"
    assert result["comparison_date"] == "2024-03-01"
    assert collector.get_temporal_drift("2023-12-01") is None


def test_cluster_consumers_share_cache_and_only_canonical_size_writes_history(replay_context):
    context, _sessions = replay_context
    with (
        patch("sklearn.cluster.HDBSCAN") as constructor,
        patch("geistfabrik.cluster_labeling.label_tfidf", return_value={0: "first", 1: "second"}),
    ):
        constructor.return_value.fit_predict.return_value = np.array([0, 0, 0, 1, 1, 1])
        canonical = context.get_clusters()
        assert ClusterAnalyser(context).get_clusters() is canonical
        assert len(cluster_mirror.suggest(context)) == 1
        constructor.assert_called_once_with(min_cluster_size=2, min_samples=3)
        before = context.db.execute(
            "SELECT note_path, cluster_label FROM session_embeddings "
            "WHERE session_id = ? ORDER BY note_path",
            (context.session.session_id,),
        ).fetchall()
        assert all(label is not None for _, label in before)

        constructor.return_value.fit_predict.return_value = np.array([-1] * 6)
        assert ClusterAnalyser(context, min_size=3).get_clusters() == {}
        assert (
            context.db.execute(
                "SELECT note_path, cluster_label FROM session_embeddings "
                "WHERE session_id = ? ORDER BY note_path",
                (context.session.session_id,),
            ).fetchall()
            == before
        )

        # Promoting a cached exploratory result to the configured policy clears old labels.
        context.vault.config.clustering.min_cluster_size = 3
        assert context.get_clusters() == {}
        assert context.db.execute(
            "SELECT count(*) FROM session_embeddings "
            "WHERE session_id = ? AND cluster_label IS NOT NULL",
            (context.session.session_id,),
        ).fetchone() == (0,)
        assert constructor.call_count == 2


@pytest.mark.parametrize("count", [0, 1, 2])
def test_small_vault_metrics_report_unclustered_notes_without_crashing(count):
    db = init_db()
    try:
        db.execute("INSERT INTO sessions (date, created_at) VALUES ('2024-01-01', '2024-01-01')")
        db.commit()
        result = EmbeddingMetricsComputer(db).compute_metrics(
            "2024-01-01", np.eye(count, 3, dtype=np.float32), [f"note-{i}" for i in range(count)]
        )
        assert result["n_clusters"] == 0
        assert result["n_gaps"] == count
        assert result["gap_pct"] == (100.0 if count else 0.0)
    finally:
        db.close()


def test_stats_clustering_uses_configured_minimum():
    db = init_db()
    try:
        config = GeistFabrikConfig()
        config.clustering.min_cluster_size = 2
        config.clustering.labeling_method = "tfidf"
        computer = EmbeddingMetricsComputer(db, config)
        constructor = Mock()
        constructor.return_value.fit_predict.return_value = np.array([-1] * 4)
        with patch("geistfabrik.embedding_metrics.HDBSCAN", constructor):
            computer._compute_clustering_metrics(np.eye(4), ["a", "b", "c", "d"])
        constructor.assert_called_once_with(min_cluster_size=2, min_samples=3)
    finally:
        db.close()


def test_large_vault_stats_are_independent_of_global_random_state():
    embeddings = np.random.default_rng(7).normal(size=(1001, 3)).astype(np.float32)
    state = np.random.get_state()
    with closing(init_db()) as db:
        computer = EmbeddingMetricsComputer(db)
        try:
            with (
                patch("geistfabrik.embedding_metrics.HAS_SKDIM", False),
                patch("geistfabrik.embedding_metrics.HAS_VENDI", False),
            ):
                np.random.seed(1)
                first = computer._compute_basic_metrics(embeddings)
                np.random.seed(2)
                second = computer._compute_basic_metrics(embeddings)
                assert first == second
        finally:
            np.random.set_state(state)
