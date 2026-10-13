"""Historical lexical evidence service exposed through VaultContext."""

import hashlib
import json
from array import array
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING

from .lexical_index import EXTRACTION_VERSION, week_start
from .sqlite_transaction import owned_transaction
from .word_burst import BurstInterval, detect_bursts, sparse_gain_cannot_burst

if TYPE_CHECKING:
    from .vault import Vault

ANALYSIS_VERSION = 1


@dataclass(frozen=True)
class WordBurstFinding:
    """A detected episode with explicit population and source-note evidence."""

    term: str
    start: str
    end: str
    level: int
    gain: float
    rate: float
    baseline_rate: float
    support_paths: tuple[str, ...]
    history_mode: str
    gaps: tuple[str, ...]
    left_censored: bool
    open: bool
    provisional: bool


@dataclass
class WordBurstDiagnostics:
    """Actual analysis work, usable by benchmarks without changing result semantics."""

    documents: int = 0
    candidates: int = 0
    decoded: int = 0
    pruned: int = 0
    cache_hit: bool = False
    reason: str = ""


@dataclass
class _Episode:
    term_id: int
    interval: BurstInterval
    paths: list[str] = field(default_factory=list)
    bodies: set[str] = field(default_factory=set)


def analyze_word_bursts(
    vault: "Vault", *, end_day: date, diagnostics: WordBurstDiagnostics | None = None
) -> list[WordBurstFinding]:
    """Decode exact document-prevalence series using one consistent DB snapshot.

    Dated cohorts use current prose assigned to declared dates. Observed additions
    use captured note/week additions; discovery is not a writing event. Identical
    normalized lexical bodies in a weekly bin contribute one observation. Cache
    keys include generation, algorithm, policy and exact cutoff, including empties.
    """
    stats = diagnostics if diagnostics is not None else WordBurstDiagnostics()
    config = vault.config.word_burst
    if not vault.config.lexical_analysis.enabled:
        stats.reason = "disabled"
        return []
    with owned_transaction(vault.db, "word-burst analysis"):
        metadata = dict(vault.db.execute("SELECT key, value FROM lexical_meta"))
        expected_policy = json.dumps(
            [EXTRACTION_VERSION, vault.config.lexical_analysis.to_dict()], sort_keys=True
        )
        if metadata.get("policy") != expected_policy:
            stats.reason = "requires_sync"
            return []
        key = hashlib.sha256(
            json.dumps(
                [
                    ANALYSIS_VERSION,
                    metadata.get("generation"),
                    metadata.get("policy"),
                    vault.config.lexical_analysis.to_dict(),
                    config.to_dict(),
                    end_day.isoformat(),
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cached = vault.db.execute(
            "SELECT result_json FROM word_burst_cache WHERE cache_key=?",
            (key,),
        ).fetchone()
        if cached:
            stats.cache_hit, stats.reason = True, "cached"
            return [
                WordBurstFinding(
                    item["term"],
                    item["start"],
                    item["end"],
                    item["level"],
                    item["gain"],
                    item["rate"],
                    item["baseline_rate"],
                    tuple(item["support_paths"]),
                    item["history_mode"],
                    tuple(item["gaps"]),
                    item["left_censored"],
                    item["open"],
                    item["provisional"],
                )
                for item in json.loads(cached[0])
            ]
        weeks = min(config.window_weeks, (week_start(end_day) - date.min).days // 7 + 1)
        first = week_start(end_day) - timedelta(weeks=weeks - 1)
        if config.history_mode == "dated_cohorts":
            query = (
                "SELECT path, cohort_day, counts_json, body_hash FROM lexical_notes "
                "WHERE cohort_day BETWEEN ? AND ? AND counts_json != '{}' ORDER BY path"
            )
            parameters = (first.isoformat(), end_day.isoformat())
        else:
            query = (
                "SELECT path, bin_start, terms_json, evidence_hash FROM lexical_events "
                "WHERE bin_start >= ? AND observed_at <= ? ORDER BY path, bin_start"
            )
            parameters = (first.isoformat(), end_day.isoformat() + "T23:59:59.999999+00:00")
        rows = vault.db.execute(query, parameters)
        exposure = [0] * weeks
        term_ids: dict[str, int] = {}
        terms: list[str] = []
        counts: list[Counter[int]] = []
        groups: dict[tuple[int, str], array[int]] = {}
        documents: list[tuple[str, int, str, array[int]]] = []
        for path, stamp, vector, body in rows:
            i = (date.fromisoformat(stamp) - first).days // 7
            if not 0 <= i < len(exposure):
                continue
            group = (i, body)
            ids = groups.get(group)
            if ids is None:
                ids = array("Q")
                for term in json.loads(vector):
                    if term not in term_ids:
                        term_ids[term] = len(terms)
                        terms.append(term)
                        counts.append(Counter())
                    term_id = term_ids[term]
                    ids.append(term_id)
                    counts[term_id][i] += 1
                groups[group] = ids
                exposure[i] += 1
            documents.append((path, i, body, ids))
        stats.documents = sum(exposure)
        findings: list[WordBurstFinding] = []
        if stats.documents < config.min_documents:
            stats.reason = "insufficient_documents"
        elif sum(n > 0 for n in exposure) < config.min_populated_bins:
            stats.reason = "insufficient_bins"
        else:
            episodes: dict[int, list[_Episode]] = {}
            for term_id, sparse in enumerate(counts):
                stats.candidates += 1
                if (
                    sum(sparse.values()) < config.min_support
                    or len(sparse) < config.min_support_bins
                    or sparse_gain_cannot_burst(
                        sparse,
                        exposure,
                        s=config.s,
                        gamma=config.gamma,
                        max_states=config.max_states,
                    )
                ):
                    stats.pruned += 1
                    continue
                stats.decoded += 1
                result = detect_bursts(
                    [sparse[i] for i in range(len(exposure))],
                    exposure,
                    s=config.s,
                    gamma=config.gamma,
                    max_states=config.max_states,
                )
                if result.intervals:
                    episodes[term_id] = [
                        _Episode(term_id, interval) for interval in result.intervals
                    ]
            # One evidence pass over compact IDs, rather than rescanning the vault per term.
            for path, i, body, ids in documents:
                for term_id in ids:
                    for episode in episodes.get(term_id, ()):
                        if episode.interval.start <= i <= episode.interval.end:
                            episode.paths.append(path)
                            episode.bodies.add(body)
            for term_id, term_episodes in episodes.items():
                for episode in term_episodes:
                    interval = episode.interval
                    if len(episode.bodies) < config.min_support:
                        continue
                    populated_support = sum(
                        counts[term_id][i] > 0 for i in range(interval.start, interval.end + 1)
                    )
                    if populated_support < config.min_support_bins:
                        continue
                    numerator = sum(
                        counts[term_id][i] for i in range(interval.start, interval.end + 1)
                    )
                    denominator = sum(exposure[interval.start : interval.end + 1])
                    start = first + timedelta(weeks=interval.start)
                    end = first + timedelta(days=min(interval.end * 7 + 6, (end_day - first).days))
                    findings.append(
                        WordBurstFinding(
                            terms[term_id],
                            start.isoformat(),
                            end.isoformat(),
                            interval.level,
                            interval.gain,
                            numerator / denominator,
                            sum(counts[term_id].values()) / stats.documents,
                            tuple(sorted(set(episode.paths))),
                            config.history_mode,
                            tuple((first + timedelta(weeks=i)).isoformat() for i in interval.gaps),
                            interval.left_censored,
                            interval.open,
                            interval.end == len(exposure) - 1 and end_day.weekday() < 6,
                        )
                    )
            stats.reason = "burst" if findings else "no_burst"
        vault.db.execute(
            "INSERT INTO word_burst_cache VALUES (?, ?)",
            (key, json.dumps([asdict(finding) for finding in findings])),
        )
        # Bound exact-cutoff variants, preserving this newly computed entry.
        vault.db.execute(
            "DELETE FROM word_burst_cache WHERE rowid NOT IN "
            "(SELECT rowid FROM word_burst_cache ORDER BY rowid DESC LIMIT 8)"
        )
        return findings
