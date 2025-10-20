"""Configuration for integration tests."""

import pytest


def pytest_configure(config):
    """Register custom markers for integration tests."""
    config.addinivalue_line("markers", "slow: marks tests as slow (requiring real model downloads)")
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (using real external services)"
    )
