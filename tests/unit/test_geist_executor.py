"""Tests for geist executor."""

import time
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik import GeistExecutor, Suggestion, Vault, VaultContext
from geistfabrik.embeddings import Session


@pytest.fixture
def sample_vault(tmp_path: Path):
    """Create a sample vault for testing."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()

    # Create a sample note
    note_file = vault_dir / "test.md"
    note_file.write_text("# Test Note\n\nSome content")

    vault = Vault(str(vault_dir), ":memory:")
    vault.sync()
    return vault


@pytest.fixture
def sample_context(sample_vault: Vault):
    """Create a VaultContext for testing."""
    session = Session(datetime(2023, 6, 15), sample_vault.db)
    return VaultContext(sample_vault, session)


@pytest.fixture
def geists_dir(tmp_path: Path):
    """Create a directory for test geists."""
    geists = tmp_path / "geists"
    geists.mkdir()
    return geists


def test_geist_executor_initialization(geists_dir: Path):
    """Test creating a GeistExecutor."""
    executor = GeistExecutor(geists_dir, timeout=5, max_failures=3)

    assert executor.geists_dir == geists_dir
    assert executor.timeout == 5
    assert executor.max_failures == 3
    assert len(executor.geists) == 0


def test_load_empty_directory(geists_dir: Path):
    """Test loading from empty geist directory."""
    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    assert len(executor.geists) == 0


def test_load_simple_geist(geists_dir: Path, sample_context: VaultContext):
    """Test loading and executing a simple geist (AC-4.2, AC-4.3)."""
    # Create a simple geist
    geist_file = geists_dir / "simple.py"
    geist_file.write_text("""
from geistfabrik import Suggestion

def suggest(vault):
    '''A simple test geist.'''
    return [
        Suggestion(
            text="This is a test suggestion",
            notes=["test.md"],
            geist_id="simple"
        )
    ]
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    assert len(executor.geists) == 1
    assert "simple" in executor.geists

    # Execute the geist
    suggestions = executor.execute_geist("simple", sample_context)

    assert len(suggestions) == 1
    assert suggestions[0].text == "This is a test suggestion"
    assert suggestions[0].geist_id == "simple"


def test_code_geist_timeout(geists_dir: Path, sample_context: VaultContext):
    """Test that geist execution times out (AC-4.4)."""
    # Create a geist that sleeps
    geist_file = geists_dir / "sleeper.py"
    geist_file.write_text("""
import time

def suggest(vault):
    time.sleep(10)  # Sleep longer than timeout
    return []
""")

    executor = GeistExecutor(geists_dir, timeout=1)  # 1 second timeout
    executor.load_geists()

    start = time.time()
    suggestions = executor.execute_geist("sleeper", sample_context)
    elapsed = time.time() - start

    # Should return empty list
    assert suggestions == []

    # Should timeout quickly (within 2 seconds)
    assert elapsed < 2.0

    # Check execution log
    log = executor.get_execution_log()
    assert any(entry["status"] == "error" and entry["error_type"] == "timeout" for entry in log)


def test_disable_after_three_failures(geists_dir: Path, sample_context: VaultContext):
    """Test that geist is disabled after 3 failures (AC-4.5)."""
    # Create a geist that always fails
    geist_file = geists_dir / "failer.py"
    geist_file.write_text("""
def suggest(vault):
    raise ValueError("Always fails")
""")

    executor = GeistExecutor(geists_dir, max_failures=3)
    executor.load_geists()

    # Execute 3 times
    for i in range(3):
        suggestions = executor.execute_geist("failer", sample_context)
        assert suggestions == []

        geist = executor.geists["failer"]
        assert geist.failure_count == i + 1

        if i < 2:
            assert geist.is_enabled
        else:
            assert not geist.is_enabled  # Disabled after 3rd failure

    # Fourth execution should skip
    suggestions = executor.execute_geist("failer", sample_context)
    assert suggestions == []

    # Check log for disabled status
    log = executor.get_execution_log()
    assert any(entry["status"] == "disabled" for entry in log)


def test_geist_syntax_error(geists_dir: Path):
    """Test handling of geist with syntax errors (AC-4.7)."""
    # Create a geist with syntax error
    geist_file = geists_dir / "syntax_error.py"
    geist_file.write_text("""
def suggest(vault):
    return [  # Missing closing bracket
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    # Should log error but not crash
    assert "syntax_error" not in executor.geists

    log = executor.get_execution_log()
    assert any(
        entry["geist_id"] == "syntax_error" and entry["status"] == "load_error" for entry in log
    )


def test_geist_import_error(geists_dir: Path):
    """Test handling of geist with import errors (AC-4.8)."""
    # Create a geist that imports non-existent module
    geist_file = geists_dir / "import_error.py"
    geist_file.write_text("""
import nonexistent_module

def suggest(vault):
    return []
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    assert "import_error" not in executor.geists

    log = executor.get_execution_log()
    assert any(
        entry["geist_id"] == "import_error" and entry["status"] == "load_error" for entry in log
    )


def test_geist_invalid_return(geists_dir: Path, sample_context: VaultContext):
    """Test handling of geist returning wrong type (AC-4.9)."""
    # Create a geist that returns wrong type
    geist_file = geists_dir / "wrong_return.py"
    geist_file.write_text("""
def suggest(vault):
    return "not a list"
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    suggestions = executor.execute_geist("wrong_return", sample_context)

    # Should return empty list
    assert suggestions == []

    # Should log error
    log = executor.get_execution_log()
    assert any(
        entry["geist_id"] == "wrong_return"
        and entry["status"] == "error"
        and "expected list" in entry["error"]
        for entry in log
    )


def test_geist_invalid_suggestion_type(geists_dir: Path, sample_context: VaultContext):
    """Test handling of geist returning non-Suggestion objects."""
    # Create a geist that returns wrong suggestion type
    geist_file = geists_dir / "wrong_suggestion.py"
    geist_file.write_text("""
def suggest(vault):
    return ["not a Suggestion object"]
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    suggestions = executor.execute_geist("wrong_suggestion", sample_context)

    assert suggestions == []

    log = executor.get_execution_log()
    assert any(
        entry["geist_id"] == "wrong_suggestion"
        and entry["status"] == "error"
        and "expected Suggestion" in entry["error"]
        for entry in log
    )


def test_duplicate_geist_ids(geists_dir: Path):
    """Test detection of duplicate geist IDs (AC-4.12)."""
    # Create two geists with same name
    geist1 = geists_dir / "duplicate.py"
    geist1.write_text("""
def suggest(vault):
    return []
""")

    # Can't have two files with same name, so test the check differently
    # by trying to load the same geist twice
    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    # Try to load again - should fail with duplicate ID
    with pytest.raises(ValueError, match="Duplicate geist ID"):
        executor._load_geist(geist1)


def test_missing_geist_directory(tmp_path: Path):
    """Test handling of missing geist directory (AC-4.13)."""
    nonexistent = tmp_path / "nonexistent"

    executor = GeistExecutor(nonexistent)
    executor.load_geists()  # Should not crash

    assert len(executor.geists) == 0


def test_geist_missing_suggest_function(geists_dir: Path):
    """Test handling of geist without suggest() function."""
    geist_file = geists_dir / "no_suggest.py"
    geist_file.write_text("""
def wrong_function_name(vault):
    return []
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    assert "no_suggest" not in executor.geists

    log = executor.get_execution_log()
    assert any(
        entry["geist_id"] == "no_suggest"
        and entry["status"] == "load_error"
        and "missing suggest()" in entry["error"]
        for entry in log
    )


def test_infinite_loop_timeout(geists_dir: Path, sample_context: VaultContext):
    """Test that infinite loops are caught by timeout (AC-4.14)."""
    geist_file = geists_dir / "infinite.py"
    geist_file.write_text("""
def suggest(vault):
    while True:
        pass
""")

    executor = GeistExecutor(geists_dir, timeout=1)
    executor.load_geists()

    start = time.time()
    suggestions = executor.execute_geist("infinite", sample_context)
    elapsed = time.time() - start

    assert suggestions == []
    assert elapsed < 2.0  # Should timeout quickly


def test_geist_excessive_suggestions(geists_dir: Path, sample_context: VaultContext):
    """Test geist returning many suggestions (AC-4.16)."""
    geist_file = geists_dir / "many.py"
    geist_file.write_text("""
from geistfabrik import Suggestion

def suggest(vault):
    # Return 1000 suggestions
    return [
        Suggestion(
            text=f"Suggestion {i}",
            notes=[],
            geist_id="many"
        )
        for i in range(1000)
    ]
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    suggestions = executor.execute_geist("many", sample_context)

    # Should handle without crashing
    assert len(suggestions) == 1000
    assert all(isinstance(s, Suggestion) for s in suggestions)


def test_geist_unicode_suggestions(geists_dir: Path, sample_context: VaultContext):
    """Test geist with unicode in suggestions (AC-4.17)."""
    geist_file = geists_dir / "unicode.py"
    geist_file.write_text("""
from geistfabrik import Suggestion

def suggest(vault):
    return [
        Suggestion(
            text="What if... 你好世界 🌍 café",
            notes=["test.md"],
            geist_id="unicode"
        )
    ]
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    suggestions = executor.execute_geist("unicode", sample_context)

    assert len(suggestions) == 1
    assert "你好世界" in suggestions[0].text
    assert "🌍" in suggestions[0].text
    assert "café" in suggestions[0].text


def test_geist_state_isolation(geists_dir: Path, sample_context: VaultContext):
    """Test that geists don't share state (AC-4.18)."""
    # Create two geists that try to use global state
    geist1 = geists_dir / "state1.py"
    geist1.write_text("""
from geistfabrik import Suggestion

counter = 0

def suggest(vault):
    global counter
    counter += 1
    return [
        Suggestion(
            text=f"Count: {counter}",
            notes=[],
            geist_id="state1"
        )
    ]
""")

    geist2 = geists_dir / "state2.py"
    geist2.write_text("""
from geistfabrik import Suggestion

counter = 0

def suggest(vault):
    global counter
    counter += 1
    return [
        Suggestion(
            text=f"Count: {counter}",
            notes=[],
            geist_id="state2"
        )
    ]
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    # Execute both geists
    sug1 = executor.execute_geist("state1", sample_context)
    sug2 = executor.execute_geist("state2", sample_context)

    # Each should have its own state
    assert sug1[0].text == "Count: 1"
    assert sug2[0].text == "Count: 1"  # Not 2!


def test_geist_exception_logging(geists_dir: Path, sample_context: VaultContext):
    """Test that exceptions are logged with details (AC-4.19)."""
    geist_file = geists_dir / "exception.py"
    geist_file.write_text("""
def suggest(vault):
    raise RuntimeError("Something went wrong")
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    executor.execute_geist("exception", sample_context)

    log = executor.get_execution_log()
    error_entry = next(
        entry for entry in log if entry["geist_id"] == "exception" and entry["status"] == "error"
    )

    assert error_entry["error_type"] == "exception"
    assert "Something went wrong" in error_entry["error"]
    assert "traceback" in error_entry


def test_execute_all(geists_dir: Path, sample_context: VaultContext):
    """Test executing all geists at once."""
    # Create multiple geists
    for i in range(3):
        geist_file = geists_dir / f"geist{i}.py"
        geist_file.write_text(f"""
from geistfabrik import Suggestion

def suggest(vault):
    return [
        Suggestion(
            text="Suggestion from geist{i}",
            notes=[],
            geist_id="geist{i}"
        )
    ]
""")

    executor = GeistExecutor(geists_dir)
    executor.load_geists()

    results = executor.execute_all(sample_context)

    assert len(results) == 3
    for i in range(3):
        assert f"geist{i}" in results
        assert len(results[f"geist{i}"]) == 1


def test_get_enabled_geists(geists_dir: Path, sample_context: VaultContext):
    """Test getting list of enabled geists."""
    # Create working and failing geists
    good = geists_dir / "good.py"
    good.write_text("""
from geistfabrik import Suggestion

def suggest(vault):
    return []
""")

    bad = geists_dir / "bad.py"
    bad.write_text("""
def suggest(vault):
    raise RuntimeError("Always fails")
""")

    executor = GeistExecutor(geists_dir, max_failures=1)
    executor.load_geists()

    # Initially both enabled
    assert set(executor.get_enabled_geists()) == {"good", "bad"}

    # Execute bad geist once to disable it
    executor.execute_geist("bad", sample_context)

    # Now only good should be enabled
    assert executor.get_enabled_geists() == ["good"]
