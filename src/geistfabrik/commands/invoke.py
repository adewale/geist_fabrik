"""Invoke command for running geists and generating suggestions."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config import MAX_SESSION_SUGGESTIONS
from ..config_loader import GeistFabrikConfig, save_config
from ..embeddings import EmbeddingComputer
from ..filtering import FilteringReport, SuggestionFilter, select_suggestions
from ..geist_executor import GeistExecutor
from ..geist_status import GeistStatusStore
from ..journal_writer import JournalWriter
from ..models import Suggestion
from ..session_time import session_seed
from ..tracery import TraceryGeist, TraceryGeistLoader
from .base import BaseCommand, ExecutionContext

#: Bundled geists that read VaultContext.get_clusters().
CLUSTER_GEISTS = frozenset({"cluster_mirror"})


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
        vault_path = self.get_vault_path(auto_detect=True)
        if vault_path is None:
            return 1

        self.print(f"Loading vault: {vault_path}")

        # Parse session date
        session_date = self.parse_session_date(getattr(self.args, "date", None))
        if session_date is None:
            return 1

        # Set up command context
        cmd_ctx = self.setup_command_context(vault_path)
        if cmd_ctx is None:
            return 1
        note_count = cmd_ctx.vault.sync()
        self.print(f"Synced {note_count} notes")

        # Set up execution context (session, VaultContext)
        exec_ctx = self.setup_execution_context(cmd_ctx, session_date)

        # Stash config for filter/count resolution in later phases
        self._config = exec_ctx.config

        # Load geists
        code_executor, tracery_geists, newly_discovered = self._load_geists(exec_ctx, session_date)

        # Handle newly discovered geists
        self._handle_new_geists(exec_ctx, newly_discovered)

        # Check if any geists are enabled
        total_geists = len(code_executor.geists)
        if total_geists == 0:
            if any(
                entry.get("status") == "load_error" for entry in code_executor.get_execution_log()
            ):
                self._show_execution_errors(code_executor)
                return 1
            self._print_no_geists_message(exec_ctx)
            return 0

        # Show configuration summary
        self._print_config_summary(exec_ctx, code_executor, tracery_geists)

        # Execute geists
        results = self._execute_geists(exec_ctx, code_executor, tracery_geists)
        if results is None:
            return 1

        # Show execution summary
        self._print_execution_summary(results, code_executor)

        self.print(f"Generated {len(results.all_suggestions)} raw suggestions")

        # Filter suggestions
        filtered, filter_report = self._filter_suggestions(results.all_suggestions, session_date)

        # Select final suggestions
        final = self._select_final_suggestions(filtered, session_date)

        if getattr(self.args, "explain", False):
            self._print_explanation(
                results,
                code_executor,
                filter_report,
                filtered_count=len(filtered),
                selected_count=len(final),
                session_date=session_date,
            )

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
            timeout=self.resolve_timeout(config),
            max_failures=self.resolve_max_failures(config),
            default_geists_dir=default_code_geists_dir,
            enabled_defaults=config.default_geists if config else {},
            debug=self.args.debug,
            status_store=GeistStatusStore(exec_ctx.vault.db),
        )
        newly_discovered_code = code_executor.load_geists()

        # Load Tracery geists
        tracery_geists_dir = vault_path / "_geistfabrik" / "geists" / "tracery"
        seed = session_seed(session_date)
        tracery_loader = TraceryGeistLoader(
            tracery_geists_dir,
            seed=seed,
            default_geists_dir=default_tracery_geists_dir,
            enabled_defaults=config.default_geists if config else {},
        )
        tracery_geists, newly_discovered_tracery = tracery_loader.load_all()
        for load_error in tracery_loader.load_errors:
            code_executor.record_load_error(
                str(load_error["geist_id"]),
                Path(str(load_error["path"])),
                str(load_error["error"]),
            )
        timeout = self.resolve_timeout(config)
        for geist in tracery_geists:
            if geist.geist_id in code_executor.geists:
                raise ValueError(f"Duplicate code/Tracery geist ID '{geist.geist_id}'")
            geist.execution_timeout = timeout
            code_executor.register_geist(geist.geist_id, geist.yaml_path, geist.suggest)
        code_executor.load_status()

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
        tracery_ids = {geist.geist_id for geist in tracery_geists}
        all_code_ids = [gid for gid in code_executor.geists if gid not in tracery_ids]
        enabled_ids = set(code_executor.get_enabled_geists())
        enabled_code_geists = [gid for gid in all_code_ids if gid in enabled_ids]
        enabled_tracery = [gid for gid in tracery_ids if gid in enabled_ids]
        code_geists_count = len(all_code_ids)
        disabled_geists = [gid for gid in code_executor.geists if gid not in enabled_ids]

        total_geists = len(code_executor.geists)
        enabled_count = len(enabled_ids)

        print(f"\n{'=' * 60}")
        print("GeistFabrik Configuration Audit")
        print(f"{'=' * 60}")
        print(f"Vault: {vault_path}")
        print(f"Geists directory: {vault_path / '_geistfabrik' / 'geists'}")
        print(f"Loaded geists: {total_geists}")
        print(f"  - Code geists: {code_geists_count} ({len(enabled_code_geists)} enabled)")
        print(f"  - Tracery geists: {len(tracery_geists)} ({len(enabled_tracery)} enabled)")
        if disabled_geists:
            print(f"  - Auto-disabled: {len(disabled_geists)} ({', '.join(disabled_geists)})")
        configured_off = [
            geist_id for geist_id, enabled in exec_ctx.config.default_geists.items() if not enabled
        ]
        if configured_off:
            print(f"  - Configured off: {len(configured_off)}")
        load_failures = [
            entry
            for entry in code_executor.get_execution_log()
            if entry.get("status") == "load_error"
        ]
        if load_failures:
            print(f"  - Load failures: {len(load_failures)}")

        filtering_status = (
            "DISABLED (--no-filter)" if self.args.no_filter else "ENABLED (4-stage pipeline)"
        )
        print(f"Filtering: {filtering_status}")

        if self.args.full or self.args.no_filter:
            sampling_status = "DISABLED (--full or --no-filter)"
        else:
            resolved_count = self.args.count
            if resolved_count is None:
                cfg = getattr(self, "_config", None)
                resolved_count = cfg.session.default_suggestions if cfg else 5
            sampling_status = f"ENABLED (count={resolved_count})"
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

        tracery_ids = {geist.geist_id for geist in tracery_geists}
        if geists_to_run:
            execution_order = geists_to_run
        elif config and config.default_geists:
            configured = [
                geist_id for geist_id in config.default_geists if geist_id in code_executor.geists
            ]
            undisclosed = sorted(set(code_executor.geists) - set(configured))
            execution_order = configured + undisclosed
        else:
            execution_order = list(code_executor.geists)

        # Clustering can outlast one geist's timeout on a large vault; compute
        # it once, under its own budget, before any geist that reads it.
        if any(geist_id in CLUSTER_GEISTS for geist_id in execution_order):
            context.warm_clusters()

        # Code and Tracery callables share one executor, but result typing and
        # configured cross-type order remain observable CLI contracts.
        for geist_id in execution_order:
            if geist_id not in code_executor.geists:
                self.print_error(f"Geist '{geist_id}' not found")
                return None
            suggestions = code_executor.execute_geist(geist_id, context)
            if geist_id in tracery_ids:
                tracery_results[geist_id] = suggestions
            else:
                code_results[geist_id] = suggestions

        # Collect all suggestions in config order
        all_suggestions = self._collect_suggestions_in_order(code_results, tracery_results, config)

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
            ordered_ids = [
                geist_id for geist_id in config.default_geists if geist_id in all_results
            ]
            ordered_ids.extend(
                sorted(
                    geist_id for geist_id in all_results if geist_id not in config.default_geists
                )
            )
        else:
            # Dictionary insertion order is the actual shared execution order.
            ordered_ids = list(code_results) + [
                geist_id for geist_id in tracery_results if geist_id not in code_results
            ]

        for geist_id in ordered_ids:
            remaining = MAX_SESSION_SUGGESTIONS - len(all_suggestions)
            if remaining <= 0:
                break
            all_suggestions.extend(all_results[geist_id][:remaining])
        return all_suggestions

    @staticmethod
    def _outcome_counts(
        result_map: dict[str, list[Suggestion]], executor: GeistExecutor
    ) -> dict[str, int]:
        """Classify executor outcomes without treating failures as empty output."""
        latest: dict[str, str] = {}
        for entry in executor.get_execution_log():
            geist_id = str(entry.get("geist_id", ""))
            status = str(entry.get("status", ""))
            if geist_id in result_map and status in {"success", "error", "skipped"}:
                latest[geist_id] = status

        counts = {
            "produced": 0,
            "healthy_empty": 0,
            "failed": 0,
            "skipped": 0,
            "unknown": 0,
        }
        for geist_id, suggestions in result_map.items():
            outcome = latest.get(geist_id)
            if outcome == "error":
                counts["failed"] += 1
            elif outcome == "skipped":
                counts["skipped"] += 1
            elif outcome == "success" and suggestions:
                counts["produced"] += 1
            elif outcome == "success":
                counts["healthy_empty"] += 1
            else:
                counts["unknown"] += 1
        return counts

    @staticmethod
    def _format_outcome_counts(counts: dict[str, int]) -> str:
        """Format all outcome categories, including explicit healthy empties."""
        return ", ".join(
            (
                f"{counts['produced']} produced output",
                f"{counts['healthy_empty']} healthy empty",
                f"{counts['failed']} failed",
                f"{counts['skipped']} skipped",
                f"{counts['unknown']} unknown",
            )
        )

    def _print_execution_summary(self, results: GeistResults, executor: GeistExecutor) -> None:
        """Print an outcome-aware execution summary."""

        if not (results.code_results or results.tracery_results):
            return

        self.print("Execution summary:")
        if results.code_results:
            counts = self._outcome_counts(results.code_results, executor)
            self.print(f"  - Code geists: {self._format_outcome_counts(counts)}")
        if results.tracery_results:
            counts = self._outcome_counts(results.tracery_results, executor)
            self.print(f"  - Tracery geists: {self._format_outcome_counts(counts)}")

    def _filter_suggestions(
        self,
        suggestions: list[Suggestion],
        session_date: datetime,
    ) -> tuple[list[Suggestion], FilteringReport | None]:
        """Filter suggestions through the filtering pipeline.

        Args:
            suggestions: Raw suggestions
            session_date: Session date

        Returns:
            Filtered suggestions
        """
        if self.args.no_filter:
            self.print("Skipping filtering pipeline (--no-filter)")
            return suggestions, None

        assert self._vault is not None  # Set in execute()
        embedding_computer = EmbeddingComputer()
        config = getattr(self, "_config", None)
        filter_config = config.filtering.to_filter_config() if config else None
        suggestion_filter = SuggestionFilter(
            self._vault.db, embedding_computer, config=filter_config
        )
        filtered, report = suggestion_filter.filter_all_with_report(suggestions, session_date)
        self.print(f"Filtered to {len(filtered)} suggestions")
        return filtered, report

    def _print_explanation(
        self,
        results: GeistResults,
        executor: GeistExecutor,
        filter_report: FilteringReport | None,
        *,
        filtered_count: int,
        selected_count: int,
        session_date: datetime,
    ) -> None:
        """Explain a run using aggregate counts and explicit outcome states."""
        all_results = {**results.code_results, **results.tracery_results}
        latest: dict[str, str] = {}
        for entry in executor.get_execution_log():
            geist_id = str(entry.get("geist_id", ""))
            status = str(entry.get("status", ""))
            if status in {"success", "error", "skipped", "load_error"}:
                latest[geist_id] = status

        self.print("Explanation:")
        for geist_id, suggestions in all_results.items():
            status = latest.get(geist_id, "unknown")
            if status == "success" and not suggestions:
                detail = "healthy empty"
            elif status == "success":
                detail = f"success, {len(suggestions)} generated"
            elif status == "error":
                detail = "failed"
            else:
                detail = status.replace("_", " ")
            self.print(f"  - {geist_id}: {detail}")

        load_failures = [
            entry for entry in executor.get_execution_log() if entry.get("status") == "load_error"
        ]
        for entry in load_failures:
            self.print(f"  - {entry['geist_id']}: load failed")

        self.print("  Filtering:")
        if filter_report is None:
            self.print(f"    - bypassed (--no-filter): {len(results.all_suggestions)} kept")
        elif not filter_report.stages:
            self.print(f"    - no configured stages: {filter_report.input_count} kept")
        else:
            for stage in filter_report.stages:
                self.print(
                    f"    - {stage.name}: {stage.input_count} -> "
                    f"{stage.output_count} ({stage.rejected_count} rejected)"
                )

        unselected = max(0, filtered_count - selected_count)
        selection_mode = (
            "all" if (self.args.full or self.args.no_filter) else "deterministic sample"
        )
        self.print(
            f"  Selection ({selection_mode}, seed={session_seed(session_date)}): "
            f"{selected_count} selected, {unselected} unselected"
        )

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
        config = getattr(self, "_config", None)
        count = getattr(self.args, "count", None)
        if count is None:
            count = config.session.default_suggestions if config else 5
        seed = session_seed(session_date)
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
        recent_suggestions = journal_writer.get_recent_suggestions(
            days=60, as_of=exec_ctx.session.date
        )

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

        try:
            mode = "full" if (self.args.full or self.args.no_filter) else "default"
            journal_path = journal_writer.write_session(
                session_date, suggestions, mode, overwrite=self.args.force
            )
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
        load_errors = [entry for entry in log if entry["status"] == "load_error"]
        timeouts = [entry for entry in log if "timeout" in str(entry.get("error", "")).lower()]
        successful = [entry for entry in log if entry["status"] == "success"]

        if not (errors or load_errors or timeouts):
            return

        print(f"\n{'=' * 60}")
        print("Detailed Execution Log")
        print(f"{'=' * 60}")
        print(f"Successful: {len(successful)} geists")
        if errors:
            print(f"Errors: {len(errors)} geists")
            for entry in errors:
                if self.verbose or getattr(self.args, "debug", False):
                    detail = entry["error"]
                else:
                    detail = entry.get("error_type", "execution error")
                print(f"  x {entry['geist_id']}: {detail}")
        if load_errors:
            print(f"Load failures: {len(load_errors)} geists")
            for entry in load_errors:
                detail = (
                    entry["error"]
                    if (self.verbose or getattr(self.args, "debug", False))
                    else "load error"
                )
                print(f"  x {entry['geist_id']}: {detail}")
        if timeouts:
            print(f"Timeouts: {len(timeouts)} geists (consider increasing --timeout)")
        print(f"{'=' * 60}\n")
