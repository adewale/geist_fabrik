"""Integration tests for VaultContext.get_clusters and its clustering config.

This file is the owner of the config plumbing between
``vault.config.clustering`` and the cluster labelers: ``labeling_method``
chooses the labeler and ``n_label_terms`` sets the label length. The labelers
themselves are unit-tested in tests/unit/test_cluster_labeling.py.

The fixture is three topic groups whose notes share vocabulary within a group
and none across groups. Under the lexical test embedding stub that gives three
well-separated groups, so HDBSCAN reliably forms one cluster per topic and
every assertion below runs against real clusters rather than an empty dict.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from geistfabrik import cluster_labeling
from geistfabrik.config_loader import ClusterConfig
from geistfabrik.vault_context import Cluster, VaultContext
from tests.fixtures.helpers import VaultBuilder

TOPICS = {
    "Garden": "compost soil seedlings tomatoes watering mulch harvest greenhouse",
    "Sailing": "keel rudder spinnaker mooring tides harbour anchor regatta",
    "Baking": "sourdough starter flour oven crust proofing dough loaves",
}
NOTES_PER_TOPIC = 6
METHODS = ("tfidf", "keybert")


@pytest.fixture
def topic_vault(tmp_path: Path) -> VaultContext:
    """Six notes per topic, each a different rotation of the topic's words."""
    builder = VaultBuilder(tmp_path)
    for topic, words in TOPICS.items():
        vocab = words.split()
        for i in range(NOTES_PER_TOPIC):
            body = " ".join(vocab[(i + k) % len(vocab)] for k in range(6))
            builder.note(f"{topic} {i}", body)
    return builder.build()


def _configure(ctx: VaultContext, method: str, n_terms: int) -> None:
    ctx.vault.config.clustering = ClusterConfig(labeling_method=method, n_label_terms=n_terms)


def _terms(cluster: Cluster) -> list[str]:
    return [term.strip() for term in cluster.label.split(",")]


def _topic_of(cluster: Cluster) -> str:
    topics = {note.title.split()[0] for note in cluster.notes}
    assert len(topics) == 1, f"cluster mixes topics: {sorted(n.title for n in cluster.notes)}"
    return topics.pop()


@pytest.mark.parametrize("method", METHODS)
def test_topic_groups_form_clusters_labelled_from_their_own_vocabulary(
    topic_vault: VaultContext, method: str
) -> None:
    """One cluster per topic, labelled with words from that topic only.

    Regression caught: clustering that merges or splits the topics, or labels
    drawn from the wrong cluster's text (e.g. a label/cluster-id mix-up).
    """
    _configure(topic_vault, method, 3)

    clusters = topic_vault.get_clusters()

    assert len(clusters) == len(TOPICS)
    seen_topics = set()
    for cluster in clusters.values():
        topic = _topic_of(cluster)
        seen_topics.add(topic)
        assert cluster.size == len(cluster.notes) == NOTES_PER_TOPIC
        allowed = {topic.lower(), *TOPICS[topic].split()}
        for term in _terms(cluster):
            assert set(term.split()) <= allowed, (
                f"{method} label term {term!r} for {topic} uses foreign words"
            )
            assert term in cluster.formatted_label
    assert seen_topics == set(TOPICS)


@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("n_terms", [2, 4])
def test_n_label_terms_sets_label_length(
    topic_vault: VaultContext, method: str, n_terms: int
) -> None:
    """Each label has exactly the configured number of terms.

    Every topic offers more candidate terms than either setting, so a label
    shorter or longer than ``n_label_terms`` means the setting was dropped.
    Regression caught: get_clusters not passing n_label_terms to the labeler
    (which then uses its own default of 4).
    """
    _configure(topic_vault, method, n_terms)

    clusters = topic_vault.get_clusters()

    assert len(clusters) == len(TOPICS)
    for cluster in clusters.values():
        assert len(_terms(cluster)) == n_terms, cluster.label


@pytest.mark.parametrize("method", METHODS)
def test_labeling_method_selects_the_labeler(
    topic_vault: VaultContext, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    """``labeling_method`` routes to that labeler, and its labels are used.

    The spies delegate to the real labelers, so they record the choice without
    supplying the result. Regression caught: get_clusters ignoring the
    configured method (e.g. always using c-TF-IDF).
    """
    calls: dict[str, list[tuple[int, dict[int, str]]]] = {name: [] for name in METHODS}

    def spy(name: str, real: Callable[..., dict[int, str]]) -> Callable[..., dict[int, str]]:
        def wrapper(*args: Any, **kwargs: Any) -> dict[int, str]:
            result = real(*args, **kwargs)
            calls[name].append((kwargs["n_terms"], result))
            return result

        return wrapper

    monkeypatch.setattr(cluster_labeling, "label_tfidf", spy("tfidf", cluster_labeling.label_tfidf))
    monkeypatch.setattr(
        cluster_labeling, "label_keybert", spy("keybert", cluster_labeling.label_keybert)
    )
    _configure(topic_vault, method, 3)

    clusters = topic_vault.get_clusters()

    other = next(name for name in METHODS if name != method)
    assert calls[other] == []
    assert len(calls[method]) == 1
    n_terms, labels = calls[method][0]
    assert n_terms == 3
    assert {int(cid): c.label for cid, c in clusters.items()} == {
        int(cid): label for cid, label in labels.items()
    }


def test_changing_config_mid_session_relabels_the_same_clusters(
    topic_vault: VaultContext,
) -> None:
    """Changing labeling settings on a live context yields fresh labels.

    get_clusters caches per session; the cache must be keyed on the labeling
    settings, not just cluster size. Regression caught: a stale cached label
    set returned after the config changes.
    """
    _configure(topic_vault, "tfidf", 2)
    short = topic_vault.get_clusters()
    _configure(topic_vault, "keybert", 4)
    long = topic_vault.get_clusters()

    def membership(clusters: dict[int, Cluster]) -> set[frozenset[str]]:
        return {frozenset(n.path for n in c.notes) for c in clusters.values()}

    assert membership(short) == membership(long)
    assert {len(_terms(c)) for c in short.values()} == {2}
    assert {len(_terms(c)) for c in long.values()} == {4}
