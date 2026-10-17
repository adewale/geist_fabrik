"""Historical lexical evidence service exposed through VaultContext."""

import hashlib
import json
import time
from array import array
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from .document_rate import DocumentRate
from .lexical_index import EXTRACTION_VERSION, week_start
from .sqlite_transaction import owned_transaction
from .word_burst import BurstInterval, BurstModel, PreparedBurstSeries

if TYPE_CHECKING:
    from .vault import Vault

ANALYSIS_VERSION = 5


@dataclass(frozen=True)
class WordBurstFinding:
    """A detected episode with explicit population and source-note evidence."""

    term: str
    start: str
    end: str
    level: int
    gain: float
    prevalence: DocumentRate
    baseline: DocumentRate
    support_paths: tuple[str, ...]
    history_mode: str
    gaps: tuple[str, ...]
    left_censored: bool
    open: bool
    provisional: bool
    direction: str = "rising"
    reference: DocumentRate | None = None
    reference_start: str | None = None
    reference_end: str | None = None

    @property
    def rate(self) -> float:
        return self.prevalence.value

    @property
    def baseline_rate(self) -> float:
        return self.baseline.value

    @property
    def reference_rate(self) -> float | None:
        return None if self.reference is None else self.reference.value

    def to_dict(self) -> dict[str, Any]:
        """Preserve reporting fields while retaining exact counts for replay/display."""
        return {
            **asdict(self),
            "rate": self.rate,
            "baseline_rate": self.baseline_rate,
            "reference_rate": self.reference_rate,
        }


@dataclass
class WordBurstDiagnostics:
    """Actual analysis work, usable by benchmarks without changing result semantics."""

    documents: int = 0
    candidates: int = 0
    decoded: int = 0
    pruned: int = 0
    series_reused: int = 0
    cache_hit: bool = False
    reason: str = ""
    collection_seconds: float = 0.0
    decoding_seconds: float = 0.0
    evidence_seconds: float = 0.0


@dataclass
class _Episode:
    term_id: int
    interval: BurstInterval
    direction: str
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
                    DocumentRate(**item["prevalence"]),
                    DocumentRate(**item["baseline"]),
                    tuple(item["support_paths"]),
                    item["history_mode"],
                    tuple(item["gaps"]),
                    item["left_censored"],
                    item["open"],
                    item["provisional"],
                    item["direction"],
                    None if item["reference"] is None else DocumentRate(**item["reference"]),
                    item["reference_start"],
                    item["reference_end"],
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
        started = time.perf_counter()
        eligible_terms = (
            {
                row[0]
                for row in vault.db.execute(
                    "SELECT term FROM lexical_terms WHERE documents >= ?", (config.min_support,)
                )
            }
            if config.history_mode == "dated_cohorts"
            else None
        )
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
                    # Current document frequency is a necessary upper bound
                    # only for current-text cohorts, never for captured history.
                    if eligible_terms is not None and term not in eligible_terms:
                        continue
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
        stats.collection_seconds = time.perf_counter() - started
        stats.documents = sum(exposure)
        findings: list[WordBurstFinding] = []
        if stats.documents < config.min_documents:
            stats.reason = "insufficient_documents"
        elif sum(n > 0 for n in exposure) < config.min_populated_bins:
            stats.reason = "insufficient_bins"
        else:
            started = time.perf_counter()
            episodes: dict[int, list[_Episode]] = {}
            model = BurstModel(
                exposure, s=config.s, gamma=config.gamma, max_states=config.max_states
            )
            # Phrases often share exactly the same weekly series. Decode each
            # distinct series/direction once, preserving every term and its
            # independently collected evidence. This is exact reuse, not sampling.
            decoded: dict[tuple[tuple[tuple[int, int], ...], str], tuple[BurstInterval, ...]] = {}
            pending: dict[str, list[tuple[tuple[tuple[int, int], ...], PreparedBurstSeries]]] = {
                direction: [] for direction in config.directions
            }
            vectors: dict[int, tuple[tuple[int, int], ...]] = {}
            prepared: dict[tuple[tuple[int, int], ...], PreparedBurstSeries] = {}
            for term_id, sparse in enumerate(counts):
                stats.candidates += 1
                if (
                    sum(sparse.values()) < config.min_support
                    or len(sparse) < config.min_support_bins
                ):
                    stats.pruned += 1
                    continue
                vector = tuple(sorted(sparse.items()))
                vectors[term_id] = vector
                if vector not in prepared:
                    prepared[vector] = model.prepare(sparse)
                for direction in config.directions:
                    cache_key = (vector, direction)
                    if cache_key in decoded:
                        stats.series_reused += 1
                    elif model.cannot_burst(prepared[vector], direction=direction):
                        stats.pruned += 1
                        decoded[cache_key] = ()
                    else:
                        stats.decoded += 1
                        decoded[cache_key] = ()
                        pending[direction].append((vector, prepared[vector]))
            for direction, work in pending.items():
                for offset in range(0, len(work), 1024):
                    batch = work[offset : offset + 1024]
                    results = model.detect_many(
                        [series for _, series in batch], direction=direction
                    )
                    for (vector, _), result in zip(batch, results, strict=True):
                        # Retain episodes, not the full state vector per term.
                        frequency = dict(vector)
                        eligible_intervals = []
                        for interval in result.intervals:
                            support_range = (
                                range(interval.start)
                                if direction == "declining"
                                else range(interval.start, interval.end + 1)
                            )
                            support = [frequency.get(i, 0) for i in support_range]
                            if (
                                sum(support) < config.min_support
                                or sum(r > 0 for r in support) < config.min_support_bins
                            ):
                                continue
                            if (
                                direction == "declining"
                                and sum(n > 0 for n in exposure[interval.start : interval.end + 1])
                                < config.min_support_bins
                            ):
                                continue
                            eligible_intervals.append(interval)
                        decoded[(vector, direction)] = tuple(eligible_intervals)
            for term_id, vector in vectors.items():
                for direction in config.directions:
                    intervals = decoded[(vector, direction)]
                    if intervals:
                        episodes.setdefault(term_id, []).extend(
                            _Episode(term_id, interval, direction) for interval in intervals
                        )
            stats.decoding_seconds = time.perf_counter() - started
            started = time.perf_counter()
            # One evidence pass over compact IDs, rather than rescanning the vault per term.
            for path, i, body, ids in documents:
                for term_id in ids:
                    for episode in episodes.get(term_id, ()):
                        if (
                            episode.direction == "rising"
                            and episode.interval.start <= i <= episode.interval.end
                        ) or (episode.direction == "declining" and i < episode.interval.start):
                            episode.paths.append(path)
                            episode.bodies.add(body)
            for term_id, term_episodes in episodes.items():
                for episode in term_episodes:
                    interval = episode.interval
                    if len(episode.bodies) < config.min_support:
                        continue
                    sparse = counts[term_id]
                    populated_support = (
                        sum(sparse[i] > 0 for i in range(interval.start))
                        if episode.direction == "declining"
                        else sum(sparse[i] > 0 for i in range(interval.start, interval.end + 1))
                    )
                    if populated_support < config.min_support_bins:
                        continue
                    numerator = sum(
                        counts[term_id][i] for i in range(interval.start, interval.end + 1)
                    )
                    denominator = sum(exposure[interval.start : interval.end + 1])
                    reference, reference_start, reference_end = None, None, None
                    prevalence = DocumentRate(numerator, denominator)
                    if episode.direction == "declining":
                        # An initially quiet period is not a decline. Require
                        # established earlier use and sustained later activity,
                        # including zero-mention weeks when exposure is positive.
                        if (
                            sum(n > 0 for n in exposure[interval.start : interval.end + 1])
                            < config.min_support_bins
                        ):
                            continue
                        prior_exposure = sum(exposure[: interval.start])
                        if not prior_exposure:
                            continue
                        reference = DocumentRate(
                            sum(sparse[i] for i in range(interval.start)), prior_exposure
                        )
                        if prevalence.fraction >= reference.fraction:
                            continue
                        reference_start = first.isoformat()
                        reference_end = (
                            first + timedelta(weeks=interval.start) - timedelta(days=1)
                        ).isoformat()
                    start = first + timedelta(weeks=interval.start)
                    end = first + timedelta(days=min(interval.end * 7 + 6, (end_day - first).days))
                    findings.append(
                        WordBurstFinding(
                            terms[term_id],
                            start.isoformat(),
                            end.isoformat(),
                            interval.level,
                            interval.gain,
                            prevalence,
                            DocumentRate(sum(counts[term_id].values()), stats.documents),
                            tuple(sorted(set(episode.paths))),
                            config.history_mode,
                            tuple((first + timedelta(weeks=i)).isoformat() for i in interval.gaps),
                            interval.left_censored,
                            interval.open,
                            interval.end == len(exposure) - 1 and end_day.weekday() < 6,
                            episode.direction,
                            reference,
                            reference_start,
                            reference_end,
                        )
                    )
            stats.evidence_seconds = time.perf_counter() - started
            stats.reason = "burst" if findings else "no_burst"
        vault.db.execute(
            "INSERT INTO word_burst_cache VALUES (?, ?)",
            (key, json.dumps([finding.to_dict() for finding in findings])),
        )
        # Bound exact-cutoff variants, preserving this newly computed entry.
        vault.db.execute(
            "DELETE FROM word_burst_cache WHERE rowid NOT IN "
            "(SELECT rowid FROM word_burst_cache ORDER BY rowid DESC LIMIT 8)"
        )
        return findings
