"""Behavioural contract for the tag-release path in .github/workflows/test.yml.

"Release the bytes you tested" (LESSONS_LEARNED.md): a tag build must publish
exactly the wheel and sdist that the package-smoke job built and smoke-tested.

These tests parse the workflow and dry-run its shell steps in a temporary
workspace instead of matching literal YAML lines. The earlier string test was
re-edited in lockstep with both release-day fixes (fd0444c: artifacts under a
hidden directory were not uploaded; 4033806: a wildcard directory in the upload
path nested the files, so the release job found no dist/*.whl) and caught
neither. Both bugs fail the dry run below.

Artifact upload/download is modelled on the documented actions/upload-artifact
behaviour (https://github.com/actions/upload-artifact#upload-an-entire-directory):
hidden files are excluded unless include-hidden-files is true, and the path
hierarchy is preserved below the first wildcard (or below a literal directory).
Syntax and expression errors are covered by actionlint in CI.
"""

import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
TEST_WORKFLOW = ROOT / ".github" / "workflows" / "test.yml"
RELEASE_ARTIFACT = "release-artifacts"
WILDCARDS = frozenset("*?[")


def _load(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    # YAML 1.1 parses the bare key `on` as boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    return triggers


def _uses(step: dict[str, Any], action: str) -> bool:
    return str(step.get("uses", "")).split("@", 1)[0] == action


def _version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _is_hidden(relative: Path) -> bool:
    return any(part.startswith(".") and part not in {".", ".."} for part in relative.parts)


def upload_layout(workspace: Path, path_spec: str, include_hidden: bool = False) -> dict[str, Path]:
    """Artifact-relative name -> source file, per actions/upload-artifact."""
    roots: list[Path] = []
    files: list[Path] = []
    for pattern in (line.strip() for line in path_spec.splitlines()):
        if not pattern or pattern.startswith("!"):
            continue
        parts = Path(pattern).parts
        first_glob = next((i for i, part in enumerate(parts) if WILDCARDS & set(part)), len(parts))
        if first_glob < len(parts):
            roots.append(workspace.joinpath(*parts[:first_glob]))
            matches = [Path(p) for p in workspace.glob(pattern)]
        else:
            literal = workspace / pattern
            roots.append(literal if literal.is_dir() else literal.parent)
            matches = [literal]
        for match in matches:
            candidates = [p for p in match.rglob("*")] if match.is_dir() else [match]
            files.extend(p for p in candidates if p.is_file())
    if not include_hidden:
        files = [f for f in files if not _is_hidden(f.relative_to(workspace))]
    if not files:
        return {}
    root = Path(os.path.commonpath([str(r) for r in roots]))
    return {f.relative_to(root).as_posix(): f for f in files}


def _run(script: str, cwd: Path, env: dict[str, str]) -> None:
    assert "${{" not in script, f"dry run cannot evaluate expressions in: {script}"
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", script],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"step failed:\n{script}\n{result.stdout}{result.stderr}"


def _require_release_runner_tools() -> None:
    missing = [tool for tool in ("bash", "sha256sum") if shutil.which(tool) is None]
    if missing:
        if sys.platform.startswith("linux"):
            pytest.fail(f"release dry run needs {missing}; the release job runs on Linux")
        pytest.skip(f"release job runs on ubuntu-latest; {missing} missing on {sys.platform}")


# --- Invariants over every workflow ---------------------------------------


@pytest.mark.parametrize("workflow_path", WORKFLOWS, ids=lambda p: p.name)
def test_artifact_uploads_do_not_depend_on_hidden_paths(workflow_path: Path) -> None:
    """upload-artifact silently drops hidden files unless told otherwise (fd0444c)."""
    for job_id, job in _load(workflow_path)["jobs"].items():
        for step in job.get("steps", []):
            if not _uses(step, "actions/upload-artifact"):
                continue
            options = step.get("with", {})
            if options.get("include-hidden-files") is True:
                continue
            for pattern in str(options.get("path", "")).splitlines():
                relative = Path(pattern.strip().replace("${{ github.workspace }}/", ""))
                assert not _is_hidden(relative), (
                    f"{workflow_path.name} job {job_id!r} uploads hidden path {pattern!r}"
                )


# --- The tag-release path -------------------------------------------------


def test_tag_pushes_trigger_a_release_gated_on_every_other_job() -> None:
    workflow = _load(TEST_WORKFLOW)
    assert "v*" in _triggers(workflow)["push"]["tags"]
    jobs = workflow["jobs"]
    release = jobs["release"]
    assert "startsWith(github.ref, 'refs/tags/v')" in release["if"]
    assert set(release["needs"]) == set(jobs) - {"release"}, (
        "the release job must wait for every other job in the workflow"
    )


def test_release_publishes_exactly_the_smoke_tested_bytes(tmp_path: Path) -> None:
    """Dry-run: smoke output -> staging -> upload -> download -> verify -> checksum -> publish."""
    _require_release_runner_tools()
    jobs = _load(TEST_WORKFLOW)["jobs"]
    version = _version()
    wheel_name = f"geistfabrik-{version}-py3-none-any.whl"
    sdist_name = f"geistfabrik-{version}.tar.gz"

    # 1. Lay out what scripts/test_wheel.sh leaves in PACKAGE_SMOKE_WORKDIR:
    #    run.XXXXXX/dist holds the tested artifacts; rebuilt/ holds a decoy wheel
    #    rebuilt from the sdist, which must never be published.
    smoke_ws = tmp_path / "smoke"
    smoke_steps = jobs["package-smoke"]["steps"]
    smoke_step = next(s for s in smoke_steps if "scripts/test_wheel.sh" in s.get("run", ""))
    workdir_spec = smoke_step["env"]["PACKAGE_SMOKE_WORKDIR"]
    workdir = Path(workdir_spec.replace("${{ github.workspace }}", str(smoke_ws)))
    run_dir = workdir / "run.Ab12Cd"
    tested = {wheel_name: b"tested wheel bytes", sdist_name: b"tested sdist bytes"}
    (run_dir / "dist").mkdir(parents=True)
    (run_dir / "rebuilt").mkdir()
    for name, payload in tested.items():
        (run_dir / "dist" / name).write_bytes(payload)
    (run_dir / "rebuilt" / wheel_name).write_bytes(b"rebuilt decoy wheel")

    # 2. Run the tag-only staging steps of package-smoke, as written.
    env = {**os.environ, "GITHUB_REF_NAME": f"v{version}", "GITHUB_WORKSPACE": str(smoke_ws)}
    upload = None
    for step in smoke_steps:
        if "refs/tags/v" not in str(step.get("if", "")):
            continue
        if "run" in step:
            _run(step["run"], smoke_ws, env)
        elif _uses(step, "actions/upload-artifact") and step["with"]["name"] == RELEASE_ARTIFACT:
            upload = step["with"]
    assert upload is not None, f"package-smoke never uploads {RELEASE_ARTIFACT!r} on tags"
    assert upload.get("if-no-files-found") == "error"
    artifact = upload_layout(
        smoke_ws, str(upload["path"]), upload.get("include-hidden-files", False)
    )
    assert artifact, f"{RELEASE_ARTIFACT!r} upload matches no files"

    # 3. Download into the release job's workspace exactly as the step asks.
    release_ws = tmp_path / "release"
    release_steps = jobs["release"]["steps"]
    download = next(s["with"] for s in release_steps if _uses(s, "actions/download-artifact"))
    assert download["name"] == RELEASE_ARTIFACT
    for name, source in artifact.items():
        target = release_ws / download["path"] / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (release_ws / "scripts").symlink_to(ROOT / "scripts")
    shim = tmp_path / "bin"
    shim.mkdir()
    (shim / "python").symlink_to(sys.executable)
    release_env = {**env, "PATH": f"{shim}{os.pathsep}{env['PATH']}"}

    # 4. Run every release shell step except the network publish, as written.
    publish = None
    for step in release_steps:
        if "run" not in step:
            continue
        if "gh release create" in step["run"]:
            publish = step["run"]
            continue
        cwd = release_ws / step.get("working-directory", ".")
        _run(step["run"], cwd, release_env)
    assert publish is not None

    # 5. What `gh release create` would upload: the tested bytes plus checksums.
    asset_globs = [arg for arg in shlex.split(publish) if WILDCARDS & set(arg)]
    published = {p.name: p for g in asset_globs for p in release_ws.glob(g)}
    assert set(published) == {wheel_name, sdist_name, "SHA256SUMS"}
    for name, payload in tested.items():
        assert published[name].read_bytes() == payload
    checksums = {
        name: digest
        for digest, name in (
            line.split() for line in published["SHA256SUMS"].read_text().splitlines()
        )
    }
    assert checksums == {name: hashlib.sha256(p).hexdigest() for name, p in tested.items()}


def test_upload_model_reproduces_both_release_day_bugs(tmp_path: Path) -> None:
    """Teeth: the pre-fix upload paths yield no files, or a nested layout."""
    for run_root in (tmp_path / ".package-smoke", tmp_path / "package-smoke-work"):
        (run_root / "run.Ab12Cd" / "dist").mkdir(parents=True)
        (run_root / "run.Ab12Cd" / "dist" / "geistfabrik-1.0.0.tar.gz").write_bytes(b"x")

    # fd0444c: hidden work directory -> nothing uploaded.
    assert upload_layout(tmp_path, ".package-smoke/run.*/dist/*") == {}
    # 4033806: wildcard directory -> hierarchy below it is kept, so the release
    # job's dist/*.tar.gz glob finds nothing.
    assert list(upload_layout(tmp_path, "package-smoke-work/run.*/dist/*")) == [
        "run.Ab12Cd/dist/geistfabrik-1.0.0.tar.gz"
    ]
    # The staged, flat layout the workflow now uses.
    (tmp_path / "release-dist").mkdir()
    (tmp_path / "release-dist" / "geistfabrik-1.0.0.tar.gz").write_bytes(b"x")
    assert list(upload_layout(tmp_path, "release-dist/*")) == ["geistfabrik-1.0.0.tar.gz"]
