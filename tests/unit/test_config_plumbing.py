"""Config plumbing + spec-sync tests.

Two jobs:
1. Pin that the config sections wired in this change (geist_execution,
   filtering with exclude_paths, session) round-trip and actually reach the
   pieces that consume them.
2. PREVENTION: assert the privacy-relevant exclude_paths boundary filter works,
   and that load_config rejects unknown keys. (The broader spec<->config
   reconciliation is enforced by test_spec_config_sync.py.)
"""

import logging
import sqlite3

import pytest

from geistfabrik.config import (
    DEFAULT_GEIST_TIMEOUT,
    DEFAULT_MAX_GEIST_FAILURES,
)
from geistfabrik.config_loader import (
    ConfigError,
    FilteringConfig,
    GeistFabrikConfig,
    load_config,
)
from geistfabrik.filtering import SuggestionFilter
from geistfabrik.models import Suggestion


class _FakeArgs:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _command(args):
    from geistfabrik.commands.invoke import InvokeCommand

    return InvokeCommand(args)


class TestConfigSectionsRoundTrip:
    def test_new_sections_survive_roundtrip(self):
        data = {
            "geist_execution": {"timeout": 12, "max_failures": 7},
            "filtering": {
                "boundary": {"enabled": False, "exclude_paths": ["Private/", "People/"]},
                "novelty": {"window_days": 90, "threshold": 0.7},
                "diversity": {"threshold": 0.8},
                "quality": {"min_length": 20, "max_length": 500},
            },
            "session": {"default_suggestions": 9},
        }
        cfg = GeistFabrikConfig.from_dict(data)
        assert cfg.geist_execution.timeout == 12
        assert cfg.geist_execution.max_failures == 7
        assert cfg.filtering.boundary_enabled is False
        assert cfg.filtering.exclude_paths == ["Private/", "People/"]
        assert cfg.filtering.novelty_window_days == 90
        assert cfg.session.default_suggestions == 9
        # from_dict(to_dict(x)) == x
        assert GeistFabrikConfig.from_dict(cfg.to_dict()) == cfg

    def test_legacy_vector_backend_settings_roundtrip_strictly(self):
        data = {
            "vector_search": {
                "backend": "sqlite-vec",
                "backends": {
                    "in_memory": {"lazy_load": False},
                    "sqlite_vec": {"index_type": "flat", "cache_size_mb": 256},
                },
            }
        }
        cfg = GeistFabrikConfig.from_dict(data)
        assert cfg.vector_search.backend_settings == {
            "in_memory": {"lazy_load": False},
            "sqlite_vec": {"index_type": "flat", "cache_size_mb": 256},
        }
        assert GeistFabrikConfig.from_dict(cfg.to_dict()) == cfg

    @pytest.mark.parametrize(
        "backends",
        [
            {"sqlite_vec": {"cache_size_mb": True}},
            {"sqlite_vec": {"cache_size_mb": 0}},
            {"sqlite_vec": {"index_type": "unknown"}},
            {"sqlite_vec": {"unknown": 1}},
            {"in_memory": {"lazy_load": "false"}},
            {"in_memory": {"unknown": False}},
        ],
    )
    def test_legacy_vector_backend_settings_reject_unknown_or_invalid_shape(self, backends):
        with pytest.raises(ConfigError):
            GeistFabrikConfig.from_dict({"vector_search": {"backends": backends}})

    def test_to_filter_config_overlays_defaults(self):
        fc = FilteringConfig(
            boundary_enabled=False,
            exclude_paths=["Secret/"],
            novelty_threshold=0.5,
        )
        out = fc.to_filter_config()
        assert out["boundary"]["enabled"] is False
        assert out["boundary"]["exclude_paths"] == ["Secret/"]
        assert out["novelty"]["threshold"] == 0.5
        # untouched defaults still present
        assert out["quality"]["check_repetition"] is True


class TestResolvers:
    def test_timeout_cli_overrides_config(self):
        cfg = GeistFabrikConfig.from_dict({"geist_execution": {"timeout": 11}})
        assert _command(_FakeArgs(timeout=99)).resolve_timeout(cfg) == 99  # CLI wins
        assert _command(_FakeArgs(timeout=None)).resolve_timeout(cfg) == 11  # config
        assert _command(_FakeArgs(timeout=None)).resolve_timeout(None) == DEFAULT_GEIST_TIMEOUT

    def test_max_failures_from_config(self):
        cfg = GeistFabrikConfig.from_dict({"geist_execution": {"max_failures": 5}})
        assert _command(_FakeArgs()).resolve_max_failures(cfg) == 5
        assert _command(_FakeArgs()).resolve_max_failures(None) == DEFAULT_MAX_GEIST_FAILURES


class TestExcludePathsBoundaryFilter:
    @pytest.fixture
    def db(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE notes (path TEXT PRIMARY KEY, title TEXT NOT NULL, "
            "is_virtual INTEGER DEFAULT 0, source_file TEXT, entry_date TEXT)"
        )
        conn.execute(
            "CREATE TABLE session_suggestions (session_date TEXT, geist_id TEXT, "
            "suggestion_text TEXT, block_id TEXT, created_at TEXT)"
        )
        conn.execute("INSERT INTO notes (path, title) VALUES ('Public/Open.md', 'Open Note')")
        conn.execute("INSERT INTO notes (path, title) VALUES ('Private/Secret.md', 'Secret Note')")
        conn.commit()
        return conn

    def _filter(self, db):
        from unittest.mock import MagicMock

        cfg = {
            "strategies": ["boundary"],
            "boundary": {"enabled": True, "exclude_paths": ["Private/"]},
        }
        return SuggestionFilter(db, MagicMock(), config=cfg)

    def test_excluded_path_suggestion_dropped(self, db):
        f = self._filter(db)
        public = Suggestion(text="About the open note.", notes=["Open Note"], geist_id="g")
        private = Suggestion(text="About the secret note.", notes=["Secret Note"], geist_id="g")
        result = f.filter_boundary([public, private])
        assert public in result
        assert private not in result, "notes under Private/ must never surface"

    def test_no_exclude_paths_keeps_everything(self, db):
        from unittest.mock import MagicMock

        f = SuggestionFilter(
            db, MagicMock(), config={"strategies": ["boundary"], "boundary": {"enabled": True}}
        )
        s = Suggestion(text="About the secret note.", notes=["Secret Note"], geist_id="g")
        assert s in f.filter_boundary([s])


class TestUnknownKeyValidation:
    def test_load_config_wraps_unrepresentable_float_as_config_error(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            "filtering:\n  novelty:\n    threshold: " + str(10**400) + "\n"
        )
        with pytest.raises(ConfigError, match="finite number"):
            load_config(cfg_path)

    def test_load_config_rejects_unknown_key(self, tmp_path):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("enabled_modules: []\nnonsense_key: 3\nanother_typo: true\n")
        with pytest.raises(ConfigError, match="another_typo, nonsense_key"):
            load_config(cfg_path)

    def test_known_keys_do_not_warn(self, tmp_path, caplog):
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("geist_execution:\n  timeout: 9\nsession:\n  default_suggestions: 4\n")
        with caplog.at_level(logging.WARNING):
            cfg = load_config(cfg_path)
        assert cfg.geist_execution.timeout == 9
        assert not any("unknown config key" in r.message.lower() for r in caplog.records)
