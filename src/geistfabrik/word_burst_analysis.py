"""Historical lexical evidence service exposed through VaultContext."""

import hashlib
import json
import time
from array import array
from collections import Counter
from dataclasses import asdict, dataclass, field, fields
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import numpy as np

from .document_rate import DocumentRate
from .lexical_index import EXTRACTION_VERSION, week_start
from .sqlite_transaction import owned_transaction
from .word_burst import BurstInterval, BurstModel, PreparedBurstSeries

if TYPE_CHECKING:
    from .vault import Vault

ANALYSIS_VERSION = 6


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
    # Callers may reuse their diagnostics receiver. Each invocation reports its
    # own work, rather than retaining a previous decode count or cache flag.
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
            "SELECT result_json, diagnostics_json FROM word_burst_cache WHERE cache_key=?",
            (key,),
        ).fetchone()
        if cached:
            population = json.loads(cached[1])
            for name in stats.population_dict():
                setattr(stats, name, population[name])
            stats.cache_hit = True
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
        # Preseed only eligible cohort terms with an unassigned ID. One lookup
        # then handles both the eligibility screen and the eventual stable ID.
        term_ids: dict[str, int] = (
            {
                row[0]: -1
                for row in vault.db.execute(
                    "SELECT term FROM lexical_terms WHERE documents >= ?", (config.min_support,)
                )
            }
            if config.history_mode == "dated_cohorts"
            else {}
        )
        rows = vault.db.execute(query, parameters)
        exposure = [0] * weeks
        terms: list[str] = []
        counts: list[Counter[int]] = []
        # One packed presence buffer per bin. Duplicate bodies share offsets,
        # so collection and evidence use the same population without copying
        # every document's term IDs or incrementing millions of Python counters.
        bins = [array("q") for _ in exposure]
        groups: dict[tuple[int, str], tuple[int, int]] = {}
        documents: list[tuple[str, int, str, tuple[int, int]]] = []
        for path, stamp, vector, body in rows:
            i = (date.fromisoformat(stamp) - first).days // 7
            if not 0 <= i < len(exposure):
                continue
            group = (i, body)
            span = groups.get(group)
            if span is None:
                ids = bins[i]
                span_start = len(ids)
                for term in json.loads(vector):
                    # Current document frequency is a necessary upper bound
                    # only for current-text cohorts, never for captured history.
                    term_id = term_ids.get(term)
                    if term_id is None:
                        if config.history_mode == "dated_cohorts":
                            continue
                    if term_id is None or term_id < 0:
                        term_id = len(terms)
                        term_ids[term] = term_id
                        terms.append(term)
                        counts.append(Counter())
                    ids.append(term_id)
                span = (span_start, len(ids))
                groups[group] = span
                exposure[i] += 1
            documents.append((path, i, body, span))
        for i, ids in enumerate(bins):
            if ids:
                # IDs index Python lists and hence fit np.intp. Each term occurs
                # at most once per distinct body, so counts are bounded by the
                # number of materialized groups and fit the platform index type.
                frequencies = np.bincount(
                    np.frombuffer(ids, dtype=np.int64).astype(np.intp, copy=False)
                )
                for term_id in np.flatnonzero(frequencies).tolist():
                    counts[term_id][i] = int(frequencies[term_id])
        stats.collection_seconds = time.perf_counter() - started
        stats.documents = sum(exposure)
        stats.populated_bins = sum(n > 0 for n in exposure)
        findings: list[WordBurstFinding] = []
        if stats.documents < config.min_documents:
            stats.reason = "insufficient_documents"
        elif stats.populated_bins < config.min_populated_bins:
            stats.reason = "insufficient_bins"
        else:
            started = time.perf_counter()
            episodes: dict[int, list[_Episode]] = {}
            model = BurstModel(
                exposure, s=config.s, gamma=config.gamma, max_states=config.max_states
            )
            batched = config.max_states == 2 and config.s - 1 > 1e-8
            # Phrases often share exactly the same weekly series. Decode each
            # distinct series/direction once, preserving every term and its
            # independently collected evidence. This is exact reuse, not sampling.
            decoded: dict[tuple[tuple[tuple[int, int], ...], str], tuple[BurstInterval, ...]] = {}
            pending: dict[str, list[tuple[tuple[tuple[int, int], ...], PreparedBurstSeries]]] = {
                direction: [] for direction in config.directions
            }
            vectors: dict[int, tuple[tuple[int, int], ...]] = {}
            prepared: dict[tuple[tuple[int, int], ...], PreparedBurstSeries] = {}
            screens: dict[int, set[str]] = {}
            for term_id, sparse in enumerate(counts):
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
                vector = tuple(sorted(sparse.items()))
                vectors[term_id] = vector
                if vector not in prepared:
                    prepared[vector] = model.prepare(sparse)
                for direction in config.directions:
                    cache_key = (vector, direction)
                    if cache_key in decoded:
                        stats.series_reused += 1
                    elif direction not in viable:
                        decoded[cache_key] = ()
                    elif not batched and model.cannot_burst(prepared[vector], direction=direction):
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
            for path, i, body, (span_start, span_end) in documents:
                for term_id in memoryview(bins[i])[span_start:span_end]:
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
                    numerator = sum(sparse[i] for i in range(interval.start, interval.end + 1))
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
                            DocumentRate(sum(sparse.values()), stats.documents),
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
            "INSERT INTO word_burst_cache (cache_key, result_json, diagnostics_json) "
            "VALUES (?, ?, ?)",
            (
                key,
                json.dumps([finding.to_dict() for finding in findings]),
                json.dumps(stats.population_dict()),
            ),
        )
        # Bound exact-cutoff variants, preserving this newly computed entry.
        vault.db.execute(
            "DELETE FROM word_burst_cache WHERE rowid NOT IN "
            "(SELECT rowid FROM word_burst_cache ORDER BY rowid DESC LIMIT 8)"
        )
        return findings
