"""GeistFabrik command-line interface."""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .embeddings import EmbeddingComputer, Session
from .filtering import SuggestionFilter, select_suggestions
from .geist_executor import GeistExecutor
from .journal_writer import JournalWriter
from .stats import (
    EmbeddingMetricsComputer,
    StatsCollector,
    StatsFormatter,
    generate_recommendations,
)
from .validator import GeistValidator
from .vault import Vault
from .vault_context import VaultContext


def find_vault_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find vault root by looking for .obsidian directory.

    Args:
        start_path: Directory to start search from (defaults to current dir)

    Returns:
        Path to vault root, or None if not found
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # Walk up the directory tree
    for parent in [current] + list(current.parents):
        obsidian_dir = parent / ".obsidian"
        if obsidian_dir.exists() and obsidian_dir.is_dir():
            return parent

    return None


def init_command(args: argparse.Namespace) -> int:
    """Execute the init command to set up a vault for GeistFabrik.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    vault_path = Path(args.vault).resolve()

    # Check if vault exists
    if not vault_path.exists():
        print(f"Error: Vault path does not exist: {vault_path}", file=sys.stderr)
        return 1

    if not vault_path.is_dir():
        print(f"Error: Vault path is not a directory: {vault_path}", file=sys.stderr)
        return 1

    # Check if it's an Obsidian vault
    obsidian_dir = vault_path / ".obsidian"
    if not obsidian_dir.exists():
        print(f"Warning: No .obsidian directory found in {vault_path}")
        print("This doesn't appear to be an Obsidian vault, but continuing anyway...")
        print()

    print(f"Initializing GeistFabrik in: {vault_path}\n")

    # Display first-run warnings
    print("⚠️  GeistFabrik will:")
    print("   • Read all markdown files in your vault")
    print("   • Create a database at _geistfabrik/vault.db")
    print("   • Compute embeddings for all notes (stored locally)")
    print("   • Create session notes in 'geist journal/' when you invoke with --write")
    print()
    print("✅ GeistFabrik will NEVER:")
    print("   • Modify your existing notes (read-only access)")
    print("   • Send data to the internet (100% local)")
    print("   • Delete any files")
    print()

    # Create _geistfabrik directory structure
    geistfabrik_dir = vault_path / "_geistfabrik"

    if geistfabrik_dir.exists() and not args.force:
        print(f"Error: _geistfabrik directory already exists at {geistfabrik_dir}")
        print("Use --force to reinitialize (this will overwrite existing configuration)")
        return 1

    # Create directory structure
    directories = [
        geistfabrik_dir / "geists" / "code",
        geistfabrik_dir / "geists" / "tracery",
        geistfabrik_dir / "metadata_inference",
        geistfabrik_dir / "vault_functions",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {directory.relative_to(vault_path)}")

    # Create default config file
    config_path = geistfabrik_dir / "config.yaml"
    if not config_path.exists() or args.force:
        from geistfabrik import generate_default_config

        config_content = generate_default_config()
        with open(config_path, "w") as f:
            f.write(config_content)
        print(f"✓ Created {config_path.relative_to(vault_path)}")

    # Initialize database
    print("\n🗄️  Initializing database...")
    db_path = geistfabrik_dir / "vault.db"
    try:
        vault = Vault(vault_path, db_path)
        note_count = vault.sync()
        vault.close()
        print(f"✓ Synced {note_count} notes to database")

        # Display summary stats
        db_size_mb = db_path.stat().st_size / (1024 * 1024)

        print("\n📊 Vault Summary:")
        print(f"   Notes found: {note_count}")
        print(f"   Database size: {db_size_mb:.2f} MB")

    except Exception as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        return 1

    # Success message
    print("\n" + "=" * 60)
    print("✨ GeistFabrik initialized successfully!")
    print("=" * 60)
    print(f"\nVault: {vault_path}")
    print(f"Configuration: {geistfabrik_dir.relative_to(vault_path)}")

    # Inform about bundled defaults
    print("\n🎁 49 default geists are bundled and ready to use:")
    print("   • 40 code geists (blind_spot_detector, temporal_drift, columbo, creation_burst, etc.)")
    print("   • 9 Tracery geists (contradictor, hub_explorer, transformation_suggester, etc.)")
    print(f"\n   Configure in: {config_path.relative_to(vault_path)}")

    print("\n🚀 Next steps:")
    print(f"   geistfabrik invoke {vault_path}")
    print("   # or just: geistfabrik invoke (from within the vault)\n")

    return 0


def invoke_command(args: argparse.Namespace) -> int:
    """Execute the invoke command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Get vault path from positional argument
    vault_path: Path = Path(args.vault)

    if not vault_path.exists():
        print(f"Error: Vault path does not exist: {vault_path}", file=sys.stderr)
        return 1

    if not vault_path.is_dir():
        print(f"Error: Vault path is not a directory: {vault_path}", file=sys.stderr)
        return 1

    # Check for conflicting flags
    if args.quiet and args.verbose:
        print("Error: Cannot use both --quiet and --verbose", file=sys.stderr)
        return 1

    if args.geist and args.geists:
        print("Error: Cannot use both --geist and --geists", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Loading vault: {vault_path}")

    # Set up database path
    geistfabrik_dir = vault_path / "_geistfabrik"
    geistfabrik_dir.mkdir(exist_ok=True)
    db_path = geistfabrik_dir / "vault.db"

    try:
        # Load vault
        vault = Vault(vault_path, db_path)
        note_count = vault.sync()
        if not args.quiet:
            print(f"Synced {note_count} notes")

        # Determine session date
        if args.date:
            try:
                session_date = datetime.strptime(args.date, "%Y-%m-%d")
            except ValueError:
                print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
                vault.close()
                return 1
        else:
            session_date = datetime.now()

        # Load configuration
        from geistfabrik import load_config, save_config

        config_path = geistfabrik_dir / "config.yaml"
        config = None
        if config_path.exists():
            config = load_config(config_path)
            if not args.quiet:
                print(f"Loaded configuration from {config_path.relative_to(vault_path)}")

        # Get default geists directories
        package_dir = Path(__file__).parent
        default_code_geists_dir = package_dir / "default_geists" / "code"
        default_tracery_geists_dir = package_dir / "default_geists" / "tracery"

        # Load metadata inference modules
        metadata_dir = geistfabrik_dir / "metadata_inference"
        metadata_loader = None
        if metadata_dir.exists():
            from geistfabrik import MetadataLoader

            metadata_loader = MetadataLoader(metadata_dir)
            metadata_loader.load_modules()
            if not args.quiet:
                print(f"Loaded {len(metadata_loader.modules)} metadata inference modules")

        # Load vault function modules
        functions_dir = geistfabrik_dir / "vault_functions"
        function_registry = None
        if functions_dir.exists():
            from geistfabrik import FunctionRegistry

            function_registry = FunctionRegistry(functions_dir)
            function_registry.load_modules()
            if not args.quiet:
                print(f"Loaded {len(function_registry.functions)} vault functions")
        else:
            # Always create function registry with built-in functions
            from geistfabrik import FunctionRegistry

            function_registry = FunctionRegistry()
            if not args.quiet:
                print(f"Using {len(function_registry.functions)} built-in vault functions")

        # Create session and context
        backend_type = config.vector_search.backend if config else "in-memory"
        session = Session(session_date, vault.db, backend=backend_type)
        if not args.quiet:
            print(f"Computing embeddings for {len(vault.all_notes())} notes...")
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(
            vault, session, metadata_loader=metadata_loader, function_registry=function_registry
        )

        # Load code geists (default + custom)
        code_geists_dir = vault_path / "_geistfabrik" / "geists" / "code"
        code_executor = GeistExecutor(
            code_geists_dir,
            timeout=args.timeout,
            max_failures=3,
            default_geists_dir=default_code_geists_dir,
            enabled_defaults=config.default_geists if config else {},
            debug=args.debug,
        )
        newly_discovered_code = code_executor.load_geists()
        code_geists_count = len(code_executor.geists)

        # Load Tracery geists (default + custom)
        tracery_geists_dir = vault_path / "_geistfabrik" / "geists" / "tracery"
        from geistfabrik.tracery import TraceryGeistLoader

        seed = int(session_date.timestamp())
        tracery_loader = TraceryGeistLoader(
            tracery_geists_dir,
            seed=seed,
            default_geists_dir=default_tracery_geists_dir,
            enabled_defaults=config.default_geists if config else {},
        )
        tracery_geists, newly_discovered_tracery = tracery_loader.load_all()

        # Add newly discovered geists to config (both code and Tracery)
        newly_discovered_all = newly_discovered_code + newly_discovered_tracery
        if newly_discovered_all and config:
            for geist_id in newly_discovered_all:
                config.default_geists[geist_id] = True  # Enable by default
            # Save updated config
            save_config(config, config_path)
            if not args.quiet:
                geist_list = ", ".join(newly_discovered_all)
                print(f"Added {len(newly_discovered_all)} new geist(s) to config: {geist_list}")

        total_geists = code_geists_count + len(tracery_geists)
        if total_geists == 0:
            if not args.quiet:
                print("\nNo geists are enabled.")
                print("Default geists ship with GeistFabrik but may be disabled in config.")
                print(f"Check {config_path.relative_to(vault_path)} to enable default geists.")
            vault.close()
            return 0

        # Get enabled code geists
        enabled_code_geists = []
        disabled_code_geists = []
        if code_executor:
            enabled_code_geists = code_executor.get_enabled_geists()
            all_code_ids = list(code_executor.geists.keys())
            disabled_code_geists = [gid for gid in all_code_ids if gid not in enabled_code_geists]

        # Show configuration summary
        enabled_geists_count = len(enabled_code_geists) + len(tracery_geists)
        disabled_geists = disabled_code_geists

        if not args.quiet or args.verbose:
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
                "DISABLED (--no-filter)" if args.no_filter else "ENABLED (4-stage pipeline)"
            )
            print(f"Filtering: {filtering_status}")
            sampling_status = (
                "DISABLED (--full or --no-filter)"
                if (args.full or args.no_filter)
                else f"ENABLED (count={args.count})"
            )
            print(f"Sampling: {sampling_status}")
            mode = "Raw output" if args.no_filter else "Filtered output" if args.full else "Default"
            print(f"Mode: {mode}")
            print(f"{'=' * 60}\n")

        # Determine which geists to run
        geists_to_run = None
        if args.geist:
            geists_to_run = [args.geist]
        elif args.geists:
            geists_to_run = [g.strip() for g in args.geists.split(",")]

        # Calculate actual count of geists being executed
        actual_geists_count = len(geists_to_run) if geists_to_run else enabled_geists_count

        if not args.quiet:
            geist_word = "geist" if actual_geists_count == 1 else "geists"
            print(f"Executing {actual_geists_count} {geist_word}...")

        # Execute specific geist(s) or all geists
        all_suggestions = []
        code_results = {}
        tracery_results = {}

        if geists_to_run:
            # Run specific geist(s)
            for geist_id in geists_to_run:
                # Check if it's a code geist
                if code_executor and geist_id in code_executor.geists:
                    code_results[geist_id] = code_executor.execute_geist(geist_id, context)
                # Check if it's a Tracery geist
                elif any(g.geist_id == geist_id for g in tracery_geists):
                    tracery_geist = next(g for g in tracery_geists if g.geist_id == geist_id)
                    try:
                        suggestions = tracery_geist.suggest(context)
                        tracery_results[geist_id] = suggestions
                    except Exception as e:
                        print(f"Error executing Tracery geist {geist_id}: {e}", file=sys.stderr)
                        tracery_results[geist_id] = []
                else:
                    print(f"Error: Geist '{geist_id}' not found", file=sys.stderr)
                    vault.close()
                    return 1
        else:
            # Execute all code geists
            if code_executor:
                code_results = code_executor.execute_all(context)

            # Execute all Tracery geists
            for tracery_geist in tracery_geists:
                try:
                    suggestions = tracery_geist.suggest(context)
                    tracery_results[tracery_geist.geist_id] = suggestions
                except Exception as e:
                    print(
                        f"Error executing Tracery geist {tracery_geist.geist_id}: {e}",
                        file=sys.stderr,
                    )
                    tracery_results[tracery_geist.geist_id] = []

        # Collect all suggestions from both code and Tracery geists in config order
        # This respects the user's ordering in config file (defaults to alphabetical)
        all_geist_results = {**code_results, **tracery_results}

        # If we have a config, use its ordering to interleave code and Tracery results
        if config and config.default_geists:
            # First: geists in config order
            for geist_id in config.default_geists.keys():
                if geist_id in all_geist_results:
                    all_suggestions.extend(all_geist_results[geist_id])
            # Then: any geists not in config (alphabetically)
            for geist_id in sorted(all_geist_results.keys()):
                if geist_id not in config.default_geists:
                    all_suggestions.extend(all_geist_results[geist_id])
        else:
            # No config: just use execution order (code first, then Tracery)
            for suggestions in code_results.values():
                all_suggestions.extend(suggestions)
            for suggestions in tracery_results.values():
                all_suggestions.extend(suggestions)

        # Show execution summary
        code_success = sum(1 for s in code_results.values() if s)
        code_empty = sum(1 for s in code_results.values() if not s)
        tracery_success = sum(1 for s in tracery_results.values() if s)
        tracery_empty = sum(1 for s in tracery_results.values() if not s)

        if (code_results or tracery_results) and not args.quiet:
            print("Execution summary:")
            if code_results:
                print(
                    f"  - Code geists: {code_success} generated suggestions, "
                    f"{code_empty} returned empty"
                )
            if tracery_results:
                print(
                    f"  - Tracery geists: {tracery_success} generated suggestions, "
                    f"{tracery_empty} returned empty"
                )

        if not args.quiet:
            print(f"Generated {len(all_suggestions)} raw suggestions")

        # Filter suggestions (unless --no-filter is specified)
        if args.no_filter:
            filtered = all_suggestions
            if not args.quiet:
                print("Skipping filtering pipeline (--no-filter)")
        else:
            embedding_computer = EmbeddingComputer()
            filter = SuggestionFilter(vault.db, embedding_computer)
            filtered = filter.filter_all(all_suggestions, session_date)
            if not args.quiet:
                print(f"Filtered to {len(filtered)} suggestions")

        # Select final suggestions based on mode
        # Both --full and --no-filter should show all suggestions (no sampling)
        mode = "full" if (args.full or args.no_filter) else "default"
        count = args.count if hasattr(args, "count") else 5
        seed = int(session_date.timestamp())
        final = select_suggestions(filtered, mode, count, seed)
        if not args.quiet:
            print(f"Selected {len(final)} final suggestions\n")

        # Handle --diff mode
        if args.diff:
            journal_writer = JournalWriter(vault_path, vault.db)
            recent_suggestions = journal_writer.get_recent_suggestions(days=60)
            if recent_suggestions:
                from difflib import SequenceMatcher

                print("🔍 Diff Mode: Comparing to recent sessions...\n")
                for suggestion in final:
                    # Check similarity to recent suggestions
                    max_similarity = 0.0
                    for recent in recent_suggestions:
                        similarity = SequenceMatcher(None, suggestion.text, recent).ratio()
                        max_similarity = max(max_similarity, similarity)

                    if max_similarity > 0.8:
                        print(f"  ⚠️  Similar to recent: {suggestion.text[:60]}...")
                    elif max_similarity > 0.5:
                        print(f"  ⚡ Somewhat similar: {suggestion.text[:60]}...")
                    else:
                        print(f"  ✨ New: {suggestion.text[:60]}...")
                print()

        # Write to journal if requested
        if args.write:
            journal_writer = JournalWriter(vault_path, vault.db)

            # Check if session already exists
            if journal_writer.session_exists(session_date):
                if not args.force:
                    if not args.quiet:
                        date_str = session_date.strftime("%Y-%m-%d")
                        print(f"\n⚠️  Session note already exists for {date_str}")
                        print("Use --force to overwrite, or delete the existing note first.")
                    vault.close()
                    return 1
                else:
                    # Delete existing session note
                    existing_path = (
                        vault_path / "geist journal" / f"{session_date.strftime('%Y-%m-%d')}.md"
                    )
                    existing_path.unlink()

            try:
                journal_path = journal_writer.write_session(session_date, final, mode)
                if not args.quiet:
                    print(f"✓ Wrote session note: {journal_path.relative_to(vault_path)}\n")
            except Exception as e:
                print(f"Error writing session note: {e}", file=sys.stderr)
                vault.close()
                return 1

        # Display results
        print(f"{'=' * 80}")
        print(f"GeistFabrik Session - {session_date.strftime('%Y-%m-%d')}")
        print(f"{'=' * 80}\n")

        if not final:
            print("No suggestions to display.")
        else:
            for i, suggestion in enumerate(final, 1):
                print(f"## {suggestion.geist_id}")
                print(f"{suggestion.text}")
                if suggestion.notes:
                    note_refs = ", ".join(f"[[{note}]]" for note in suggestion.notes)
                    print(f"_Notes: {note_refs}_")
                print()

            print(f"{'=' * 80}")
            print(f"Total: {len(final)} suggestions")
            print(f"{'=' * 80}\n")

        # Display performance profiles in debug mode
        if code_executor and args.debug:
            profiles = code_executor.get_execution_profiles()
            if profiles:
                print(f"\n{'=' * 60}")
                print("Performance Profiling (--debug mode)")
                print(f"{'=' * 60}\n")

                for profile in profiles:
                    status_icon = "✓" if profile.status == "success" else "✗"
                    print(f"{status_icon} {profile.geist_id}: {profile.total_time:.3f}s", end="")

                    if profile.status == "success":
                        print(f" ({profile.suggestion_count} suggestions)")
                    else:
                        print(f" ({profile.status})")

                    # Show top expensive operations if available
                    if profile.function_stats and len(profile.function_stats) > 0:
                        print("  Top 5 operations:")
                        for i, stats in enumerate(profile.function_stats[:5], 1):
                            pct = (
                                (stats.total_time / profile.total_time) * 100
                                if profile.total_time > 0
                                else 0
                            )
                            # Simplify name for readability
                            name = stats.name.split(":")[-1] if ":" in stats.name else stats.name
                            print(f"    {i}. {name} - {stats.total_time:.3f}s ({pct:.1f}%)")
                        print()

                print(f"{'=' * 60}\n")

        # Display execution log summary (for code geists only - they have detailed logs)
        if code_executor:
            log = code_executor.get_execution_log()
            errors = [entry for entry in log if entry["status"] == "error"]
            timeouts = [entry for entry in log if "timeout" in str(entry.get("error", "")).lower()]
            successful = [entry for entry in log if entry["status"] == "success"]

            if errors or timeouts:
                print(f"\n{'=' * 60}")
                print("Detailed Execution Log")
                print(f"{'=' * 60}")
                print(f"Successful: {len(successful)} geists")
                if errors:
                    print(f"Errors: {len(errors)} geists")
                    for entry in errors:
                        print(f"  ✗ {entry['geist_id']}: {entry['error']}")
                if timeouts:
                    print(f"Timeouts: {len(timeouts)} geists (consider increasing --timeout)")
                print(f"{'=' * 60}\n")

        vault.close()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def test_command(args: argparse.Namespace) -> int:
    """Execute the test command to test a single geist.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Get vault path from positional argument
    vault_path: Path = Path(args.vault)

    if not vault_path.exists():
        print(f"Error: Vault path does not exist: {vault_path}", file=sys.stderr)
        return 1

    if not vault_path.is_dir():
        print(f"Error: Vault path is not a directory: {vault_path}", file=sys.stderr)
        return 1

    geist_id = args.geist_id

    if args.verbose:
        print(f"Testing geist '{geist_id}' in vault: {vault_path}\n")

    # Set up database path
    geistfabrik_dir = vault_path / "_geistfabrik"
    if not geistfabrik_dir.exists():
        print(f"Error: GeistFabrik not initialized in {vault_path}", file=sys.stderr)
        print(f"Run: geistfabrik init {vault_path}")
        return 1

    db_path = geistfabrik_dir / "vault.db"

    try:
        # Load vault
        vault = Vault(vault_path, db_path)
        note_count = vault.sync()
        if args.verbose:
            print(f"Loaded {note_count} notes")

        # Determine session date
        if args.date:
            try:
                session_date = datetime.strptime(args.date, "%Y-%m-%d")
            except ValueError:
                print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
                vault.close()
                return 1
        else:
            session_date = datetime.now()

        if args.verbose:
            print(f"Session date: {session_date.strftime('%Y-%m-%d')}")

        # Load configuration
        from geistfabrik import load_config

        config_path = geistfabrik_dir / "config.yaml"
        config = None
        if config_path.exists():
            config = load_config(config_path)
            if args.verbose:
                print(f"Loaded configuration from {config_path.relative_to(vault_path)}")

        # Load metadata inference modules
        metadata_dir = geistfabrik_dir / "metadata_inference"
        metadata_loader = None
        if metadata_dir.exists():
            from geistfabrik import MetadataLoader

            metadata_loader = MetadataLoader(metadata_dir)
            metadata_loader.load_modules()
            if args.verbose:
                print(f"Loaded {len(metadata_loader.modules)} metadata inference modules")

        # Load vault function modules
        functions_dir = geistfabrik_dir / "vault_functions"
        function_registry = None
        if functions_dir.exists():
            from geistfabrik import FunctionRegistry

            function_registry = FunctionRegistry(functions_dir)
            function_registry.load_modules()
            if args.verbose:
                print(f"Loaded {len(function_registry.functions)} vault functions")
        else:
            from geistfabrik import FunctionRegistry

            function_registry = FunctionRegistry()
            if args.verbose:
                print(f"Using {len(function_registry.functions)} built-in vault functions")

        # Create session and context
        backend_type = config.vector_search.backend if config else "in-memory"
        session = Session(session_date, vault.db, backend=backend_type)
        if args.verbose:
            print("Computing embeddings...")
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(
            vault, session, metadata_loader=metadata_loader, function_registry=function_registry
        )

        # Load and execute the specific geist
        geists_dir = vault_path / "_geistfabrik" / "geists" / "code"
        if not geists_dir.exists():
            print(f"\nError: No geists directory found at {geists_dir}", file=sys.stderr)
            vault.close()
            return 1

        executor = GeistExecutor(geists_dir, timeout=args.timeout, max_failures=3, debug=args.debug)
        executor.load_geists()

        if geist_id not in executor.geists:
            print(f"\nError: Geist '{geist_id}' not found in {geists_dir}", file=sys.stderr)
            print("\nAvailable geists:")
            for gid in sorted(executor.geists.keys()):
                print(f"  - {gid}")
            vault.close()
            return 1

        print(f"\n{'=' * 60}")
        print(f"Executing geist: {geist_id}")
        print(f"{'=' * 60}\n")

        # Execute the geist
        suggestions = executor.execute_geist(geist_id, context)

        # Display results
        if not suggestions:
            print("⚠️  No suggestions generated")
        else:
            print(f"✓ Generated {len(suggestions)} suggestion(s):\n")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion.text}")
                if suggestion.notes:
                    note_refs = ", ".join(f"[[{note}]]" for note in suggestion.notes)
                    print(f"   Notes: {note_refs}")
                if suggestion.title:
                    print(f"   Suggested title: {suggestion.title}")
                print()

        # Display execution summary
        profiles = executor.get_execution_profiles()
        for profile in profiles:
            if profile.geist_id == geist_id:
                if profile.status == "success":
                    print("✓ Status: Success")
                    print(f"  Execution time: {profile.total_time:.3f}s")

                    # Show profiling details in debug mode
                    if args.debug and profile.function_stats:
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
                    print(f"✗ Status: {profile.status}")
                    log = executor.get_execution_log()
                    for entry in log:
                        if entry["geist_id"] == geist_id and "error" in entry:
                            print(f"  Error: {entry['error']}")
                            break

        print(f"\n{'=' * 60}\n")

        vault.close()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def test_all_command(args: argparse.Namespace) -> int:
    """Execute the test-all command to test all geists.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Get vault path from positional argument
    vault_path: Path = Path(args.vault)

    if not vault_path.exists():
        print(f"Error: Vault path does not exist: {vault_path}", file=sys.stderr)
        return 1

    if not vault_path.is_dir():
        print(f"Error: Vault path is not a directory: {vault_path}", file=sys.stderr)
        return 1

    print(f"Testing all geists in vault: {vault_path}\n")

    # Set up database path
    geistfabrik_dir = vault_path / "_geistfabrik"
    if not geistfabrik_dir.exists():
        print(f"Error: GeistFabrik not initialized in {vault_path}", file=sys.stderr)
        print(f"Run: geistfabrik init {vault_path}")
        return 1

    db_path = geistfabrik_dir / "vault.db"

    try:
        # Load vault
        vault = Vault(vault_path, db_path)
        note_count = vault.sync()
        if args.verbose:
            print(f"Loaded {note_count} notes")

        # Determine session date
        if args.date:
            try:
                session_date = datetime.strptime(args.date, "%Y-%m-%d")
            except ValueError:
                print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
                vault.close()
                return 1
        else:
            session_date = datetime.now()

        if args.verbose:
            print(f"Session date: {session_date.strftime('%Y-%m-%d')}")

        # Load configuration
        from geistfabrik import load_config

        config_path = geistfabrik_dir / "config.yaml"
        config = None
        if config_path.exists():
            config = load_config(config_path)
            if args.verbose:
                print(f"Loaded configuration from {config_path.relative_to(vault_path)}")

        # Load metadata inference modules
        metadata_dir = geistfabrik_dir / "metadata_inference"
        metadata_loader = None
        if metadata_dir.exists():
            from geistfabrik import MetadataLoader

            metadata_loader = MetadataLoader(metadata_dir)
            metadata_loader.load_modules()
            if args.verbose:
                print(f"Loaded {len(metadata_loader.modules)} metadata inference modules")

        # Load vault function modules
        functions_dir = geistfabrik_dir / "vault_functions"
        function_registry = None
        if functions_dir.exists():
            from geistfabrik import FunctionRegistry

            function_registry = FunctionRegistry(functions_dir)
            function_registry.load_modules()
            if args.verbose:
                print(f"Loaded {len(function_registry.functions)} vault functions")
        else:
            from geistfabrik import FunctionRegistry

            function_registry = FunctionRegistry()
            if args.verbose:
                print(f"Using {len(function_registry.functions)} built-in vault functions")

        # Create session and context
        backend_type = config.vector_search.backend if config else "in-memory"
        session = Session(session_date, vault.db, backend=backend_type)
        if args.verbose:
            print("Computing embeddings...")
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(
            vault, session, metadata_loader=metadata_loader, function_registry=function_registry
        )

        # Load code geists
        geists_dir = vault_path / "_geistfabrik" / "geists" / "code"
        if not geists_dir.exists():
            print(f"\nError: No geists directory found at {geists_dir}", file=sys.stderr)
            vault.close()
            return 1

        executor = GeistExecutor(geists_dir, timeout=args.timeout, max_failures=3, debug=args.debug)
        executor.load_geists()

        if not executor.geists:
            print("\nNo code geists found to test")
            vault.close()
            return 0

        print(f"\n{'=' * 60}")
        print(f"Testing {len(executor.geists)} geists")
        print(f"{'=' * 60}\n")

        # Test all geists
        results = {}
        for geist_id in sorted(executor.geists.keys()):
            print(f"Testing {geist_id}...", end=" ")
            suggestions = executor.execute_geist(geist_id, context)

            # Get profile for timing info
            profile = None
            for p in executor.get_execution_profiles():
                if p.geist_id == geist_id:
                    profile = p
                    break

            if profile:
                if profile.status == "success":
                    print(f"✓ ({len(suggestions)} suggestions, {profile.total_time:.3f}s)")
                    results[geist_id] = {"status": "success", "count": len(suggestions)}
                else:
                    # Get error details from execution log
                    error_msg = profile.status
                    for entry in executor.get_execution_log():
                        if entry["geist_id"] == geist_id and "error" in entry:
                            error_msg = entry["error"]
                            break
                    print(f"✗ {error_msg}")
                    results[geist_id] = {"status": "error", "error": error_msg}
            else:
                print("? Unknown status")
                results[geist_id] = {"status": "unknown"}

        # Print summary
        print(f"\n{'=' * 60}")
        print("Summary")
        print(f"{'=' * 60}")

        success = sum(1 for r in results.values() if r["status"] == "success")
        errors = sum(1 for r in results.values() if r["status"] == "error")
        total = len(results)

        print(f"Total: {total} geists")
        print(f"Success: {success} ({success * 100 // total if total > 0 else 0}%)")
        print(f"Errors: {errors}")

        if errors > 0:
            print("\nFailed geists:")
            for geist_id, result in results.items():
                if result["status"] == "error":
                    print(f"  ✗ {geist_id}: {result.get('error', 'Unknown error')}")
                    print(f"    Test with: geistfabrik test {geist_id} {vault_path}")

        print(f"\n{'=' * 60}\n")

        vault.close()
        return 0 if errors == 0 else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def validate_command(args: argparse.Namespace) -> int:
    """Execute the validate command to check geist files for errors.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Find vault path
    if hasattr(args, "vault") and args.vault:
        vault_path: Path = Path(args.vault).resolve()
    else:
        # Auto-detect vault
        vault_path_maybe = find_vault_root()
        if vault_path_maybe is None:
            print(
                "Error: No vault specified and could not auto-detect vault.",
                file=sys.stderr,
            )
            print("Either run from within a vault or specify vault path.", file=sys.stderr)
            return 1
        vault_path = vault_path_maybe

    # Check if vault is initialized
    geistfabrik_dir = vault_path / "_geistfabrik"
    if not geistfabrik_dir.exists():
        print(f"Error: GeistFabrik not initialized in {vault_path}", file=sys.stderr)
        print(f"Run: geistfabrik init {vault_path}", file=sys.stderr)
        return 1

    # Set up directories
    code_dir = geistfabrik_dir / "geists" / "code"
    tracery_dir = geistfabrik_dir / "geists" / "tracery"

    # Get default geists directories
    package_dir = Path(__file__).parent
    default_code_dir = package_dir / "default_geists" / "code"
    default_tracery_dir = package_dir / "default_geists" / "tracery"

    # Initialize validator
    validator = GeistValidator(strict=args.strict if hasattr(args, "strict") else False)

    # Determine what to validate
    if hasattr(args, "geist") and args.geist:
        # Validate specific geist
        geist_id = args.geist

        # Check code geist
        code_file = code_dir / f"{geist_id}.py"
        default_code_file = default_code_dir / f"{geist_id}.py"
        tracery_file = tracery_dir / f"{geist_id}.yaml"
        default_tracery_file = default_tracery_dir / f"{geist_id}.yaml"

        results = []
        if code_file.exists():
            results.append(validator.validate_code_geist(code_file))
        elif default_code_file.exists():
            results.append(validator.validate_code_geist(default_code_file))
        elif tracery_file.exists():
            results.append(validator.validate_tracery_geist(tracery_file))
        elif default_tracery_file.exists():
            results.append(validator.validate_tracery_geist(default_tracery_file))
        else:
            print(f"Error: Geist '{geist_id}' not found", file=sys.stderr)
            return 1
    else:
        # Validate all geists
        results = []
        # Custom geists
        results.extend(validator.validate_all(code_dir, tracery_dir))
        # Default geists
        results.extend(validator.validate_all(default_code_dir, default_tracery_dir))

    # Format output
    if hasattr(args, "format") and args.format == "json":
        # JSON output
        import json

        output = {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "geists": [
                {
                    "id": r.geist_id,
                    "type": r.geist_type,
                    "path": str(r.file_path),
                    "passed": r.passed,
                    "issues": [
                        {
                            "severity": i.severity,
                            "message": i.message,
                            "line": i.line_number,
                            "suggestion": i.suggestion,
                        }
                        for i in r.issues
                    ],
                }
                for r in results
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        print(f"Validating geists in {vault_path}/_geistfabrik/geists/...\n")

        for result in results:
            if result.passed:
                print(f"✅ {result.geist_type}/{result.geist_id}")
                if result.has_warnings or (hasattr(args, "verbose") and args.verbose):
                    for issue in result.issues:
                        if issue.severity == "info":
                            print(f"   ℹ️  {issue.message}")
                        elif issue.severity == "warning":
                            print(f"   ⚠️  {issue.message}")
            else:
                print(f"❌ {result.geist_type}/{result.geist_id}")
                for issue in result.issues:
                    if issue.severity == "error":
                        if issue.line_number:
                            print(f"   Line {issue.line_number}: {issue.message}")
                        else:
                            print(f"   {issue.message}")
                        if issue.suggestion and (
                            hasattr(args, "verbose") and args.verbose or len(result.issues) <= 3
                        ):
                            # Show suggestions for verbose mode or if few issues
                            print(f"      → {issue.suggestion}")
                    elif issue.severity == "warning":
                        print(f"   ⚠️  {issue.message}")

            print()

        # Summary
        passed = sum(1 for r in results if r.passed)
        errors = sum(1 for r in results if r.has_errors)
        warnings = sum(1 for r in results if r.has_warnings and not r.has_errors)

        print("─" * 60)
        print(f"Summary: {passed} passed, {errors} errors, {warnings} warnings")
        print("─" * 60)

    # Exit code
    if any(not r.passed for r in results):
        return 1
    return 0


def stats_command(args: argparse.Namespace) -> int:
    """Execute the stats command to show vault statistics.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Find vault path
        if hasattr(args, "vault") and args.vault:
            vault_path: Path = Path(args.vault).resolve()
        else:
            # Auto-detect vault
            vault_path_maybe = find_vault_root()
            if vault_path_maybe is None:
                print(
                    "Error: No vault specified and could not auto-detect vault.",
                    file=sys.stderr,
                )
                print("Either run from within a vault or specify vault path.", file=sys.stderr)
                return 1
            vault_path = vault_path_maybe

        # Check if vault is initialized
        db_path = vault_path / "_geistfabrik" / "vault.db"
        if not db_path.exists():
            print("Error: GeistFabrik not initialized in this vault.", file=sys.stderr)
            print(f"Run: geistfabrik init {vault_path}", file=sys.stderr)
            return 1

        # Load vault (no sync needed - just read existing DB)
        from .config_loader import GeistFabrikConfig, load_config

        vault = Vault(vault_path, db_path)
        config_path = vault_path / "_geistfabrik" / "config.yaml"
        config = load_config(config_path) if config_path.exists() else GeistFabrikConfig()

        # Collect statistics
        collector = StatsCollector(vault, config, history_days=args.history)

        # Compute embedding metrics if embeddings exist
        if collector.has_embeddings():
            latest = collector.get_latest_embeddings()
            if latest:
                session_date, embeddings, paths = latest
                metrics_computer = EmbeddingMetricsComputer(vault.db)
                force_recompute = getattr(args, "force_recompute", False)
                metrics = metrics_computer.compute_metrics(
                    session_date, embeddings, paths, force_recompute=force_recompute
                )
                collector.add_embedding_metrics(metrics)

                # Compute temporal drift analysis if multiple sessions exist
                temporal = collector.get_temporal_drift(session_date, days_back=args.history)
                if temporal:
                    collector.add_temporal_analysis(temporal)

        # Add verbose details if requested
        if args.verbose:
            collector.add_verbose_details()

        # Generate recommendations
        recommendations = generate_recommendations(collector.stats)

        # Format output
        formatter = StatsFormatter(collector.stats, recommendations, verbose=args.verbose)

        if args.json:
            output = formatter.format_json()
        else:
            output = formatter.format_text()

        print(output)

        vault.close()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="geistfabrik",
        description="A divergence engine for Obsidian vaults",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Lifecycle: Setup → Preview → Write
  geistfabrik init ~/my-vault                   # [1] Initialize vault (45 geists bundled)
  geistfabrik invoke ~/my-vault                 # [2] Preview suggestions
  geistfabrik invoke ~/my-vault --write         # [3] Write to journal

  # Advanced usage
  geistfabrik invoke ~/my-vault --geist drift   # Run specific geist
  geistfabrik invoke ~/my-vault --full          # All filtered suggestions
  geistfabrik invoke ~/my-vault --date 2025-01-15  # Replay session
  geistfabrik test my_geist ~/my-vault          # Test geist during development
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Init command
    init_parser = subparsers.add_parser(
        "init",
        help="[Step 1] Initialize GeistFabrik in a vault (creates _geistfabrik/ directory)",
    )
    init_parser.add_argument(
        "vault",
        type=str,
        help="Path to Obsidian vault",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Reinitialize even if _geistfabrik directory exists",
    )

    # Invoke command
    invoke_parser = subparsers.add_parser(
        "invoke",
        help=(
            "[Step 2] Run geists and generate suggestions "
            "(preview mode by default, use --write to save)"
        ),
    )
    invoke_parser.add_argument(
        "vault",
        type=str,
        help="Path to Obsidian vault",
    )
    invoke_parser.add_argument(
        "--geist",
        type=str,
        help="Run specific geist by ID (e.g., temporal_drift)",
    )
    invoke_parser.add_argument(
        "--geists",
        type=str,
        help="Run multiple specific geists by ID, comma-separated (e.g., drift,columbo,skeptic)",
    )
    invoke_parser.add_argument(
        "--date",
        type=str,
        help="Session date in YYYY-MM-DD format (defaults to today)",
    )
    invoke_parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Geist execution timeout in seconds (default: 5)",
    )
    invoke_parser.add_argument(
        "--full",
        action="store_true",
        help="Show all filtered suggestions (no sampling, filtering still applies)",
    )
    invoke_parser.add_argument(
        "--no-filter",
        action="store_true",
        dest="no_filter",
        help="Skip filtering pipeline (raw output from all geists)",
    )
    invoke_parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of suggestions to select in default mode (default: 5)",
    )
    invoke_parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Write suggestions to journal note at <vault>/geist journal/YYYY-MM-DD.md "
            "(default: preview only)"
        ),
    )
    invoke_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing session note (use with --write)",
    )
    invoke_parser.add_argument(
        "--diff",
        action="store_true",
        help="Show what changed since last session",
    )
    invoke_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed execution information",
    )
    invoke_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable performance profiling and diagnostic output for geist execution",
    )
    invoke_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-essential output (only show suggestions)",
    )

    # Test command
    test_parser = subparsers.add_parser(
        "test",
        help="[Debug] Test a single geist in isolation",
    )
    test_parser.add_argument(
        "geist_id",
        type=str,
        help="ID of the geist to test",
    )
    test_parser.add_argument(
        "vault",
        type=str,
        help="Path to Obsidian vault",
    )
    test_parser.add_argument(
        "--date",
        type=str,
        help="Session date in YYYY-MM-DD format (defaults to today)",
    )
    test_parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Geist execution timeout in seconds (default: 5)",
    )
    test_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed execution information",
    )
    test_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable performance profiling and diagnostic output",
    )

    # Test-all command
    test_all_parser = subparsers.add_parser(
        "test-all",
        help="[Debug] Test all geists and report results",
    )
    test_all_parser.add_argument(
        "vault",
        type=str,
        help="Path to Obsidian vault",
    )
    test_all_parser.add_argument(
        "--date",
        type=str,
        help="Session date in YYYY-MM-DD format (defaults to today)",
    )
    test_all_parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Geist execution timeout in seconds (default: 5)",
    )
    test_all_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed execution information",
    )
    test_all_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable performance profiling and diagnostic output",
    )

    # Stats command
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show vault statistics and health metrics",
    )
    stats_parser.add_argument(
        "vault",
        type=str,
        nargs="?",
        help="Path to Obsidian vault (optional, auto-detects from current directory)",
    )
    stats_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed statistics and breakdowns",
    )
    stats_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON for scripting",
    )
    stats_parser.add_argument(
        "--history",
        type=int,
        default=30,
        help="Days of session history to analyze (default: 30)",
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate geist files for errors without executing them",
    )
    validate_parser.add_argument(
        "vault",
        type=str,
        nargs="?",
        help="Path to Obsidian vault (optional, auto-detects from current directory)",
    )
    validate_parser.add_argument(
        "--geist",
        type=str,
        help="Validate specific geist by ID",
    )
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    validate_parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    validate_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed validation information",
    )

    args = parser.parse_args()

    # Show help if no command specified
    if not args.command:
        parser.print_help()
        return 1

    # Route to command handler
    if args.command == "init":
        return init_command(args)
    elif args.command == "invoke":
        return invoke_command(args)
    elif args.command == "test":
        return test_command(args)
    elif args.command == "test-all":
        return test_all_command(args)
    elif args.command == "stats":
        return stats_command(args)
    elif args.command == "validate":
        return validate_command(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
