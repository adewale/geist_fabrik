"""Prevention test: the spec's config schema must stay reconciled with reality.

This is the mechanical guard against "specified but never built" config drift.
It parses the config.yaml block from specs/geistfabrik_spec.md and asserts that
EVERY key is accounted for in specs/SPEC_STATUS.md. So an aspirational spec edit
that adds a config key now fails CI until someone records its status (build it,
or mark it NOT-BUILT / DEFERRED). It also pins that the keys we claim BUILT are
actually reachable through GeistFabrikConfig, catching false "implemented"
claims (the failure mode that hid exclude_paths for months).

Same culture as test_geist_count_consistency.py: a single source of truth plus
a test that fails when docs and code disagree.
"""

import re
from pathlib import Path

import yaml

from geistfabrik.config_loader import GeistFabrikConfig

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "specs" / "geistfabrik_spec.md"
LEDGER = REPO / "specs" / "SPEC_STATUS.md"

VALID_STATUSES = {"BUILT", "BUILT-DIFFERENTLY", "NOT-WIRED", "NOT-BUILT", "DEFERRED"}


def _spec_config_keys() -> set[str]:
    """Dotted keys of the spec's config.yaml example block."""
    lines = SPEC.read_text().splitlines()
    start = next(
        i for i, line in enumerate(lines)
        if "_geistfabrik/config.yaml" in line and line.strip().startswith("#")
    )
    end = next(i for i in range(start + 1, len(lines)) if lines[i].strip() == "```")
    data = yaml.safe_load("\n".join(lines[start + 1 : end])) or {}

    def flat(d: dict, prefix: str = "") -> list[str]:
        out: list[str] = []
        for k, v in d.items():
            key = f"{prefix}{k}"
            out += flat(v, key + ".") if isinstance(v, dict) else [key]
        return out

    return set(flat(data))


def _ledger_rows() -> dict[str, str]:
    """Parse the config-keys table: `key` -> STATUS."""
    rows: dict[str, str] = {}
    for line in LEDGER.read_text().splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([A-Z-]+)\s*\|", line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


def _live_config_leaf_paths() -> set[str]:
    cfg = GeistFabrikConfig().to_dict()

    def flat(d: dict, prefix: str = "") -> list[str]:
        out: list[str] = []
        for k, v in d.items():
            key = f"{prefix}{k}"
            out += flat(v, key + ".") if isinstance(v, dict) else [key]
        return out

    return set(flat(cfg))


def test_every_spec_config_key_is_in_the_ledger():
    """No spec config key may be undocumented - the anti-drift guard."""
    spec_keys = _spec_config_keys()
    ledger = _ledger_rows()
    missing = sorted(spec_keys - set(ledger))
    assert not missing, (
        "These spec config keys are not recorded in specs/SPEC_STATUS.md - "
        "decide and document their status (BUILT / NOT-BUILT / ...):\n"
        + "\n".join(missing)
    )


def test_ledger_statuses_are_valid():
    bad = {k: v for k, v in _ledger_rows().items() if v not in VALID_STATUSES}
    assert not bad, f"Invalid status values in SPEC_STATUS.md: {bad}"


def test_ledger_has_no_phantom_keys():
    """The ledger's config-key rows must all be real spec keys (no rot)."""
    extra = sorted(set(_ledger_rows()) - _spec_config_keys())
    assert not extra, (
        "SPEC_STATUS.md lists config keys that are not in the spec block "
        "(stale rows?):\n" + "\n".join(extra)
    )


def test_built_keys_are_reachable_in_live_config():
    """A key marked literally BUILT must have its leaf in the live config, so
    the ledger cannot claim a config key is implemented when it isn't (the
    false-"implemented" failure mode). BUILT-DIFFERENTLY is a human-reviewed
    divergence by definition (different shape/name or behavioural-not-config),
    so it is intentionally not code-checked here."""
    live_leaves = {p.split(".")[-1] for p in _live_config_leaf_paths()}
    offenders = []
    for key, status in _ledger_rows().items():
        if status != "BUILT":
            continue
        leaf = key.split(".")[-1]
        if leaf not in live_leaves:
            offenders.append(f"{key} (BUILT) - leaf '{leaf}' not in live config")
    assert not offenders, "Ledger claims BUILT but code disagrees:\n" + "\n".join(offenders)
