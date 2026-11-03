"""Conservative body projection without constructing unused YAML metadata."""

import re
from datetime import date

# --- Frontmatter strip without YAML parsing -------------------------------
#
# parse_frontmatter() runs a full, bounded YAML parse only to decide whether
# the leading "---" block is metadata (stripped) or ordinary Markdown (kept:
# invalid YAML, a non-mapping, or non-string keys). That parse was most of
# the cost for body-only consumers. strip_frontmatter() decides the common
# shapes of real frontmatter -- "key: value" lines, "- item" lists under a
# key, inline [a, b] lists, quoted strings, integers and dates -- with a
# conservative recogniser that only accepts blocks PyYAML is certain to load
# as a string-keyed mapping, and hands anything else to parse_frontmatter()
# itself. The body is therefore always the one parse_frontmatter() returns.

# Every character PyYAML's reader accepts, minus tab and the YAML 1.1 line
# breaks NEL (\x85), LS and PS, and BOM (\ufeff), which complicate scanning.
_YAML_SAFE_CHARS = (
    "\x20-\x7e\xa0-\u2027\u202a-\ud7ff\ue000-\ufefe\uff00-\ufffd\U00010000-\U0010ffff"
)
_SAFE_LINE = re.compile(f"[{_YAML_SAFE_CHARS}]*")
_FM_KEY_LINE = re.compile(r"([A-Za-z_][A-Za-z0-9_-]{0,63}):(?: +(.*?))? *")
_FM_ITEM_LINE = re.compile(r"( *)-(?: +(.*?))? *")
_FM_COMMENT_LINE = re.compile(r" *(?:#.*)?")
# Keys PyYAML would load as booleans or None (no longer string keys).
_FM_NON_STRING_KEYS = frozenset({"yes", "no", "true", "false", "on", "off", "null", "y", "n"})
_FM_INT = re.compile(r"[0-9]{1,30}")
_FM_DATE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_FM_DOUBLE_QUOTED = re.compile(r'"[^"\\]*"')
_FM_SINGLE_QUOTED = re.compile(r"'[^']*'")
_FM_FLOW_ITEM = re.compile(r'(?:[A-Za-z_][A-Za-z0-9_ ./-]*|"[^"\\]*"|\'[^\']*\')')
_FM_MAX_CHARS = 100_000  # far below the loader's 1 MiB bound
_FM_MAX_NODES = 10_000  # half the loader's node bound
_FM_MAX_FLOW_ITEMS = 200
# Every character an int, float or timestamp scalar can contain.
_FM_NUMERIC_CHARS = frozenset("0123456789abcdefABCDEFxXoObB_.:+-eEtTzZ ")


def _plain_text_value(value: str) -> bool:
    """A plain scalar that always loads as a string and never fails to parse.

    It starts with a letter or "_" (never a YAML indicator), or with a digit
    but contains a character no number or timestamp can (as in "0🌲").
    """
    # ": " (or a trailing ":") would start a nested mapping, an error here;
    # " #" starts a comment, so any "#" is left to the full parser.
    if "#" in value or ": " in value or value.endswith(":"):
        return False
    first = value[0]
    if first.isalpha() or first == "_":
        return True
    if "0" <= first <= "9":
        return any(character not in _FM_NUMERIC_CHARS for character in value)
    return False


def _value_nodes(value: str | None) -> int | None:
    """YAML nodes for one value if it is certainly loadable, else None."""
    if value is None or value == "":
        return 1  # null
    if _plain_text_value(value) or _FM_INT.fullmatch(value):
        return 1
    if _FM_DOUBLE_QUOTED.fullmatch(value) or _FM_SINGLE_QUOTED.fullmatch(value):
        return 1
    date_match = _FM_DATE.fullmatch(value)
    if date_match:
        try:
            date(*(int(part) for part in date_match.groups()))
        except ValueError:
            return None  # loader raises on an impossible date; let it
        return 1
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return 1
        items = [item.strip() for item in inner.split(",")]
        if len(items) > _FM_MAX_FLOW_ITEMS:
            return None
        if all(_FM_FLOW_ITEM.fullmatch(item) for item in items):
            return 1 + len(items)
    return None


def _is_simple_mapping(lines: list[str]) -> bool:
    """True only if PyYAML certainly loads these lines as a str-keyed mapping
    (or as nothing at all: blank and comment lines only)."""
    if sum(len(line) + 1 for line in lines) > _FM_MAX_CHARS:
        return False
    nodes = 1
    # None: no key yet; "value": last key had a value; "open": last key had
    # none, so "- item" lines may follow; an int: indent of the current items
    items_state: str | int | None = None
    for raw in lines:
        line = raw[:-1] if raw.endswith("\r") else raw
        if not _SAFE_LINE.fullmatch(line):
            return False
        if _FM_COMMENT_LINE.fullmatch(line):
            continue
        key_match = _FM_KEY_LINE.fullmatch(line)
        if key_match:
            if key_match[1].lower() in _FM_NON_STRING_KEYS:
                return False
            value_nodes = _value_nodes(key_match[2])
            if value_nodes is None:
                return False
            nodes += 1 + value_nodes
            items_state = "value" if key_match[2] else "open"
            continue
        item_match = _FM_ITEM_LINE.fullmatch(line)
        if item_match and items_state is not None and items_state != "value":
            indent = len(item_match[1])
            if items_state == "open":
                items_state = indent
                nodes += 1  # the sequence
            elif items_state != indent:
                return False
            value_nodes = _value_nodes(item_match[2])
            if value_nodes is None:
                return False
            nodes += value_nodes
            continue
        return False
    return nodes <= _FM_MAX_NODES


def strip_frontmatter(content: str) -> str:
    """parse_frontmatter(content)[1], usually without parsing any YAML."""
    if not content.startswith("---"):
        return content
    lines = content.split("\n")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return content
    if _is_simple_mapping(lines[1:end_idx]):
        return "\n".join(lines[end_idx + 1 :])
    # Only the uncommon fallback needs the full parser. Keeping this import
    # here lets models import the projection once without an import cycle.
    from .markdown_parser import parse_frontmatter

    return parse_frontmatter(content)[1]
