"""Write which test node ids a pytest run selected and deselected, as JSON.

Loaded explicitly by ``scripts/check_phase_completion.py``::

    uv run pytest <targets> -m "<markers>" -p tests.plugins.selection_report \\
        --selection-report=/tmp/report.json

The acceptance-criteria gate uses the report to reject partial evidence: a
criterion that names a whole file while the marker filter deselects some of
that file's tests, or a criterion that selects no tests at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

OPTION = "--selection-report"


class SelectionReport:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.deselected: list[str] = []

    def pytest_deselected(self, items: list[pytest.Item]) -> None:
        self.deselected.extend(item.nodeid for item in items)

    @pytest.hookimpl(trylast=True)
    def pytest_collection_finish(self, session: pytest.Session) -> None:
        payload = {
            "selected": sorted({item.nodeid for item in session.items}),
            "deselected": sorted(set(self.deselected)),
        }
        self.path.write_text(json.dumps(payload, indent=1), encoding="utf-8")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(OPTION, default=None, help="Write selected/deselected node ids as JSON.")


def pytest_configure(config: pytest.Config) -> None:
    path = config.getoption(OPTION)
    if path:
        config.pluginmanager.register(SelectionReport(Path(path)), "selection-report")
