"""Offset-preserving visible topic prose, using CommonMark's syntax ownership.

The returned string is a mask of the original source, not rendered Markdown.
Characters are never inserted, deleted, moved, or decoded. Block boundaries are
reported separately because an empty line has no spare character in which to
place a sentence separator without changing the original newline coordinates.
"""

import re
import unicodedata
from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from html.parser import HTMLParser
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.rules_inline import StateInline, image, link
from markdown_it.rules_inline.backticks import backtick
from markdown_it.rules_inline.html_inline import html_inline
from markdown_it.token import Token

from .markdown_parser import iter_wikilinks, parse_frontmatter

_SECTION_LABELS = frozenset(
    {
        "notes",
        "references",
        "contents",
        "features",
        "to-do",
        "readme",
        "related",
        "introduction",
        "background",
        "methods",
        "results",
        "discussion",
        "summary",
    }
)
MAX_COMMENT_REPARSES = 32

_NON_PROSE = frozenset({"code", "pre", "script", "style", "head", "title", "template", "textarea"})
_VOID_HTML = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


def _key(label: str) -> str:
    return " ".join(unicodedata.normalize("NFC", label).casefold().split())


def _erase(chars: list[str], start: int, end: int, *, barrier: bool = True) -> None:
    first = True
    for position in range(start, end):
        if chars[position] not in "\r\n":
            chars[position] = "." if first and barrier else " "
            first = False


def _line_offsets(source: str) -> list[int]:
    return [0, *(position + 1 for position, char in enumerate(source) if char == "\n")]


def _block_span(token: Token, offsets: list[int], length: int) -> tuple[int, int]:
    assert token.map is not None
    start, end = token.map
    return offsets[start], offsets[end] if end < len(offsets) else length


def _source_map(token: Token, source: str, offsets: list[int]) -> list[int | None]:
    """Map an inline token inside its physical source lines, never a global search.

    CommonMark strips heading/list/quote prefixes. Its inline token content is
    otherwise source text. A partially consumed indentation tab can introduce
    synthetic leading spaces; those spaces have no source character and remain
    unmapped. Unmappable lines abstain rather than borrowing another occurrence.
    """
    assert token.map is not None
    mapping: list[int | None] = []
    pieces = token.content.split("\n")
    for index, piece in enumerate(pieces):
        number = token.map[0] + index
        if number >= len(offsets):
            mapping.extend([None] * len(piece))
            if index + 1 < len(pieces):
                mapping.append(None)
            continue
        start = offsets[number]
        end = offsets[number + 1] if number + 1 < len(offsets) else len(source)
        line = source[start:end].rstrip("\r\n")
        relative = line.find(piece)
        leading = 0
        if relative < 0:
            leading = len(piece) - len(piece.lstrip(" "))
            relative = line.find(piece[leading:])
        if relative < 0:
            mapping.extend([None] * len(piece))
        else:
            mapping.extend([None] * leading)
            mapping.extend(start + relative + i for i in range(len(piece) - leading))
        if index + 1 < len(pieces):
            newline = end - 1 if end > start and source[end - 1] == "\n" else None
            mapping.append(newline)
    return mapping


def _mapped_span(mapping: list[int | None], start: int, end: int) -> tuple[int, int] | None:
    positions = [position for position in mapping[start:end] if position is not None]
    return (min(positions), max(positions) + 1) if positions else None


def _inline_regions(
    source: str, environment: dict[str, Any]
) -> tuple[
    list[tuple[int, int]], list[tuple[int, int]], list[tuple[int, int]], list[tuple[int, int]]
]:
    """Return masked spans and syntactic-owner spans in one exact inline source."""
    parser = MarkdownIt("commonmark", {"html": True, "store_labels": True})
    masked: list[tuple[int, int]] = []
    owners: list[tuple[int, int]] = []
    html_tags: list[tuple[int, int]] = []
    barriers: list[tuple[int, int]] = []
    wiki_spans = {match.start(): match for match in iter_wikilinks(source)}

    def wiki(state: StateInline, silent: bool) -> bool:
        if silent or state.src != source:
            return False
        match = wiki_spans.get(state.pos)
        if match is None:
            return False
        if match[1]:
            masked.append(match.span())
            owners.append(match.span())
            barriers.append(match.span())
        else:
            group = 3 if match[3] is not None else 2
            syntax = ((match.start(), match.start(group)), (match.end(group), match.end()))
            masked.extend(syntax)
            owners.extend(syntax)
        state.push("text", "", 0).content = match[0]
        state.pos = match.end()
        return True

    def capture_link(state: StateInline, silent: bool) -> bool:
        if state.src[state.pos] != "[":
            return False
        start = state.pos
        label_end = state.md.helpers.parseLinkLabel(state, start, True)
        if not link(state, silent):
            return False
        if not silent and state.src == source:
            syntax = ((start, start + 1), (label_end, state.pos))
            owners.extend(syntax)
            masked.extend(syntax)
        return True

    def capture_image(state: StateInline, silent: bool) -> bool:
        start = state.pos
        if not image(state, silent):
            return False
        if not silent and state.src == source:
            masked.append((start, state.pos))
            owners.append((start, state.pos))
            barriers.append((start, state.pos))
        return True

    def code(state: StateInline, silent: bool) -> bool:
        start, before = state.pos, len(state.tokens)
        if not backtick(state, silent):
            return False
        if (
            not silent
            and state.src == source
            and len(state.tokens) > before
            and state.tokens[-1].type == "code_inline"
        ):
            masked.append((start, state.pos))
            owners.append((start, state.pos))
            barriers.append((start, state.pos))
        return True

    def html(state: StateInline, silent: bool) -> bool:
        start = state.pos
        if not html_inline(state, silent):
            return False
        if not silent and state.src == source:
            owners.append((start, state.pos))
            html_tags.append((start, state.pos))
        return True

    parser.inline.ruler.before("link", "topic_wiki", wiki)
    parser.inline.ruler.at("link", capture_link)
    parser.inline.ruler.at("image", capture_image)
    parser.inline.ruler.at("backticks", code)
    parser.inline.ruler.at("html_inline", html)
    parser.inline.parse(source, parser, environment, [])
    return masked, owners, html_tags, barriers


class _HTMLRegions(HTMLParser):
    """Track HTML source spans without rendering or changing their coordinates."""

    def __init__(self, source: str, properties: list[tuple[int, int]] | None = None):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.offsets = _line_offsets(source)
        self.regions: list[tuple[int, int]] = []
        self.stack: list[tuple[str, bool]] = []
        self.properties = properties or []
        self.property_starts = [start for start, _ in self.properties]
        self.active_property: int | None = None
        self.property_stack: list[str] = []
        self.property_raw_text: str | None = None

    def _position(self) -> int:
        line, column = self.getpos()
        return self.offsets[line - 1] + column

    def _markup(self, raw: str) -> None:
        start = self._position()
        self.regions.append((start, start + len(raw)))

    def _property_index(self) -> int | None:
        position = self._position()
        index = bisect_right(self.property_starts, position) - 1
        current = index if index >= 0 and position < self.properties[index][1] else None
        if current != self.active_property:
            self.property_stack.clear()
            self.active_property = current
        return current

    def set_cdata_mode(self, elem: str, **kwargs: Any) -> None:
        if self._property_index() is not None:
            self.property_raw_text = elem
        super().set_cdata_mode(elem, **kwargs)

    def finish_property(self) -> None:
        """End property-local raw text before feeding any later document text."""
        if self.property_raw_text is not None:
            # Unclosed local raw text may remain buffered. Flush only whitespace
            # with identical coordinates, rather than parsing its apparent tags.
            self.rawdata = "".join(char if char in "\r\n" else " " for char in self.rawdata)
            self.clear_cdata_mode()
            self.property_raw_text = None
            self.feed("")
        self.property_stack.clear()
        self.active_property = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._markup(self.get_starttag_text() or "")
        if self._property_index() is not None:
            # Property-created nesting has paragraph-local lifetime. It can
            # consume its own closers, but cannot own later document text.
            if tag not in _VOID_HTML:
                self.property_stack.append(tag)
            if tag in {"title", "textarea"}:
                self.set_cdata_mode(tag)
            return
        attributes = dict(attrs)
        hidden = (
            tag in _NON_PROSE
            or "hidden" in attributes
            or (attributes.get("aria-hidden") or "").casefold() == "true"
        )
        if tag not in _VOID_HTML:
            self.stack.append((tag, hidden))
        if tag in {"title", "textarea"}:
            self.set_cdata_mode(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # In HTML, a slash does not close non-void elements such as script/div.
        self.handle_starttag(tag, attrs)
        if tag in self.CDATA_CONTENT_ELEMENTS:
            # Match HTMLParser's normal start-tag raw-text handling too: apparent
            # parent closing tags inside script/style cannot close hidden owners.
            self.set_cdata_mode(tag)

    def handle_endtag(self, tag: str) -> None:
        start = self._position()
        end = self.source.find(">", start)
        self.regions.append((start, end + 1 if end >= 0 else len(self.source)))
        if self._property_index() is not None:
            if self.property_raw_text == tag:
                self.property_raw_text = None
            for index in range(len(self.property_stack) - 1, -1, -1):
                if self.property_stack[index] == tag:
                    del self.property_stack[index:]
                    return
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if any(hidden for _, hidden in self.stack):
            self._markup(data)

    def handle_comment(self, data: str) -> None:
        self._markup("<!--" + data + "-->")

    def handle_decl(self, decl: str) -> None:
        self._markup("<!" + decl + ">")

    def handle_pi(self, data: str) -> None:
        self._markup("<?" + data + ">")

    def handle_entityref(self, name: str) -> None:
        # Decoding would fabricate a source spelling. Do not extract entity names.
        self._markup("&" + name + ";")

    def handle_charref(self, name: str) -> None:
        self._markup("&#" + name + ";")


def _html_regions(source: str) -> list[tuple[int, int]]:
    parser = _HTMLRegions(source)
    parser.feed(source)
    parser.close()
    return parser.regions


def _parse(source: str) -> tuple[list[Token], dict[str, Any]]:
    parser = MarkdownIt("commonmark", {"html": True, "inline_definitions": True})
    parser.core.ruler.disable(["inline"])
    environment: dict[str, Any] = {}
    return parser.parse(source, environment), environment


_PROPERTY_LINE = re.compile(r"[ \t]*\w[\w -]*::(?:[ \t]+[^\r\n]*|[ \t]*)\r?")


def _syntax_ownership(
    source: str, tokens: list[Token], environment: dict[str, Any]
) -> tuple[list[tuple[int, int]], list[tuple[int, int]], list[tuple[int, int]]]:
    """Resolve property paragraphs and HTML in source order after Markdown.

    A property-only paragraph is structural metadata. Its value cannot open HTML
    outside the paragraph, but an earlier hidden HTML element still owns closing
    syntax inside it. Preserve raw coordinates while feeding those owners in order.
    """
    offsets = _line_offsets(source)
    admitted = [char if char in "\r\n" else " " for char in source]
    owners: list[tuple[int, int]] = []
    properties: list[tuple[int, int]] = []
    html_openers: set[int] = set()
    heading = False
    for token in tokens:
        if token.type == "heading_open":
            heading = True
        elif token.type == "heading_close":
            heading = False
        if token.map is None:
            continue
        block = _block_span(token, offsets, len(source))
        if token.type in {"fence", "code_block", "definition"}:
            owners.append(block)
            continue
        if token.type not in {"inline", "html_block"}:
            continue
        mapping = _source_map(token, source, offsets)
        for position in mapping:
            if position is not None:
                admitted[position] = source[position]
        if token.type == "inline":
            masked, syntax, tags, _ = _inline_regions(token.content, environment)
            for start, end in masked:
                if (span := _mapped_span(mapping, start, end)) is not None:
                    _erase(admitted, *span, barrier=False)
            owners.extend(
                span
                for start, end in syntax
                if (span := _mapped_span(mapping, start, end)) is not None
            )
            for start, end in tags:
                html_openers.update(
                    position
                    for position in mapping[start:end]
                    if position is not None and source[position] == "<"
                )
            lines = token.content.splitlines()
            if not heading and lines and all(_PROPERTY_LINE.fullmatch(line) for line in lines):
                properties.append(block)
        else:
            if token.content.startswith("<!--"):
                owners.append(block)
            html_openers.update(
                position for position in mapping if position is not None and source[position] == "<"
            )
    for position, char in enumerate(admitted):
        if char == "<" and position not in html_openers:
            admitted[position] = " "
    html_source = "".join(admitted)
    metadata = sorted(properties)
    parser = _HTMLRegions(html_source, metadata)
    cursor = 0
    for start, end in metadata:
        parser.feed(html_source[cursor:start])
        parser.feed(html_source[start:end])
        parser.finish_property()
        cursor = end
    parser.feed(html_source[cursor:])
    parser.close()
    return metadata, parser.regions, owners


def _percent_comments(chars: list[str]) -> None:
    """Respect earlier syntax owners, batching simple comments in each parse.

    A comment containing structural syntax can invalidate later parser ownership.
    Reparse only in that case, with an explicit work bound instead of quadratic
    full-note scans or silent truncation on hostile inputs.
    """
    cursor = 0
    reparses = 0
    while True:
        source = "".join(chars)
        if "%%" not in source[cursor:]:
            return
        reparses += 1
        if reparses > MAX_COMMENT_REPARSES:
            raise ValueError("topic comment preprocessing exceeds work limit")
        tokens, environment = _parse(source)
        metadata, html_regions, owners = _syntax_ownership(source, tokens, environment)
        protected = metadata + html_regions + owners
        merged: list[tuple[int, int]] = []
        for start, end in sorted(protected):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        owner = 0
        while True:
            start = source.find("%%", cursor)
            if start < 0:
                return
            while owner < len(merged) and merged[owner][1] <= start:
                owner += 1
            if owner < len(merged) and merged[owner][0] <= start:
                cursor = merged[owner][1]
                continue
            closing = source.find("%%", start + 2)
            end = closing + 2 if closing >= 0 else len(source)
            _erase(chars, start, end)
            cursor = end
            if re.search(r"[`~<\[\r\n]", source[start:end]):
                break  # Structural owners may change; parse the masked suffix again.


@dataclass(frozen=True)
class _Projection:
    prose: str
    headings: tuple[tuple[int, int], ...]
    boundaries: tuple[int, ...]
    generic_section_spans: tuple[tuple[int, int], ...]


@lru_cache(maxsize=8)
def _projection(content: str) -> _Projection:
    _, body = parse_frontmatter(content)
    frontmatter_end = len(content) - len(body)
    chars = list(content)
    _erase(chars, 0, frontmatter_end)
    _percent_comments(chars)
    source = "".join(chars)
    tokens, environment = _parse(source)
    offsets = _line_offsets(source)
    output = [char if char in "\r\n" else " " for char in content]
    headings: list[tuple[int, int]] = []
    generic_section_spans: list[tuple[int, int]] = []
    boundaries: set[int] = set()
    html_openers: set[int] = set()
    h1 = False
    heading = False
    for token in tokens:
        if token.type == "heading_open":
            h1 = token.tag == "h1"
            heading = True
            continue
        if token.type == "heading_close":
            h1 = heading = False
            continue
        if token.type not in {"inline", "html_block"} or token.map is None:
            continue
        if token.type == "html_block" and token.content.startswith("<!--"):
            continue  # Includes unclosed CommonMark comment blocks.
        mapping = _source_map(token, source, offsets)
        block = _mapped_span(mapping, 0, len(mapping))
        if block is None:
            h1 = heading = False
            continue
        boundaries.update(block)
        for position in mapping:
            if position is not None:
                output[position] = chars[position]
        if token.type == "inline":
            masked, _, tags, barriers = _inline_regions(token.content, environment)
            for start, end in tags:
                span = _mapped_span(mapping, start, end)
                if span is not None:
                    html_openers.add(span[0])
            for start, end in masked:
                span = _mapped_span(mapping, start, end)
                if span is not None:
                    _erase(output, *span, barrier=False)
            for start, end in barriers:
                span = _mapped_span(mapping, start, end)
                if span is not None:
                    _erase(output, *span)
                    boundaries.update(span)
            if h1:
                headings.append(block)
            # Generic section names are a fallible source-role hint, separate
            # from syntax-owned non-prose. Preserve the existing projection.
            name = re.sub(r"^\d+[.)]?\s+", "", token.content.strip())
            if heading and _key(name) in _SECTION_LABELS:
                generic_section_spans.append(block)
                _erase(output, *block)
        else:
            html_openers.update(
                position for position in mapping if position is not None and source[position] == "<"
            )
        h1 = heading = False
    # HTML sees only source admitted by Markdown. Tags in code/comment masks
    # cannot open or close a hidden-element region.
    html_source = list(output)
    for position, char in enumerate(html_source):
        if char == "<" and position not in html_openers:
            html_source[position] = " "
    role_hard_exclusions: list[tuple[int, int]] = []
    if "::" in source or html_openers or any(token.type == "html_block" for token in tokens):
        metadata, html_regions, _ = _syntax_ownership(source, tokens, environment)
        role_hard_exclusions.extend(metadata)
        for start, end in metadata:
            _erase(output, start, end)
    else:
        html_regions = _html_regions("".join(html_source))
    for start, end in html_regions:
        _erase(output, start, min(end, len(output)))
    for pattern in (
        re.compile(r"(?:https?://|www\.)[^\s<>]+", re.IGNORECASE),
        re.compile(r"(?<!\S)#[\w/-]+"),
    ):
        for match in pattern.finditer("".join(output)):
            _erase(output, match.start(), match.end())
    for match in re.finditer(r"[#*_~>|\[\]]", "".join(output)):
        _erase(output, match.start(), match.end(), barrier=False)
    # A Markdown heading can still be owned by HTML opened in an earlier
    # block. Hard ownership wins without changing the existing prose mask.
    role_hard_exclusions.extend(html_regions)
    hard_ranges = sorted(role_hard_exclusions)
    owner = 0
    visible_section_spans: list[tuple[int, int]] = []
    for start, end in sorted(generic_section_spans):
        while owner < len(hard_ranges) and hard_ranges[owner][1] <= start:
            owner += 1
        if owner < len(hard_ranges) and hard_ranges[owner][0] < end:
            continue
        visible_section_spans.append((start, end))
    return _Projection(
        "".join(output), tuple(headings), tuple(sorted(boundaries)), tuple(visible_section_spans)
    )


def topic_prose(content: str) -> str:
    """Return visible source characters at their original offsets and newlines."""
    return _projection(content).prose


def topic_boundaries(content: str) -> tuple[int, ...]:
    """Block edges a source-grounded candidate must not cross."""
    return _projection(content).boundaries


def topic_role_exclusions(content: str) -> tuple[tuple[int, int], ...]:
    """Original ranges masked by the fallible generic-section-name heuristic.

    These are visible heading labels judged unlikely to be personal subjects,
    not syntax-owned code or metadata. Reporting them does not change the
    existing topic prose projection or candidate eligibility.
    """
    return _projection(content).generic_section_spans


def explicit_labels(content: str, prose: str) -> Iterator[tuple[str, int, int, str]]:
    """Seed the first visible primary heading and observed wikilink display words."""
    for start, end in _projection(content).headings:
        segment = prose[start:end]
        label = segment.strip()
        if not label or not any(character.isalpha() for character in label):
            continue
        if _key(label) not in _SECTION_LABELS and 1 <= len(label.split()) <= 5:
            left = start + len(segment) - len(segment.lstrip())
            yield label, left, left + len(label), "heading"
        break  # Later headings cannot displace the authored primary subject.
    for match in iter_wikilinks(content):
        if match[1]:
            continue
        start, end = match.span(3 if match[3] is not None else 2)
        segment = prose[start:end]
        label = segment.strip()
        if 1 <= len(label.split()) <= 3:
            left = start + len(segment) - len(segment.lstrip())
            yield label, left, left + len(label), "wikilink"
