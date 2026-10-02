"""Write which test node ids a pytest run selected, deselected and skipped, as JSON.

``tests/conftest.py`` registers this plugin's option for every run, so any
pytest invocation inside the repository accepts it::

    uv run pytest <targets> -m "<markers>" --selection-report=/tmp/report.json

``scripts/check_phase_completion.py`` adds that option to the pytest commands it
runs. The acceptance-criteria gate uses the report to reject evidence that is
not whole: a criterion that names a whole file while the marker filter
deselects some of that file's tests, a criterion that selects no tests at all,
or a target whose selected tests were all skipped.

(Outside the repository's conftest, e.g. in a ``pytester`` project, load it
with ``-p tests.plugins.selection_report``.)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

OPTION = "--selection-report"


class SelectionReport:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.selected: list[str] = []
        self.deselected: list[str] = []
        self._skipped: set[str] = set()
        self._ran: set[str] = set()

    def pytest_deselected(self, items: list[pytest.Item]) -> None:
        self.deselected.extend(item.nodeid for item in items)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        # A skip may arrive in setup (skipif) or call (pytest.skip); an xfail is
        # also reported as skipped. A test "ran" only if its call phase did.
        if report.skipped:
            self._skipped.add(report.nodeid)
        elif report.when == "call":
            self._ran.add(report.nodeid)

    def _write(self) -> None:
        payload = {
            "selected": self.selected,
            "deselected": sorted(set(self.deselected)),
            "skipped": sorted(self._skipped - self._ran),
        }
        self.path.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    @pytest.hookimpl(trylast=True)
    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.selected = sorted({item.nodeid for item in session.items})
        self._write()

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self) -> None:
        self._write()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        OPTION, default=None, help="Write selected/deselected/skipped node ids as JSON."
    )


def pytest_configure(config: pytest.Config) -> None:
    path = config.getoption(OPTION)
    if path:
        config.pluginmanager.register(SelectionReport(Path(path)), "selection-report")
