"""Incremental lexical capture inside the vault's owned sync transaction."""

import fnmatch
import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from collections.abc import Callable, Collection, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from html import escape as escape_html
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.rules_block import StateBlock
from markdown_it.rules_block.reference import reference
from markdown_it.rules_inline import StateInline, entity, escape, image, link
from markdown_it.rules_inline.backticks import backtick
from markdown_it.token import Token

from .config_loader import LexicalAnalysisConfig
from .lexical_html import HTMLProse
from .lexical_presence import PresenceWriter
from .markdown_parser import (
    declared_creation_day,
    iter_wikilinks,
    parse_frontmatter,
)
from .models import Note, _normalise_vault_path

EXTRACTION_VERSION = 7
_REMOVED = re.compile(r"https?://[^\s)\]>]+", re.IGNORECASE)


def _link_spans(
    body: str, parser: MarkdownIt, environment: dict[str, Any]
) -> list[tuple[int, int, str]]:
    """Parser-owned link/image/code spans within a single inline block."""
    spans: list[tuple[int, int, str]] = []
    wiki_spans = {match.start(): match.end() for match in iter_wikilinks(body)}

    def visible(tokens: list[Token]) -> str:
        return "".join(
            "\n"
            if token.type in {"softbreak", "hardbreak"}
            else "\x00" + "\n" * token.meta.get("source_newlines", 0)
            if token.type == "code_inline"
            else visible(token.children or [])
            if token.type == "image"
            else escape_html(token.content, quote=False).replace("\n", "\u2028")
            if token.type == "text_special"
            else escape_html(token.content, quote=False)
            if token.type == "text"
            else token.content
            if token.type == "html_inline"
            else ""
            for token in tokens
        )

    def wiki(state: StateInline, silent: bool) -> bool:
        # Silent scanning discovers an enclosing Markdown link's label. Claiming
        # a wiki token there looks like a forbidden nested link to CommonMark.
        if silent:
            return False
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
            spans.append((start, state.pos, visible(created[first:])))
        return True

    def code(state: StateInline, silent: bool) -> bool:
        start, before = state.pos, len(state.tokens)
        if not backtick(state, silent):
            return False
        if not silent and len(state.tokens) > before and state.tokens[-1].type == "code_inline":
            newlines = state.src[start : state.pos].count("\n")
            state.tokens[-1].meta["source_newlines"] = newlines
            if state.src == body:
                spans.append((start, state.pos, "\x00" + "\n" * newlines))
        return True

    def special(
        state: StateInline, silent: bool, rule: Callable[[StateInline, bool], bool]
    ) -> bool:
        start, before = state.pos, len(state.tokens)
        if not rule(state, silent):
            return False
        if not silent and state.src == body and len(state.tokens) > before:
            token = state.tokens[-1]
            if token.type == "text_special":
                # The following HTML pass must see decoded literal text as data,
                # never as a new tag or a second character-reference expansion.
                spans.append(
                    (
                        start,
                        state.pos,
                        escape_html(token.content, quote=False).replace("\n", "\u2028"),
                    )
                )
        return True

    parser.inline.ruler.at("backticks", code)
    parser.inline.ruler.at("escape", lambda state, silent: special(state, silent, escape))
    parser.inline.ruler.at("entity", lambda state, silent: special(state, silent, entity))
    parser.inline.ruler.before("link", "lexical_wiki", wiki)
    parser.inline.ruler.at("link", capture)
    parser.inline.ruler.at("image", capture)
    parser.inline.parse(body, parser, environment, [])
    return spans


def _clean_inline_blocks(body: str, quoted_lines: set[int], code_lines: set[int]) -> str:
    """Mask code and rewrite links using authoritative block and inline spans.

    No character offsets are inferred from normalized text. Each emitted line
    belongs to the same original source line; eligibility is decided separately
    on original source, so tab/container normalization cannot admit hidden prose.
    """
    parser = MarkdownIt("commonmark", {"inline_definitions": True, "store_labels": True})
    parser.core.ruler.disable(["inline"])

    def prose_footnotes(state: StateBlock, start: int, end: int, silent: bool) -> bool:
        position = state.bMarks[start] + state.tShift[start]
        return (
            False if state.src.startswith("[^", position) else reference(state, start, end, silent)
        )

    parser.block.ruler.at("reference", prose_footnotes)
    environment: dict[str, Any] = {}
    tokens = parser.parse(body, environment)
    lines = body.split("\n")
    for token in tokens:
        if token.type == "blockquote_open" and token.map:
            quoted_lines.update(range(token.map[0] + 1, token.map[1] + 1))
        elif token.type in {"fence", "code_block"} and token.map:
            code_lines.update(range(token.map[0] + 1, token.map[1] + 1))
        elif token.type == "definition" and token.map:
            for i in range(*token.map):
                lines[i] = "\x00"
        elif (
            token.type == "inline"
            and token.map
            and any(marker in token.content for marker in ("[", "`", "\\", "&"))
        ):
            inline = MarkdownIt("commonmark", {"store_labels": True})
            spans = _link_spans(token.content, inline, environment)
            if not spans:
                continue
            pieces: list[str] = []
            position = 0
            for start, end, label in sorted(spans, key=lambda span: (span[0], -span[1])):
                if start >= position:
                    # Hidden destination/ID newlines remain physical boundaries.
                    label += "\n" * (token.content[start:end].count("\n") - label.count("\n"))
                    pieces.extend((token.content[position:start], label))
                    position = end
            pieces.append(token.content[position:])
            cleaned = "".join(pieces).split("\n")
            if len(cleaned) != token.content.count("\n") + 1:
                raise ValueError("inline normalization must preserve source lines")
            for offset, line in enumerate(cleaned, start=token.map[0]):
                lines[offset] = line
    return "\n".join(lines)


def _mask_comments(body: str) -> str:
    """Hide comments without changing the source-line coordinate system."""
    return re.sub(
        r"<!--.*?-->",
        lambda match: "\n".join(
            line[: len(line) - len(line.lstrip(" \t"))] + "\x00" for line in match[0].split("\n")
        ),
        body,
        flags=re.DOTALL,
    )


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def extraction_policy(options: LexicalAnalysisConfig) -> str:
    """Identify semantic extraction settings, independent of capture controls."""
    return _canonical_policy(json.dumps([EXTRACTION_VERSION, options.to_dict()]))


def _canonical_policy(payload: str) -> str:
    version, settings = json.loads(payload)
    # Retain the old envelope so previous PR installations migrate without a
    # rebuild. Prefix order and duplicates cannot change extraction semantics.
    return json.dumps(
        [
            version,
            {
                "ngram_max": settings["ngram_max"],
                "include_quotes": settings["include_quotes"],
                "exclude_paths": sorted(
                    {_normalise_vault_path(p) for p in settings["exclude_paths"]}
                ),
            },
        ],
        sort_keys=True,
    )


def week_start(day: date) -> date:
    """Monday of a calendar date's UTC/declared weekly bin."""
    return day - timedelta(days=day.weekday())


def _prose_regions(content: str, include_quotes: bool) -> Iterator[str]:
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    _, body = parse_frontmatter(content)
    original = _mask_comments(body)
    quoted_lines: set[int] = set()
    code_lines: set[int] = set()
    cleaned = (
        _clean_inline_blocks(body, quoted_lines, code_lines)
        if any(marker in body for marker in ("[", "`", "~", ">", "<", "\\", "&"))
        else body
    )
    cleaned = _mask_comments(cleaned)
    # Literal tags in Markdown fences must neither open nor close HTML state,
    # even when a genuine HTML element started before that fenced example.
    cleaned = "\n".join(
        "\x00" if number in code_lines else line
        for number, line in enumerate(cleaned.split("\n"), start=1)
    )
    html = HTMLProse(cleaned, include_quotes) if "<" in cleaned or "&" in cleaned else None
    prose: list[str] = []
    quoted = False
    # Track raw quote state before excluding code/indentation, including lazy
    # continuations. Only an eligible HTML opening can own subsequent syntax;
    # raw > or an indented closing tag inside it must not change Markdown state.
    for number, (line, cleaned_line) in enumerate(
        zip(original.split("\n"), cleaned.split("\n"), strict=True), start=1
    ):
        in_html = html is not None and html.in_markup
        if not include_quotes and not in_html:
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
        allowed = in_html or not (
            number in code_lines
            or line.expandtabs(4).startswith("    ")
            or (not include_quotes and number in quoted_lines)
        )
        if html is not None:
            data_allowed = allowed and not (
                in_html
                and html.hidden
                and (
                    line.expandtabs(4).startswith("    ")
                    or (not include_quotes and re.match(r"^ {0,3}>", line))
                )
            )
            html.feed_line(number, allowed=allowed, data_allowed=bool(data_allowed))
        else:
            prose.append(cleaned_line if allowed else "\x00")
    for line in (html.prose() if html is not None else "\n".join(prose)).splitlines():
        # Link syntax has already been resolved inside its actual inline block.
        line = re.sub(r"\[\[([^]|\n]+)\|([^]\n]+)\]\]", r"\2", line)
        line = re.sub(r"\[\[([^]\n]+)\]\]", r"\1", line)
        visible = unicodedata.normalize("NFKC", line)
        # Sentence/semicolon boundaries are not phrases. Removed regions and
        # line boundaries also interrupt them, including inline-code gaps.
        yield from re.split(r"[.!?;]+|\x00|\ufffd", _REMOVED.sub("\x00", visible))


@dataclass(frozen=True)
class _Word:
    text: str
    start: int
    end: int


def _words(region: str) -> list[_Word]:
    """Tokenize once before casefold expansion, retaining marks and source spans."""
    result = []
    position = 0
    while position < len(region):
        if not region[position].isalpha():
            position += 1
            continue
        start = position
        position += 1
        while position < len(region):
            character = region[position]
            if character.isalpha() or unicodedata.category(character).startswith("M"):
                position += 1
            elif (
                character in "'’" and position + 1 < len(region) and region[position + 1].isalpha()
            ):
                position += 1
            else:
                break
        text = unicodedata.normalize("NFKC", region[start:position].casefold())
        result.append(_Word(text, start, position))
    return result


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
        words = [word.text for word in _words(region)]
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
        matches = _words(region)
        words = [match.text for match in matches]
        for i in range(len(words) - len(target) + 1):
            if words[i : i + len(target)] == target:
                start = matches[max(0, i - 6)].start
                end = matches[min(len(matches) - 1, i + len(target) + 5)].end
                passage = region[start:end].strip()
                if len(passage) > 160:
                    start = matches[i].start
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
    _presence_writer: PresenceWriter | None = field(default=None, init=False, repr=False)
    _capture: bool = field(default=False, init=False, repr=False)
    _policy: str = field(default="", init=False, repr=False)
    _restore: bool = field(default=False, init=False, repr=False)

    def _presence(self, terms: Collection[str]) -> bytes:
        if self._presence_writer is None:
            self._presence_writer = PresenceWriter(self.db)
        return self._presence_writer.encode(terms)

    def prepare(self) -> bool:
        """Rebaseline incompatible extraction while retaining policy-scoped evidence."""
        policy = self._policy = extraction_policy(self.options)
        row = self.db.execute("SELECT value FROM lexical_meta WHERE key = 'policy'").fetchone()
        state = dict(self.db.execute("SELECT key, value FROM lexical_meta"))
        self.db.execute(
            "CREATE TEMP TABLE IF NOT EXISTS _lexical_new_sources (path TEXT PRIMARY KEY)"
        )
        self.db.execute("DELETE FROM _lexical_new_sources")
        previous = _canonical_policy(row[0]) if row else None
        legacy_capture = bool(
            row and all(json.loads(row[0])[1].get(k, True) for k in ("enabled", "capture_observed"))
        )
        self._capture = (
            previous == policy
            and self.options.capture_observed
            and state.get("capture_active", "1" if legacy_capture else "0") == "1"
            and state.get("index_active", "1") == "1"
        )
        resuming = state.get("index_active") == "0" or (
            self.options.capture_observed and state.get("capture_active") == "0"
        )
        if resuming:
            self.db.execute(
                "INSERT OR IGNORE INTO lexical_baseline_pending SELECT path FROM lexical_notes"
            )
        if previous == policy:
            if row and row[0] != policy:
                self.db.execute("UPDATE lexical_meta SET value=? WHERE key='policy'", (policy,))
            return resuming
        if previous is not None:
            self.db.execute(
                "INSERT OR REPLACE INTO lexical_event_archive "
                "SELECT ?, path, bin_start, previous_at, observed_at, terms_json, "
                "revisions_json, evidence_hash FROM lexical_events",
                (previous,),
            )
        self._restore = True
        self.db.execute("DELETE FROM lexical_notes")
        self.db.execute("DELETE FROM lexical_terms")
        self.db.execute("DELETE FROM lexical_presence_terms")
        self._presence_writer = None
        self.db.execute("DELETE FROM word_burst_cache")
        self.db.execute("DELETE FROM word_burst_work")
        self.db.execute(
            "INSERT INTO lexical_meta(key, value) VALUES ('policy', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (policy,),
        )
        return True

    def pause(self) -> None:
        """Stop indexing without deleting observations or advancing their baseline."""
        self.db.executemany(
            "INSERT INTO lexical_meta(key, value) VALUES (?, '0') "
            "ON CONFLICT(key) DO UPDATE SET value='0'",
            [("index_active",), ("capture_active",)],
        )

    def sync_note(self, note: Note) -> None:
        """Capture one processed note and positive additions since its last observation."""
        if not self.options.enabled:
            return
        now = self.observed_at.astimezone(UTC).isoformat()
        old = self.db.execute(
            "SELECT raw_hash, counts_json, observed_at, presence FROM lexical_notes WHERE path = ?",
            (note.path,),
        ).fetchone()
        raw_hash = _digest(note.content)
        needs_baseline = (
            self.db.execute(
                "SELECT 1 FROM lexical_baseline_pending WHERE path=?", (note.path,)
            ).fetchone()
            is not None
        )
        if old and old[0] == raw_hash and not needs_baseline:
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
        elif (declared := declared_creation_day(note.path, note.content)) is not None:
            cohort, provenance = declared.isoformat(), "declared_date"
        watermark = self.db.execute(
            "SELECT value FROM lexical_meta WHERE key = 'last_sync_at'"
        ).fetchone()
        previous_at = max(str(old[2]) if old else "", str(watermark[0]) if watermark else "") or now
        # Clock regressions must not create backdated events or move the baseline backwards.
        clock_regressed = now < previous_at
        now = max(now, previous_at)
        additions = counts - Counter(json.loads(old[1])) if old else Counter()
        presence = (
            old[3] if old and old[1] == encoded and old[3] is not None else self._presence(counts)
        )
        self.db.execute(
            "INSERT INTO lexical_notes "
            "(path, raw_hash, body_hash, cohort_day, provenance, counts_json, "
            "observed_at, presence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(path) DO UPDATE SET raw_hash=excluded.raw_hash, "
            "body_hash=excluded.body_hash, cohort_day=excluded.cohort_day, "
            "provenance=excluded.provenance, counts_json=excluded.counts_json, "
            "observed_at=excluded.observed_at, presence=excluded.presence",
            (
                note.path,
                raw_hash,
                body_hash,
                cohort,
                provenance,
                encoded,
                now,
                presence,
            ),
        )
        # JSON updates invalidate any old projection, including direct SQL writes.
        # Restore our freshly constructed projection within this same transaction.
        self.db.execute(
            "UPDATE lexical_notes SET presence=? WHERE path=? AND presence IS NULL",
            (presence, note.path),
        )
        if self._restore or old is None:
            self.db.execute(
                "INSERT OR REPLACE INTO lexical_events "
                "(path, bin_start, previous_at, observed_at, terms_json, "
                "revisions_json, evidence_hash) "
                "SELECT path, bin_start, previous_at, observed_at, terms_json, revisions_json, "
                "evidence_hash FROM lexical_event_archive WHERE policy=? AND path=?",
                (self._policy, note.path),
            )
            self.db.execute(
                "DELETE FROM lexical_event_archive WHERE policy=? AND path=?",
                (self._policy, note.path),
            )
        self.changed += bool(not old or old[1] != encoded)
        # First discovery bootstraps. Later new sources are newly observed text,
        # including imports; their original writing date remains unknown.
        newly_seen = (
            self._capture
            and old is None
            and self.db.execute(
                "SELECT 1 FROM _lexical_new_sources WHERE path=?", (note.path,)
            ).fetchone()
            is not None
        )
        if newly_seen and self._capture:
            additions = counts
        self.db.execute("DELETE FROM lexical_baseline_pending WHERE path=?", (note.path,))
        if self._capture and not needs_baseline and not clock_regressed and additions:
            bin_start = week_start(datetime.fromisoformat(now).date()).isoformat()
            event = self.db.execute(
                "SELECT terms_json, revisions_json, previous_at FROM lexical_events "
                "WHERE path=? AND bin_start=?",
                (note.path, bin_start),
            ).fetchone()
            terms = set(json.loads(event[0])) if event else set()
            terms.update(additions)
            revisions = list(json.loads(event[1])) if event else []
            revisions.append(_digest((str(old[1]) if old else "newly_observed:") + encoded))
            evidence = _digest(json.dumps(revisions, separators=(",", ":")))
            presence = self._presence(terms)
            self.db.execute(
                "INSERT INTO lexical_events "
                "(path, bin_start, previous_at, observed_at, terms_json, revisions_json, "
                "evidence_hash, presence) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(path, bin_start) DO UPDATE SET observed_at=excluded.observed_at, "
                "terms_json=excluded.terms_json, revisions_json=excluded.revisions_json, "
                "evidence_hash=excluded.evidence_hash, presence=excluded.presence",
                (
                    note.path,
                    bin_start,
                    event[2] if event else previous_at,
                    now,
                    json.dumps(sorted(terms)),
                    json.dumps(revisions),
                    evidence,
                    presence,
                ),
            )
            self.db.execute(
                "UPDATE lexical_events SET presence=? "
                "WHERE path=? AND bin_start=? AND presence IS NULL",
                (presence, note.path, bin_start),
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
        self.db.executemany(
            "INSERT INTO lexical_meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            [("index_active", "1"), ("capture_active", str(int(self.options.capture_observed)))],
        )
