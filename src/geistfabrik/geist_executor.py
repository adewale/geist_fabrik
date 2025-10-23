"""Geist execution system - loads and runs code geists."""

import importlib.util
import signal
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import Suggestion
from .vault_context import VaultContext


@dataclass
class GeistMetadata:
    """Metadata about a loaded geist."""

    id: str
    path: Path
    func: Callable[[VaultContext], List[Suggestion]]
    failure_count: int = 0
    is_enabled: bool = True


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
        timeout: int = 5,
        max_failures: int = 3,
        default_geists_dir: Optional[Path] = None,
        enabled_defaults: Optional[Dict[str, bool]] = None,
    ):
        """Initialize geist executor.

        Args:
            geists_dir: Directory containing custom geist modules
            timeout: Execution timeout in seconds
            max_failures: Number of failures before disabling geist
            default_geists_dir: Directory containing default geists (optional)
            enabled_defaults: Dictionary of default geist enabled states (optional)
        """
        self.geists_dir = geists_dir
        self.timeout = timeout
        self.max_failures = max_failures
        self.default_geists_dir = default_geists_dir
        self.enabled_defaults = enabled_defaults or {}
        self.geists: Dict[str, GeistMetadata] = {}
        self.execution_log: List[Dict[str, Any]] = []

    def load_geists(self) -> None:
        """Discover and load all geists from the geists directories.

        Loads default geists first (if configured), then custom geists.
        """
        # Load default geists first
        if self.default_geists_dir and self.default_geists_dir.exists():
            self._load_geists_from_directory(self.default_geists_dir, is_default=True)

        # Load custom geists
        if self.geists_dir.exists():
            self._load_geists_from_directory(self.geists_dir, is_default=False)

    def _load_geists_from_directory(self, directory: Path, is_default: bool = False) -> None:
        """Load geists from a specific directory.

        Args:
            directory: Directory containing geist files
            is_default: Whether these are default geists
        """
        # Find all .py files (except __init__.py)
        geist_files = [f for f in directory.glob("*.py") if f.name != "__init__.py"]

        for geist_file in geist_files:
            geist_id = geist_file.stem

            # For default geists, check if they're enabled in config
            if is_default and not self.enabled_defaults.get(geist_id, True):
                continue  # Skip disabled default geists

            try:
                self._load_geist(geist_file)
            except Exception as e:
                # Log error but continue loading other geists
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
            raise ValueError(f"Duplicate geist ID: {geist_id}")

        # Load module dynamically
        spec = importlib.util.spec_from_file_location(geist_id, geist_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module spec for {geist_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[geist_id] = module
        spec.loader.exec_module(module)

        # Get suggest function
        if not hasattr(module, "suggest"):
            raise AttributeError(f"Geist {geist_id} missing suggest() function")

        suggest_func = getattr(module, "suggest")

        # Store geist metadata
        self.geists[geist_id] = GeistMetadata(id=geist_id, path=geist_file, func=suggest_func)

    def execute_geist(self, geist_id: str, context: VaultContext) -> List[Suggestion]:
        """Execute a single geist with timeout and error handling.

        Args:
            geist_id: ID of geist to execute
            context: Vault context to pass to geist

        Returns:
            List of suggestions from geist (empty on error)
        """
        if geist_id not in self.geists:
            raise ValueError(f"Unknown geist: {geist_id}")

        geist = self.geists[geist_id]

        # Skip if disabled
        if not geist.is_enabled:
            self.execution_log.append(
                {"geist_id": geist_id, "status": "skipped", "reason": "disabled"}
            )
            return []

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

                # Log success
                self.execution_log.append(
                    {
                        "geist_id": geist_id,
                        "status": "success",
                        "suggestion_count": len(suggestions),
                    }
                )

                return suggestions

            finally:
                # Cancel timeout
                if sys.platform != "win32":
                    signal.alarm(0)

        except GeistTimeoutError:
            self._handle_failure(geist_id, "timeout", "Execution timed out")
            return []

        except Exception as e:
            self._handle_failure(geist_id, "exception", str(e), traceback.format_exc())
            return []

    def execute_all(self, context: VaultContext) -> Dict[str, List[Suggestion]]:
        """Execute all enabled geists.

        Args:
            context: Vault context to pass to geists

        Returns:
            Dictionary mapping geist IDs to their suggestions
        """
        results = {}

        for geist_id in self.geists:
            suggestions = self.execute_geist(geist_id, context)
            results[geist_id] = suggestions

        return results

    def _handle_failure(
        self,
        geist_id: str,
        error_type: str,
        error_msg: str,
        tb: Optional[str] = None,
    ) -> None:
        """Handle geist execution failure.

        Args:
            geist_id: ID of failed geist
            error_type: Type of error (timeout, exception, etc.)
            error_msg: Error message
            tb: Optional traceback
        """
        geist = self.geists[geist_id]
        geist.failure_count += 1

        # Log failure
        log_entry: Dict[str, Any] = {
            "geist_id": geist_id,
            "status": "error",
            "error_type": error_type,
            "error": error_msg,
            "failure_count": geist.failure_count,
        }
        if tb:
            log_entry["traceback"] = tb

        self.execution_log.append(log_entry)

        # Disable if too many failures
        if geist.failure_count >= self.max_failures:
            geist.is_enabled = False
            self.execution_log.append(
                {
                    "geist_id": geist_id,
                    "status": "disabled",
                    "reason": f"exceeded {self.max_failures} failures",
                }
            )

    def get_enabled_geists(self) -> List[str]:
        """Get list of enabled geist IDs.

        Returns:
            List of geist IDs that are currently enabled
        """
        return [gid for gid, g in self.geists.items() if g.is_enabled]

    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Get execution log.

        Returns:
            List of execution log entries
        """
        return self.execution_log.copy()
