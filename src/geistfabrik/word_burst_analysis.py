"""Historical lexical evidence service exposed through VaultContext."""

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from .document_rate import DocumentRate
from .lexical_index import EXTRACTION_VERSION, week_start
from .lexical_presence import ensure_selected_presence
from .sqlite_transaction import owned_transaction
from .word_burst import BurstInterval, BurstModel, PreparedBurstSeries
from .word_burst_sparse import SparsePopulation, collect_population, selected_presence

if TYPE_CHECKING:
    from .vault import Vault

ANALYSIS_VERSION = 7

_DECODE_BATCH = 1024
_SERIES_CACHE = 8192
_SERIES_CACHE_POINTS = 262_144
_PREPARED_POINTS = 131_072


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
    """Evidence population and actual work, including faithful cached abstentions."""

    documents: int = 0
    populated_bins: int = 0
    min_documents: int = 0
    min_populated_bins: int = 0
    history_mode: str = ""
    candidates: int = 0
    decoded: int = 0
    pruned: int = 0
    series_reused: int = 0
    cache_hit: bool = False
    reason: str = ""
    collection_seconds: float = 0.0
    decoding_seconds: float = 0.0
    evidence_seconds: float = 0.0

    def explanation(self) -> str:
        """Explain evidence limits without confusing a cache hit with an outcome."""
        if self.reason == "disabled":
            return "abstained: lexical analysis is disabled"
        if self.reason == "requires_sync":
            return "abstained: lexical index policy requires sync"
        population = (
            "captured observations"
            if self.history_mode == "observed_additions"
            else "dated-cohort observations"
        )
        if self.reason == "insufficient_documents":
            message = (
                f"abstained: {self.documents} {population}; minimum {self.min_documents} required"
            )
        elif self.reason == "insufficient_bins":
            message = (
                f"abstained: {self.populated_bins} populated weekly bins; "
                f"minimum {self.min_populated_bins} required "
                f"({self.documents} {population})"
            )
        else:
            outcome = (
                "supported burst episodes found"
                if self.reason == "burst"
                else "no supported burst episodes"
            )
            message = (
                f"{outcome}: {self.documents} {population} "
                f"across {self.populated_bins} populated weekly bins"
            )
        return message + (" (cached analysis)" if self.cache_hit else "")

    def population_dict(self) -> dict[str, Any]:
        """Persist evidence metadata, excluding work avoided by a cache hit."""
        return {
            name: getattr(self, name)
            for name in (
                "documents",
                "populated_bins",
                "min_documents",
                "min_populated_bins",
                "history_mode",
                "candidates",
                "reason",
            )
        }


@dataclass
class _Episode:
    term_id: int
    interval: BurstInterval
    direction: str
    paths: list[str] = field(default_factory=list)
    bodies: set[str] = field(default_factory=set)


def _decode_cached(payload: str, end_day: date, canonical_end: date) -> list[WordBurstFinding]:
    findings = []
    for item in json.loads(payload):
        finding = WordBurstFinding(
            item["term"],
            item["start"],
            min(item["end"], end_day.isoformat()),
            item["level"],
            item["gain"],
            DocumentRate(**item["prevalence"]),
            DocumentRate(**item["baseline"]),
            tuple(item["support_paths"]),
            item["history_mode"],
            tuple(item["gaps"]),
            item["left_censored"],
            item["open"],
            item["end"] == canonical_end.isoformat() and end_day.weekday() < 6,
            item["direction"],
            None if item["reference"] is None else DocumentRate(**item["reference"]),
            item["reference_start"],
            item["reference_end"],
        )
        findings.append(finding)
    return findings


def _present(finding: WordBurstFinding, end_day: date, canonical_end: date) -> WordBurstFinding:
    """Apply reporting dates without changing intervals or exposure."""
    end = min(finding.end, end_day.isoformat())
    provisional = finding.end == canonical_end.isoformat() and end_day.weekday() < 6
    if finding.end == end and finding.provisional == provisional:
        return finding
    return replace(finding, end=end, provisional=provisional)


def _cache_key(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _store(vault: "Vault", key: str, payload: str, diagnostics: str) -> None:
    vault.db.execute(
        "INSERT OR REPLACE INTO word_burst_cache (cache_key, result_json, diagnostics_json) "
        "VALUES (?, ?, ?)",
        (key, payload, diagnostics),
    )


def _decode_population(
    population: SparsePopulation,
    exposure: list[int],
    config: Any,
    stats: WordBurstDiagnostics,
) -> dict[int, list[_Episode]]:
    """Prepare only a batch at a time; retain a bounded exact-series cache."""
    episodes: dict[int, list[_Episode]] = {}
    model = BurstModel(exposure, s=config.s, gamma=config.gamma, max_states=config.max_states)
    batched = config.max_states == 2 and config.s - 1 > 1e-8
    decoded: OrderedDict[tuple[tuple[tuple[int, int], ...], str], tuple[BurstInterval, ...]] = (
        OrderedDict()
    )
    screens: dict[int, set[str]] = {}
    cached_points = 0
    offset = 0
    while offset < len(population.order):
        limit, points = offset, 0
        while limit < min(offset + _DECODE_BATCH, len(population.order)):
            column = int(population.order[limit])
            size = int(population.indptr[column + 1] - population.indptr[column])
            if limit > offset and points + size > _PREPARED_POINTS:
                break
            limit += 1
            points += size
        vectors: dict[int, tuple[tuple[int, int], ...]] = {}
        prepared: dict[tuple[tuple[int, int], ...], PreparedBurstSeries] = {}
        pending: dict[str, list[tuple[tuple[tuple[int, int], ...], PreparedBurstSeries]]] = {
            direction: [] for direction in config.directions
        }
        # A batch may contain more keys than the long-lived LRU's remaining
        # space. Evict only after assigning its episodes, never pending work.
        current: dict[tuple[tuple[tuple[int, int], ...], str], tuple[BurstInterval, ...]] = {}
        for candidate in population.order[offset:limit]:
            term_id = int(candidate)
            sparse = population.column(term_id)
            stats.candidates += 1
            relevant = sum(sparse.values())
            if relevant < config.min_support or len(sparse) < config.min_support_bins:
                stats.pruned += 1
                continue
            viable = screens.get(relevant)
            if viable is None:
                viable = screens[relevant] = {
                    direction
                    for direction in config.directions
                    if not model.cannot_burst_total(relevant, direction=direction)
                }
            stats.pruned += len(config.directions) - len(viable)
            if not viable:
                continue
            vector = tuple(sparse.items())
            vectors[term_id] = vector
            for direction in config.directions:
                cache_key = (vector, direction)
                if cache_key in current:
                    stats.series_reused += 1
                elif cache_key in decoded:
                    stats.series_reused += 1
                    current[cache_key] = decoded[cache_key]
                    decoded.move_to_end(cache_key)
                elif direction not in viable:
                    current[cache_key] = ()
                else:
                    if vector not in prepared:
                        prepared[vector] = model.prepare(sparse)
                    series = prepared[vector]
                    current[cache_key] = ()
                    if not batched and model.cannot_burst(series, direction=direction):
                        stats.pruned += 1
                    else:
                        stats.decoded += 1
                        pending[direction].append((vector, series))
        for direction, work in pending.items():
            results = model.detect_many([series for _, series in work], direction=direction)
            for (vector, _), result in zip(work, results, strict=True):
                frequency = dict(vector)
                eligible = []
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
                    eligible.append(interval)
                current[(vector, direction)] = tuple(eligible)
        for term_id, vector in vectors.items():
            for direction in config.directions:
                intervals = current[(vector, direction)]
                if intervals:
                    episodes.setdefault(term_id, []).extend(
                        _Episode(term_id, interval, direction) for interval in intervals
                    )
        for cache_key, intervals in current.items():
            if cache_key not in decoded:
                cached_points += len(cache_key[0])
            decoded[cache_key] = intervals
        # Bound both entries and their sparse-coordinate payload. Long configured
        # windows cannot turn a nominally bounded LRU into millions of tuples.
        while len(decoded) > _SERIES_CACHE or cached_points > _SERIES_CACHE_POINTS:
            evicted, _ = decoded.popitem(last=False)
            cached_points -= len(evicted[0])
        offset = limit
    return episodes


def analyze_word_bursts(
    vault: "Vault", *, end_day: date, diagnostics: WordBurstDiagnostics | None = None
) -> list[WordBurstFinding]:
    """Decode exact document prevalence using one consistent database snapshot.

    Exact-cutoff hits use metadata only. Across days, unchanged selected source
    membership and the same weekly exposure frame reuse date-independent results;
    final-week end dates and provisional reporting are refreshed separately.
    Changes to generation, policy, settings, rolling frame or selected membership
    invalidate reuse. Current prose and captured additions retain distinct history.
    """
    stats = diagnostics if diagnostics is not None else WordBurstDiagnostics()
    empty = WordBurstDiagnostics()
    for diagnostic_field in fields(stats):
        setattr(stats, diagnostic_field.name, getattr(empty, diagnostic_field.name))
    config = vault.config.word_burst
    stats.history_mode = config.history_mode
    stats.min_documents = config.min_documents
    stats.min_populated_bins = config.min_populated_bins
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
        weeks = min(config.window_weeks, (week_start(end_day) - date.min).days // 7 + 1)
        first = week_start(end_day) - timedelta(weeks=weeks - 1)
        canonical_end = date.fromordinal(
            min(date.max.toordinal(), first.toordinal() + weeks * 7 - 1)
        )
        identity = [
            ANALYSIS_VERSION,
            metadata.get("generation"),
            metadata.get("policy"),
            vault.config.lexical_analysis.to_dict(),
            config.to_dict(),
            first.isoformat(),
            weeks,
        ]
        exact_key = _cache_key(["cutoff", identity, end_day.isoformat()])
        cached = vault.db.execute(
            "SELECT result_json, diagnostics_json FROM word_burst_cache WHERE cache_key=?",
            (exact_key,),
        ).fetchone()
        if cached:
            for name, value in json.loads(cached[1]).items():
                setattr(stats, name, value)
            stats.cache_hit = True
            return _decode_cached(cached[0], end_day, canonical_end)
        if config.history_mode == "dated_cohorts":
            source = (
                "FROM lexical_notes WHERE cohort_day BETWEEN ? AND ? "
                "AND CASE WHEN presence IS NULL OR length(presence) = 0 "
                "THEN counts_json != '{}' ELSE 1 END "
                "ORDER BY path"
            )
            metadata_query = "SELECT path, cohort_day, body_hash " + source
            presence_query = "SELECT path, cohort_day, presence, body_hash " + source
            parameters = (first.isoformat(), end_day.isoformat())
        else:
            source = (
                "FROM lexical_events WHERE bin_start >= ? AND observed_at <= ? "
                "ORDER BY path, bin_start"
            )
            metadata_query = "SELECT path, bin_start, evidence_hash " + source
            presence_query = "SELECT path, bin_start, presence, evidence_hash " + source
            parameters = (first.isoformat(), end_day.isoformat() + "T23:59:59.999999+00:00")
        # Hash only selected metadata; never read or deserialize frequency/presence
        # payloads to establish whether tomorrow has the same statistical inputs.
        signature = hashlib.sha256()
        exposure = [0] * weeks
        seen: set[tuple[int, str]] = set()
        for path, stamp, body in vault.db.execute(metadata_query, parameters):
            i = (date.fromisoformat(stamp) - first).days // 7
            if not 0 <= i < weeks:
                continue
            signature.update(json.dumps([path, stamp, body], ensure_ascii=False).encode())
            if (i, body) not in seen:
                seen.add((i, body))
                exposure[i] += 1
        population_key = _cache_key(["population", identity, signature.hexdigest()])
        cached = vault.db.execute(
            "SELECT result_json, diagnostics_json FROM word_burst_cache WHERE cache_key=?",
            (population_key,),
        ).fetchone()
        if cached:
            for name, value in json.loads(cached[1]).items():
                setattr(stats, name, value)
            stats.cache_hit = True
            _store(vault, exact_key, cached[0], cached[1])
            findings = _decode_cached(cached[0], end_day, canonical_end)
        else:
            stats.documents = sum(exposure)
            stats.populated_bins = sum(n > 0 for n in exposure)
            raw_findings: list[WordBurstFinding] = []
            if stats.documents < config.min_documents:
                stats.reason = "insufficient_documents"
            elif stats.populated_bins < config.min_populated_bins:
                stats.reason = "insufficient_bins"
            else:
                started = time.perf_counter()
                if config.history_mode == "dated_cohorts":
                    ensure_selected_presence(
                        vault.db, history_mode="dated_cohorts", first=first, end_day=end_day
                    )
                else:
                    ensure_selected_presence(
                        vault.db, history_mode="observed_additions", first=first, end_day=end_day
                    )
                population = collect_population(
                    vault.db,
                    iter(vault.db.execute(presence_query, parameters)),
                    first=first,
                    weeks=weeks,
                    min_documents=config.min_support
                    if config.history_mode == "dated_cohorts"
                    else 0,
                )
                stats.collection_seconds = time.perf_counter() - started
                started = time.perf_counter()
                episodes = _decode_population(population, exposure, config, stats)
                stats.decoding_seconds = time.perf_counter() - started
                started = time.perf_counter()
                # Evidence is streamed a second time only for detected columns;
                # full-vault document vectors do not survive collection.
                active_columns = np.asarray(sorted(episodes), dtype=np.intp)
                active_ids = population.stable_ids[active_columns]
                evidence_rows = vault.db.execute(presence_query, parameters) if episodes else ()
                for path, stamp, blob, body in evidence_rows:
                    i = (date.fromisoformat(stamp) - first).days // 7
                    if not 0 <= i < weeks:
                        continue
                    for candidate in active_columns[selected_presence(blob, active_ids)]:
                        for episode in episodes.get(int(candidate), ()):
                            if (
                                episode.direction == "rising"
                                and episode.interval.start <= i <= episode.interval.end
                            ) or (episode.direction == "declining" and i < episode.interval.start):
                                episode.paths.append(path)
                                episode.bodies.add(body)
                for term_id, term_episodes in episodes.items():
                    term = cast(
                        tuple[str],
                        vault.db.execute(
                            "SELECT term FROM lexical_presence_terms WHERE term_id=?",
                            (int(population.stable_ids[term_id]),),
                        ).fetchone(),
                    )[0]
                    sparse = population.column(term_id)
                    for episode in term_episodes:
                        interval = episode.interval
                        if len(episode.bodies) < config.min_support:
                            continue
                        populated_support = (
                            sum(sparse.get(i, 0) > 0 for i in range(interval.start))
                            if episode.direction == "declining"
                            else sum(
                                sparse.get(i, 0) > 0
                                for i in range(interval.start, interval.end + 1)
                            )
                        )
                        if populated_support < config.min_support_bins:
                            continue
                        numerator = sum(
                            sparse.get(i, 0) for i in range(interval.start, interval.end + 1)
                        )
                        denominator = sum(exposure[interval.start : interval.end + 1])
                        reference, reference_start, reference_end = None, None, None
                        prevalence = DocumentRate(numerator, denominator)
                        if episode.direction == "declining":
                            if (
                                sum(n > 0 for n in exposure[interval.start : interval.end + 1])
                                < config.min_support_bins
                            ):
                                continue
                            prior_exposure = sum(exposure[: interval.start])
                            if not prior_exposure:
                                continue
                            reference = DocumentRate(
                                sum(sparse.get(i, 0) for i in range(interval.start)), prior_exposure
                            )
                            if prevalence.fraction >= reference.fraction:
                                continue
                            reference_start = first.isoformat()
                            reference_end = (
                                first + timedelta(weeks=interval.start) - timedelta(days=1)
                            ).isoformat()
                        start = first + timedelta(weeks=interval.start)
                        end = date.fromordinal(
                            min(date.max.toordinal(), first.toordinal() + interval.end * 7 + 6)
                        )
                        raw_findings.append(
                            WordBurstFinding(
                                term,
                                start.isoformat(),
                                end.isoformat(),
                                interval.level,
                                interval.gain,
                                prevalence,
                                DocumentRate(sum(sparse.values()), stats.documents),
                                tuple(sorted(set(episode.paths))),
                                config.history_mode,
                                tuple(
                                    (first + timedelta(weeks=i)).isoformat() for i in interval.gaps
                                ),
                                interval.left_censored,
                                interval.open,
                                False,
                                episode.direction,
                                reference,
                                reference_start,
                                reference_end,
                            )
                        )
                stats.evidence_seconds = time.perf_counter() - started
                stats.reason = "burst" if raw_findings else "no_burst"
            payload = json.dumps([finding.to_dict() for finding in raw_findings])
            population_json = json.dumps(stats.population_dict())
            _store(vault, population_key, payload, population_json)
            _store(vault, exact_key, payload, population_json)
            findings = [_present(finding, end_day, canonical_end) for finding in raw_findings]
        vault.db.execute(
            "DELETE FROM word_burst_cache WHERE rowid NOT IN "
            "(SELECT rowid FROM word_burst_cache ORDER BY rowid DESC LIMIT 8)"
        )
        return findings
