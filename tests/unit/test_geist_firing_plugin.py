"""Tests for the opt-in geist firing gate (tests/plugins/geist_firing.py).

Inner pytest runs are in-process (``pytester.runpytest``) and use fake geist
names (alpha, beta, gamma) under a temporary directory, so they can never be
mistaken for bundled geists by an outer ``--require-geist-firing`` session.
"""

import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from geistfabrik.models import Suggestion
from geistfabrik.tracery import TraceryGeist
from tests.plugins import geist_firing
from tests.plugins.geist_firing import GeistFiringRecorder, evaluate

pytest_plugins = ("pytester",)


def _record(recorder: GeistFiringRecorder, run: Callable[[], object]) -> dict[str, str]:
    recorder.install()
    try:
        run()
    finally:
        recorder.uninstall()
    return recorder.fired


def test_construction_inside_a_geist_file_is_attributed(tmp_path: Path) -> None:
    code_dir = tmp_path / "code"
    recorder = GeistFiringRecorder(code_dir, tmp_path / "tracery")
    source = "def suggest():\n    return [Suggestion(text='t', notes=[], geist_id='x')]\n"
    namespace: dict[str, object] = {"Suggestion": Suggestion}
    exec(compile(source, str(code_dir / "alpha.py"), "exec"), namespace)  # noqa: S102

    suggest = cast(Callable[[], object], namespace["suggest"])
    fired = _record(recorder, suggest)

    assert set(fired) == {"alpha"}  # attributed by file, not by the geist_id argument


def test_direct_construction_in_a_test_is_not_attributed(tmp_path: Path) -> None:
    recorder = GeistFiringRecorder(tmp_path / "code", tmp_path / "tracery")

    fired = _record(recorder, lambda: Suggestion(text="t", notes=[], geist_id="alpha"))

    assert fired == {}


def test_tracery_attribution_requires_a_bundled_yaml_path(tmp_path: Path) -> None:
    tracery_dir = tmp_path / "tracery"
    recorder = GeistFiringRecorder(tmp_path / "code", tracery_dir)
    bundled = TraceryGeist(
        "gamma", {"origin": ["a bundled line"]}, 1, 0, tracery_dir / "gamma.yaml"
    )
    user = TraceryGeist("delta", {"origin": ["a user line"]}, 1, 0, tmp_path / "delta.yaml")

    def run() -> None:
        assert len(bundled.suggest(MagicMock())) == 1
        assert len(user.suggest(MagicMock())) == 1

    assert set(_record(recorder, run)) == {"gamma"}


def test_uninstall_restores_the_original_constructor(tmp_path: Path) -> None:
    before = Suggestion.__init__
    recorder = GeistFiringRecorder(tmp_path / "code", tmp_path / "tracery")
    recorder.install()
    assert Suggestion.__init__ is not before
    recorder.uninstall()
    assert Suggestion.__init__ is before


def test_evaluate_reports_missing_and_stale_entries() -> None:
    missing, stale = evaluate(
        expected={"alpha", "beta", "gamma", "delta"},
        fired={"alpha", "gamma"},
        allowlist={"gamma": "reason", "delta": "reason", "gone": "reason"},
    )
    assert missing == ["beta"]
    assert stale == ["gamma: allowlisted but it fired", "gone: not bundled"]


def test_allowlist_entries_name_bundled_geists_with_reasons() -> None:
    bundled = geist_firing.bundled_geists()
    assert set(geist_firing.ALLOWLIST) <= bundled
    assert all(len(reason) > 20 for reason in geist_firing.ALLOWLIST.values())


_FAKE_GATE_CONFTEST = """
from pathlib import Path

from tests.plugins.geist_firing import GeistFiringPlugin, GeistFiringRecorder

ROOT = Path(__file__).parent / "fake_geists"


def pytest_configure(config):
    recorder = GeistFiringRecorder(ROOT / "code", ROOT / "tracery")
    recorder.install()
    plugin = GeistFiringPlugin(
        recorder, expected=lambda: {{"alpha", "beta", "gamma"}}, allowlist={allowlist}
    )
    config.pluginmanager.register(plugin, "fake-geist-firing-gate")
"""

_FAKE_GATE_TESTS = """
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

from geistfabrik.models import Suggestion
from geistfabrik.tracery import TraceryGeist

ROOT = Path(__file__).parent / "fake_geists"


def test_alpha_loaded_by_file_path_like_the_executor():
    spec = importlib.util.spec_from_file_location("fresh_alpha", ROOT / "code" / "alpha.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert len(module.suggest(None)) == 1


def test_beta_is_only_constructed_directly():
    assert Suggestion(text="t", notes=[], geist_id="beta").geist_id == "beta"


def test_gamma_tracery():
    geist = TraceryGeist("gamma", {"origin": ["line"]}, 1, 0, ROOT / "tracery" / "gamma.yaml")
    assert len(geist.suggest(MagicMock())) == 1
"""


def _fake_project(pytester: pytest.Pytester, allowlist: str) -> None:
    code = pytester.path / "fake_geists" / "code"
    code.mkdir(parents=True)
    (pytester.path / "fake_geists" / "tracery").mkdir()
    (code / "alpha.py").write_text(
        textwrap.dedent(
            """
            from geistfabrik.models import Suggestion

            def suggest(vault):
                return [Suggestion(text="a", notes=[], geist_id="alpha")]
            """
        )
    )
    pytester.makeconftest(_FAKE_GATE_CONFTEST.format(allowlist=allowlist))
    pytester.makepyfile(test_fake=_FAKE_GATE_TESTS)


def test_gate_fails_a_green_run_when_a_geist_never_fired(pytester: pytest.Pytester) -> None:
    _fake_project(pytester, allowlist="{}")

    result = pytester.runpytest("-p", "no:cacheprovider")

    result.assert_outcomes(passed=3)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(["*1 bundled geist(s) never produced a Suggestion:", "  - beta"])
    assert "  - alpha" not in result.stdout.str()
    assert "  - gamma" not in result.stdout.str()


def test_gate_passes_with_a_reasoned_allowlist(pytester: pytest.Pytester) -> None:
    _fake_project(pytester, allowlist='{"beta": "only constructed directly in this demo"}')

    result = pytester.runpytest("-p", "no:cacheprovider")

    assert result.ret == pytest.ExitCode.OK
    result.stdout.fnmatch_lines(["*geist firing gate passed: 2 bundled geists*"])


def test_gate_fails_on_a_stale_allowlist_entry(pytester: pytest.Pytester) -> None:
    _fake_project(pytester, allowlist='{"beta": "demo", "alpha": "but alpha fires"}')

    result = pytester.runpytest("-p", "no:cacheprovider")

    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(["*alpha: allowlisted but it fired"])


def test_real_flag_reports_every_unexercised_bundled_geist(pytester: pytest.Pytester) -> None:
    """A partial run with the real flag lists the geists it did not exercise."""
    pytester.makepyfile(test_nothing="def test_nothing():\n    assert 1 + 1 == 2\n")

    flagged = pytester.runpytest("-p", "tests.plugins.geist_firing", geist_firing.OPTION)
    unflagged = pytester.runpytest("-p", "tests.plugins.geist_firing")

    expected_missing = sorted(geist_firing.bundled_geists() - set(geist_firing.ALLOWLIST))
    assert expected_missing  # the bundled set is non-empty
    assert flagged.ret == pytest.ExitCode.TESTS_FAILED
    flagged.stdout.fnmatch_lines([f"  - {geist}" for geist in expected_missing])
    assert unflagged.ret == pytest.ExitCode.OK
    assert "geist firing gate" not in unflagged.stdout.str()
