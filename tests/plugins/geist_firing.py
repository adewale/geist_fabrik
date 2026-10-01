"""Opt-in gate: every bundled geist must produce a Suggestion somewhere in the run.

Why this exists: for months about fifteen bundled geists never produced output
in any test, so every assertion about their output sat in a loop over ``[]``
and the suite could not fail. This plugin makes "the geist actually fired" a
property of the whole unit lane rather than something each test has to
remember to assert.

How attribution works (and why it is done this way):

* ``Suggestion.__init__`` is wrapped for the duration of the session. After a
  Suggestion is successfully constructed, the wrapper walks the calling stack
  and attributes it to the *nearest* frame that is either
  - code whose file lives directly in ``default_geists/code/<geist>.py``, or
  - ``TraceryGeist.suggest`` running a grammar loaded from
    ``default_geists/tracery/<geist>.yaml``.
* Wrapping imported geist modules would not work: ``GeistExecutor`` loads code
  geists by file path, which creates fresh module objects. Every load path,
  though, ends in the one ``Suggestion`` class, and ``co_filename`` of the
  constructing frame is the real source path regardless of how the module was
  imported. So hooking construction covers direct ``module.suggest(vault)``
  calls, executor runs and CLI runs alike.
* A test that writes ``Suggestion(geist_id="columbo", ...)`` itself is *not*
  counted: the constructing frame is the test file, not the geist.

The gate is opt-in (``--require-geist-firing``) because it is only meaningful
when the whole unit lane runs. ``scripts/validate.sh`` and CI enable it on the
unit step. A partial run with the flag will (correctly) report every geist that
the selected tests did not exercise.
"""

from __future__ import annotations

import functools
import os
import sys
from collections.abc import Callable, Generator, Iterable
from pathlib import Path
from types import FrameType
from typing import Any

import pytest

OPTION = "--require-geist-firing"

# Bundled geists allowed to stay silent for the whole unit lane, with a written
# reason each. An entry that fires, or names a geist that no longer exists, is
# reported as stale and fails the gate, so this list can only shrink honestly.
# Every bundled geist currently fires; prefer a designed-to-fire unit test over
# adding an entry.
ALLOWLIST: dict[str, str] = {}


def bundled_geists() -> set[str]:
    """Every bundled geist id (code and Tracery). Looked up lazily per session."""
    from geistfabrik.default_geists import DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS

    return set(DEFAULT_CODE_GEISTS) | set(DEFAULT_TRACERY_GEISTS)


def bundled_dirs() -> tuple[Path, Path]:
    """The real (code, tracery) directories of the installed default geists."""
    import geistfabrik.default_geists as package

    root = Path(os.path.realpath(Path(package.__file__).parent))
    return root / "code", root / "tracery"


class GeistFiringRecorder:
    """Attribute constructed Suggestions to the bundled geist that built them."""

    def __init__(self, code_dir: Path, tracery_dir: Path) -> None:
        from geistfabrik.tracery import TraceryGeist

        self.code_dir = Path(os.path.realpath(code_dir))
        self.tracery_dir = Path(os.path.realpath(tracery_dir))
        self._tracery_suggest_code = TraceryGeist.suggest.__code__
        self._file_cache: dict[str, str | None] = {}
        self.fired: dict[str, str] = {}  # geist id -> first test node id
        self.current_nodeid = "<outside any test>"
        self._original_init: Callable[..., None] | None = None

    def _code_geist_for(self, filename: str) -> str | None:
        if filename not in self._file_cache:
            path = Path(os.path.realpath(filename))
            is_geist = (
                path.parent == self.code_dir and path.suffix == ".py" and path.stem != "__init__"
            )
            self._file_cache[filename] = path.stem if is_geist else None
        return self._file_cache[filename]

    def _tracery_geist_for(self, frame: FrameType) -> str | None:
        yaml_path = getattr(frame.f_locals.get("self"), "yaml_path", None)
        if yaml_path is None:
            return None
        path = Path(os.path.realpath(yaml_path))
        if path.parent == self.tracery_dir and path.suffix == ".yaml":
            return path.stem
        return None

    def attribute(self, frame: FrameType | None) -> str | None:
        """Return the bundled geist owning the nearest relevant frame, if any."""
        while frame is not None:
            code = frame.f_code
            if code is self._tracery_suggest_code:
                return self._tracery_geist_for(frame)
            geist = self._code_geist_for(code.co_filename)
            if geist is not None:
                return geist
            frame = frame.f_back
        return None

    def install(self) -> None:
        from geistfabrik.models import Suggestion

        original: Callable[..., None] = Suggestion.__init__
        recorder = self

        def recording_init(instance: Any, *args: Any, **kwargs: Any) -> None:
            original(instance, *args, **kwargs)
            geist = recorder.attribute(sys._getframe(1))
            if geist is not None and geist not in recorder.fired:
                recorder.fired[geist] = recorder.current_nodeid

        functools.update_wrapper(recording_init, original)
        self._original_init = original
        type.__setattr__(Suggestion, "__init__", recording_init)

    def uninstall(self) -> None:
        from geistfabrik.models import Suggestion

        if self._original_init is not None:
            type.__setattr__(Suggestion, "__init__", self._original_init)
            self._original_init = None


def evaluate(
    expected: Iterable[str], fired: Iterable[str], allowlist: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Return (never_fired, stale_allowlist_entries)."""
    expected_set, fired_set = set(expected), set(fired)
    missing = sorted(expected_set - fired_set - set(allowlist))
    stale = sorted(
        f"{geist}: allowlisted but it fired" if geist in fired_set else f"{geist}: not bundled"
        for geist in allowlist
        if geist in fired_set or geist not in expected_set
    )
    return missing, stale


class GeistFiringPlugin:
    """Session hooks: track the running test, evaluate and report at the end."""

    def __init__(
        self,
        recorder: GeistFiringRecorder,
        expected: Callable[[], set[str]] = bundled_geists,
        allowlist: dict[str, str] | None = None,
    ) -> None:
        self.recorder = recorder
        self.expected = expected
        self.allowlist = ALLOWLIST if allowlist is None else allowlist
        self.report: list[str] = []

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_protocol(self, item: pytest.Item) -> Generator[None, object, object]:
        self.recorder.current_nodeid = item.nodeid
        try:
            return (yield)
        finally:
            self.recorder.current_nodeid = "<outside any test>"

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if exitstatus == pytest.ExitCode.INTERRUPTED:
            self.report = ["geist firing gate skipped: the run was interrupted"]
            return
        expected = self.expected()
        missing, stale = evaluate(expected, self.recorder.fired, self.allowlist)
        if not missing and not stale:
            fired = len(expected & set(self.recorder.fired))
            self.report = [
                f"geist firing gate passed: {fired} bundled geists "
                f"produced a Suggestion ({len(self.allowlist)} allowlisted)"
            ]
            return
        lines = []
        if missing:
            lines.append(f"{len(missing)} bundled geist(s) never produced a Suggestion:")
            lines.extend(f"  - {geist}" for geist in missing)
            lines.append(
                "Add a test whose fixture makes each one fire (see "
                "tests/unit/GEIST_TESTING_TEMPLATE.md), or allowlist it with a reason in "
                "tests/plugins/geist_firing.py."
            )
        if stale:
            lines.append("Stale geist-firing allowlist entries:")
            lines.extend(f"  - {entry}" for entry in stale)
        self.report = lines
        if session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

    def pytest_terminal_summary(self, terminalreporter: Any) -> None:
        if self.report:
            terminalreporter.section("geist firing gate")
            for line in self.report:
                terminalreporter.write_line(line)

    def pytest_unconfigure(self) -> None:
        self.recorder.uninstall()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        OPTION,
        action="store_true",
        default=False,
        help="Fail the session unless every bundled geist produced a Suggestion "
        "(only meaningful for the full unit lane).",
    )


def pytest_configure(config: pytest.Config) -> None:
    if not config.getoption(OPTION):
        return
    recorder = GeistFiringRecorder(*bundled_dirs())
    recorder.install()
    config.pluginmanager.register(GeistFiringPlugin(recorder), "geist-firing-gate")
