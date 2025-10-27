"""Tests for suggestion filtering."""

import sqlite3
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from geistfabrik.filtering import SuggestionFilter
from geistfabrik.models import Suggestion


@pytest.fixture
def db():
    """Create in-memory database for testing."""
    conn = sqlite3.connect(":memory:")

    # Create minimal schema for tests
    conn.execute("""
        CREATE TABLE notes (
            path TEXT PRIMARY KEY,
            title TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE session_suggestions (
            session_date TEXT NOT NULL,
            geist_id TEXT NOT NULL,
            suggestion_text TEXT NOT NULL,
            block_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Insert test notes
    conn.execute("INSERT INTO notes (path, title) VALUES ('note1.md', 'Note 1')")
    conn.execute("INSERT INTO notes (path, title) VALUES ('note2.md', 'Note 2')")
    conn.commit()

    return conn


@pytest.fixture
def mock_embedding_computer():
    """Create mock embedding computer."""
    mock = MagicMock()
    mock.compute_semantic.return_value = [0.1] * 384  # Mock embedding
    return mock


class TestSuggestionFilterConfig:
    """Tests for custom configuration handling."""

    def test_filter_uses_default_config_when_none_provided(self, db, mock_embedding_computer):
        """Test that filter uses default config when None is passed."""
        filter_obj = SuggestionFilter(db, mock_embedding_computer, config=None)

        # Default config should have all strategies
        assert "boundary" in filter_obj.config.get("strategies", [])
        assert "novelty" in filter_obj.config.get("strategies", [])
        assert "diversity" in filter_obj.config.get("strategies", [])
        assert "quality" in filter_obj.config.get("strategies", [])

    def test_filter_uses_custom_config_when_provided(self, db, mock_embedding_computer):
        """Test that filter uses custom config when provided."""
        custom_config = {
            "strategies": ["boundary", "quality"],  # Only these two
            "boundary": {"enabled": True},
            "quality": {
                "enabled": True,
                "min_length": 50,  # Custom minimum
                "max_length": 500,  # Custom maximum
                "check_repetition": False,
            },
        }

        filter_obj = SuggestionFilter(db, mock_embedding_computer, config=custom_config)

        # Should use custom config
        assert filter_obj.config == custom_config
        assert filter_obj.config["strategies"] == ["boundary", "quality"]
        assert filter_obj.config["quality"]["min_length"] == 50
        assert filter_obj.config["quality"]["max_length"] == 500

    def test_filter_respects_custom_quality_settings(self, db, mock_embedding_computer):
        """Test that custom quality settings are actually used during filtering."""
        custom_config = {
            "strategies": ["quality"],
            "quality": {
                "enabled": True,
                "min_length": 100,  # Very high minimum
                "max_length": 200,
                "check_repetition": True,
            },
        }

        filter_obj = SuggestionFilter(db, mock_embedding_computer, config=custom_config)

        suggestions = [
            Suggestion(
                text="Too short",  # 9 chars - should be filtered
                notes=["Note 1"],
                geist_id="test",
            ),
            Suggestion(
                text="A" * 150,  # 150 chars - should pass
                notes=["Note 1"],
                geist_id="test",
            ),
            Suggestion(
                text="A" * 300,  # 300 chars - should be filtered (too long)
                notes=["Note 1"],
                geist_id="test",
            ),
        ]

        session_date = datetime(2023, 1, 1)
        filtered = filter_obj.filter_all(suggestions, session_date)

        # Only the 150-char suggestion should pass
        assert len(filtered) == 1
        assert len(filtered[0].text) == 150

    def test_filter_can_disable_all_strategies(self, db, mock_embedding_computer):
        """Test that strategies can be disabled via config."""
        custom_config = {
            "strategies": [],  # No strategies enabled
        }

        filter_obj = SuggestionFilter(db, mock_embedding_computer, config=custom_config)

        # Create suggestion referencing non-existent note (would normally be filtered)
        suggestions = [
            Suggestion(
                text="Test",
                notes=["NonExistent"],  # This note doesn't exist
                geist_id="test",
            ),
        ]

        session_date = datetime(2023, 1, 1)
        filtered = filter_obj.filter_all(suggestions, session_date)

        # Should pass through unfiltered when no strategies enabled
        assert len(filtered) == 1

    def test_filter_default_config_has_expected_values(self, db, mock_embedding_computer):
        """Test that default config has expected structure and values."""
        filter_obj = SuggestionFilter(db, mock_embedding_computer, config=None)

        # Check structure
        assert "strategies" in filter_obj.config
        assert isinstance(filter_obj.config["strategies"], list)

        # Check default strategies are present
        assert "boundary" in filter_obj.config
        assert "novelty" in filter_obj.config
        assert "diversity" in filter_obj.config
        assert "quality" in filter_obj.config

        # Check quality defaults
        quality = filter_obj.config["quality"]
        assert quality["enabled"] is True
        assert quality["min_length"] == 10  # From DEFAULT_MIN_SUGGESTION_LENGTH
        assert quality["max_length"] == 2000  # From DEFAULT_MAX_SUGGESTION_LENGTH
        assert quality["check_repetition"] is True

        # Check novelty defaults
        novelty = filter_obj.config["novelty"]
        assert novelty["enabled"] is True
        assert novelty["threshold"] == 0.85  # DEFAULT_SIMILARITY_THRESHOLD
        assert novelty["window_days"] == 60  # DEFAULT_NOVELTY_WINDOW_DAYS

    def test_filter_custom_strategy_order(self, db, mock_embedding_computer):
        """Test that custom strategy order is respected."""
        custom_config = {
            "strategies": ["quality", "boundary"],  # Reversed order
            "boundary": {"enabled": True},
            "quality": {
                "enabled": True,
                "min_length": 10,
                "max_length": 2000,
                "check_repetition": True,
            },
        }

        filter_obj = SuggestionFilter(db, mock_embedding_computer, config=custom_config)

        # Order should be preserved
        assert filter_obj.config["strategies"] == ["quality", "boundary"]
