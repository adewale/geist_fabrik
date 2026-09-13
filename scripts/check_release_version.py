#!/usr/bin/env python3
"""Fail a release when its tag, source versions, or artifact names disagree."""

from __future__ import annotations

import argparse
import ast
import sys
import tomllib
from pathlib import Path


def _package_version(init_path: Path) -> str:
    module = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    for statement in module.body:
        if not isinstance(statement, ast.Assign):
            continue
        is_version_assignment = any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        )
        if not is_version_assignment:
            continue
        if isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            return statement.value.value
    raise ValueError(f"Could not find a literal __version__ in {init_path}")


def check_release(tag: str, root: Path, artifact_dir: Path | None = None) -> list[str]:
    """Return release contract violations, or an empty list when consistent."""
    with (root / "pyproject.toml").open("rb") as handle:
        project_version = str(tomllib.load(handle)["project"]["version"])
    package_version = _package_version(root / "src" / "geistfabrik" / "__init__.py")
    expected_tag = f"v{project_version}"

    errors: list[str] = []
    if tag != expected_tag:
        errors.append(f"tag {tag!r} does not match project version {expected_tag!r}")
    if package_version != project_version:
        errors.append(
            f"package __version__ {package_version!r} does not match "
            f"project version {project_version!r}"
        )
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{project_version}]" not in changelog:
        errors.append(f"CHANGELOG.md has no release section for {project_version!r}")

    if artifact_dir is not None:
        prefix = f"geistfabrik-{project_version}"
        wheels = sorted(artifact_dir.glob("*.whl"))
        sdists = sorted(artifact_dir.glob("*.tar.gz"))
        if len(wheels) != 1:
            errors.append(f"expected exactly one wheel in {artifact_dir}, found {len(wheels)}")
        if len(sdists) != 1:
            errors.append(f"expected exactly one sdist in {artifact_dir}, found {len(sdists)}")
        for wheel in wheels:
            if not wheel.name.startswith(f"{prefix}-"):
                errors.append(
                    f"artifact {wheel.name!r} does not carry project version {project_version!r}"
                )
        for sdist in sdists:
            if sdist.name != f"{prefix}.tar.gz":
                errors.append(
                    f"artifact {sdist.name!r} does not carry project version {project_version!r}"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="release tag, including the v prefix")
    parser.add_argument(
        "--artifact-dir", type=Path, help="directory containing the tested wheel and sdist"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    errors = check_release(args.tag, root, args.artifact_dir)
    if errors:
        for error in errors:
            print(f"release check failed: {error}", file=sys.stderr)
        return 1
    print(f"Release contract verified for {args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
