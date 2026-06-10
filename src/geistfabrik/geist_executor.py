"""Geist execution system - loads and runs code geists."""

import cProfile
import importlib.util
import io
import logging
import pstats
import signal
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .geist_status import GeistStatusStore
from .models import Suggestion
from .vault_context import VaultContext

logger = logging.getLogger(__name__)


@dataclass
class GeistMetadata:
    """Metadata about a loaded geist."""

    id: str
    path: Path
    func: Callable[[VaultContext], list[Suggestion]]
    failure_count: int = 0
    is_enabled: bool = True


@dataclass
class ProfileStats:
    """Statistics for a function call in profiling."""

    name: str
    calls: int
    total_time: float  # seconds
    cumulative_time: float  # seconds including subcalls
    per_call: float  # average time per call


@dataclass
class GeistExecutionProfile:
    """Detailed execution profile for a geist."""

    geist_id: str
    status: str  # "success", "timeout", "error"
    total_time: float  # seconds
    suggestion_count: int = 0

    # Optional profiling data (only collected in verbose mode)
    function_stats: list[ProfileStats] | None = None
    stack_trace: str | None = None  # Stack at timeout


class GeistTimeoutError(Exception):
    """Raised when a geist exceeds its execution timeout."""

    pass


def timeout_handler(signum: int, frame: Any) -> None:
    """Signal handler for geist timeouts."""
    raise GeistTimeoutError("Geist execution timed out")


class GeistExecutor:
    """Executes code geists and manages their lifecycle."""

    def __init__(
        self,
        geists_dir: Path,
        timeout: int = 30,
        max_failures: int = 3,
        default_geists_dir: Path | None = None,
        enabled_defaults: dict[str, bool] | None = None,
        debug: bool = False,
        status_store: GeistStatusStore | None = None,
    ):
        """Initialise geist executor.

        Args:
            geists_dir: Directory containing custom geist modules
            timeout: Execution timeout in seconds
            max_failures: Number of failures before disabling geist
            default_geists_dir: Directory containing default geists (optional)
            enabled_defaults: Dictionary of default geist enabled states (optional)
            debug: Enable detailed performance profiling and diagnostics (optional)
        """
        self.geists_dir = geists_dir
        self.timeout = timeout
        self.max_failures = max_failures
        self.default_geists_dir = default_geists_dir
        self.enabled_defaults = enabled_defaults or {}
        self.debug = debug
        # Persistent failure tracking (cross-session disable); None in tests
        # falls back to the in-memory counter.
        self.status_store = status_store
        self.geists: dict[str, GeistMetadata] = {}
        self.execution_log: list[dict[str, Any]] = []
        self.execution_profiles: list[GeistExecutionProfile] = []
        self.newly_discovered: list[str] = []

    def load_geists(self) -> list[str]:
        """Discover and load all geists from the geists directories.

        Loads default geists first (if configured), then custom geists.
        Tracks any geists found on disk but not in config.

        Returns:
            List of newly discovered geist IDs (not in config)
        """
        self.newly_discovered = []

        # Load default geists first
        if self.default_geists_dir and self.default_geists_dir.exists():
            self._load_geists_from_directory(self.default_geists_dir, is_default=True)

        # Load custom geists
        if self.geists_dir.exists():
            self._load_geists_from_directory(self.geists_dir, is_default=False)

        # Seed failure counts / disabled state from persistent storage so a
        # geist disabled in an earlier session stays disabled this session.
        if self.status_store is not None:
            statuses = self.status_store.load()
            for geist_id, status in statuses.items():
                geist = self.geists.get(geist_id)
                if geist is not None:
                    geist.failure_count = status.failure_count
                    if status.disabled:
                        geist.is_enabled = False

        return self.newly_discovered

    def _load_geists_from_directory(self, directory: Path, is_default: bool = False) -> None:
        """Load geists from a specific directory.

        Loads geists in config order if they're in config, alphabetically if not.
        Tracks newly discovered geists (not in config) for addition to config.

        Args:
            directory: Directory containing geist files
            is_default: Whether these are default geists
        """
        # Find all .py files (except __init__.py)
        all_geist_files = {f.stem: f for f in directory.glob("*.py") if f.name != "__init__.py"}

        if self.enabled_defaults:
            # Load geists in config order (preserves user's ordering)
            # Python 3.7+ dicts maintain insertion order
            for geist_id in self.enabled_defaults.keys():
                if not self.enabled_defaults.get(geist_id, True):
                    continue  # Skip disabled geists

                geist_file = all_geist_files.get(geist_id)
                if geist_file is None:
                    continue  # Geist in config but not on disk

                try:
                    self._load_geist(geist_file)
                except Exception as e:
                    self.execution_log.append(
                        {
                            "geist_id": geist_id,
                            "status": "load_error",
                            "error": str(e),
                            "traceback": traceback.format_exc(),
                        }
                    )

        # Load any geists found on disk but not in config (alphabetically)
        # These are "newly discovered" geists that should be added to config
        remaining_geists = sorted(
            geist_id for geist_id in all_geist_files.keys() if geist_id not in self.enabled_defaults
        )
        for geist_id in remaining_geists:
            self.newly_discovered.append(geist_id)
            try:
                self._load_geist(all_geist_files[geist_id])
            except Exception as e:
                self.execution_log.append(
                    {
                        "geist_id": geist_id,
                        "status": "load_error",
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    }
                )

    def _load_geist(self, geist_file: Path) -> None:
        """Load a single geist module.

        Args:
            geist_file: Path to geist Python file

        Raises:
            ImportError: If module cannot be loaded
            AttributeError: If module doesn't have suggest() function
        """
        geist_id = geist_file.stem

        # Check for duplicate IDs
        if geist_id in self.geists:
            existing_path = self.geists[geist_id].path
            raise ValueError(
                f"Duplicate geist ID '{geist_id}'\n"
                f"  Existing: {existing_path}\n"
                f"  New: {geist_file}\n"
                f"  → Rename one of the files to use a unique ID"
            )

        # Load module dynamically
        spec = importlib.util.spec_from_file_location(geist_id, geist_file)
        if spec is None or spec.loader is None:
            raise ImportError(
                f"Could not load module spec for {geist_file}\n"
                f"  → Check for syntax errors: python -m py_compile {geist_file}\n"
                f"  → Validate the geist: geistfabrik validate --geist {geist_id}"
            )

        module = importlib.util.module_from_spec(spec)
        module_key = f"geistfabrik.user_geists.{geist_id}"
        sys.modules[module_key] = module
        spec.loader.exec_module(module)

        # Get suggest function
        if not hasattr(module, "suggest"):
            raise AttributeError(
                f"Geist '{geist_id}' in {geist_file} missing suggest() function\n"
                f"  → Add this function to your geist:\n\n"
                f"  def suggest(vault: VaultContext) -> List[Suggestion]:\n"
                f'      """Generate suggestions."""\n'
                f"      return []"
            )

        suggest_func = getattr(module, "suggest")

        # Store geist metadata
        self.geists[geist_id] = GeistMetadata(id=geist_id, path=geist_file, func=suggest_func)

    def execute_geist(self, geist_id: str, context: VaultContext) -> list[Suggestion]:
        """Execute a single geist with timeout and error handling.

        When verbose mode is enabled, collects detailed profiling information
        including function-level timing data for performance diagnostics.

        Args:
            geist_id: ID of geist to execute
            context: Vault context to pass to geist

        Returns:
            List of suggestions from geist (empty on error)
        """
        if geist_id not in self.geists:
            raise ValueError(f"Unknown geist: {geist_id}")

        geist = self.geists[geist_id]

        # Skip if disabled (e.g. auto-disabled after repeated failures)
        if not geist.is_enabled:
            self.execution_log.append(
                {
                    "geist_id": geist_id,
                    "status": "skipped",
                    "reason": (
                        f"disabled after {geist.failure_count} consecutive failures - "
                        f"run 'geistfabrik test {geist_id} <vault>' to debug and re-enable"
                    ),
                }
            )
            return []

        # Start timing
        start_time = time.perf_counter()
        profiler = None

        # Enable profiling in debug mode
        if self.debug:
            try:
                profiler = cProfile.Profile()
                profiler.enable()
            except Exception as e:
                # Profiling failed - log warning but continue execution
                logger.warning("Failed to enable profiling for %s: %s", geist_id, e)
                profiler = None

        try:
            # Set up timeout (Unix-only)
            if sys.platform != "win32":
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(self.timeout)

            try:
                # Execute geist
                suggestions = geist.func(context)

                # Validate return type
                if not isinstance(suggestions, list):
                    raise TypeError(f"Geist {geist_id} returned {type(suggestions)}, expected list")

                # Validate suggestion types
                for i, suggestion in enumerate(suggestions):
                    if not isinstance(suggestion, Suggestion):
                        raise TypeError(
                            f"Geist {geist_id} suggestion {i} is {type(suggestion)}, "
                            f"expected Suggestion"
                        )

                profile_stats = self._finalize_profiler(profiler, geist_id)

                # Calculate execution time
                end_time = time.perf_counter()
                execution_time = end_time - start_time

                # A successful run clears any accumulated consecutive-failure
                # count (transient failures should not permanently penalise).
                if self.status_store is not None and geist.failure_count > 0:
                    self.status_store.record_success(geist_id)
                    geist.failure_count = 0

                # Log success
                self.execution_log.append(
                    {
                        "geist_id": geist_id,
                        "status": "success",
                        "suggestion_count": len(suggestions),
                    }
                )

                profile = GeistExecutionProfile(
                    geist_id=geist_id,
                    status="success",
                    total_time=execution_time,
                    suggestion_count=len(suggestions),
                    function_stats=profile_stats,
                )
                self.execution_profiles.append(profile)

                # Warn if slow (approaching timeout)
                if execution_time > self.timeout * 0.8:
                    self._warn_slow_geist(geist_id, execution_time)

                return suggestions

            finally:
                # Cancel timeout
                if sys.platform != "win32":
                    signal.alarm(0)

        except GeistTimeoutError:
            profile_stats = self._finalize_profiler(profiler, geist_id)

            profile = GeistExecutionProfile(
                geist_id=geist_id,
                status="timeout",
                total_time=self.timeout,
                function_stats=profile_stats,
                stack_trace=traceback.format_exc(),
            )
            self.execution_profiles.append(profile)

            # Show detailed diagnostic in debug mode
            if self.debug:
                self._show_timeout_diagnostic(geist_id, profile, geist.path)
            else:
                timeout_msg = (
                    f"Execution timed out (>{self.timeout}s)\n"
                    f"  → Test with longer timeout: geistfabrik test {geist_id} <vault>\n"
                    f"  → Check for infinite loops or expensive operations in {geist.path}"
                )
                self._handle_failure(geist_id, "timeout", timeout_msg)

            return []

        except Exception as e:
            self._finalize_profiler(profiler, geist_id, extract_stats=False)

            # Calculate execution time
            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Create error profile
            profile = GeistExecutionProfile(
                geist_id=geist_id,
                status="error",
                total_time=execution_time,
                stack_trace=traceback.format_exc(),
            )
            self.execution_profiles.append(profile)

            error_msg = (
                f"{type(e).__name__}: {str(e)}\n"
                f"  File: {geist.path}\n"
                f"  → Test this geist: geistfabrik test {geist_id} <vault>\n"
                f"  → Validate syntax: geistfabrik validate --geist {geist_id}"
            )
            self._handle_failure(geist_id, "exception", error_msg, traceback.format_exc())
            return []

    def execute_all(self, context: VaultContext) -> dict[str, list[Suggestion]]:
        """Execute all enabled geists in load order.

        Geists execute in the order they were loaded:
        - Default geists: config file order (user-controllable)
        - Custom geists: alphabetical order
        - New defaults not in config: alphabetical order (appended)

        Args:
            context: Vault context to pass to geists

        Returns:
            Dictionary mapping geist IDs to their suggestions
        """
        results = {}

        for geist_id in self.geists.keys():
            suggestions = self.execute_geist(geist_id, context)
            results[geist_id] = suggestions

        return results

    def _handle_failure(
        self,
        geist_id: str,
        error_type: str,
        error_msg: str,
        tb: str | None = None,
    ) -> None:
        """Handle geist execution failure.

        Args:
            geist_id: ID of failed geist
            error_type: Type of error (timeout, exception, etc.)
            error_msg: Error message
            tb: Optional traceback
        """
        geist = self.geists[geist_id]

        # Persist the failure (cross-session consecutive-failure count) when a
        # store is attached; otherwise fall back to the in-memory counter.
        if self.status_store is not None:
            status = self.status_store.record_failure(geist_id, error_msg, self.max_failures)
            geist.failure_count = status.failure_count
            disabled = status.disabled
        else:
            geist.failure_count += 1
            disabled = geist.failure_count >= self.max_failures

        # Log failure
        log_entry: dict[str, Any] = {
            "geist_id": geist_id,
            "status": "error",
            "error_type": error_type,
            "error": error_msg,
            "failure_count": geist.failure_count,
        }
        if tb:
            log_entry["traceback"] = tb

        self.execution_log.append(log_entry)

        # Disable if too many consecutive failures
        if disabled:
            geist.is_enabled = False
            self.execution_log.append(
                {
                    "geist_id": geist_id,
                    "status": "disabled",
                    "reason": f"exceeded {self.max_failures} consecutive failures",
                }
            )

    def get_enabled_geists(self) -> list[str]:
        """Get list of enabled geist IDs.

        Returns:
            List of geist IDs that are currently enabled
        """
        return [gid for gid, g in self.geists.items() if g.is_enabled]

    def get_execution_log(self) -> list[dict[str, Any]]:
        """Get execution log.

        Returns:
            List of execution log entries
        """
        return self.execution_log.copy()

    def get_execution_profiles(self) -> list[GeistExecutionProfile]:
        """Get execution profiles with timing data.

        Only populated when debug mode is enabled.

        Returns:
            List of execution profiles (empty if debug=False)
        """
        return self.execution_profiles.copy()

    def _finalize_profiler(
        self,
        profiler: cProfile.Profile | None,
        geist_id: str,
        extract_stats: bool = True,
    ) -> list[ProfileStats] | None:
        """Stop the profiler and (optionally) extract its stats, best-effort.

        Shared teardown for the success/timeout/error paths (previously
        copy-pasted three times). Profiler failures must never mask the
        geist's own outcome, so everything here swallows-and-logs.

        Args:
            profiler: Active profiler, or None when not in debug mode
            geist_id: Geist being executed (for log messages)
            extract_stats: Whether to extract function-level stats

        Returns:
            ProfileStats list, or None if no profiler/extraction failed/skipped
        """
        if profiler is None:
            return None
        try:
            profiler.disable()
        except Exception:
            # Profiler disable failed - ignore and continue
            pass
        if not extract_stats:
            return None
        try:
            return self._extract_profile_stats(profiler)
        except Exception as e:
            logger.warning("Failed to extract profile stats for %s: %s", geist_id, e)
            return None

    def _extract_profile_stats(self, profiler: cProfile.Profile | None) -> list[ProfileStats]:
        """Extract function-level statistics from profiler.

        Args:
            profiler: cProfile.Profile instance

        Returns:
            List of ProfileStats for top functions by total time
        """
        if not profiler:
            return []

        # Get stats from profiler
        stream = io.StringIO()
        ps = pstats.Stats(profiler, stream=stream)
        ps.strip_dirs()
        ps.sort_stats(pstats.SortKey.TIME)

        # Extract function stats - access via dict-like interface
        stats_list = []
        # Note: mypy doesn't have accurate type info for pstats.Stats.stats
        # We use type: ignore to bypass the check
        for func, (cc, nc, tt, ct, callers) in ps.stats.items():  # type: ignore[attr-defined]
            # Format function name
            filename, line, func_name = func
            if filename.startswith("<"):
                # Built-in or special
                name = func_name
            else:
                # Show module.function for clarity
                name = f"{filename}:{func_name}"

            stats_list.append(
                ProfileStats(
                    name=name,
                    calls=nc,  # primitive call count
                    total_time=tt,
                    cumulative_time=ct,
                    per_call=tt / nc if nc > 0 else 0,
                )
            )

        # Sort by total time and return top 20
        stats_list.sort(key=lambda x: x.total_time, reverse=True)
        return stats_list[:20]

    def _warn_slow_geist(self, geist_id: str, execution_time: float) -> None:
        """Warn about geists approaching timeout threshold.

        Args:
            geist_id: ID of the slow geist
            execution_time: Execution time in seconds
        """
        pct = (execution_time / self.timeout) * 100
        logger.warning(
            "%s completed in %.3fs (%.0f%% of timeout)",
            geist_id,
            execution_time,
            pct,
        )
        if not self.debug:
            logger.info("Run with --debug for detailed performance breakdown")

    def _show_timeout_diagnostic(
        self, geist_id: str, profile: GeistExecutionProfile, geist_path: Path
    ) -> None:
        """Show detailed timeout diagnostic in verbose mode.

        Args:
            geist_id: ID of timed-out geist
            profile: Execution profile with timing data
            geist_path: Path to geist file
        """
        logger.warning("%s timed out after %.3fs", geist_id, self.timeout)

        if profile.function_stats:
            # Show top time-consuming functions
            logger.info("Top expensive operations:")
            total_accounted = 0.0
            for i, stats in enumerate(profile.function_stats[:10], 1):
                pct = (stats.total_time / self.timeout) * 100
                total_accounted += stats.total_time

                # Simplify name for display
                name = stats.name
                if "vault_context.py:" in name:
                    name = f"vault.{name.split(':')[-1]}"
                elif ".py:" in name:
                    # Show just module:function
                    parts = name.split("/")
                    if len(parts) > 0:
                        module_func = parts[-1]
                        name = module_func

                logger.info(
                    "  %d. %s - %.3fs (%.1f%%) - %d calls",
                    i,
                    name,
                    stats.total_time,
                    pct,
                    stats.calls,
                )

            # Show percentage accounted for
            pct_accounted = (total_accounted / self.timeout) * 100
            logger.info(
                "Total accounted: %.3fs (%.1f%%)",
                total_accounted,
                pct_accounted,
            )

        # Generate and show smart suggestions
        logger.info("Suggestions:")
        suggestions = self._generate_suggestions(geist_id, profile)
        for suggestion in suggestions:
            logger.info("  -> %s", suggestion)

    def _generate_suggestions(self, geist_id: str, profile: GeistExecutionProfile) -> list[str]:
        """Generate actionable suggestions based on execution profile.

        Args:
            geist_id: ID of the geist
            profile: Execution profile

        Returns:
            List of actionable suggestion strings
        """
        suggestions = []

        if not profile.function_stats:
            suggestions.append("Run with --debug for detailed performance breakdown")
            suggestions.append(
                f"Test with longer timeout: geistfabrik test {geist_id} <vault> --timeout 10"
            )
            return suggestions

        # Analyze function stats for common patterns
        function_names = [s.name for s in profile.function_stats]

        # Pattern 1: Expensive clustering
        if any("HDBSCAN" in name or "hdbscan" in name.lower() for name in function_names):
            clustering_time = sum(
                s.total_time
                for s in profile.function_stats
                if "HDBSCAN" in s.name or "hdbscan" in s.name.lower()
            )
            suggestions.append(
                f"HDBSCAN clustering took {clustering_time:.1f}s - "
                "consider caching results or reducing min_size"
            )

        # Pattern 2: Many semantic searches
        search_calls = sum(
            s.calls
            for s in profile.function_stats
            if "semantic_search" in s.name or "search" in s.name.lower()
        )
        if search_calls > 10:
            suggestions.append(
                f"{search_calls} search operations - consider batching or limiting query count"
            )

        # Pattern 3: Processing all notes
        if any("all_notes" in name.lower() for name in function_names):
            all_notes_time = sum(
                s.total_time for s in profile.function_stats if "all_notes" in s.name.lower()
            )
            if all_notes_time > 1.0:
                suggestions.append(
                    f"Processing all notes took {all_notes_time:.1f}s - "
                    "consider using queries or sampling"
                )

        # Pattern 4: get_clusters performance
        if any("get_clusters" in name.lower() for name in function_names):
            cluster_time = sum(
                s.total_time for s in profile.function_stats if "get_clusters" in s.name.lower()
            )
            suggestions.append(
                f"get_clusters took {cluster_time:.1f}s - clustering is expensive, "
                "consider caching or reducing vault size"
            )

        # Generic suggestions
        suggestions.append(
            f"Test with longer timeout: geistfabrik test {geist_id} <vault> --timeout 10 --debug"
        )

        return suggestions
