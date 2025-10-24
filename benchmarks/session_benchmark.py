#!/usr/bin/env python3
"""Benchmark a full GeistFabrik session.

Measures timing for each phase:
1. Vault sync (file parsing + DB operations)
2. Embedding computation (sentence-transformers)
3. Geist execution (all code geists)
4. Filtering (if implemented)
5. Journal writing

Identifies algorithmic complexity and bottlenecks.
"""

import time
from datetime import datetime
from pathlib import Path

from geistfabrik import GeistExecutor, Vault, VaultContext
from geistfabrik.embeddings import EmbeddingComputer, Session
from geistfabrik.function_registry import FunctionRegistry


class Timer:
    """Context manager for timing code blocks."""

    def __init__(self, name: str):
        self.name = name
        self.start_time = 0.0
        self.elapsed = 0.0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, *args):
        self.elapsed = time.time() - self.start_time
        print(f"  {self.name}: {self.elapsed:.3f}s")


def benchmark_session(vault_path: str, geists_dir: str):
    """Benchmark a complete GeistFabrik session.

    Args:
        vault_path: Path to Obsidian vault
        geists_dir: Path to geists directory
    """
    print("=" * 80)
    print("GeistFabrik Session Benchmark")
    print("=" * 80)
    print(f"Vault: {vault_path}")
    print(f"Geists: {geists_dir}")
    print()

    total_start = time.time()

    # Phase 1: Vault Sync
    print("Phase 1: Vault Sync")
    with Timer("  Total vault sync"):
        vault = Vault(vault_path, ":memory:")

        with Timer("    File parsing + DB writes"):
            vault.sync()

    note_count = len(vault.all_notes())
    print(f"  Notes loaded: {note_count}")
    print()

    # Phase 2: Embedding Computation
    print("Phase 2: Embedding Computation")
    session_date = datetime(2023, 10, 1)
    session = Session(session_date, vault.db)

    with Timer("  Total embedding computation"):
        notes = vault.all_notes()

        with Timer("    Model initialization"):
            # Force model load
            computer = EmbeddingComputer()
            _ = computer.model  # Trigger lazy load

        with Timer("    Embedding computation (all notes)"):
            session.compute_embeddings(notes)

    print(f"  Embeddings computed: {len(notes)}")
    print("  Embedding dimension: 387 (384 semantic + 3 temporal)")
    print()

    # Phase 3: VaultContext Setup
    print("Phase 3: VaultContext Setup")
    with Timer("  VaultContext initialization"):
        function_registry = FunctionRegistry()
        vault_context = VaultContext(
            vault=vault, session=session, seed=20231001, function_registry=function_registry
        )
    print()

    # Phase 4: Geist Loading
    print("Phase 4: Geist Loading")
    geists_path = Path(geists_dir)
    executor = GeistExecutor(geists_path, timeout=5)

    with Timer("  Geist module loading"):
        executor.load_geists()

    geist_count = len(executor.geists)
    print(f"  Geists loaded: {geist_count}")
    print()

    # Phase 5: Geist Execution
    print("Phase 5: Geist Execution")
    all_suggestions = []

    with Timer("  Total geist execution"):
        for geist_id in sorted(executor.geists.keys()):
            with Timer(f"    Geist '{geist_id}'"):
                suggestions = executor.execute_geist(geist_id, vault_context)
                all_suggestions.extend(suggestions)

    print(f"  Total suggestions generated: {len(all_suggestions)}")
    print()

    # Summary
    total_elapsed = time.time() - total_start
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total session time: {total_elapsed:.3f}s")
    print(f"Notes: {note_count}")
    print(f"Geists: {geist_count}")
    print(f"Suggestions: {len(all_suggestions)}")
    print(f"Avg time per note: {total_elapsed / note_count:.3f}s")
    print(f"Avg time per geist: {total_elapsed / geist_count if geist_count > 0 else 0:.3f}s")
    print()

    vault.close()


def main():
    """Run benchmark on kepano test vault."""
    # Find test vault
    repo_root = Path(__file__).parent.parent
    vault_path = repo_root / "testdata" / "kepano-obsidian-main"
    geists_dir = repo_root / "src" / "geistfabrik" / "default_geists" / "code"

    if not vault_path.exists():
        print(f"Error: Test vault not found at {vault_path}")
        return

    if not geists_dir.exists():
        print(f"Error: Geists directory not found at {geists_dir}")
        return

    benchmark_session(str(vault_path), str(geists_dir))


if __name__ == "__main__":
    main()
