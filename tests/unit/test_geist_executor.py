"""Tests for geist executor."""

import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik import GeistExecutor, Vault, VaultContext
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


def test_debug_execution_profile_reports_geist_function_stats(
    geists_dir: Path, sample_context: VaultContext
) -> None:
    """Debug mode turns real cProfile output into ProfileStats for the geist's own code."""
    (geists_dir / "profiled.py").write_text(
        "def profiled_work():\n"
        "    total = 0\n"
        "    for index in range(300_000):\n"
        "        total += index\n"
        "    return total\n"
        "\n"
        "def suggest(vault):\n"
        "    profiled_work()\n"
        "    return []\n"
    )
    executor = GeistExecutor(geists_dir, debug=True)
    executor.load_geists()

    assert executor.execute_geist("profiled", sample_context) == []

    [profile] = executor.get_execution_profiles()
    assert (profile.geist_id, profile.status, profile.suggestion_count) == (
        "profiled",
        "success",
        0,
    )
    assert profile.function_stats is not None
    row = next(item for item in profile.function_stats if item.name.endswith(":profiled_work"))
    assert row.calls == 1
    assert row.total_time > 0
    assert row.cumulative_time >= row.total_time


@pytest.mark.parametrize(
    "timeout,max_failures,field",
    [
        (0, 3, "timeout"),
        (-1, 3, "timeout"),
        (True, 3, "timeout"),
        (30, 0, "max_failures"),
        (30, True, "max_failures"),
    ],
)
def test_executor_rejects_non_positive_limits(
    geists_dir: Path, timeout: int, max_failures: int, field: str
) -> None:
    """A zero/boolean limit would disable the timeout or the failure cap."""
    with pytest.raises(ValueError, match=f"{field} must be a positive integer"):
        GeistExecutor(geists_dir, timeout=timeout, max_failures=max_failures)


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
    assert executor.get_execution_log() == [
        {"geist_id": "simple", "status": "success", "suggestion_count": 1}
    ]


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

    # The empty return must be explained by a recorded timeout failure.
    [entry] = executor.get_execution_log()
    assert entry["geist_id"] == "sleeper"
    assert entry["status"] == "error"
    assert entry["error_type"] == "timeout"
    assert entry["failure_count"] == 1
    assert "timed out (>1s)" in entry["error"]


def test_code_geist_import_timeout(geists_dir: Path) -> None:
    """Supported POSIX main-thread runs also bound top-level import hangs."""
    if sys.platform == "win32":
        pytest.skip("hard plugin timeout unavailable on Windows")
    (geists_dir / "import_sleeper.py").write_text(
        "import time\ntime.sleep(10)\ndef suggest(vault): return []\n"
    )
    executor = GeistExecutor(geists_dir, timeout=1)
    start = time.monotonic()
    executor.load_geists()
    elapsed = time.monotonic() - start

    assert elapsed < 2
    assert "import_sleeper" not in executor.geists
    assert executor.get_execution_log()[0]["status"] == "load_error"
    assert "timed out" in executor.get_execution_log()[0]["error"]


def test_debug_timeout_uses_same_failure_accounting(geists_dir: Path, sample_context: VaultContext):
    """Debug diagnostics must not bypass timeout failure accounting."""
    (geists_dir / "debug_sleeper.py").write_text(
        "import time\ndef suggest(vault):\n    time.sleep(10)\n    return []\n"
    )
    executor = GeistExecutor(geists_dir, timeout=1, max_failures=1, debug=True)
    executor.load_geists()
    assert executor.execute_geist("debug_sleeper", sample_context) == []
    failures = [
        entry
        for entry in executor.get_execution_log()
        if entry.get("geist_id") == "debug_sleeper" and entry.get("error_type") == "timeout"
    ]
    assert len(failures) == 1
    assert executor.geists["debug_sleeper"].is_enabled is False


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

    log = executor.get_execution_log()
    assert [(entry["status"], entry.get("error_type")) for entry in log] == [
        ("error", "exception"),
        ("error", "exception"),
        ("error", "exception"),
        ("disabled", None),
    ]
    assert all("Always fails" in entry["error"] for entry in log[:3])

    # Fourth execution is skipped: the geist is not run again.
    suggestions = executor.execute_geist("failer", sample_context)
    assert suggestions == []
    assert executor.geists["failer"].failure_count == 3
    assert executor.get_execution_log()[-1]["status"] == "skipped"
    assert len(executor.get_execution_log()) == 5


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


def test_duplicate_geist_ids(geists_dir: Path, tmp_path: Path):
    """A custom geist cannot shadow a default with the same ID (AC-4.12)."""
    defaults_dir = tmp_path / "defaults"
    defaults_dir.mkdir()
    default_geist = defaults_dir / "duplicate.py"
    default_geist.write_text("def suggest(vault):\n    return []\n")
    custom_geist = geists_dir / "duplicate.py"
    custom_geist.write_text("def suggest(vault):\n    return []\n")

    executor = GeistExecutor(geists_dir, default_geists_dir=defaults_dir)
    executor.load_geists()

    assert executor.geists["duplicate"].path == default_geist
    [entry] = executor.get_execution_log()
    assert entry["geist_id"] == "duplicate"
    assert entry["status"] == "load_error"
    assert entry["path"] == str(custom_geist)
    assert "Duplicate geist ID 'duplicate'" in entry["error"]


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
    [entry] = executor.get_execution_log()
    assert (entry["geist_id"], entry["status"], entry["error_type"]) == (
        "infinite",
        "error",
        "timeout",
    )


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

    # Per-geist amplification is rejected before aggregate filtering/persistence.
    assert suggestions == []
    assert any(
        entry.get("status") == "error" and "more than 100 suggestions" in entry.get("error", "")
        for entry in executor.get_execution_log()
    )


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

    assert list(results) == ["geist0", "geist1", "geist2"]
    assert all(len(suggestions) == 1 for suggestions in results.values())
    assert executor.get_execution_log() == [
        {"geist_id": f"geist{i}", "status": "success", "suggestion_count": 1} for i in range(3)
    ]


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
