"""Incremental lexical capture inside the vault's owned sync transaction."""

import fnmatch
import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from .config_loader import LexicalAnalysisConfig
from .markdown_parser import declared_creation_date, markdown_prose_lines, parse_frontmatter
from .models import Note, _normalise_vault_path

EXTRACTION_VERSION = 2
_WORDS = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
_REMOVED = re.compile(r"https?://[^\s)\]>]+")
_INLINE_CODE = re.compile(r"(?P<ticks>`+)(?!`).*?(?<!`)(?P=ticks)(?!`)", re.DOTALL)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def week_start(day: date) -> date:
    """Monday of a calendar date's UTC/declared weekly bin."""
    return day - timedelta(days=day.weekday())


def extract_terms(
    content: str, *, ngram_max: int = 1, include_quotes: bool = False
) -> Counter[str]:
    """Exact occurrences of words and within-line phrases in Markdown prose.

    Frontmatter, code, URLs and (by default) blockquotes are excluded. Removed
    inline regions and line boundaries interrupt phrases. Unicode NFKC/casefold
    normalization is deterministic; numeric IDs are not words.
    """
    if isinstance(ngram_max, bool) or not isinstance(ngram_max, int) or not 1 <= ngram_max <= 3:
        raise ValueError("ngram_max must be an integer in [1, 3]")
    if not isinstance(include_quotes, bool):
        raise ValueError("include_quotes must be boolean")
    _, body = parse_frontmatter(content)
    body = re.sub(r"<!--.*?-->", "\n\x00\n", body, flags=re.DOTALL)
    prose = []
    previous = 0
    for number, line in markdown_prose_lines(body):
        if number != previous + 1:
            prose.append("\x00")
        previous = number
        if not include_quotes and line.lstrip().startswith(">"):
            prose.append("\x00")
        else:
            prose.append(line)
    # Matching delimiter lengths also handles multiline inline-code spans.
    body = _INLINE_CODE.sub("\x00", "\n".join(prose))
    counts: Counter[str] = Counter()
    for line in body.splitlines():
        # Keep visible Markdown labels; link destinations are not writing.
        line = re.sub(r"!?\[([^]\n]*)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"\[\[([^]|\n]+)\|([^]\n]+)\]\]", r"\2", line)
        line = re.sub(r"\[\[([^]\n]+)\]\]", r"\1", line)
        normalized = unicodedata.normalize("NFKC", line).casefold()
        for region in _REMOVED.sub("\x00", normalized).split("\x00"):
            words = _WORDS.findall(region)
            for size in range(1, ngram_max + 1):
                counts.update(" ".join(words[i : i + size]) for i in range(len(words) - size + 1))
    return counts


@dataclass
class LexicalIndex:
    """One synchronization's lexical policy, timestamp and diagnostic counter.

    Methods never commit. The production caller holds Vault.sync's writer lock.
    Initial discovery and policy changes establish baselines, not writing events.
    """

    db: sqlite3.Connection
    options: LexicalAnalysisConfig
    observed_at: datetime
    extracted: int = 0
    changed: int = 0

    def prepare(self) -> bool:
        """Reset incompatible extraction/history and return whether a rebuild is needed."""
        policy = json.dumps([EXTRACTION_VERSION, self.options.to_dict()], sort_keys=True)
        row = self.db.execute("SELECT value FROM lexical_meta WHERE key = 'policy'").fetchone()
        if row and row[0] == policy:
            return False
        self.db.execute("DELETE FROM lexical_notes")
        self.db.execute("DELETE FROM lexical_terms")
        self.db.execute("DELETE FROM word_burst_cache")
        self.db.execute(
            "INSERT INTO lexical_meta(key, value) VALUES ('policy', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (policy,),
        )
        return True

    def sync_note(self, note: Note) -> None:
        """Capture one processed note and positive additions since its last observation."""
        if not self.options.enabled:
            return
        now = self.observed_at.astimezone(UTC).isoformat()
        old = self.db.execute(
            "SELECT raw_hash, counts_json, observed_at FROM lexical_notes WHERE path = ?",
            (note.path,),
        ).fetchone()
        raw_hash = _digest(note.content)
        if old and old[0] == raw_hash:
            return
        paths = {_normalise_vault_path(note.path)}
        if note.source_file:
            paths.add(_normalise_vault_path(note.source_file))
        patterns = [_normalise_vault_path(pattern) for pattern in self.options.exclude_paths]
        excluded = any(
            path.startswith(("_geistfabrik/", "geist journal/"))
            or any(
                path.startswith(pattern) or fnmatch.fnmatchcase(path, pattern)
                for pattern in patterns
            )
            for path in paths
        )
        counts = (
            Counter()
            if excluded
            else extract_terms(
                note.content,
                ngram_max=self.options.ngram_max,
                include_quotes=self.options.include_quotes,
            )
        )
        self.extracted += not excluded
        encoded = json.dumps(counts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        body_hash = _digest(encoded)
        cohort, provenance = None, "filesystem_estimate"
        if note.entry_date:
            cohort, provenance = note.entry_date.isoformat(), "entry_heading"
        elif (declared := declared_creation_date(note.path, note.content)) is not None:
            cohort, provenance = declared.date().isoformat(), "declared_date"
        watermark = self.db.execute(
            "SELECT value FROM lexical_meta WHERE key = 'last_sync_at'"
        ).fetchone()
        previous_at = (
            max(str(old[2]), str(watermark[0]) if watermark else str(old[2])) if old else now
        )
        # Clock regressions must not create backdated events or move the baseline backwards.
        clock_regressed = old is not None and now < previous_at
        if old:
            now = max(now, previous_at)
        additions = counts - Counter(json.loads(old[1])) if old else Counter()
        self.db.execute(
            "INSERT INTO lexical_notes VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(path) DO UPDATE SET raw_hash=excluded.raw_hash, "
            "body_hash=excluded.body_hash, cohort_day=excluded.cohort_day, "
            "provenance=excluded.provenance, counts_json=excluded.counts_json, "
            "observed_at=excluded.observed_at",
            (note.path, raw_hash, body_hash, cohort, provenance, encoded, now),
        )
        self.changed += bool(not old or old[1] != encoded)
        if old and self.options.capture_observed and not clock_regressed and additions:
            bin_start = week_start(datetime.fromisoformat(now).date()).isoformat()
            event = self.db.execute(
                "SELECT terms_json, revisions_json, previous_at FROM lexical_events "
                "WHERE path=? AND bin_start=?",
                (note.path, bin_start),
            ).fetchone()
            terms = set(json.loads(event[0])) if event else set()
            terms.update(additions)
            revisions = list(json.loads(event[1])) if event else []
            revisions.append(_digest(str(old[1]) + encoded))
            evidence = _digest(json.dumps(revisions, separators=(",", ":")))
            self.db.execute(
                "INSERT INTO lexical_events VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(path, bin_start) DO UPDATE SET observed_at=excluded.observed_at, "
                "terms_json=excluded.terms_json, revisions_json=excluded.revisions_json, "
                "evidence_hash=excluded.evidence_hash",
                (
                    note.path,
                    bin_start,
                    event[2] if event else previous_at,
                    now,
                    json.dumps(sorted(terms)),
                    json.dumps(revisions),
                    evidence,
                ),
            )

    def finish(self) -> None:
        """Tighten bounds only when every changed source was successfully mirrored.

        A skipped/unreadable source cannot confirm its old content. Keeping the
        global bound conservative avoids rewriting every unchanged lexical row.
        """
        now = self.observed_at.astimezone(UTC).isoformat()
        self.db.execute(
            "INSERT INTO lexical_meta SELECT 'last_sync_at', ? WHERE NOT EXISTS "
            "(SELECT fingerprint FROM _lexical_changed_sources EXCEPT "
            "SELECT source_fingerprint FROM notes) ON CONFLICT(key) "
            "DO UPDATE SET value = max(value, excluded.value)",
            (now,),
        )
        self.db.execute("DELETE FROM lexical_terms WHERE documents = 0")
