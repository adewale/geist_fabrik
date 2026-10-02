"""Tests for the opt-in geist firing gate (tests/plugins/geist_firing.py).

Inner pytest runs are in-process (``pytester.runpytest``) and use fake geist
names (alpha, beta, gamma) under a temporary directory, so they can never be
mistaken for bundled geists by an outer ``--require-geist-firing`` session.
"""

from collections.abc import Callable
from pathlib import Path
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


_ALPHA_SOURCE = """
from geistfabrik.models import Suggestion

def _build(text):
    return Suggestion(text=text, notes=[], geist_id="x")

def suggest(vault=None):
    return [_build("via suggest")]
"""


def _load_alpha(code_dir: Path) -> dict[str, Callable[..., object]]:
    namespace: dict[str, Callable[..., object]] = {}
    exec(compile(_ALPHA_SOURCE, str(code_dir / "alpha.py"), "exec"), namespace)  # noqa: S102
    return namespace


def test_construction_under_a_geists_suggest_is_attributed(tmp_path: Path) -> None:
    code_dir = tmp_path / "code"
    recorder = GeistFiringRecorder(code_dir, tmp_path / "tracery")
    alpha = _load_alpha(code_dir)

    fired = _record(recorder, alpha["suggest"])

    assert set(fired) == {"alpha"}  # by file and entry point, not by the geist_id argument


def test_calling_a_geists_private_helper_directly_is_not_attributed(tmp_path: Path) -> None:
    code_dir = tmp_path / "code"
    recorder = GeistFiringRecorder(code_dir, tmp_path / "tracery")
    alpha = _load_alpha(code_dir)

    fired = _record(recorder, lambda: alpha["_build"]("helper only"))

    assert fired == {}


def test_direct_construction_in_a_test_is_not_attributed(tmp_path: Path) -> None:
    recorder = GeistFiringRecorder(tmp_path / "code", tmp_path / "tracery")

    fired = _record(recorder, lambda: Suggestion(text="t", notes=[], geist_id="alpha"))

    assert fired == {}


def _tracery_yaml(path: Path, geist_id: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"type: geist-tracery\nid: {geist_id}\ntracery:\n  origin: ['a line']\n",
        encoding="utf-8",
    )
    return path


def test_tracery_credit_requires_the_bundled_yaml_loaded_under_its_own_id(
    tmp_path: Path,
) -> None:
    tracery_dir = tmp_path / "tracery"
    recorder = GeistFiringRecorder(tmp_path / "code", tracery_dir)
    gamma_yaml = _tracery_yaml(tracery_dir / "gamma.yaml", "gamma")
    renamed_yaml = _tracery_yaml(tracery_dir / "epsilon.yaml", "zeta")  # id != file stem
    user_yaml = _tracery_yaml(tmp_path / "user" / "delta.yaml", "delta")

    def run() -> None:
        geists = [
            TraceryGeist.from_yaml(gamma_yaml, seed=0),
            TraceryGeist.from_yaml(renamed_yaml, seed=0),
            TraceryGeist.from_yaml(user_yaml, seed=0),
            # A hand-built grammar that only borrows a bundled yaml_path.
            TraceryGeist("epsilon", {"origin": ["custom"]}, 1, 0, renamed_yaml),
            TraceryGeist("gamma", {"origin": ["custom"]}, 1, 0, gamma_yaml),
        ]
        assert [len(geist.suggest(MagicMock())) for geist in geists] == [1, 1, 1, 1, 1]

    assert set(_record(recorder, run)) == {"gamma"}


def test_custom_grammar_with_a_bundled_yaml_path_alone_is_not_attributed(
    tmp_path: Path,
) -> None:
    tracery_dir = tmp_path / "tracery"
    recorder = GeistFiringRecorder(tmp_path / "code", tracery_dir)
    gamma_yaml = _tracery_yaml(tracery_dir / "gamma.yaml", "gamma")
    custom = TraceryGeist("gamma", {"origin": ["custom"]}, 1, 0, gamma_yaml)

    fired = _record(recorder, lambda: custom.suggest(MagicMock()))

    assert fired == {}


def test_uninstall_restores_the_original_constructor_and_loader(tmp_path: Path) -> None:
    before_init = Suggestion.__dict__["__init__"]
    before_from_yaml = TraceryGeist.__dict__["from_yaml"]
    recorder = GeistFiringRecorder(tmp_path / "code", tmp_path / "tracery")
    recorder.install()
    assert Suggestion.__dict__["__init__"] is not before_init
    assert TraceryGeist.__dict__["from_yaml"] is not before_from_yaml
    recorder.uninstall()
    assert Suggestion.__dict__["__init__"] is before_init
    assert TraceryGeist.__dict__["from_yaml"] is before_from_yaml


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


def _alpha():
    spec = importlib.util.spec_from_file_location("fresh_alpha", ROOT / "code" / "alpha.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alpha_loaded_by_file_path_like_the_executor():
    assert len(_alpha().suggest(None)) == 1


def test_beta_is_only_constructed_directly():
    assert Suggestion(text="t", notes=[], geist_id="beta").geist_id == "beta"


def test_gamma_tracery():
    geist = TraceryGeist.from_yaml(ROOT / "tracery" / "gamma.yaml", seed=0)
    assert len(geist.suggest(MagicMock())) == 1
"""

# Every way a test can build a geist-shaped Suggestion without the geist firing.
_NO_CREDIT_TESTS = """
from pathlib import Path
from unittest.mock import MagicMock

from geistfabrik.tracery import TraceryGeist

from test_fake import _alpha

ROOT = Path(__file__).parent / "fake_geists"


def test_alpha_private_helper_called_directly():
    assert _alpha()._build("helper").text == "helper"


def test_custom_grammar_borrowing_gammas_yaml_path():
    custom = TraceryGeist("gamma", {"origin": ["custom"]}, 1, 0, ROOT / "tracery" / "gamma.yaml")
    assert len(custom.suggest(MagicMock())) == 1
"""


def _fake_project(pytester: pytest.Pytester, allowlist: str, tests: str = _FAKE_GATE_TESTS) -> None:
    code = pytester.path / "fake_geists" / "code"
    code.mkdir(parents=True)
    (code / "alpha.py").write_text(_ALPHA_SOURCE)
    _tracery_yaml(pytester.path / "fake_geists" / "tracery" / "gamma.yaml", "gamma")
    pytester.makeconftest(_FAKE_GATE_CONFTEST.format(allowlist=allowlist))
    pytester.makepyfile(test_fake=_FAKE_GATE_TESTS)
    if tests is not _FAKE_GATE_TESTS:
        pytester.makepyfile(test_other=tests)


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


def test_gate_gives_no_credit_for_helpers_or_borrowed_yaml_paths(
    pytester: pytest.Pytester,
) -> None:
    _fake_project(pytester, allowlist="{}", tests=_NO_CREDIT_TESTS)

    result = pytester.runpytest("-p", "no:cacheprovider", "test_other.py")

    result.assert_outcomes(passed=2)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(
        ["*3 bundled geist(s) never produced a Suggestion:", "  - alpha", "  - beta", "  - gamma"]
    )


def test_gate_is_skipped_when_the_run_is_interrupted(pytester: pytest.Pytester) -> None:
    _fake_project(pytester, allowlist="{}")
    pytester.makepyfile(test_stop="import pytest\n\ndef test_stop():\n    pytest.exit('stop')\n")

    result = pytester.runpytest("-p", "no:cacheprovider", "test_stop.py")

    assert result.ret == pytest.ExitCode.INTERRUPTED
    result.stdout.fnmatch_lines(["geist firing gate skipped: the run was interrupted"])
    assert "never produced a Suggestion" not in result.stdout.str()


def test_gate_leaves_a_non_ok_exit_status_unchanged(pytester: pytest.Pytester) -> None:
    _fake_project(pytester, allowlist="{}")

    result = pytester.runpytest("-p", "no:cacheprovider", "-k", "no_such_test")

    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED  # not rewritten to TESTS_FAILED
    result.stdout.fnmatch_lines(["*3 bundled geist(s) never produced a Suggestion:"])


def test_unconfigure_restores_the_hooks_after_a_real_flagged_run(
    pytester: pytest.Pytester,
) -> None:
    before_init = Suggestion.__dict__["__init__"]
    before_from_yaml = TraceryGeist.__dict__["from_yaml"]
    pytester.makepyfile(
        # In-process run: the object id of the pre-run constructor is stable.
        test_probe=(
            "from geistfabrik.models import Suggestion\n\n"
            "def test_probe():\n"
            f"    assert id(Suggestion.__dict__['__init__']) != {id(before_init)}\n"
        )
    )

    result = pytester.runpytest("-p", "tests.plugins.geist_firing", geist_firing.OPTION)

    result.assert_outcomes(passed=1)  # the hook was live during the run
    assert Suggestion.__dict__["__init__"] is before_init
    assert TraceryGeist.__dict__["from_yaml"] is before_from_yaml


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
