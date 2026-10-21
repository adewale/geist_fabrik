"""Shared source boundaries for idea generation and emitted citations.

Template files are still parsed, indexed and embedded by the raw Vault. They
are scaffolding rather than ideas, so the execution context and final boundary
filter leave them out. Lexical-analysis exclusions remain a separate policy.
"""

import posixpath
from collections.abc import Iterable
from dataclasses import dataclass

from .models import NoteLinkIndex, _normalise_vault_path


def _normalise_source(path: str) -> str:
    """Canonical vault-relative spelling; case remains significant."""
    return posixpath.normpath(_normalise_vault_path(path))


@dataclass(frozen=True)
class SourceEligibility:
    """Case-sensitive folder/prefix boundaries, including root Templates/.

    Configured prefixes retain filtering.boundary.exclude_paths semantics:
    ``Private/`` excludes that folder; ``Private`` also excludes a filename
    such as ``Private ideas.md``. Neither patterns nor lexical exclusions are
    inferred here. Slash direction and redundant path segments are normalized.
    """

    exclude_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        prefixes = []
        for path in ("Templates/", *self.exclude_paths):
            normalised = _normalise_source(path) if path else ""
            if _normalise_vault_path(path).endswith("/"):
                normalised += "/"
            prefixes.append(normalised)
        object.__setattr__(self, "exclude_paths", tuple(prefixes))

    def allows(self, path: str, source_file: str | None = None) -> bool:
        """Check a note's identity and the physical file behind virtual notes."""
        for identity in (path, source_file):
            if identity is None:
                continue
            normalised = _normalise_source(identity)
            if (
                normalised.startswith(("/", "../"))
                or normalised == ".."
                or normalised.startswith(self.exclude_paths)
            ):
                return False
        return True

    def references_allowed(
        self,
        index: NoteLinkIndex,
        targets: Iterable[str],
        source_path: str | None = None,
    ) -> bool:
        """Fail closed on missing references or any excluded alias identity.

        Keep raw matches as well as normalized path matches: a literal title
        may contain a path-like spelling, and must not hide an excluded note.
        """
        for target in targets:
            matches = set(index.matching_paths(target))
            matches.update(index.candidates(target, source_path))
            reference = _normalise_vault_path(target.split("|", 1)[0].strip())
            filename, separator, fragment = reference.partition("#")
            normalised = _normalise_source(filename) if filename else ""
            matches.update(index.matching_paths(normalised + separator + fragment))
            if not matches or any(not self.allows(path, index.sources[path]) for path in matches):
                return False
        return True
