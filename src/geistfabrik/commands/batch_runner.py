"""Test-all command for testing all geists and reporting results."""

from dataclasses import dataclass
from pathlib import Path

from ..geist_executor import GeistExecutor
from ..geist_status import GeistStatusStore
from ..tracery import TraceryGeistLoader
from .base import BaseCommand, ExecutionContext


@dataclass
class TestResult:
    """Result of testing a single geist."""

    status: str
    count: int = 0
    error: str | None = None
    geist_id: str | None = None


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

        # Reject malformed dates before database creation, sync, or plugin load.
        session_date = self.parse_session_date(getattr(self.args, "date", None))
        if session_date is None:
            return 1

        # Set up command context
        cmd_ctx = self.setup_command_context(vault_path)
        if cmd_ctx is None:
            return 1

        # Sync vault
        note_count = cmd_ctx.vault.sync()
        self.print_verbose(f"Loaded {note_count} notes")

        self.print_verbose(f"Session date: {session_date.strftime('%Y-%m-%d')}")

        # Set up execution context
        exec_ctx = self.setup_execution_context(cmd_ctx, session_date)

        # Get default geists directories
        package_dir = Path(__file__).parent.parent
        default_code_geists_dir = package_dir / "default_geists" / "code"
        default_tracery_geists_dir = package_dir / "default_geists" / "tracery"

        # Load code geists
        code_geists_dir = exec_ctx.vault_path / "_geistfabrik" / "geists" / "code"
        executor = GeistExecutor(
            code_geists_dir,
            timeout=self.resolve_timeout(exec_ctx.config),
            max_failures=self.resolve_max_failures(exec_ctx.config),
            default_geists_dir=default_code_geists_dir,
            debug=getattr(self.args, "debug", False),
            status_store=GeistStatusStore(exec_ctx.vault.db),
        )
        executor.load_geists()

        # Load Tracery geists
        tracery_geists_dir = exec_ctx.vault_path / "_geistfabrik" / "geists" / "tracery"
        seed = int(session_date.timestamp())
        tracery_loader = TraceryGeistLoader(
            tracery_geists_dir,
            seed=seed,
            default_geists_dir=default_tracery_geists_dir,
        )
        tracery_geists, _ = tracery_loader.load_all()
        timeout = self.resolve_timeout(exec_ctx.config)
        for geist in tracery_geists:
            if geist.geist_id in executor.geists:
                tracery_loader.load_errors.append(
                    {
                        "geist_id": geist.geist_id,
                        "path": str(geist.yaml_path),
                        "error": f"Duplicate code/Tracery geist ID '{geist.geist_id}'",
                    }
                )
                continue
            geist.execution_timeout = timeout
            executor.register_geist(geist.geist_id, geist.yaml_path, geist.suggest)
        executor.load_status()

        total_geists = len(executor.geists)
        load_errors = [
            entry for entry in executor.get_execution_log() if entry["status"] == "load_error"
        ] + tracery_loader.load_errors
        if total_geists == 0 and not load_errors:
            print("\nNo geists found to test")
            return 0

        # Test all geists
        results = self._test_all_geists(executor, exec_ctx)
        for entry in load_errors:
            geist_id = entry["geist_id"]
            key = f"{geist_id} ({entry['path']})"
            results[key] = TestResult(
                status="error", error=f"Load failed: {entry['error']}", geist_id=geist_id
            )

        # Print summary
        return self._print_summary(results, exec_ctx.vault_path)

    def _test_all_geists(
        self,
        executor: GeistExecutor,
        exec_ctx: ExecutionContext,
    ) -> dict[str, TestResult]:
        """Test every registered code and Tracery geist and collect results.

        Args:
            executor: The geist executor
            exec_ctx: Execution context

        Returns:
            Dictionary mapping geist ID to test result
        """
        if not executor.geists:
            return {}

        print(f"\n{'=' * 60}")
        print(f"Testing {len(executor.geists)} geists")
        print(f"{'=' * 60}\n")

        results: dict[str, TestResult] = {}

        for geist_id in sorted(executor.geists.keys()):
            print(f"Testing {geist_id}...", end=" ")
            # test-all is a diagnostic/recovery command: persisted disablement
            # must not conceal whether the current implementation is healthy.
            suggestions = executor.execute_geist(
                geist_id, exec_ctx.vault_context, allow_disabled=True
            )

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
                print("x Missing execution profile")
                results[geist_id] = TestResult(status="error", error="Missing execution profile")

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
                    print(
                        f"    Test with: geistfabrik test {result.geist_id or geist_id} "
                        f"{vault_path}"
                    )

        print(f"\n{'=' * 60}\n")

        return 0 if errors == 0 else 1
