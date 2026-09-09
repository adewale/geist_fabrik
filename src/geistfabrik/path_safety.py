"""Portable containment checks for vault-managed paths."""

from pathlib import Path


class PathSafetyError(ValueError):
    """Raised when a path escapes its intended root or uses a managed symlink."""


def ensure_contained(
    path: Path,
    root: Path,
    *,
    must_exist: bool = False,
    reject_symlinks: bool = False,
) -> Path:
    """Resolve *path* and require it to remain under *root*.

    ``reject_symlinks`` additionally rejects every existing component between
    the root and path. This is used for configuration, plugins, databases, and
    managed writes where provenance must remain unambiguous.
    """
    lexical = path.absolute()
    resolved_root = root.resolve(strict=True)
    try:
        relative = lexical.relative_to(root.absolute())
    except ValueError as exc:
        raise PathSafetyError(f"Path is outside vault: {lexical}") from exc

    if reject_symlinks:
        current = root.absolute()
        if current.is_symlink():
            raise PathSafetyError(f"Managed root must not be a symlink: {current}")
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise PathSafetyError(f"Managed path must not contain symlinks: {current}")
            if not current.exists():
                break

    try:
        resolved = lexical.resolve(strict=must_exist)
    except (FileNotFoundError, RuntimeError) as exc:
        raise PathSafetyError(f"Cannot safely resolve path: {lexical}: {exc}") from exc
    if not resolved.is_relative_to(resolved_root):
        raise PathSafetyError(f"Path escapes vault: {lexical} -> {resolved}")
    return resolved
