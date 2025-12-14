"""Invoke command for running geists and generating suggestions."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config_loader import GeistFabrikConfig, save_config
from ..embeddings import EmbeddingComputer
from ..filtering import SuggestionFilter, select_suggestions
from ..geist_executor import GeistExecutor
from ..journal_writer import JournalWriter
from ..models import Suggestion
from ..tracery import TraceryGeist, TraceryGeistLoader
from ..vault import Vault
from .base import BaseCommand, ExecutionContext


@dataclass
class GeistResults:
    """Results from geist execution."""

    code_results: dict[str, list[Suggestion]]
    tracery_results: dict[str, list[Suggestion]]
    all_suggestions: list[Suggestion]


class InvokeCommand(BaseCommand):
    """Command to run geists and generate suggestions.

    Supports multiple modes:
    - Default: Run all geists, filter, sample ~5 suggestions
    - Single geist: --geist <id>
    - Multiple geists: --geists <id1>,<id2>
    - Full mode: --full (all filtered suggestions)
    - Raw mode: --no-filter (skip filtering)
    """

    def execute(self) -> int:
        """Execute the invoke command.

        Returns:
            Exit code (0 for success, 1 for error)
        """
        # Validate arguments
        if not self._validate_args():
            return 1

        # Get and validate vault path
        vault_path = self.get_vault_path()
        if vault_path is None:
            return 1

        self.print(f"Loading vault: {vault_path}")

        # Set up database
        geistfabrik_dir = vault_path / "_geistfabrik"
        geistfabrik_dir.mkdir(exist_ok=True)
        db_path = geistfabrik_dir / "vault.db"

        # Load vault and sync
        self._vault = Vault(vault_path, db_path)
        note_count = self._vault.sync()
        self.print(f"Synced {note_count} notes")

        # Parse session date
        session_date = self.parse_session_date(getattr(self.args, "date", None))
        if session_date is None:
            return 1

        # Set up command context
        cmd_ctx = self.setup_command_context(vault_path)
        if cmd_ctx is None:
            return 1

        # Set up execution context (session, VaultContext)
        exec_ctx = self.setup_execution_context(cmd_ctx, session_date)

        # Load geists
        code_executor, tracery_geists, newly_discovered = self._load_geists(
            exec_ctx, session_date
        )

        # Handle newly discovered geists
        self._handle_new_geists(exec_ctx, newly_discovered)

        # Check if any geists are enabled
        total_geists = len(code_executor.geists) + len(tracery_geists)
        if total_geists == 0:
            self._print_no_geists_message(exec_ctx)
            return 0

        # Show configuration summary
        self._print_config_summary(exec_ctx, code_executor, tracery_geists)

        # Execute geists
        results = self._execute_geists(exec_ctx, code_executor, tracery_geists)
        if results is None:
            return 1

        # Show execution summary
        self._print_execution_summary(results)

        self.print(f"Generated {len(results.all_suggestions)} raw suggestions")

        # Filter suggestions
        filtered = self._filter_suggestions(results.all_suggestions, session_date)

        # Select final suggestions
        final = self._select_final_suggestions(filtered, session_date)

        # Handle --diff mode
        if self.args.diff:
            self._show_diff(exec_ctx, final)

        # Write to journal if requested
        if self.args.write:
            if not self._write_journal(exec_ctx, session_date, final):
                return 1

        # Display results
        self._display_results(session_date, final)

        # Show debug info if requested
        if self.args.debug and code_executor:
            self._show_debug_profiles(code_executor)

        # Show execution log for errors
        if code_executor:
            self._show_execution_errors(code_executor)

        return 0

    def _validate_args(self) -> bool:
        """Validate command arguments for conflicts.

        Returns:
            True if valid, False otherwise
        """
        if self.quiet and self.verbose:
            self.print_error("Cannot use both --quiet and --verbose")
            return False

        if self.args.geist and self.args.geists:
            self.print_error("Cannot use both --geist and --geists")
            return False

        return True

    def _load_geists(
        self,
        exec_ctx: ExecutionContext,
        session_date: datetime,
    ) -> tuple[GeistExecutor, list[TraceryGeist], list[str]]:
        """Load code and Tracery geists.

        Args:
            exec_ctx: Execution context
            session_date: Session date for Tracery seed

        Returns:
            Tuple of (code_executor, tracery_geists, newly_discovered_ids)
        """
        config = exec_ctx.config
        vault_path = exec_ctx.vault_path

        # Get default geists directories
        package_dir = Path(__file__).parent.parent
        default_code_geists_dir = package_dir / "default_geists" / "code"
        default_tracery_geists_dir = package_dir / "default_geists" / "tracery"

        # Load code geists
        code_geists_dir = vault_path / "_geistfabrik" / "geists" / "code"
        code_executor = GeistExecutor(
            code_geists_dir,
            timeout=self.args.timeout,
            max_failures=3,
            default_geists_dir=default_code_geists_dir,
            enabled_defaults=config.default_geists if config else {},
            debug=self.args.debug,
        )
        newly_discovered_code = code_executor.load_geists()

        # Load Tracery geists
        tracery_geists_dir = vault_path / "_geistfabrik" / "geists" / "tracery"
        seed = int(session_date.timestamp())
        tracery_loader = TraceryGeistLoader(
            tracery_geists_dir,
            seed=seed,
            default_geists_dir=default_tracery_geists_dir,
            enabled_defaults=config.default_geists if config else {},
        )
        tracery_geists, newly_discovered_tracery = tracery_loader.load_all()

        newly_discovered = newly_discovered_code + newly_discovered_tracery
        return code_executor, tracery_geists, newly_discovered

    def _handle_new_geists(
        self,
        exec_ctx: ExecutionContext,
        newly_discovered: list[str],
    ) -> None:
        """Add newly discovered geists to config.

        Args:
            exec_ctx: Execution context
            newly_discovered: List of newly discovered geist IDs
        """
        if newly_discovered and exec_ctx.config:
            for geist_id in newly_discovered:
                exec_ctx.config.default_geists[geist_id] = True
            save_config(exec_ctx.config, exec_ctx.config_path)
            geist_list = ", ".join(newly_discovered)
            self.print(f"Added {len(newly_discovered)} new geist(s) to config: {geist_list}")

    def _print_no_geists_message(self, exec_ctx: ExecutionContext) -> None:
        """Print message when no geists are enabled."""
        self.print("\nNo geists are enabled.")
        self.print("Default geists ship with GeistFabrik but may be disabled in config.")
        config_rel = exec_ctx.config_path.relative_to(exec_ctx.vault_path)
        self.print(f"Check {config_rel} to enable default geists.")

    def _print_config_summary(
        self,
        exec_ctx: ExecutionContext,
        code_executor: GeistExecutor,
        tracery_geists: list[TraceryGeist],
    ) -> None:
        """Print configuration summary."""
        if self.quiet and not self.verbose:
            return

        vault_path = exec_ctx.vault_path
        code_geists_count = len(code_executor.geists)
        enabled_code_geists = code_executor.get_enabled_geists()
        all_code_ids = list(code_executor.geists.keys())
        disabled_geists = [gid for gid in all_code_ids if gid not in enabled_code_geists]

        total_geists = code_geists_count + len(tracery_geists)
        enabled_count = len(enabled_code_geists) + len(tracery_geists)

        print(f"\n{'=' * 60}")
        print("GeistFabrik Configuration Audit")
        print(f"{'=' * 60}")
        print(f"Vault: {vault_path}")
        print(f"Geists directory: {vault_path / '_geistfabrik' / 'geists'}")
        print(f"Total geists found: {total_geists}")
        print(f"  - Code geists: {code_geists_count} ({len(enabled_code_geists)} enabled)")
        print(f"  - Tracery geists: {len(tracery_geists)}")
        if disabled_geists:
            print(f"  - Disabled: {len(disabled_geists)} ({', '.join(disabled_geists)})")

        filtering_status = (
            "DISABLED (--no-filter)" if self.args.no_filter else "ENABLED (4-stage pipeline)"
        )
        print(f"Filtering: {filtering_status}")

        sampling_status = (
            "DISABLED (--full or --no-filter)"
            if (self.args.full or self.args.no_filter)
            else f"ENABLED (count={self.args.count})"
        )
        print(f"Sampling: {sampling_status}")

        if self.args.no_filter:
            mode = "Raw output"
        elif self.args.full:
            mode = "Filtered output"
        else:
            mode = "Default"
        print(f"Mode: {mode}")
        print(f"{'=' * 60}\n")

        # Print execution message
        geists_to_run = self._get_geists_to_run()
        actual_count = len(geists_to_run) if geists_to_run else enabled_count
        geist_word = "geist" if actual_count == 1 else "geists"
        self.print(f"Executing {actual_count} {geist_word}...")

    def _get_geists_to_run(self) -> list[str] | None:
        """Get list of specific geists to run, or None for all."""
        if self.args.geist:
            return [self.args.geist]
        elif self.args.geists:
            return [g.strip() for g in self.args.geists.split(",")]
        return None

    def _execute_geists(
        self,
        exec_ctx: ExecutionContext,
        code_executor: GeistExecutor,
        tracery_geists: list[TraceryGeist],
    ) -> GeistResults | None:
        """Execute geists and collect results.

        Args:
            exec_ctx: Execution context
            code_executor: Code geist executor
            tracery_geists: List of Tracery geists

        Returns:
            GeistResults, or None on error
        """
        context = exec_ctx.vault_context
        config = exec_ctx.config
        geists_to_run = self._get_geists_to_run()

        code_results: dict[str, list[Suggestion]] = {}
        tracery_results: dict[str, list[Suggestion]] = {}

        if geists_to_run:
            # Run specific geist(s)
            for geist_id in geists_to_run:
                if geist_id in code_executor.geists:
                    code_results[geist_id] = code_executor.execute_geist(geist_id, context)
                elif any(g.geist_id == geist_id for g in tracery_geists):
                    tracery_geist = next(g for g in tracery_geists if g.geist_id == geist_id)
                    try:
                        suggestions = tracery_geist.suggest(context)
                        tracery_results[geist_id] = suggestions
                    except Exception as e:
                        self.print_error(f"Executing Tracery geist {geist_id}: {e}")
                        tracery_results[geist_id] = []
                else:
                    self.print_error(f"Geist '{geist_id}' not found")
                    return None
        else:
            # Execute all code geists
            code_results = code_executor.execute_all(context)

            # Execute all Tracery geists
            for tracery_geist in tracery_geists:
                try:
                    suggestions = tracery_geist.suggest(context)
                    tracery_results[tracery_geist.geist_id] = suggestions
                except Exception as e:
                    self.print_error(
                        f"Executing Tracery geist {tracery_geist.geist_id}: {e}"
                    )
                    tracery_results[tracery_geist.geist_id] = []

        # Collect all suggestions in config order
        all_suggestions = self._collect_suggestions_in_order(
            code_results, tracery_results, config
        )

        return GeistResults(
            code_results=code_results,
            tracery_results=tracery_results,
            all_suggestions=all_suggestions,
        )

    def _collect_suggestions_in_order(
        self,
        code_results: dict[str, list[Suggestion]],
        tracery_results: dict[str, list[Suggestion]],
        config: GeistFabrikConfig | None,
    ) -> list[Suggestion]:
        """Collect suggestions respecting config order.

        Args:
            code_results: Results from code geists
            tracery_results: Results from Tracery geists
            config: Configuration object

        Returns:
            List of suggestions in order
        """
        all_suggestions: list[Suggestion] = []
        all_results = {**code_results, **tracery_results}

        if config and config.default_geists:
            # First: geists in config order
            for geist_id in config.default_geists.keys():
                if geist_id in all_results:
                    all_suggestions.extend(all_results[geist_id])
            # Then: any geists not in config (alphabetically)
            for geist_id in sorted(all_results.keys()):
                if geist_id not in config.default_geists:
                    all_suggestions.extend(all_results[geist_id])
        else:
            # No config: use execution order
            for suggestions in code_results.values():
                all_suggestions.extend(suggestions)
            for suggestions in tracery_results.values():
                all_suggestions.extend(suggestions)

        return all_suggestions

    def _print_execution_summary(self, results: GeistResults) -> None:
        """Print execution summary."""
        code_success = sum(1 for s in results.code_results.values() if s)
        code_empty = sum(1 for s in results.code_results.values() if not s)
        tracery_success = sum(1 for s in results.tracery_results.values() if s)
        tracery_empty = sum(1 for s in results.tracery_results.values() if not s)

        if not (results.code_results or results.tracery_results):
            return

        self.print("Execution summary:")
        if results.code_results:
            self.print(
                f"  - Code geists: {code_success} generated suggestions, "
                f"{code_empty} returned empty"
            )
        if results.tracery_results:
            self.print(
                f"  - Tracery geists: {tracery_success} generated suggestions, "
                f"{tracery_empty} returned empty"
            )

    def _filter_suggestions(
        self,
        suggestions: list[Suggestion],
        session_date: datetime,
    ) -> list[Suggestion]:
        """Filter suggestions through the filtering pipeline.

        Args:
            suggestions: Raw suggestions
            session_date: Session date

        Returns:
            Filtered suggestions
        """
        if self.args.no_filter:
            self.print("Skipping filtering pipeline (--no-filter)")
            return suggestions

        assert self._vault is not None  # Set in execute()
        embedding_computer = EmbeddingComputer()
        suggestion_filter = SuggestionFilter(self._vault.db, embedding_computer)
        filtered = suggestion_filter.filter_all(suggestions, session_date)
        self.print(f"Filtered to {len(filtered)} suggestions")
        return filtered

    def _select_final_suggestions(
        self,
        filtered: list[Suggestion],
        session_date: datetime,
    ) -> list[Suggestion]:
        """Select final suggestions based on mode.

        Args:
            filtered: Filtered suggestions
            session_date: Session date

        Returns:
            Final selected suggestions
        """
        mode = "full" if (self.args.full or self.args.no_filter) else "default"
        count = getattr(self.args, "count", 5)
        seed = int(session_date.timestamp())
        final = select_suggestions(filtered, mode, count, seed)
        self.print(f"Selected {len(final)} final suggestions\n")
        return final

    def _show_diff(
        self,
        exec_ctx: ExecutionContext,
        suggestions: list[Suggestion],
    ) -> None:
        """Show diff compared to recent sessions.

        Args:
            exec_ctx: Execution context
            suggestions: Final suggestions
        """
        journal_writer = JournalWriter(exec_ctx.vault_path, exec_ctx.vault.db)
        recent_suggestions = journal_writer.get_recent_suggestions(days=60)

        if not recent_suggestions:
            return

        from difflib import SequenceMatcher

        print("Diff Mode: Comparing to recent sessions...\n")
        for suggestion in suggestions:
            max_similarity = 0.0
            for recent in recent_suggestions:
                similarity = SequenceMatcher(None, suggestion.text, recent).ratio()
                max_similarity = max(max_similarity, similarity)

            if max_similarity > 0.8:
                print(f"  Similar to recent: {suggestion.text[:60]}...")
            elif max_similarity > 0.5:
                print(f"  Somewhat similar: {suggestion.text[:60]}...")
            else:
                print(f"  New: {suggestion.text[:60]}...")
        print()

    def _write_journal(
        self,
        exec_ctx: ExecutionContext,
        session_date: datetime,
        suggestions: list[Suggestion],
    ) -> bool:
        """Write suggestions to journal.

        Args:
            exec_ctx: Execution context
            session_date: Session date
            suggestions: Suggestions to write

        Returns:
            True if successful, False otherwise
        """
        journal_writer = JournalWriter(exec_ctx.vault_path, exec_ctx.vault.db)

        # Check if session already exists
        if journal_writer.session_exists(session_date):
            if not self.args.force:
                date_str = session_date.strftime("%Y-%m-%d")
                self.print(f"\nSession note already exists for {date_str}")
                self.print("Use --force to overwrite, or delete the existing note first.")
                return False
            else:
                # Delete existing session note
                date_str = session_date.strftime("%Y-%m-%d")
                existing_path = exec_ctx.vault_path / "geist journal" / f"{date_str}.md"
                existing_path.unlink()

        try:
            mode = "full" if (self.args.full or self.args.no_filter) else "default"
            journal_path = journal_writer.write_session(session_date, suggestions, mode)
            rel_path = journal_path.relative_to(exec_ctx.vault_path)
            self.print(f"Wrote session note: {rel_path}\n")
            return True
        except Exception as e:
            self.print_error(f"Writing session note: {e}")
            return False

    def _display_results(
        self,
        session_date: datetime,
        suggestions: list[Suggestion],
    ) -> None:
        """Display the final suggestions.

        Args:
            session_date: Session date
            suggestions: Final suggestions
        """
        print(f"{'=' * 80}")
        print(f"GeistFabrik Session - {session_date.strftime('%Y-%m-%d')}")
        print(f"{'=' * 80}\n")

        if not suggestions:
            print("No suggestions to display.")
        else:
            for suggestion in suggestions:
                print(f"## {suggestion.geist_id}")
                print(f"{suggestion.text}")
                if suggestion.notes:
                    note_refs = ", ".join(f"[[{note}]]" for note in suggestion.notes)
                    print(f"_Notes: {note_refs}_")
                print()

            print(f"{'=' * 80}")
            print(f"Total: {len(suggestions)} suggestions")
            print(f"{'=' * 80}\n")

    def _show_debug_profiles(self, code_executor: GeistExecutor) -> None:
        """Show performance profiling info in debug mode.

        Args:
            code_executor: Code geist executor
        """
        profiles = code_executor.get_execution_profiles()
        if not profiles:
            return

        print(f"\n{'=' * 60}")
        print("Performance Profiling (--debug mode)")
        print(f"{'=' * 60}\n")

        for profile in profiles:
            status_icon = "v" if profile.status == "success" else "x"
            print(f"{status_icon} {profile.geist_id}: {profile.total_time:.3f}s", end="")

            if profile.status == "success":
                print(f" ({profile.suggestion_count} suggestions)")
            else:
                print(f" ({profile.status})")

            if profile.function_stats and len(profile.function_stats) > 0:
                print("  Top 5 operations:")
                for i, stats in enumerate(profile.function_stats[:5], 1):
                    pct = (
                        (stats.total_time / profile.total_time) * 100
                        if profile.total_time > 0
                        else 0
                    )
                    name = stats.name.split(":")[-1] if ":" in stats.name else stats.name
                    print(f"    {i}. {name} - {stats.total_time:.3f}s ({pct:.1f}%)")
                print()

        print(f"{'=' * 60}\n")

    def _show_execution_errors(self, code_executor: GeistExecutor) -> None:
        """Show execution errors and timeouts.

        Args:
            code_executor: Code geist executor
        """
        log = code_executor.get_execution_log()
        errors = [entry for entry in log if entry["status"] == "error"]
        timeouts = [entry for entry in log if "timeout" in str(entry.get("error", "")).lower()]
        successful = [entry for entry in log if entry["status"] == "success"]

        if not (errors or timeouts):
            return

        print(f"\n{'=' * 60}")
        print("Detailed Execution Log")
        print(f"{'=' * 60}")
        print(f"Successful: {len(successful)} geists")
        if errors:
            print(f"Errors: {len(errors)} geists")
            for entry in errors:
                print(f"  x {entry['geist_id']}: {entry['error']}")
        if timeouts:
            print(f"Timeouts: {len(timeouts)} geists (consider increasing --timeout)")
        print(f"{'=' * 60}\n")
