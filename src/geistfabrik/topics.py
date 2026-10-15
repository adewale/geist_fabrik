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

from . import markdown_parser
from .config import GEIST_JOURNAL_DIR
from .markdown_parser import iter_wikilinks, markdown_prose_lines, parse_frontmatter
from .models import _normalise_vault_path

MAX_TOPICS = 5
MAX_TOPIC_CHARS = 100_000
_SETTINGS: dict[str, Any] = {
    "lan": "en", "n": 3, "top": 50, "dedup_lim": 0.9, "window_size": 2,
}
_WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
_REGION_OPEN = re.compile(r"<!--|%%|`+")
_LINK = re.compile(r"(!?)\[([^\]\n]*)\]\([^\)\n]*\)")
_REFERENCE_LINK = re.compile(r"(!?)\[([^\]\n]+)\]\[[^\]\n]*\]")
_REFERENCE_DEF = re.compile(r"(?m)^ {0,3}\[[^\]\n]+\]:[^\n]*(?:\n[ \t]+[^\n]+)*")
_SECTION_LABELS = {
    "notes", "references", "contents", "features", "to-do", "readme", "related",
    "introduction", "background", "methods", "results", "discussion", "summary",
}
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


def _mask(chars: list[str], start: int, end: int, *, barrier: bool = True) -> None:
    first = True
    for pos in range(start, end):
        if chars[pos] not in "\r\n":
            chars[pos] = "." if barrier and first else " "
            first = False


def _mask_regions(chars: list[str], content: str) -> None:
    """First opener owns its delimiters, including code markers in hidden metadata."""
    text = "".join(chars)
    pos = 0
    while True:
        candidates = [
            (match.start(), order, pattern, match)
            for order, pattern in enumerate(
                (_REGION_OPEN, _REFERENCE_DEF, _LINK, _REFERENCE_LINK)
            )
            if (match := pattern.search(content if pattern == _REFERENCE_DEF else text, pos))
            is not None
        ]
        if not candidates:
            return
        _, _, pattern, match = min(candidates, key=lambda item: item[:2])
        if pattern == _REFERENCE_DEF:
            _mask(chars, match.start(), match.end())
            pos = match.end()
            text = "".join(chars)
            continue
        if pattern in (_LINK, _REFERENCE_LINK):
            if match[1]:
                _mask(chars, match.start(), match.end())
                pos = match.end()
            else:
                _mask(chars, match.start(), match.start(2), barrier=False)
                _mask(chars, match.end(2), match.end(), barrier=False)
                pos = match.start(2)
            text = "".join(chars)
            continue
        opener = match[0]
        if opener in {"<!--", "%%"}:
            closer = "-->" if opener == "<!--" else "%%"
            closing = text.find(closer, match.end())
            end = closing + len(closer) if closing >= 0 else len(text)
        else:
            closing_match = re.search(
                r"(?<!`)" + re.escape(opener) + r"(?!`)", text[match.end():]
            )
            if closing_match is None:
                pos = match.end()
                continue  # An unmatched backtick is literal Markdown prose.
            end = match.end() + closing_match.end()
        _mask(chars, match.start(), end)
        pos = end


def topic_prose(content: str) -> str:
    """Mask code and metadata while preserving character offsets and line numbers."""
    _, body = parse_frontmatter(content)
    offset = len(content) - len(body)
    chars = list(content)
    _mask(chars, 0, offset)
    projection = "\n".join(
        re.sub(r"^ {0,3}(?:>[ \t]?)+", "", line) for line in body.split("\n")
    )
    allowed = {number for number, _ in markdown_prose_lines(projection)}
    pos = offset
    for number, line in enumerate(body.splitlines(keepends=True), start=1):
        heading = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*$", line)
        name = re.sub(r"^\d+[.)]?\s+", "", heading[1]) if heading else ""
        if number not in allowed or (heading and topic_key(name) in _SECTION_LABELS):
            _mask(chars, pos, pos + len(line))
        elif line.endswith("\n") and (
            not line.strip() or re.match(r"^ {0,3}(?:#{1,6}\s|[-*+]\s)", line)
        ):
            chars[pos + len(line) - 1] = "."
        # Separate prose from a following list or heading as well.
        if re.match(r"^ {0,3}(?:#{1,6}\s|[-*+]\s)", line) and pos > offset:
            if chars[pos - 1] == "\n":
                chars[pos - 1] = "."
        pos += len(line)
    _mask_regions(chars, content)
    for pattern in (
        re.compile(r"</?[A-Za-z][^>\n]*>"),
        re.compile(r"(?:https?://|www\.)[^\s<>]+"),
        re.compile(r"(?<!\S)#[\w/-]+"),
    ):
        for match in pattern.finditer("".join(chars)):
            _mask(chars, match.start(), match.end())
    for match in iter_wikilinks("".join(chars)):
        if match[1]:
            _mask(chars, match.start(), match.end())
        else:
            group = 3 if match[3] is not None else 2
            _mask(chars, match.start(), match.start(group), barrier=False)
            _mask(chars, match.end(group), match.end(), barrier=False)
    for match in re.finditer(r"[#*_~>|\[\]]", "".join(chars)):
        _mask(chars, match.start(), match.end(), barrier=False)
    return "".join(chars)


def _explicit_labels(content: str, prose: str) -> Iterator[tuple[str, int, int, str]]:
    for match in re.finditer(r"(?m)^ {0,3}#[ \t]+(.+?)\s*$", content):
        start, end = match.span(1)
        label = prose[start:end].strip().rstrip(".").strip()
        if topic_key(label) not in _SECTION_LABELS and 1 <= len(label.split()) <= 5:
            end = start + len(prose[start:end].rstrip(". \r\n"))
            yield label, start, end, "heading"
    for match in iter_wikilinks(content):
        if not match[1]:
            start, end = match.span(3 if match[3] is not None else 2)
            label = prose[start:end].strip()
            if 1 <= len(label.split()) <= 3:
                yield label, start, end, "wikilink"


def extract_topics(content: str, extractor: KeywordExtractor | None = None) -> list[TopicTag]:
    """Ground all labels in visible text; report oversize inputs instead of truncating."""
    if len(content) > MAX_TOPIC_CHARS:
        raise ValueError(f"topic extraction exceeds {MAX_TOPIC_CHARS} characters")
    prose = topic_prose(content)
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
        match = re.search(expression, prose, re.IGNORECASE)
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
    for path in (Path(__file__), Path(markdown_parser.__file__)):
        digest.update(path.read_bytes())
    digest.update(version("yake").encode())
    digest.update(json.dumps(_SETTINGS, sort_keys=True).encode())
    return digest.hexdigest()


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


class TopicIndex:
    """Transactional derived storage. Geists access it through VaultContext."""

    def __init__(self, db: sqlite3.Connection, exclude_paths: Sequence[str] = ()):
        self.db = db
        self.exclude_paths = tuple(sorted({
            _normalise_vault_path(path).strip("/")
            for path in (*exclude_paths, GEIST_JOURNAL_DIR, "_geistfabrik") if path.strip("/")
        }))

    def _excluded(self, path: str) -> bool:
        path = _normalise_vault_path(path)
        return any(path == prefix or path.startswith(prefix + "/") for prefix in self.exclude_paths)

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
                    source_errors: dict[str, str] | None = None) -> None:
        if not self.db.in_transaction:
            raise RuntimeError("Topic synchronization requires the Vault.sync transaction")
        self.db.execute("DELETE FROM topic_source_errors")
        self.db.executemany("INSERT INTO topic_source_errors VALUES (?, ?)", (
            (path, error) for path, error in (source_errors or {}).items()
            if not self._excluded(path)
        ))
        algorithm = self._algorithm_digest()
        rows = self.db.execute(
            "SELECT n.path,n.content,n.source_file,s.source_digest,s.algorithm_digest,s.status "
            "FROM notes n LEFT JOIN note_topic_state s ON s.note_path=n.path ORDER BY n.path"
        ).fetchall()
        for path, content, source_file, previous_content, previous_algorithm, previous_status in rows:
            if self._excluded(source_file or path):
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
        path, content, source_file, digest, algorithm, status, error, source_error = row
        if self._excluded(source_file or path):
            return TopicState("excluded")
        if source_error:
            return TopicState("error", str(source_error))
        if digest != _content_digest(content) or algorithm != self._algorithm_digest():
            return TopicState("pending")
        return TopicState("complete") if status == "complete" else TopicState("error", error)

    def _rows(self, path: str | None = None) -> list[tuple[Any, ...]]:
        sql = (
            "SELECT n.path,n.content,n.source_file,s.source_digest,s.algorithm_digest,"
            "s.status,s.error,e.error FROM notes n "
            "LEFT JOIN note_topic_state s ON s.note_path=n.path "
            "LEFT JOIN topic_source_errors e ON e.source_path=COALESCE(n.source_file,n.path)"
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
            error = self.db.execute(
                "SELECT error FROM topic_source_errors WHERE source_path=?", (path,)
            ).fetchone()
            return TopicState("error", error[0]) if error else TopicState("pending")

    def states(self) -> dict[str, TopicState]:
        with self.read_snapshot():
            rows = self._rows()
            states = {row[0]: self._state_from_row(row) for row in rows}
            represented = {row[2] or row[0] for row in rows}
            for path, error in self.db.execute("SELECT source_path,error FROM topic_source_errors"):
                if path not in represented and not self._excluded(path):
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
