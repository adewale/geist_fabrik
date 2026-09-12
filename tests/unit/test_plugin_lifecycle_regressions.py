"""Regression contracts for plugin ownership, imports, and diagnostic loading."""

import pickle
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from geistfabrik.cli import create_parser
from geistfabrik.commands.batch_runner import TestAllCommand as BatchCommand
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry, vault_function
from geistfabrik.geist_executor import GeistExecutor
from geistfabrik.metadata_system import MetadataLoader
from geistfabrik.tracery import TraceryGeistLoader


def test_registries_can_coexist_without_registering_builtins_globally() -> None:
    @vault_function("host_function")
    def host_function(vault: Any) -> str:
        return "host"

    first = FunctionRegistry()
    second = FunctionRegistry()
    assert first.has_function("sample_notes")
    assert second.has_function("sample_notes")
    assert first.functions["host_function"] is host_function
    assert second.functions["host_function"] is host_function
    assert _GLOBAL_REGISTRY == {"host_function": host_function}
    first.register("only_first", host_function)
    assert not second.has_function("only_first")


def test_plugin_decorators_belong_to_the_loading_vault(tmp_path: Path) -> None:
    registries = []
    for name in ("first", "second"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "functions.py").write_text(
            "from geistfabrik import vault_function\n"
            "@vault_function('local_function')\n"
            f"def local_function(vault): return {name!r}\n"
        )
        registry = FunctionRegistry(directory)
        registry.load_modules()
        registries.append(registry)
    assert [registry.functions["local_function"](None) for registry in registries] == [
        "first",
        "second",
    ]
    assert not FunctionRegistry().has_function("local_function")
    assert "local_function" not in _GLOBAL_REGISTRY


def test_failed_plugin_import_discards_partial_decorators(tmp_path: Path) -> None:
    (tmp_path / "a_broken.py").write_text(
        "from geistfabrik import vault_function\n"
        "@vault_function('partial')\n"
        "def partial(vault): return 'wrong'\n"
        "raise RuntimeError('broken import')\n"
    )
    (tmp_path / "b_good.py").write_text(
        "from geistfabrik import vault_function\n"
        "@vault_function('partial')\n"
        "def partial(vault): return 'healthy'\n"
    )
    registry = FunctionRegistry(tmp_path)
    registry.load_modules()
    assert registry.functions["partial"](None) == "healthy"
    assert "partial" not in _GLOBAL_REGISTRY
    assert not any(
        key.startswith("_vaultfunc_") and key.endswith("_a_broken") for key in sys.modules
    )


@pytest.mark.parametrize("kind", ["code", "metadata", "function"])
def test_plugin_module_identity_supports_annotated_dataclasses(tmp_path: Path, kind: str) -> None:
    source = (
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "import sys\n"
        "assert sys.modules[__name__].__dict__ is globals()\n"
        "@dataclass\n"
        "class Options:\n"
        "    value: int = 7\n"
        "assert Options().value == 7\n"
    )
    if kind == "code":
        source += "def suggest(vault): return []\n"
    elif kind == "metadata":
        source += "def infer(note, vault): return {'value': Options().value}\n"
    else:
        source += (
            "from geistfabrik import vault_function\n"
            "@vault_function('annotated')\n"
            "def annotated(vault): return Options().value\n"
        )
    (tmp_path / "annotated.py").write_text(source)
    if kind == "code":
        executor = GeistExecutor(tmp_path)
        executor.load_geists()
        assert "annotated" in executor.geists, executor.get_execution_log()
        assert executor.geists["annotated"].func(cast(Any, None)) == []
    elif kind == "metadata":
        loader = MetadataLoader(tmp_path)
        loader.load_modules()
        assert "annotated" in loader.modules
        assert loader.modules["annotated"](cast(Any, None), cast(Any, None)) == {"value": 7}
    else:
        registry = FunctionRegistry(tmp_path)
        registry.load_modules()
        assert registry.functions["annotated"](None) == 7


@pytest.mark.parametrize("kind", ["code", "metadata", "function"])
def test_live_loaders_keep_distinct_picklable_module_identities(
    tmp_path: Path, kind: str
) -> None:
    """Same-named plugins in different vaults must not replace one another."""
    exports: list[Any] = []
    for label in ("first", "second"):
        directory = tmp_path / label
        directory.mkdir()
        if kind == "code":
            source = f"TOKEN = {label!r}\ndef suggest(vault): return [TOKEN]\n"
        elif kind == "metadata":
            source = f"TOKEN = {label!r}\ndef infer(note, vault): return {{'token': TOKEN}}\n"
        else:
            source = (
                f"TOKEN = {label!r}\n"
                "from geistfabrik import vault_function\n"
                "@vault_function('shared')\n"
                "def shared(vault): return TOKEN\n"
            )
        (directory / "shared.py").write_text(source)

        if kind == "code":
            executor = GeistExecutor(directory)
            executor.load_geists()
            export = executor.geists["shared"].func
        elif kind == "metadata":
            loader = MetadataLoader(directory)
            loader.load_modules()
            export = loader.modules["shared"]
        else:
            registry = FunctionRegistry(directory)
            registry.load_modules()
            export = registry.functions["shared"]
        exports.append(export)

    assert exports[0].__module__ != exports[1].__module__
    for export in exports:
        function = export
        assert sys.modules[function.__module__].__dict__ is function.__globals__
        pickle.dumps(function)


@pytest.mark.parametrize("kind", ["code", "metadata"])
@pytest.mark.parametrize("failure", ["interrupt", "export_lookup"])
def test_failed_plugin_load_always_restores_sys_modules(
    tmp_path: Path, kind: str, failure: str
) -> None:
    """Interruptions and hostile export lookup must not leave half-loaded modules."""
    plugin = tmp_path / "broken.py"
    if failure == "interrupt":
        plugin.write_text("raise KeyboardInterrupt('stop')\n")
        expected_error: type[BaseException] = KeyboardInterrupt
    else:
        export = "suggest" if kind == "code" else "infer"
        plugin.write_text(
            "def __getattr__(name):\n"
            f"    if name == {export!r}:\n"
            "        raise RuntimeError('hostile export lookup')\n"
            "    raise AttributeError(name)\n"
        )
        expected_error = RuntimeError

    if kind == "code":
        code_loader = GeistExecutor(tmp_path)
        key = f"_geistfabrik_geist_{code_loader._module_namespace}_broken"
        with pytest.raises(expected_error):
            code_loader._load_geist(plugin)
    else:
        metadata_loader = MetadataLoader(tmp_path)
        key = f"_metadata_{metadata_loader._module_namespace}_broken"
        with pytest.raises(expected_error):
            metadata_loader._load_module("broken", plugin)

    assert key not in sys.modules


@pytest.mark.parametrize("include_healthy", [False, True])
def test_test_all_counts_code_and_tracery_load_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, include_healthy: bool
) -> None:
    from geistfabrik.commands import batch_runner

    code_dir = tmp_path / "_geistfabrik/geists/code"
    tracery_dir = tmp_path / "_geistfabrik/geists/tracery"
    code_dir.mkdir(parents=True)
    tracery_dir.mkdir(parents=True)
    (code_dir / "broken_code.py").write_text("def invalid syntax\n")
    (tracery_dir / "broken_yaml.yaml").write_text("tracery: [\n")
    if include_healthy:
        (code_dir / "healthy.py").write_text("def suggest(vault): return []\n")

    def code_loader(*args, **kwargs):
        kwargs["default_geists_dir"] = None
        return GeistExecutor(*args, **kwargs)

    def tracery_loader(*args, **kwargs):
        kwargs["default_geists_dir"] = None
        return TraceryGeistLoader(*args, **kwargs)

    monkeypatch.setattr(batch_runner, "GeistExecutor", code_loader)
    monkeypatch.setattr(batch_runner, "TraceryGeistLoader", tracery_loader)
    command = BatchCommand(create_parser().parse_args(["test-all", str(tmp_path)]))
    assert command.run() == 1
    output = capsys.readouterr().out
    assert f"Total: {2 + int(include_healthy)} geists" in output
    assert "Errors: 2" in output
    assert "broken_code" in output
    assert "broken_yaml" in output
    assert "Load failed:" in output


def test_tracery_loader_reports_and_resets_configured_load_errors(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("tracery: [\n")
    loader = TraceryGeistLoader(tmp_path, enabled_defaults={"broken": True})
    assert loader.load_all()[0] == []
    assert loader.load_errors[0]["geist_id"] == "broken"
    assert loader.load_errors[0]["path"] == str(path)
    path.write_text("type: geist-tracery\nid: broken\ntracery:\n  origin: healthy\n")
    assert len(loader.load_all()[0]) == 1
    assert loader.load_errors == []
