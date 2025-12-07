"""Test command for testing a single geist in isolation."""

from pathlib import Path

from ..geist_executor import GeistExecutor
from ..models import Suggestion
from .base import BaseCommand


class TestCommand(BaseCommand):
    """Command to test a single geist in isolation.

    Useful for debugging and developing geists.
    """

    def execute(self) -> int:
        """Execute the test command.

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

        geist_id = self.args.geist_id
        self.print_verbose(f"Testing geist '{geist_id}' in vault: {vault_path}\n")

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

        # Load geists (both custom and default)
        geists_dir = exec_ctx.vault_path / "_geistfabrik" / "geists" / "code"

        # Get default geists directory
        package_dir = Path(__file__).parent.parent
        default_geists_dir = package_dir / "default_geists" / "code"

        executor = GeistExecutor(
            geists_dir,
            timeout=self.args.timeout,
            max_failures=3,
            default_geists_dir=default_geists_dir,
            debug=getattr(self.args, "debug", False),
        )
        executor.load_geists()

        # Check if geist exists
        if geist_id not in executor.geists:
            self.print_error(f"Geist '{geist_id}' not found")
            print("\nAvailable geists:")
            for gid in sorted(executor.geists.keys()):
                print(f"  - {gid}")
            return 1

        # Execute the geist
        self._print_execution_header(geist_id)
        suggestions = executor.execute_geist(geist_id, exec_ctx.vault_context)

        # Display results
        self._display_results(suggestions)

        # Display execution summary
        self._display_summary(executor, geist_id)

        return 0

    def _print_execution_header(self, geist_id: str) -> None:
        """Print the execution header.

        Args:
            geist_id: ID of the geist being tested
        """
        print(f"\n{'=' * 60}")
        print(f"Executing geist: {geist_id}")
        print(f"{'=' * 60}\n")

    def _display_results(self, suggestions: list[Suggestion]) -> None:
        """Display test results.

        Args:
            suggestions: List of suggestions from the geist
        """
        if not suggestions:
            print("No suggestions generated")
        else:
            print(f"Generated {len(suggestions)} suggestion(s):\n")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion.text}")
                if suggestion.notes:
                    note_refs = ", ".join(f"[[{note}]]" for note in suggestion.notes)
                    print(f"   Notes: {note_refs}")
                if suggestion.title:
                    print(f"   Suggested title: {suggestion.title}")
                print()

    def _display_summary(self, executor: GeistExecutor, geist_id: str) -> None:
        """Display execution summary with timing and status.

        Args:
            executor: The geist executor
            geist_id: ID of the tested geist
        """
        profiles = executor.get_execution_profiles()
        for profile in profiles:
            if profile.geist_id == geist_id:
                if profile.status == "success":
                    print("Status: Success")
                    print(f"  Execution time: {profile.total_time:.3f}s")

                    # Show profiling details in debug mode
                    if getattr(self.args, "debug", False) and profile.function_stats:
                        print("\n  Top 5 operations:")
                        for i, stats in enumerate(profile.function_stats[:5], 1):
                            pct = (
                                (stats.total_time / profile.total_time) * 100
                                if profile.total_time > 0
                                else 0
                            )
                            name = stats.name.split(":")[-1] if ":" in stats.name else stats.name
                            print(f"    {i}. {name} - {stats.total_time:.3f}s ({pct:.1f}%)")
                else:
                    print(f"Status: {profile.status}")
                    log = executor.get_execution_log()
                    for entry in log:
                        if entry["geist_id"] == geist_id and "error" in entry:
                            print(f"  Error: {entry['error']}")
                            break

        print(f"\n{'=' * 60}\n")
