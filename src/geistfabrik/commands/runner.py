"""Test command for testing a single geist in isolation."""

from pathlib import Path

from ..geist_executor import GeistExecutor
from ..models import Suggestion
from ..tracery import TraceryGeist, TraceryGeistLoader
from .base import BaseCommand, ExecutionContext


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

        # Get default geists directories
        package_dir = Path(__file__).parent.parent
        default_code_geists_dir = package_dir / "default_geists" / "code"
        default_tracery_geists_dir = package_dir / "default_geists" / "tracery"

        # Load code geists
        code_geists_dir = exec_ctx.vault_path / "_geistfabrik" / "geists" / "code"
        executor = GeistExecutor(
            code_geists_dir,
            timeout=self.args.timeout,
            max_failures=3,
            default_geists_dir=default_code_geists_dir,
            debug=getattr(self.args, "debug", False),
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
        tracery_geists_map = {g.geist_id: g for g in tracery_geists}

        # Check if geist exists in either code or Tracery
        is_code_geist = geist_id in executor.geists
        is_tracery_geist = geist_id in tracery_geists_map

        if not is_code_geist and not is_tracery_geist:
            self.print_error(f"Geist '{geist_id}' not found")
            print("\nAvailable geists:")
            print("  Code geists:")
            for gid in sorted(executor.geists.keys()):
                print(f"    - {gid}")
            print("  Tracery geists:")
            for gid in sorted(tracery_geists_map.keys()):
                print(f"    - {gid}")
            return 1

        # Execute the geist
        self._print_execution_header(geist_id)

        if is_code_geist:
            suggestions = executor.execute_geist(geist_id, exec_ctx.vault_context)
            # Display results
            self._display_results(suggestions)
            # Display execution summary (code geists only have profiling)
            self._display_code_summary(executor, geist_id)
        else:
            tracery_geist = tracery_geists_map[geist_id]
            suggestions = self._execute_tracery_geist(tracery_geist, exec_ctx)
            # Display results
            self._display_results(suggestions)
            # Display Tracery-specific summary
            self._display_tracery_summary(suggestions)

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

    def _execute_tracery_geist(
        self,
        tracery_geist: TraceryGeist,
        exec_ctx: ExecutionContext,
    ) -> list[Suggestion]:
        """Execute a Tracery geist and return suggestions.

        Args:
            tracery_geist: The Tracery geist to execute
            exec_ctx: Execution context

        Returns:
            List of suggestions from the geist
        """
        try:
            return tracery_geist.suggest(exec_ctx.vault_context)
        except Exception as e:
            self.print_error(f"Executing Tracery geist {tracery_geist.geist_id}: {e}")
            return []

    def _display_code_summary(self, executor: GeistExecutor, geist_id: str) -> None:
        """Display execution summary with timing and status for code geists.

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

    def _display_tracery_summary(
        self,
        suggestions: list[Suggestion],
    ) -> None:
        """Display execution summary for Tracery geists.

        Args:
            suggestions: Suggestions generated by the geist
        """
        print("Status: Success")
        print("  Type: Tracery geist")
        print(f"  Suggestions: {len(suggestions)}")
        print(f"\n{'=' * 60}\n")
