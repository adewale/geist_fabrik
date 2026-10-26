"""Verification must certify the declared graph and detect tool-induced drift."""

import os
import subprocess
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_project_core_dependencies_are_represented_in_the_lock() -> None:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    project = tomllib.loads((REPO / "pyproject.toml").read_text())
    locked = tomllib.loads((REPO / "uv.lock").read_text())
    packages = {canonicalize_name(package["name"]): package for package in locked["package"]}
    root = packages[canonicalize_name(project["project"]["name"])]
    edges = {canonicalize_name(edge["name"]) for edge in root["dependencies"]}
    requirements = root["metadata"]["requires-dist"]
    for dependency in project["project"]["dependencies"]:
        required = Requirement(dependency)
        name = canonicalize_name(required.name)
        assert name in packages and name in edges, f"Unrepresented core dependency: {dependency}"
        assert any(
            canonicalize_name(item["name"]) == name
            and (
                Requirement(item["name"] + item.get("specifier", "")).specifier
                == required.specifier
            )
            for item in requirements
        ), f"Stale dependency requirement: {dependency}"


def test_validator_rejects_a_dependency_tool_rewriting_its_input(tmp_path: Path) -> None:
    script = REPO / "scripts" / "validate.sh"
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    (tmp_path / "uv.lock").write_text("original locked graph\n")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    smoke = scripts / "test_wheel.sh"
    smoke.write_text("#!/usr/bin/env bash\nexit 0\n")
    smoke.chmod(0o755)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    uv = binaries / "uv"
    uv.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = sync ] && [ "${MUTATE_TEST_LOCK:-0}" = 1 ]; then\n'
        "  printf 'changed graph\\n' >> uv.lock\n"
        "fi\nexit 0\n"
    )
    uv.chmod(0o755)
    go = binaries / "go"
    go.write_text("#!/usr/bin/env bash\nexit 0\n")
    go.chmod(0o755)
    environment = {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"]}
    control = subprocess.run(
        ["bash", str(script)],
        cwd=tmp_path,
        env={**environment, "MUTATE_TEST_LOCK": "0"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert control.returncode == 0, control.stdout + control.stderr
    mutated = subprocess.run(
        ["bash", str(script)],
        cwd=tmp_path,
        env={**environment, "MUTATE_TEST_LOCK": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert mutated.returncode != 0
    assert "Dependency lock unchanged failed" in mutated.stdout
