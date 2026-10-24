"""Local, rebuildable derived labels with exact evidence and explicit completeness."""

import hashlib
import json
import math
import re
import sqlite3
import unicodedata
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal, Protocol, cast

import yake  # type: ignore[import-untyped]

from . import markdown_parser, source_eligibility, topic_text
from .config import GEIST_JOURNAL_DIR
from .source_eligibility import SourceEligibility
from .topic_text import explicit_labels as _explicit_labels
from .topic_text import topic_boundaries, topic_prose

MAX_TOPICS = 5
MAX_TOPIC_CHARS = 100_000
_SETTINGS: dict[str, Any] = {
    "lan": "en", "n": 3, "top": 50, "dedup_lim": 0.9, "window_size": 2,
}
_WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
# Ranking hints, never validity rules. Subjects such as "use cases" remain eligible.
_PREDICATE_HINTS = frozenset(
    "need needs use uses using make makes made help helps improve improves "
    "develop develops connect connects change changes reduce reduces include includes "
    "depend depends begin begins contain contains combine combines explore explores "
    "protect protects detect detects disagree evolve evolves discussed focused "
    "through over and or but".split()
)


class KeywordExtractor(Protocol):
    def extract_keywords(self, text: str) -> list[tuple[str, float]]: ...


@dataclass(frozen=True)
class TopicTag:
    """A label and its exact evidence in stored note/virtual-entry content."""

    key: str
    label: str
    score: float
    start: int
    end: int
    text: str
    line: int
    provenance: str = "yake"


@dataclass(frozen=True)
class TopicState:
    status: Literal["complete", "pending", "error", "excluded"]
    error: str | None = None


class TopicIndexIncompleteError(RuntimeError):
    """Unfinished extraction cannot establish absence or corpus counts."""


def topic_key(label: str) -> str:
    """Case/Unicode/whitespace normalization only; no semantic merging or stemming."""
    return " ".join(unicodedata.normalize("NFC", label).casefold().split())


def extract_topics(content: str, extractor: KeywordExtractor | None = None) -> list[TopicTag]:
    """Ground all labels in visible text; report oversize inputs instead of truncating."""
    if len(content) > MAX_TOPIC_CHARS:
        raise ValueError(f"topic extraction exceeds {MAX_TOPIC_CHARS} characters")
    prose = topic_prose(content)
    boundaries = topic_boundaries(content)
    if not _WORD.search(prose):
        return []
    if extractor is None:
        extractor = cast(KeywordExtractor, yake.KeywordExtractor(**_SETTINGS))
    tags: dict[str, TopicTag] = {}
    for label, start, end, provenance in _explicit_labels(content, prose):
        key = topic_key(label)
        if len(key) >= 2 and " ".join(_WORD.findall(key)) == key and any(c.isalpha() for c in key):
            tags.setdefault(key, TopicTag(
                key, label, 0.0 if provenance == "heading" else 0.001,
                start, end, content[start:end], content.count("\n", 0, start) + 1, provenance,
            ))
    for label, raw_score in extractor.extract_keywords(prose):
        key = topic_key(label)
        words = _WORD.findall(key)
        score = float(raw_score)
        if any(word in _PREDICATE_HINTS for word in words):
            score *= 32.0
        if (not words or " ".join(words) != key or not any(c.isalpha() for c in key)
                or len(key) < 2 or len(set(words)) != len(words)
                or not math.isfinite(score) or score < 0):
            continue
        expression = r"(?<!\w)" + r"\s+".join(re.escape(w) for w in label.split()) + r"(?!\w)"
        match = next((candidate for candidate in re.finditer(expression, prose, re.IGNORECASE)
                      if not any(candidate.start() < edge < candidate.end()
                                 for edge in boundaries)), None)
        if match is None:
            continue
        tag = TopicTag(key, " ".join(label.split()), score, match.start(), match.end(),
                       content[match.start():match.end()], content.count("\n", 0, match.start()) + 1)
        if key not in tags or score < tags[key].score:
            tags[key] = tag
    selected: list[TopicTag] = []
    for tag in sorted(tags.values(), key=lambda item: (item.score, item.key)):
        if any(f" {tag.key} " in f" {other.key} " or f" {other.key} " in f" {tag.key} "
               for other in selected):
            continue
        selected.append(tag)
        if len(selected) == MAX_TOPICS:
            break
    return selected


@lru_cache(maxsize=1)
def _extractor_identity() -> str:
    digest = hashlib.sha256()
    for path in (Path(__file__), Path(markdown_parser.__file__), Path(source_eligibility.__file__),
                 Path(topic_text.__file__)):
        digest.update(path.read_bytes())
    digest.update(version("yake").encode())
    digest.update(version("markdown-it-py").encode())
    digest.update(json.dumps(_SETTINGS, sort_keys=True).encode())
    return digest.hexdigest()


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


class TopicIndex:
    """Transactional derived storage. Geists access it through VaultContext."""

    def __init__(self, db: sqlite3.Connection, exclude_paths: Sequence[str] = ()):
        self.db = db
        self.exclude_paths = tuple(sorted(set(exclude_paths)))
        self._eligibility = SourceEligibility(
            (*self.exclude_paths, GEIST_JOURNAL_DIR + "/", "_geistfabrik/")
        )

    def _excluded(self, path: str, source_file: str | None = None) -> bool:
        return not self._eligibility.allows(path, source_file)

    def _algorithm_digest(self) -> str:
        return hashlib.sha256(json.dumps(
            [_extractor_identity(), self.exclude_paths], ensure_ascii=False
        ).encode()).hexdigest()

    @contextmanager
    def read_snapshot(self) -> Iterator[None]:
        """Keep validation and use consistent without committing a caller's transaction."""
        owned = not self.db.in_transaction
        if owned:
            self.db.execute("BEGIN")
        try:
            yield
        finally:
            if owned and self.db.in_transaction:
                self.db.rollback()

    def synchronize(self, *, rebuild: bool = False,
                    source_errors: dict[str, str] | None = None,
                    source_identities: dict[str, str] | None = None) -> None:
        if not self.db.in_transaction:
            raise RuntimeError("Topic synchronization requires the Vault.sync transaction")
        if source_identities is not None:
            self.db.execute("DELETE FROM topic_source_identity")
            self.db.executemany("INSERT INTO topic_source_identity VALUES (?, ?)",
                                source_identities.items())
        identities = dict(self.db.execute("SELECT source_path,resolved_path FROM topic_source_identity"))
        self.db.execute("DELETE FROM topic_source_errors")
        self.db.executemany("INSERT INTO topic_source_errors VALUES (?, ?)", (
            (path, error) for path, error in (source_errors or {}).items()
            if not self._excluded(path, identities.get(path))
        ))
        algorithm = self._algorithm_digest()
        rows = self.db.execute(
            "SELECT n.path,n.content,n.source_file,s.source_digest,s.algorithm_digest,s.status "
            "FROM notes n LEFT JOIN note_topic_state s ON s.note_path=n.path ORDER BY n.path"
        ).fetchall()
        for path, content, source_file, previous_content, previous_algorithm, previous_status in rows:
            if self._excluded(path, source_file) or self._excluded(
                source_file or path, identities.get(source_file or path)
            ):
                self.db.execute("DELETE FROM note_topics WHERE note_path=?", (path,))
                self.db.execute("DELETE FROM note_topic_state WHERE note_path=?", (path,))
                continue
            digest = _content_digest(content)
            if (not rebuild and digest == previous_content and algorithm == previous_algorithm
                    and previous_status == "complete"):
                continue
            try:
                tags = extract_topics(content)
                status, error = "complete", None
            except Exception as exc:
                tags, status, error = [], "error", f"{type(exc).__name__}: topic extraction failed"
            self.db.execute("DELETE FROM note_topics WHERE note_path=?", (path,))
            self.db.execute(
                "INSERT OR REPLACE INTO note_topic_state "
                "(note_path,source_digest,algorithm_digest,status,error) VALUES (?,?,?,?,?)",
                (path, digest, algorithm, status, error),
            )
            for tag in tags:
                self.db.execute("INSERT OR IGNORE INTO topics VALUES (?)", (tag.key,))
                self.db.execute(
                    "INSERT INTO note_topics (note_path,topic_key,label,score,source_start,"
                    "source_end,source_text,source_line,provenance) VALUES (?,?,?,?,?,?,?,?,?)",
                    (path, tag.key, tag.label, tag.score, tag.start, tag.end,
                     tag.text, tag.line, tag.provenance),
                )
        self.db.execute("DELETE FROM topics WHERE topic_key NOT IN (SELECT topic_key FROM note_topics)")

    def _state_from_row(self, row: tuple[Any, ...]) -> TopicState:
        path, content, source_file, digest, algorithm, status, error, source_error, resolved = row
        if self._excluded(path, source_file) or (resolved and self._excluded(resolved)):
            return TopicState("excluded")
        if source_error:
            return TopicState("error", str(source_error))
        if resolved is None:
            return TopicState("pending")  # Physical provenance has not been confirmed.
        if digest != _content_digest(content) or algorithm != self._algorithm_digest():
            return TopicState("pending")
        return TopicState("complete") if status == "complete" else TopicState("error", error)

    def _rows(self, path: str | None = None) -> list[tuple[Any, ...]]:
        sql = (
            "SELECT n.path,n.content,n.source_file,s.source_digest,s.algorithm_digest,"
            "s.status,s.error,e.error,i.resolved_path FROM notes n "
            "LEFT JOIN note_topic_state s ON s.note_path=n.path "
            "LEFT JOIN topic_source_errors e ON e.source_path=COALESCE(n.source_file,n.path) "
            "LEFT JOIN topic_source_identity i ON i.source_path=COALESCE(n.source_file,n.path)"
        )
        return self.db.execute(sql + (" WHERE n.path=?" if path is not None else ""),
                               (path,) if path is not None else ()).fetchall()

    def state(self, path: str) -> TopicState:
        with self.read_snapshot():
            rows = self._rows(path)
            if rows:
                return self._state_from_row(rows[0])
            if self._excluded(path):
                return TopicState("excluded")
            identity = self.db.execute(
                "SELECT resolved_path FROM topic_source_identity WHERE source_path=?", (path,)
            ).fetchone()
            if identity and self._excluded(path, identity[0]):
                return TopicState("excluded")
            error = self.db.execute(
                "SELECT e.error,i.resolved_path FROM topic_source_errors e "
                "LEFT JOIN topic_source_identity i ON i.source_path=e.source_path "
                "WHERE e.source_path=?", (path,)
            ).fetchone()
            if error and self._excluded(path, error[1]):
                return TopicState("excluded")
            return TopicState("error", error[0]) if error else TopicState("pending")

    def states(self) -> dict[str, TopicState]:
        with self.read_snapshot():
            rows = self._rows()
            states = {row[0]: self._state_from_row(row) for row in rows}
            represented = {row[2] or row[0] for row in rows}
            for path, error, resolved in self.db.execute(
                "SELECT e.source_path,e.error,i.resolved_path FROM topic_source_errors e "
                "LEFT JOIN topic_source_identity i ON i.source_path=e.source_path"
            ):
                if path not in represented and not self._excluded(path, resolved):
                    states[path] = TopicState("error", error)
            return states

    def require_complete(self, states: dict[str, TopicState] | None = None) -> None:
        states = self.states() if states is None else states
        if any(state.status not in {"complete", "excluded"} for state in states.values()):
            raise TopicIndexIncompleteError("Topic index is incomplete; sync or inspect source errors")

    def tags(self, path: str) -> list[TopicTag]:
        with self.read_snapshot():
            state = self.state(path)
            if state.status == "excluded":
                return []
            if state.status != "complete":
                raise TopicIndexIncompleteError(f"Topic extraction for {path} is {state.status}")
            return [TopicTag(*row) for row in self.db.execute(
                "SELECT topic_key,label,score,source_start,source_end,source_text,source_line,"
                "provenance FROM note_topics WHERE note_path=? ORDER BY score,topic_key", (path,)
            )]

    def catalog(self) -> list[tuple[str, int]]:
        with self.read_snapshot():
            states = self.states()
            self.require_complete(states)
            counts: dict[str, int] = {}
            for key, path in self.db.execute("SELECT topic_key,note_path FROM note_topics"):
                if states[path].status == "complete":
                    counts[key] = counts.get(key, 0) + 1
            return sorted(counts.items())

    def paths(self, topic: str) -> list[str]:
        with self.read_snapshot():
            states = self.states()
            self.require_complete(states)
            return [path for (path,) in self.db.execute(
                "SELECT note_path FROM note_topics WHERE topic_key=? ORDER BY note_path",
                (topic_key(topic),)
            ) if states[path].status == "complete"]
