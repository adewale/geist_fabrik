"""HTML prose for lexical counting and excerpts, without rendering or executing it."""

import re
from collections.abc import Iterator
from html.parser import HTMLParser

from markdown_it.common.html_blocks import block_names
from markdown_it.common.html_re import HTML_TAG_RE

_BLOCKS = frozenset(block_names) | {"br"}
_NON_PROSE = frozenset({"code", "pre", "script", "style", "head", "title", "template"})
_TAG_NAME = re.compile(r"[a-zA-Z][a-zA-Z0-9-]*\Z")
# Use CommonMark's tag grammar with an explicit source offset instead of ^.
_HTML_TAG = re.compile(HTML_TAG_RE.pattern.removeprefix("^"))


def _tag_spans(source: str) -> Iterator[tuple[int, int]]:
    """Yield complete CommonMark HTML tokens without retrying inside attributes."""
    cursor = 0
    while (start := source.find("<", cursor)) >= 0:
        match = _HTML_TAG.match(source, start)
        cursor = match.end() if match else start + 1
        if match:
            yield start, cursor


class HTMLProse(HTMLParser):
    """Discard tag syntax; keep physical line and non-prose boundaries.

    HTMLParser owns quoted attributes, raw script/style text and entity decoding.
    CSS and browser layout are not interpreted. Inline formatting keeps visible
    adjacency; block elements and removed code interrupt word/phrase regions.
    """

    def __init__(self, source: str, include_quotes: bool) -> None:
        super().__init__(convert_charrefs=True)
        # Only complete CommonMark tokens are markup. Incomplete '<tag attr="'
        # remains literal data and cannot consume unrelated paragraphs at EOF.
        pieces: list[str] = []
        cursor = 0
        for start, end in _tag_spans(source):
            pieces.extend((source[cursor:start].replace("<", "&lt;"), source[start:end]))
            cursor = end
        pieces.append(source[cursor:].replace("<", "&lt;"))
        source = "".join(pieces)
        self.source = source
        self.lines = source.split("\n")
        self.parts: list[str] = []
        self.hidden: list[str] = []
        self.data_allowed = True
        self.non_prose = _NON_PROSE | ({"blockquote"} if not include_quotes else set())
        self.line_offsets = [0]
        self.line_offsets.extend(i + 1 for i, char in enumerate(source) if char == "\n")

    @property
    def in_markup(self) -> bool:
        """An eligible opening owns its pending syntax and hidden closing tag.

        HTMLParser retains incomplete lexemes in rawdata. All literal '<' was
        escaped above, so a buffered lexeme is actual complete-token syntax,
        possibly split across physical lines, rather than an arbitrary fragment.
        """
        return bool(self.hidden or self.rawdata)

    def feed_line(self, number: int, *, allowed: bool, data_allowed: bool) -> None:
        """Feed one physical line; excluded openings cannot activate HTML state."""
        self.data_allowed = data_allowed
        self.feed((self.lines[number - 1] if allowed else "\x00") + "\n")

    def prose(self) -> str:
        self.close()
        return "".join(self.parts)

    def _raw_tag(self) -> str:
        line, column = self.getpos()
        start = self.line_offsets[line - 1] + column
        end = self.source.find(">", start)
        return self.source[start : end + 1] if end >= start else ""

    def _boundary(self, raw: str, *, block: bool) -> None:
        self.parts.append(("\x00" if block or "\x00" in raw else "") + "\n" * raw.count("\n"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or ""
        if not _TAG_NAME.fullmatch(tag):
            # CommonMark email/URL autolinks are not HTML element names.
            self.handle_data(raw)
            return
        self._boundary(raw, block=tag in _BLOCKS or tag in self.non_prose)
        if tag in self.non_prose:
            self.hidden.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # A self-closing non-prose tag must not hide subsequent prose.
        raw = self.get_starttag_text() or ""
        if not _TAG_NAME.fullmatch(tag):
            self.handle_data(raw)
        else:
            self._boundary(raw, block=tag in _BLOCKS or tag in self.non_prose)

    def handle_endtag(self, tag: str) -> None:
        if not _TAG_NAME.fullmatch(tag):
            self.handle_data(self._raw_tag())
            return
        self._boundary(self._raw_tag(), block=tag in _BLOCKS or tag in self.non_prose)
        if tag in self.hidden:
            # Closing an ancestor also ends malformed nested non-prose content.
            del self.hidden[len(self.hidden) - 1 - self.hidden[::-1].index(tag) :]

    def handle_data(self, data: str) -> None:
        self.parts.append("\n" * data.count("\n") if self.hidden or not self.data_allowed else data)

    def handle_comment(self, data: str) -> None:
        self._boundary(data, block=True)

    def handle_decl(self, decl: str) -> None:
        self._boundary(decl, block=True)

    def handle_pi(self, data: str) -> None:
        self._boundary(data, block=True)

    def unknown_decl(self, data: str) -> None:
        self._boundary(data, block=True)
