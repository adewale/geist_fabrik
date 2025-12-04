"""Test-all command for testing all geists and reporting results."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..geist_executor import GeistExecutor
from .base import BaseCommand, ExecutionContext


@dataclass
class TestResult:
    """Result of testing a single geist."""

    status: str
    count: int = 0
    error: Optional[str] = None


class TestAllCommand(BaseCommand):
    """Command to test all geists and report results.

    Runs all geists in the vault and provides a summary of successes and failures.
    """

    def execute(self) -> int:
        """Execute the test-all command.

        Returns:
            Exit code (0 for success, 1 for error)
        """
        # Get and validate vault path
        vault_path = self.get_vault_path()
        if vault_path is None:
            return 1

        # Check if GeistFabrik is initialised
        if not self.validate_geistfabrik_initialised(vault_path):
            return 1

        print(f"Testing all geists in vault: {vault_path}\n")

        # Set up command context
        cmd_ctx = self.setup_command_context(vault_path)
        if cmd_ctx is None:
            return 1

        # Sync vault
        note_count = cmd_ctx.vault.sync()
        self.print_verbose(f"Loaded {note_count} notes")

        # Parse session date
        session_date = self.parse_session_date(getattr(self.args, "date", None))
        if session_date is None:
            return 1

        self.print_verbose(f"Session date: {session_date.strftime('%Y-%m-%d')}")

        # Set up execution context
        exec_ctx = self.setup_execution_context(cmd_ctx, session_date)

        # Load geists
        geists_dir = exec_ctx.vault_path / "_geistfabrik" / "geists" / "code"
        if not geists_dir.exists():
            self.print_error(f"No geists directory found at {geists_dir}")
            return 1

        executor = GeistExecutor(
            geists_dir,
            timeout=self.args.timeout,
            max_failures=3,
            debug=getattr(self.args, "debug", False),
        )
        executor.load_geists()

        if not executor.geists:
            print("\nNo code geists found to test")
            return 0

        # Test all geists
        results = self._test_all_geists(executor, exec_ctx)

        # Print summary
        return self._print_summary(results, exec_ctx.vault_path)

    def _test_all_geists(
        self,
        executor: GeistExecutor,
        exec_ctx: ExecutionContext,
    ) -> dict[str, TestResult]:
        """Test all geists and collect results.

        Args:
            executor: The geist executor
            exec_ctx: Execution context

        Returns:
            Dictionary mapping geist ID to test result
        """
        print(f"\n{'=' * 60}")
        print(f"Testing {len(executor.geists)} geists")
        print(f"{'=' * 60}\n")

        results: dict[str, TestResult] = {}

        for geist_id in sorted(executor.geists.keys()):
            print(f"Testing {geist_id}...", end=" ")
            suggestions = executor.execute_geist(geist_id, exec_ctx.vault_context)

            # Get profile for timing info
            profile = None
            for p in executor.get_execution_profiles():
                if p.geist_id == geist_id:
                    profile = p
                    break

            if profile:
                if profile.status == "success":
                    print(f"v ({len(suggestions)} suggestions, {profile.total_time:.3f}s)")
                    results[geist_id] = TestResult(
                        status="success",
                        count=len(suggestions),
                    )
                else:
                    # Get error details from execution log
                    error_msg = profile.status
                    for entry in executor.get_execution_log():
                        if entry["geist_id"] == geist_id and "error" in entry:
                            error_msg = entry["error"]
                            break
                    print(f"x {error_msg}")
                    results[geist_id] = TestResult(
                        status="error",
                        error=error_msg,
                    )
            else:
                print("? Unknown status")
                results[geist_id] = TestResult(status="unknown")

        return results

    def _print_summary(
        self,
        results: dict[str, TestResult],
        vault_path: Path,
    ) -> int:
        """Print test summary and return exit code.

        Args:
            results: Test results
            vault_path: Path to the vault

        Returns:
            Exit code (0 if all passed, 1 if any failed)
        """
        print(f"\n{'=' * 60}")
        print("Summary")
        print(f"{'=' * 60}")

        success = sum(1 for r in results.values() if r.status == "success")
        errors = sum(1 for r in results.values() if r.status == "error")
        total = len(results)

        print(f"Total: {total} geists")
        print(f"Success: {success} ({success * 100 // total if total > 0 else 0}%)")
        print(f"Errors: {errors}")

        if errors > 0:
            print("\nFailed geists:")
            for geist_id, result in results.items():
                if result.status == "error":
                    print(f"  x {geist_id}: {result.error or 'Unknown error'}")
                    print(f"    Test with: geistfabrik test {geist_id} {vault_path}")

        print(f"\n{'=' * 60}\n")

        return 0 if errors == 0 else 1
