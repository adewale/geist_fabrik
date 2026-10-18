"""Independent lifecycle and scale contracts from the no-tests adversarial review."""

import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from geistfabrik.config_loader import GeistFabrikConfig
from geistfabrik.document_rate import DocumentRate
from geistfabrik.vault import Vault
from geistfabrik.word_burst_analysis import WordBurstDiagnostics, analyze_word_bursts


def test_observation_cutoff_invalidates_reuse_only_when_captured_population_changes(
    tmp_path, monkeypatch
):
    """An event's Monday bin does not make it observable before its actual capture."""
    observed = datetime(2026, 1, 5, 12, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return observed.astimezone(tz)

    monkeypatch.setattr("geistfabrik.vault.datetime", Clock)
    for name in ("alpha", "beta"):
        (tmp_path / f"{name}.md").write_text(f"soil {name}", encoding="utf-8")
    with closing(Vault(tmp_path)) as vault:
        vault.sync()
        for day, name in ((6, "alpha"), (8, "beta")):
            observed = datetime(2026, 1, day, 12, tzinfo=UTC)
            (tmp_path / f"{name}.md").write_text(f"soil {name} aurora", encoding="utf-8")
            vault.sync()
        vault.config.word_burst.history_mode = "observed_additions"
        stats = WordBurstDiagnostics()
        for day, documents, hit in ((5, 0, False), (6, 1, False), (7, 1, True), (8, 2, False)):
            assert analyze_word_bursts(vault, end_day=date(2026, 1, day), diagnostics=stats) == []
            assert stats.documents == documents
            assert stats.cache_hit is hit
            assert stats.reason == "insufficient_documents"


@pytest.mark.parametrize("populated_weeks", [10, 12])
def test_cached_dates_follow_request_order_without_extending_over_unobserved_weeks(
    tmp_path, populated_weeks
):
    """Open describes the last observed state, not an empty final calendar week."""
    start = date(2026, 1, 5)
    for week in range(populated_weeks):
        for source in range(10):
            identity = f"identity{chr(97 + week)}{chr(97 + source)}"
            body = f"soil {identity}" + (
                " aurora" if week >= populated_weeks - 2 and source < 8 else ""
            )
            (tmp_path / f"{week:02}-{source}.md").write_text(
                f"---\ncreated: {start + timedelta(weeks=week)}\n---\n{body}", encoding="utf-8"
            )
    config = GeistFabrikConfig()
    config.lexical_analysis.ngram_max = 1
    expected_paths = tuple(
        f"{week:02}-{source}.md"
        for week in range(populated_weeks - 2, populated_weeks)
        for source in range(8)
    )
    expected_start = start + timedelta(weeks=populated_weeks - 2)
    observed_end = start + timedelta(weeks=populated_weeks) - timedelta(days=1)
    with closing(Vault(tmp_path, config=config)) as vault:
        vault.sync()
        stats = WordBurstDiagnostics()
        # A later request must not poison an earlier date's clipping, nor may an
        # earlier clipped request truncate a subsequently requested date.
        for iteration, day in enumerate((26, 29, 25, 27, 23)):
            cutoff = date(2026, 3, day)
            findings = analyze_word_bursts(vault, end_day=cutoff, diagnostics=stats)
            finding = next(item for item in findings if item.term == "aurora")
            assert stats.cache_hit is bool(iteration)
            assert (finding.start, finding.end) == (
                expected_start.isoformat(),
                min(observed_end, cutoff).isoformat(),
            )
            assert finding.open
            assert finding.provisional is (populated_weeks == 12 and cutoff.weekday() < 6)
            assert finding.prevalence == DocumentRate(16, 20)
            assert finding.baseline == DocumentRate(16, populated_weeks * 10)
            assert finding.support_paths == expected_paths


@settings(max_examples=12, deadline=None)
@example(source_count=1100, weeks=1, duplicate_distance=400)
@example(source_count=1100, weeks=1, duplicate_distance=1100)
@given(
    source_count=st.integers(min_value=257, max_value=1100),
    weeks=st.integers(min_value=1, max_value=104),
    duplicate_distance=st.integers(min_value=1, max_value=1100),
)
def test_weekly_count_conservation_across_source_flushes(source_count, weeks, duplicate_distance):
    """Chunk boundaries cannot narrow counts, double-count copies or drop terms."""
    from geistfabrik.word_burst_sparse import collect_population

    first = date(2026, 1, 5)
    ids = {"alpha": 2**63 - 1, "beta": 2**32 + 7, "gamma": 29}
    expected = {term: Counter() for term in ids}
    expected_order = []
    rows = []
    seen = set()
    for source in range(source_count):
        identity = source % duplicate_distance
        week = identity % weeks
        terms = ("alpha", "beta") if identity % 2 else ("alpha", "gamma")
        body = hashlib.sha256(
            json.dumps({term: identity + 1 for term in terms}, sort_keys=True).encode()
        ).hexdigest()
        rows.append(
            (
                f"{source:04}.md",
                (first + timedelta(weeks=week)).isoformat(),
                np.asarray(sorted(ids[term] for term in terms), dtype="<u8").tobytes(),
                body,
            )
        )
        if (week, body) in seen:
            continue
        seen.add((week, body))
        for term in sorted(terms):
            if term not in expected_order:
                expected_order.append(term)
            expected[term][week] += 1
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE lexical_presence_terms(term_id INTEGER PRIMARY KEY, term TEXT)")
        db.executemany(
            "INSERT INTO lexical_presence_terms VALUES (?, ?)",
            ((term_id, term) for term, term_id in ids.items()),
        )
        population = collect_population(db, iter(rows), first=first, weeks=weeks, min_documents=0)
    terms_by_id = {term_id: term for term, term_id in ids.items()}
    actual = {
        terms_by_id[int(population.stable_ids[column])]: population.column(int(column))
        for column in population.order
    }
    assert list(actual) == expected_order
    assert actual == {term: expected[term] for term in expected_order}
