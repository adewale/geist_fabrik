"""Tests for cluster labelling methods (c-TF-IDF and KeyBERT)."""

from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.cluster_labeling import apply_mmr


@pytest.fixture
def mock_db(tmp_path):
    """Create a mock database with test notes."""
    import sqlite3

    db_path = tmp_path / "test.db"
    db = sqlite3.connect(str(db_path))

    # Create notes table
    db.execute(
        """
        CREATE TABLE notes (
            path TEXT PRIMARY KEY,
            title TEXT,
            content TEXT
        )
        """
    )

    # Insert test notes for clustering
    test_notes = [
        ("note1.md", "Machine Learning", "Deep learning neural networks training models"),
        ("note2.md", "Neural Networks", "Backpropagation gradient descent optimisation"),
        ("note3.md", "AI Training", "Model training validation testing evaluation"),
        ("note4.md", "React Components", "React hooks useState useEffect components"),
        ("note5.md", "Frontend Development", "JavaScript TypeScript web development"),
        ("note6.md", "Web Architecture", "Frontend architecture patterns state management"),
    ]

    db.executemany("INSERT INTO notes (path, title, content) VALUES (?, ?, ?)", test_notes)
    db.commit()

    return db


class TestClusterLabelingTFIDF:
    """Test c-TF-IDF cluster labelling method."""

    def test_label_clusters_tfidf_basic(self, mock_db):
        """Test that c-TF-IDF labelling produces keyword lists."""

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # Create cluster labels (2 clusters)
        paths = ["note1.md", "note2.md", "note3.md", "note4.md", "note5.md", "note6.md"]
        labels = np.array([0, 0, 0, 1, 1, 1])  # 3 notes in each cluster

        result = metrics._label_clusters_tfidf(paths, labels, n_terms=3)

        # Should have labels for both clusters
        assert 0 in result
        assert 1 in result

        # Labels should be comma-separated strings
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)
        assert "," in result[0] or len(result[0].split()) <= 3
        assert "," in result[1] or len(result[1].split()) <= 3

    def test_label_clusters_tfidf_empty(self, mock_db):
        """Test c-TF-IDF with no clusters."""

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # All noise points
        paths = ["note1.md", "note2.md"]
        labels = np.array([-1, -1])

        result = metrics._label_clusters_tfidf(paths, labels, n_terms=3)

        # Should return empty dict
        assert result == {}

    def test_label_clusters_tfidf_single_cluster(self, mock_db):
        """Test c-TF-IDF with single cluster."""

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        paths = ["note1.md", "note2.md", "note3.md"]
        labels = np.array([0, 0, 0])

        result = metrics._label_clusters_tfidf(paths, labels, n_terms=3)

        assert 0 in result
        assert isinstance(result[0], str)


class TestClusterLabelingKeyBERT:
    """Test KeyBERT cluster labelling method."""

    def test_label_clusters_keybert_basic(self, mock_db):
        """Test that KeyBERT labelling produces semantic phrases."""

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # Create cluster labels (2 clusters)
        paths = ["note1.md", "note2.md", "note3.md", "note4.md", "note5.md", "note6.md"]
        labels = np.array([0, 0, 0, 1, 1, 1])

        result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

        # Should have labels for both clusters
        assert 0 in result
        assert 1 in result

        # Labels should be comma-separated strings
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)

    def test_label_clusters_keybert_empty(self, mock_db):
        """Test KeyBERT with no clusters."""

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        # All noise points
        paths = ["note1.md", "note2.md"]
        labels = np.array([-1, -1])

        result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

        # Should return empty dict
        assert result == {}

    def test_label_clusters_keybert_fallback_on_error(self, mock_db):
        """Test KeyBERT falls back gracefully on errors."""

        from unittest.mock import patch

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        paths = ["note1.md", "note2.md", "note3.md"]
        labels = np.array([0, 0, 0])

        # Mock EmbeddingComputer to raise an error
        with patch("geistfabrik.embeddings.EmbeddingComputer") as mock_computer:
            mock_computer.return_value.compute_batch_semantic.side_effect = Exception(
                "Model failed"
            )

            result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

            # Should have fallback label
            assert 0 in result
            assert "Cluster 0" in result[0]


class TestClusterLabelingComparison:
    """Compare c-TF-IDF and KeyBERT methods."""

    def test_both_methods_produce_labels(self, mock_db):
        """Verify both methods produce valid labels for the same input."""

        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)

        paths = ["note1.md", "note2.md", "note3.md", "note4.md", "note5.md", "note6.md"]
        labels = np.array([0, 0, 0, 1, 1, 1])

        tfidf_result = metrics._label_clusters_tfidf(paths, labels, n_terms=3)
        keybert_result = metrics._label_clusters_keybert(paths, labels, n_terms=3)

        # Both should have same cluster IDs
        assert set(tfidf_result.keys()) == set(keybert_result.keys())

        # Both should produce non-empty strings
        for cluster_id in tfidf_result:
            assert len(tfidf_result[cluster_id]) > 0
            assert len(keybert_result[cluster_id]) > 0

    def test_keybert_labels_use_trigrams_tfidf_labels_do_not(self, mock_db):
        """KeyBERT draws candidates from 1-3 word n-grams, c-TF-IDF from 1-2.

        Under the lexical stub a trigram of central words sits closest to the
        cluster centroid, so KeyBERT picks one; narrowing its ngram_range
        (or routing it through the c-TF-IDF candidates) fails this test.
        """
        from geistfabrik.embedding_metrics import EmbeddingMetricsComputer

        metrics = EmbeddingMetricsComputer(mock_db)
        paths = ["note1.md", "note2.md", "note3.md", "note4.md", "note5.md", "note6.md"]
        labels = np.array([0, 0, 0, 1, 1, 1])

        keybert = metrics._label_clusters_keybert(paths, labels, n_terms=3)
        tfidf = metrics._label_clusters_tfidf(paths, labels, n_terms=3)

        def ngram_lengths(label: str) -> list[int]:
            return [len(term.split()) for term in label.split(", ")]

        for cluster_id in (0, 1):
            assert max(ngram_lengths(keybert[cluster_id])) == 3, keybert
            assert max(ngram_lengths(tfidf[cluster_id])) <= 2, tfidf


def _naive_mmr(terms: list[str], scores: list[float], lambda_param: float, k: int) -> list[str]:
    """Textbook greedy MMR with word-set Jaccard as the redundancy measure."""
    if len(terms) <= k:
        return terms

    def jaccard(x: str, y: str) -> float:
        a, b = set(x.lower().split()), set(y.lower().split())
        return len(a & b) / len(a | b) if a and b else 0.0

    selected: list[str] = []
    while len(selected) < k:
        best_term, best_score = "", float("-inf")
        for term, relevance in zip(terms, scores, strict=True):
            if term in selected:
                continue
            redundancy = max((jaccard(term, s) for s in selected), default=0.0)
            score = lambda_param * relevance - (1 - lambda_param) * redundancy
            if score > best_score:  # first maximum wins, like np.argmax
                best_term, best_score = term, score
        selected.append(best_term)
    return selected


_WORDS = ["neural", "network", "deep", "learning", "model", "graph", "garden"]
_terms = st.lists(
    st.lists(st.sampled_from(_WORDS), min_size=1, max_size=3).map(" ".join),
    min_size=1,
    max_size=10,
    unique=True,
)


@given(
    data=st.data(),
    terms=_terms,
    lambda_param=st.sampled_from([0.0, 0.3, 0.5, 0.7, 1.0]),
    k=st.integers(min_value=1, max_value=6),
)
@settings(max_examples=100, deadline=None)
def test_apply_mmr_matches_naive_reference(
    data: st.DataObject, terms: list[str], lambda_param: float, k: int
) -> None:
    """apply_mmr selects exactly what greedy MMR selects, in order.

    Regressions caught: penalising by the least (not most) similar selected
    term, dropping the diversity term or the lambda weighting, re-selecting a
    term, and an exception silently degrading to plain top-k by score.
    """
    scores = data.draw(
        st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            min_size=len(terms),
            max_size=len(terms),
        )
    )

    got = apply_mmr(terms, np.array(scores), lambda_param=lambda_param, k=k)

    assert got == _naive_mmr(terms, scores, lambda_param, k)


def test_apply_mmr_prefers_diverse_term_over_redundant_one() -> None:
    """Known answer: the runner-up shares a word with the winner, so a less
    relevant but unrelated term is picked second."""
    terms = ["neural network", "neural model", "garden soil"]
    scores = np.array([0.9, 0.85, 0.6])

    assert apply_mmr(terms, scores, lambda_param=0.5, k=2) == ["neural network", "garden soil"]
    # Pure relevance ignores redundancy.
    assert apply_mmr(terms, scores, lambda_param=1.0, k=2) == ["neural network", "neural model"]


class TestClusterConfig:
    """Test cluster configuration integration."""

    def test_config_defaults(self):
        """Verify clustering config has sensible defaults."""
        from geistfabrik.config_loader import ClusterConfig

        config = ClusterConfig()

        assert config.labeling_method == "keybert"
        assert config.min_cluster_size == 5
        assert config.n_label_terms == 4


def test_label_text_skips_frontmatter_code_and_numbers() -> None:
    """Contract: cluster labels come from what notes say, not YAML or code.

    Regression: labels were built from raw content, giving names like
    "tags daily notes, 2023, 09" from frontmatter and dates.
    """
    import re

    from geistfabrik.cluster_labeling import _WORD_TOKEN_PATTERN, _label_text

    content = "---\ntags: [daily]\ncreated: 2023-09-12\n---\nSoil and compost.\n```\nx = 1\n```\n"
    text = _label_text("Garden", content)

    assert "tags" not in text and "2023" not in text and "x = 1" not in text
    assert text.startswith("Garden") and "Soil and compost." in text
    assert re.findall(_WORD_TOKEN_PATTERN, "notes 2023 09 v2 io_rate garden") == [
        "notes",
        "garden",
    ]


# ---------------------------------------------------------------------------
# Label text without YAML parsing: equivalence with parse_frontmatter
# ---------------------------------------------------------------------------

_FM_KEYS = ["title", "tags", "aliases", "On", "yes", "Null", "a-b", "_x", "2023", "k e", "~"]
_FM_VALUES = [
    "",
    "plain text",
    "x: y",
    "x:",
    "x #c",
    "x#c",
    "#c",
    "[a, b]",
    "[a, ]",
    "[]",
    "[ ]",
    "[[Note]]",
    '"[[Note]]"',
    '"esc \\q"',
    '"a, b"',
    '["x]y", z]',
    "'single'",
    "'it''s'",
    "2023-02-30",
    "2023-09-12",
    "0000-01-01",
    "2023-9-1",
    "12",
    "007",
    "0x1F",
    "-5",
    "1.5",
    "1_000",
    "12:30",
    "0🌲",
    "3 apples",
    "1e5",
    "~",
    "<<",
    "=",
    "@x",
    "`x`",
    "x\ty",
    "a\u2028b",
    "x\x85y",
    "x\ufeffy",
    "x\x00",
    "value  ",
    "*alias",
    "&anchor x",
    "!tag x",
    "|",
    ">",
    "https://x.y/z",
    "x, y",
    "{a: 1}",
    "%x",
    "?",
    "? x",
    "- x",
    "-",
    "x\r",
    "yes",
    "Ünïcödé",
]


@st.composite
def _frontmatter_documents(draw: st.DrawFn) -> str:
    line = st.one_of(
        st.builds(
            "{}:{}{}".format,
            st.sampled_from(_FM_KEYS),
            st.sampled_from(["", " ", "  ", "\t"]),
            st.sampled_from(_FM_VALUES),
        ),
        st.builds(
            "{}-{}{}".format,
            st.sampled_from(["", " ", "  ", "   ", "\t"]),
            st.sampled_from(["", " ", "  "]),
            st.sampled_from(_FM_VALUES),
        ),
        st.sampled_from(["", "  ", "# comment", "  # c", "...", "---x", "plain", "key:value"]),
        st.sampled_from(["%YAML 1.1", "\r", "a: 1\r", "  nested: 1", "a: b\rc: d"]),
    )
    lines = draw(st.lists(line, max_size=8))
    opening = draw(st.sampled_from(["---", "---", "--- ", "---x"]))
    closing = draw(st.sampled_from(["---", "---", " --- ", "---\r", None]))
    parts = [opening, *lines] + ([closing] if closing is not None else [])
    return "\n".join([*parts, "Body line one.", "Body `code` two."])


def _outcome(function, content: str) -> tuple[str, object]:
    try:
        return ("ok", function(content))
    except Exception as exc:  # the full parser can raise (e.g. impossible dates)
        return ("raise", type(exc))


@settings(max_examples=600, deadline=None)
@given(_frontmatter_documents())
def test_strip_frontmatter_equals_parse_frontmatter_body(content: str) -> None:
    """Equivalence: the YAML-free strip returns exactly parse_frontmatter()'s
    body (or raises as it does) for valid, invalid, non-mapping, non-string
    key, and resource-edge frontmatter alike."""
    from geistfabrik.cluster_labeling import _strip_frontmatter
    from geistfabrik.markdown_parser import parse_frontmatter

    assert _outcome(_strip_frontmatter, content) == _outcome(
        lambda c: parse_frontmatter(c)[1], content
    )


def _repository_notes() -> list[str]:
    root = Path(__file__).resolve().parents[2] / "testdata"
    return [path.read_text() for path in sorted(root.rglob("*.md"))]


_REAL_FRONTMATTER = """---
categories:
  - "[[Meetings]]"
type: []
date: 2023-09-14
aliases: [Steph, 'S. Ango']
url: https://stephango.com/evergreen-notes
tags:
- 0🌲
- clippings
status: draft
year: 2020
---
# Meeting

Talked about `emergence` and gardens.
"""


def _head_label_text(title: str, content: str) -> str:
    """_label_text as it was: full YAML parse, then every prose line."""
    from geistfabrik.markdown_parser import (
        INLINE_CODE_PATTERN,
        markdown_prose_lines,
        parse_frontmatter,
    )

    body = parse_frontmatter(content)[1]
    prose = "\n".join(line for _, line in markdown_prose_lines(body))
    return f"{title} {INLINE_CODE_PATTERN.sub(' ', prose)[:200]}"


@settings(max_examples=300, deadline=None)
@given(
    st.lists(
        st.sampled_from(
            ["word " * 30, "`a` b `c", "```", "~~~", "    indented code", "x" * 250, "", "- [ ] t"]
        ),
        max_size=12,
    ),
    st.sampled_from(["", _REAL_FRONTMATTER, "---\nbad: [\n---\n"]),
)
def test_label_text_equals_previous_implementation(lines: list[str], frontmatter: str) -> None:
    """Equivalence: reading prose lines only until 200 characters are kept
    (and stripping frontmatter without YAML) gives the same label text."""
    from geistfabrik.cluster_labeling import _label_text

    content = frontmatter + "\n".join(lines)
    assert _label_text("Title", content) == _head_label_text("Title", content)


def test_label_text_matches_previous_implementation_on_repository_notes() -> None:
    from geistfabrik.cluster_labeling import _label_text

    notes = [*_repository_notes(), _REAL_FRONTMATTER]
    assert len(notes) > 5
    for content in notes:
        assert _label_text("T", content) == _head_label_text("T", content)


def test_label_text_parses_no_yaml_for_typical_obsidian_frontmatter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: every clustered note's frontmatter went through a full
    bounded YAML parse per labelling run (~0.9 of 1.0 s of label-text time
    for 1,662 notes). Typical frontmatter now needs none."""
    import geistfabrik.markdown_parser as markdown_parser
    from geistfabrik.cluster_labeling import _label_text

    parses: list[str] = []
    real = markdown_parser.load_bounded_yaml_text

    def counting(text: str, source: str = "<yaml>") -> object:
        parses.append(text)
        return real(text, source)

    monkeypatch.setattr(markdown_parser, "load_bounded_yaml_text", counting)

    typical = [content for content in _repository_notes() if content.startswith("---")]
    assert typical
    for content in [*typical, _REAL_FRONTMATTER]:
        assert "categories" not in _label_text("T", content)

    assert parses == []


# ---------------------------------------------------------------------------
# KeyBERT: reuse the session's computer; re-encode only changed label texts
# ---------------------------------------------------------------------------


class _RecordingComputer:
    """Deterministic bag-of-words embeddings; records every encoded text."""

    def __init__(self) -> None:
        self.encoded: list[str] = []

    def compute_batch_semantic(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        self.encoded.extend(texts)
        rows = np.zeros((len(texts), 64))
        for row, text in zip(rows, texts):
            for word in text.lower().split():
                row[sum(map(ord, word)) % 64] += 1.0
            row[63] += 0.01  # never a zero vector
        return rows


def test_label_keybert_reuses_given_computer(mock_db, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: label_keybert built a new EmbeddingComputer (reloading the
    model) on every call instead of using the session's."""
    import geistfabrik.embeddings as embeddings
    from geistfabrik.cluster_labeling import label_keybert

    def no_new_computer(*args: object, **kwargs: object) -> None:
        raise AssertionError("label_keybert must reuse the computer it is given")

    monkeypatch.setattr(embeddings, "EmbeddingComputer", no_new_computer)
    computer = _RecordingComputer()
    paths = ["note1.md", "note2.md", "note3.md", "note4.md", "note5.md", "note6.md"]

    result = label_keybert(paths, np.array([0, 0, 0, 1, 1, 1]), mock_db, computer=computer)

    assert set(result) == {0, 1}
    assert all(not label.startswith("Cluster") for label in result.values())
    assert computer.encoded


def test_label_keybert_reencodes_only_changed_label_texts(mock_db) -> None:
    """Label-text embeddings are cached per computer by content hash: a second
    run encodes no note text, an edit re-encodes just that note, and labels
    equal a cold run's."""
    from geistfabrik.cluster_labeling import _label_text, label_keybert

    paths = ["note1.md", "note2.md", "note3.md", "note4.md", "note5.md", "note6.md"]
    labels = np.array([0, 0, 0, 1, 1, 1])
    note_texts = {
        _label_text(title, content)
        for title, content in mock_db.execute("SELECT title, content FROM notes")
    }
    computer = _RecordingComputer()

    first = label_keybert(paths, labels, mock_db, computer=computer)
    assert note_texts <= set(computer.encoded)

    computer.encoded.clear()
    assert label_keybert(paths, labels, mock_db, computer=computer) == first
    assert not note_texts & set(computer.encoded)  # only candidate phrases

    mock_db.execute(
        "UPDATE notes SET content = 'Gradient clipping and learning rates' WHERE path = 'note2.md'"
    )
    computer.encoded.clear()
    warm = label_keybert(paths, labels, mock_db, computer=computer)
    changed = _label_text("Neural Networks", "Gradient clipping and learning rates")
    assert [text for text in computer.encoded if text in note_texts | {changed}] == [changed]
    assert warm == label_keybert(paths, labels, mock_db, computer=_RecordingComputer())
