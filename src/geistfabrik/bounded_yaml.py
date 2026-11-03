"""Resource-bounded YAML loading for configuration, frontmatter, and Tracery."""

from pathlib import Path
from typing import Any

import yaml
from yaml.nodes import Node

MAX_YAML_BYTES = 1024 * 1024
MAX_YAML_NODES = 20_000
MAX_YAML_DEPTH = 100


class BoundedYAMLError(ValueError):
    """Raised when YAML is invalid or exceeds a resource limit."""


class _BoundedSafeLoader(yaml.SafeLoader):
    """Enforce quotas while composing, before constructing Python values."""

    def __init__(self, text: str, source: str):
        super().__init__(text)
        self.source = source
        self.node_count = 0
        self.collection_depth = 0

    def compose_node(self, parent: Node | None, index: Any) -> Node:
        if self.check_event(yaml.events.AliasEvent):  # type: ignore[no-untyped-call]
            raise BoundedYAMLError(f"YAML aliases are not permitted: {self.source}")
        self.node_count += 1
        if self.node_count > MAX_YAML_NODES:
            raise BoundedYAMLError(f"YAML node count exceeds {MAX_YAML_NODES}: {self.source}")
        collection = self.check_event(  # type: ignore[no-untyped-call]
            yaml.events.MappingStartEvent, yaml.events.SequenceStartEvent
        )
        self.collection_depth += int(collection)
        try:
            if self.collection_depth > MAX_YAML_DEPTH:
                raise BoundedYAMLError(f"YAML nesting exceeds {MAX_YAML_DEPTH}: {self.source}")
            node = super().compose_node(parent, index)
            assert node is not None
            return node
        finally:
            self.collection_depth -= int(collection)


def load_bounded_yaml_text(text: str, source: str = "<yaml>") -> Any:
    """Safely parse YAML text with byte, alias, node, and depth bounds."""
    if len(text.encode("utf-8")) > MAX_YAML_BYTES:
        raise BoundedYAMLError(f"YAML input exceeds {MAX_YAML_BYTES} bytes: {source}")
    try:
        loader = _BoundedSafeLoader(text, source)
        try:
            return loader.get_single_data()
        finally:
            loader.dispose()  # type: ignore[no-untyped-call]
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
