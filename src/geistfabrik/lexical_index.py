"""Incremental lexical capture inside the vault's owned sync transaction."""

import fnmatch
import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.rules_block import StateBlock, reference
from markdown_it.rules_inline import StateInline, image, link
from markdown_it.token import Token

from .config_loader import LexicalAnalysisConfig
from .markdown_parser import (
    declared_creation_date,
    iter_wikilinks,
    markdown_prose_lines,
    parse_frontmatter,
)
from .models import Note, _normalise_vault_path

EXTRACTION_VERSION = 4
_WORDS = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.UNICODE)
_REMOVED = re.compile(r"https?://[^\s)\]>]+", re.IGNORECASE)
_INLINE_CODE = re.compile(r"(?P<ticks>`+)(?!`).*?(?<!`)(?P=ticks)(?!`)", re.DOTALL)


def _reference_spans(
    body: str, parser: MarkdownIt, environment: dict[str, Any]
) -> list[tuple[int, int, str]]:
    """Replace only resolved reference syntax, preserving all other source.

    The library owns definition/label validity. Inline rules record source spans
    instead of rendering the whole document: an unused definition must not alter
    existing code, Unicode line, entity or HTML extraction boundaries.
    """
    spans: list[tuple[int, int, str]] = []
    wiki_spans = {match.start(): match.end() for match in iter_wikilinks(body)}

    def visible(tokens: list[Token]) -> str:
        return "".join(
            "\n"
            if token.type in {"softbreak", "hardbreak"}
            else "\x00"
            if token.type == "code_inline"
            else visible(token.children or [])
            if token.type == "image"
            else token.content
            if token.type in {"text", "text_special", "html_inline"}
            else ""
            for token in tokens
        )

    def wiki(state: StateInline, silent: bool) -> bool:
        end = wiki_spans.get(state.pos) if state.src == body else None
        if end is None:
            return False
        if not silent:
            state.push("text", "", 0).content = state.src[state.pos : end]
        state.pos = end
        return True

    def capture(state: StateInline, silent: bool) -> bool:
        start, before = state.pos, len(state.tokens)
        is_image = state.src.startswith("![", start)
        if not (image if is_image else link)(state, silent):
            return False
        if not silent and state.src == body:
            created = state.tokens[before:]
            kind = "image" if is_image else "link_open"
            first = next(i for i, token in enumerate(created) if token.type == kind)
            if created[first].meta.get("label"):
                spans.append((start, state.pos, visible(created[first:])))
        return True

    parser.inline.ruler.before("link", "lexical_wiki", wiki)
    parser.inline.ruler.at("link", capture)
    parser.inline.ruler.at("image", capture)
    parser.inline.parse(body, parser, environment, [])
    return spans


def _clean_references(body: str, include_quotes: bool) -> str:
    """Resolve references within their real inline blocks, before prose masking."""
    parser = MarkdownIt("commonmark", {"inline_definitions": True, "store_labels": True})
    # Only block maps and definitions are needed here. Parse selected inline
    # blocks below, after excluding documents without reference definitions.
    parser.core.ruler.disable(["inline"])

    def prose_footnotes(state: StateBlock, start: int, end: int, silent: bool) -> bool:
        # Caret labels belong to Obsidian footnotes. Keep their bodies inline,
        # including any real reference links/images within those bodies.
        position = state.bMarks[start] + state.tShift[start]
        if state.src.startswith("[^", position):
            return False
        return reference(state, start, end, silent)

    parser.block.ruler.at("reference", prose_footnotes)
    environment: dict[str, Any] = {}
    tokens = parser.parse(body, environment)
    if not environment.get("references"):
        return body
    lines = body.split("\n")
    offsets, offset = [], 0
    for line in lines:
        offsets.append(offset)
        offset += len(line) + 1
    replacements: list[tuple[int, int, str]] = []
    depth = 0
    for token in tokens:
        if token.type == "blockquote_open":
            depth += 1
        elif token.type == "blockquote_close":
            depth -= 1
        elif token.type == "definition" and token.map:
            for i in range(*token.map):
                marker = "> \x00" if lines[i].lstrip().startswith(">") else "\x00"
                replacements.append((offsets[i], offsets[i] + len(lines[i]), marker))
        elif token.type == "inline" and token.map and (include_quotes or not depth):
            if "[" not in token.content:
                continue
            positions: list[int] = []
            for i, line in enumerate(token.content.split("\n"), start=token.map[0]):
                # Core Markdown normalization replaces NUL one-for-one; source
                # offsets therefore still refer to the original characters.
                start = lines[i].replace("\x00", "\ufffd").find(line)
                if start < 0:
                    break
                positions.extend(range(offsets[i] + start, offsets[i] + start + len(line)))
                positions.append(offsets[i] + len(lines[i]))
            else:
                # A fresh inline parser keeps its rules local to this source.
                inline = MarkdownIt("commonmark", {"store_labels": True})
                for start, end, label in _reference_spans(token.content, inline, environment):
                    first, last = positions[start], positions[end - 1] + 1
                    # Hidden ID newlines are boundaries, not new prose. Keep
                    # them so unrelated following lines retain their eligibility.
                    label += "\n" * max(0, body[first:last].count("\n") - label.count("\n"))
                    replacements.append((first, last, label))
    pieces: list[str] = []
    position = 0
    for start, end, label in sorted(replacements, key=lambda span: (span[0], -span[1])):
        if start >= position:
            pieces.extend((body[position:start], label))
            position = end
    pieces.append(body[position:])
    return "".join(pieces)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def week_start(day: date) -> date:
    """Monday of a calendar date's UTC/declared weekly bin."""
    return day - timedelta(days=day.weekday())


def _prose_regions(content: str, include_quotes: bool) -> Iterator[str]:
    _, body = parse_frontmatter(content)
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    if "]:" in body:
        body = _clean_references(body, include_quotes)
    body = re.sub(r"<!--.*?-->", "\n\x00\n", body, flags=re.DOTALL)
    prose = []
    previous = 0
    quoted_lines: set[int] = set()
    if not include_quotes:
        quoted = False
        # Track raw lines before the code filter, which can hide indented lazy
        # continuations. A skipped line alone does not end a quoted paragraph.
        for number, line in enumerate(body.split("\n"), start=1):
            if not line.strip():
                quoted = False
            if re.match(r"^ {0,3}>", line):
                quoted = True
            elif re.match(
                r"^ {0,3}(?:#{1,6}(?:\s|$)|`{3,}|~{3,}|[-+*]\s|1[.)]\s)", line
            ) or re.match(r"^ {0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$", line):
                quoted = False
            if quoted:
                quoted_lines.add(number)
    for number, line in markdown_prose_lines(body):
        if number != previous + 1:
            prose.append("\x00")
        previous = number
        if number in quoted_lines:
            prose.append("\x00")
        else:
            prose.append(line)
    # Matching delimiter lengths also handles multiline inline-code spans.
    body = _INLINE_CODE.sub("\x00", "\n".join(prose))
    for line in body.splitlines():
        # Keep visible Markdown labels; link destinations are not writing.
        line = re.sub(r"!?\[([^]\n]*)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"\[\[([^]|\n]+)\|([^]\n]+)\]\]", r"\2", line)
        line = re.sub(r"\[\[([^]\n]+)\]\]", r"\1", line)
        visible = unicodedata.normalize("NFKC", line)
        # Sentence/semicolon boundaries are not phrases. Removed regions and
        # line boundaries also interrupt them, including inline-code gaps.
        yield from re.split(r"[.!?;]+|\x00", _REMOVED.sub("\x00", visible))


def extract_terms(
    content: str, *, ngram_max: int = 1, include_quotes: bool = False
) -> Counter[str]:
    """Exact words and 1–3 word phrases within visible sentence/line regions.

    Frontmatter, code, URLs and (by default) blockquotes are excluded. Unicode
    NFKC/casefold normalization is deterministic; numeric IDs are not words.
    """
    if isinstance(ngram_max, bool) or not isinstance(ngram_max, int) or not 1 <= ngram_max <= 3:
        raise ValueError("ngram_max must be an integer in [1, 3]")
    if not isinstance(include_quotes, bool):
        raise ValueError("include_quotes must be boolean")
    counts: Counter[str] = Counter()
    for region in _prose_regions(content, include_quotes):
        region = region.casefold()
        words = _WORDS.findall(region)
        for size in range(1, ngram_max + 1):
            counts.update(" ".join(words[i : i + size]) for i in range(len(words) - size + 1))
    return counts


def lexical_excerpt(content: str, term: str, *, include_quotes: bool = False) -> str | None:
    """A bounded current-prose passage containing the exact normalized term.

    This never claims to recover historical wording from captured additions.
    Only the same visible regions used for extraction are eligible.
    """
    target = term.split()
    if not target:
        return None
    for region in _prose_regions(content, include_quotes):
        matches = list(_WORDS.finditer(region))
        words = [match.group().casefold() for match in matches]
        for i in range(len(words) - len(target) + 1):
            if words[i : i + len(target)] == target:
                start = matches[max(0, i - 6)].start()
                end = matches[min(len(matches) - 1, i + len(target) + 5)].end()
                passage = region[start:end].strip()
                if len(passage) > 160:
                    start = matches[i].start()
                    passage = region[start : start + 157].strip() + "…"
                return passage
    return None


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
            "(SELECT 1 FROM _lexical_unconfirmed_sources) ON CONFLICT(key) "
            "DO UPDATE SET value = max(value, excluded.value)",
            (now,),
        )
        self.db.execute("DELETE FROM lexical_terms WHERE documents = 0")
