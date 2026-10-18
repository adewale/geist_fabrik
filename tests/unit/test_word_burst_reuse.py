"""Cross-day lifecycle and compact sufficient-statistic correctness contracts."""

import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import date, timedelta

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.vault import Vault
from geistfabrik.word_burst_analysis import WordBurstDiagnostics, analyze_word_bursts
from geistfabrik.word_burst_sparse import collect_population


def _open_episode(root):
    start = date(2026, 1, 5)
    for week in range(12):
        for i in range(10):
            name = f"identity{chr(97 + week)}{chr(97 + i)}"
            content = f"soil habitat {name}" + (" aurora" if week >= 10 and i < 8 else "")
            (root / f"{week:02}-{i}.md").write_text(
                f"---\ncreated: {start + timedelta(weeks=week)}\n---\n{content}",
                encoding="utf-8",
            )
    vault = Vault(root)
    vault.sync()
    return vault


def test_unchanged_next_day_reuses_analysis_but_refreshes_provisional_dates(tmp_path):
    """Cache lifetime follows actual exposure, while reporting follows today's date."""
    with closing(_open_episode(tmp_path)) as vault:
        stats = WordBurstDiagnostics()
        initial = analyze_word_bursts(vault, end_day=date(2026, 3, 25), diagnostics=stats)
        before = next(f for f in initial if f.term == "aurora")
        assert before.open and before.provisional and before.end == "2026-03-25"
        population = stats.population_dict()
        for cutoff in (date(2026, 3, 26), date(2026, 3, 29)):
            result = analyze_word_bursts(vault, end_day=cutoff, diagnostics=stats)
            after = next(f for f in result if f.term == "aurora")
            assert stats.cache_hit
            assert stats.population_dict() == population
            assert stats.collection_seconds == stats.decoding_seconds == stats.evidence_seconds == 0
            assert stats.decoded == stats.pruned == stats.series_reused == 0
            assert after.end == cutoff.isoformat()
            assert after.provisional is (cutoff.weekday() < 6)
            assert after.open and after.gain == before.gain
            assert (
                after.prevalence == before.prevalence
                and after.support_paths == before.support_paths
            )


def test_future_cohort_becoming_visible_invalidates_same_week_reuse(tmp_path):
    with closing(_open_episode(tmp_path)) as vault:
        (tmp_path / "future.md").write_text(
            "---\ncreated: 2026-03-27\n---\nfuture source with aurora", encoding="utf-8"
        )
        vault.sync()
        stats = WordBurstDiagnostics()
        analyze_word_bursts(vault, end_day=date(2026, 3, 26), diagnostics=stats)
        assert stats.documents == 120
        analyze_word_bursts(vault, end_day=date(2026, 3, 27), diagnostics=stats)
        assert not stats.cache_hit and stats.documents == 121
        assert stats.decoded > 0


def test_rolling_frame_shift_invalidates_unchanged_population(tmp_path):
    with closing(_open_episode(tmp_path)) as vault:
        stats = WordBurstDiagnostics()
        analyze_word_bursts(vault, end_day=date(2026, 3, 29), diagnostics=stats)
        analyze_word_bursts(vault, end_day=date(2026, 3, 30), diagnostics=stats)
        assert not stats.cache_hit and stats.documents == 120


@settings(max_examples=50, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(0, 7), st.sets(st.integers(0, 5), max_size=6)),
        min_size=0,
        max_size=40,
    ),
    st.integers(0, 3),
    st.permutations(range(6)),
)
def test_compact_weekly_counts_match_independent_body_set_oracle(documents, minimum, assignment):
    """Hostile sparse IDs and body duplicates must not change exact counts/order."""
    vocabulary = ["alpha", "beta gamma", "delta", "of a", "theory of mind", "zeta"]
    # Permute lexical order and leave enormous numeric holes: dictionary IDs are
    # identities, never dense positions, term ranking or memory allocation sizes.
    ids = {term: 2**62 + (assignment[i] + 1) * 19 for i, term in enumerate(vocabulary)}
    frequencies = Counter(vocabulary[t] for _, words in documents for t in words)
    eligible = {term for term in vocabulary if not minimum or frequencies[term] >= minimum}
    seen = set()
    expected_order = []
    expected = {}
    rows = []
    first = date(2026, 1, 5)
    for ordinal, (week, words) in enumerate(documents):
        terms = sorted(vocabulary[i] for i in words)
        body = hashlib.sha256(json.dumps(terms).encode()).hexdigest()
        rows.append(
            (
                f"{ordinal:03}.md",
                (first + timedelta(weeks=week)).isoformat(),
                np.asarray(sorted(ids[term] for term in terms), dtype="<u8").tobytes(),
                body,
            )
        )
        if (week, body) in seen:
            continue
        seen.add((week, body))
        for term in terms:
            if term not in eligible:
                continue
            if term not in expected:
                expected_order.append(term)
                expected[term] = Counter()
            expected[term][week] += 1
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE lexical_presence_terms(term_id INTEGER PRIMARY KEY, term TEXT)")
        db.execute("CREATE TABLE lexical_terms(term TEXT PRIMARY KEY, documents INTEGER)")
        db.executemany(
            "INSERT INTO lexical_presence_terms VALUES (?, ?)", ((i, t) for t, i in ids.items())
        )
        db.executemany(
            "INSERT INTO lexical_terms VALUES (?, ?)", ((t, frequencies[t]) for t in vocabulary)
        )
        actual = collect_population(db, iter(rows), first=first, weeks=8, min_documents=minimum)
    by_id = {i: term for term, i in ids.items()}
    actual_order = [by_id[int(actual.stable_ids[i])] for i in actual.order]
    assert actual_order == expected_order
    assert {
        by_id[int(actual.stable_ids[i])]: actual.column(int(i)) for i in actual.order
    } == expected


def test_noncanonical_empty_json_keeps_legacy_exposure_after_projection(tmp_path):
    """Canonical empty bodies abstain; legacy spaced JSON still counts as before."""
    with closing(_open_episode(tmp_path)) as vault:
        vault.db.execute("UPDATE lexical_notes SET counts_json = '{ }' WHERE path = '00-0.md'")
        vault.db.execute("UPDATE lexical_notes SET counts_json = '{}' WHERE path = '00-1.md'")
        vault.db.commit()
        stats = WordBurstDiagnostics()
        analyze_word_bursts(vault, end_day=date(2026, 3, 25), diagnostics=stats)
        assert stats.documents == 119 and not stats.cache_hit
        assert (
            vault.db.execute(
                "SELECT presence FROM lexical_notes WHERE path = '00-0.md'"
            ).fetchone()[0]
            == b""
        )
        analyze_word_bursts(vault, end_day=date(2026, 3, 26), diagnostics=stats)
        assert stats.cache_hit and stats.documents == 119
