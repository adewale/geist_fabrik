"""Resource-bounded YAML loading for configuration, frontmatter, and Tracery."""

from pathlib import Path
from typing import Any

import yaml

MAX_YAML_BYTES = 1024 * 1024
MAX_YAML_NODES = 20_000
MAX_YAML_DEPTH = 100


class BoundedYAMLError(ValueError):
    """Raised when YAML is invalid or exceeds a resource limit."""


def load_bounded_yaml_text(text: str, source: str = "<yaml>") -> Any:
    """Safely parse YAML text with byte, alias, node, and depth bounds."""
    if len(text.encode("utf-8")) > MAX_YAML_BYTES:
        raise BoundedYAMLError(f"YAML input exceeds {MAX_YAML_BYTES} bytes: {source}")
    try:
        depth = 0
        nodes = 0
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            if isinstance(event, yaml.events.AliasEvent):
                raise BoundedYAMLError(f"YAML aliases are not permitted: {source}")
            if isinstance(event, (yaml.events.MappingStartEvent, yaml.events.SequenceStartEvent)):
                depth += 1
                if depth > MAX_YAML_DEPTH:
                    raise BoundedYAMLError(f"YAML nesting exceeds {MAX_YAML_DEPTH}: {source}")
            elif isinstance(event, (yaml.events.MappingEndEvent, yaml.events.SequenceEndEvent)):
                depth -= 1
            if isinstance(
                event,
                (
                    yaml.events.ScalarEvent,
                    yaml.events.MappingStartEvent,
                    yaml.events.SequenceStartEvent,
                ),
            ):
                nodes += 1
                if nodes > MAX_YAML_NODES:
                    raise BoundedYAMLError(f"YAML node count exceeds {MAX_YAML_NODES}: {source}")
        return yaml.safe_load(text)
    except BoundedYAMLError:
        raise
    except yaml.YAMLError as exc:
        raise BoundedYAMLError(f"Invalid YAML in {source}: {exc}") from exc


def load_bounded_yaml(path: Path) -> Any:
    """Read and safely parse a UTF-8 YAML file with resource bounds."""
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_YAML_BYTES + 1)
    except OSError as exc:
        raise BoundedYAMLError(f"Unable to read YAML {path}: {exc}") from exc
    if len(raw) > MAX_YAML_BYTES:
        raise BoundedYAMLError(f"YAML file exceeds {MAX_YAML_BYTES} bytes: {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BoundedYAMLError(f"YAML is not valid UTF-8: {path}: {exc}") from exc
    return load_bounded_yaml_text(text, str(path))
