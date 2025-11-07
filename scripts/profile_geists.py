#!/usr/bin/env python3
"""Profile real geist execution to measure optimization impact.

This script runs actual geists on real vaults and measures:
- Total execution time
- Cache hit rates
- Method call counts
- Time breakdown by operation type

Usage:
    python scripts/profile_geists.py
    python scripts/profile_geists.py --geist hidden_hub
    python scripts/profile_geists.py --vault /path/to/vault
"""

import argparse
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from geistfabrik.embeddings import Session
from geistfabrik.geist_executor import GeistExecutor
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


class ProfilingVaultContext(VaultContext):
    """VaultContext with profiling instrumentation."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.profile_stats: Dict[str, Any] = {
            "call_counts": defaultdict(int),
            "cache_hits": defaultdict(int),
            "cache_misses": defaultdict(int),
            "timings": defaultdict(float),
        }

    def _profile_method(self, method_name: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Wrap method call with profiling."""
        self.profile_stats["call_counts"][method_name] += 1

        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start

        self.profile_stats["timings"][method_name] += elapsed
        return result

    def backlinks(self, note):
        """Instrumented backlinks."""
        method_name = "backlinks"
        self.profile_stats["call_counts"][method_name] += 1

        # Check cache
        if note.path in self._backlinks_cache:
            self.profile_stats["cache_hits"][method_name] += 1
        else:
            self.profile_stats["cache_misses"][method_name] += 1

        start = time.perf_counter()
        result = super().backlinks(note)
        elapsed = time.perf_counter() - start

        self.profile_stats["timings"][method_name] += elapsed
        return result

    def outgoing_links(self, note):
        """Instrumented outgoing_links."""
        method_name = "outgoing_links"
        self.profile_stats["call_counts"][method_name] += 1

        # Check cache
        if note.path in self._outgoing_links_cache:
            self.profile_stats["cache_hits"][method_name] += 1
        else:
            self.profile_stats["cache_misses"][method_name] += 1

        start = time.perf_counter()
        result = super().outgoing_links(note)
        elapsed = time.perf_counter() - start

        self.profile_stats["timings"][method_name] += elapsed
        return result

    def graph_neighbors(self, note):
        """Instrumented graph_neighbors."""
        method_name = "graph_neighbors"
        self.profile_stats["call_counts"][method_name] += 1

        # Check cache
        if note.path in self._graph_neighbors_cache:
            self.profile_stats["cache_hits"][method_name] += 1
        else:
            self.profile_stats["cache_misses"][method_name] += 1

        start = time.perf_counter()
        result = super().graph_neighbors(note)
        elapsed = time.perf_counter() - start

        self.profile_stats["timings"][method_name] += elapsed
        return result

    def similarity(self, a, b):
        """Instrumented similarity."""
        method_name = "similarity"
        self.profile_stats["call_counts"][method_name] += 1

        # Check cache
        sorted_paths = sorted([a.path, b.path])
        cache_key = (sorted_paths[0], sorted_paths[1])

        if cache_key in self._similarity_cache:
            self.profile_stats["cache_hits"][method_name] += 1
        else:
            self.profile_stats["cache_misses"][method_name] += 1

        start = time.perf_counter()
        result = super().similarity(a, b)
        elapsed = time.perf_counter() - start

        self.profile_stats["timings"][method_name] += elapsed
        return result

    def neighbours(self, note, k=10):
        """Instrumented neighbours."""
        method_name = "neighbours"
        self.profile_stats["call_counts"][method_name] += 1

        # Check cache
        cache_key = (note.path, k)
        if cache_key in self._neighbours_cache:
            self.profile_stats["cache_hits"][method_name] += 1
        else:
            self.profile_stats["cache_misses"][method_name] += 1

        start = time.perf_counter()
        result = super().neighbours(note, k)
        elapsed = time.perf_counter() - start

        self.profile_stats["timings"][method_name] += elapsed
        return result


def profile_geist(vault_path: str, geist_id: str) -> Dict[str, Any]:
    """Profile a single geist execution.

    Args:
        vault_path: Path to Obsidian vault
        geist_id: ID of geist to profile

    Returns:
        Dict with profiling results
    """
    print(f"\n{'=' * 70}")
    print(f"Profiling geist: {geist_id}")
    print(f"Vault: {vault_path}")
    print(f"{'=' * 70}\n")

    # Load vault
    vault = Vault(vault_path)
    vault.sync()

    # Compute embeddings
    session = Session(date=datetime(2025, 1, 15), db=vault.db)
    session.compute_embeddings(vault.all_notes())

    # Create profiling context
    context = ProfilingVaultContext(vault, session)

    # Load geists (use empty custom dir, load only defaults)
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        executor = GeistExecutor(
            geists_dir=Path(tmpdir),
            default_geists_dir=Path("src/geistfabrik/default_geists/code"),
        )
        executor.load_geists()

        # Execute geist
        print(f"Executing {geist_id}...")
        start_time = time.perf_counter()

        try:
            suggestions = executor.execute_geist(geist_id, context)
            elapsed = time.perf_counter() - start_time
            success = True
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            suggestions = []
            success = False
            print(f"ERROR: {e}")

    # Print results
    print(f"\n{'─' * 70}")
    print("EXECUTION SUMMARY")
    print(f"{'─' * 70}")
    print(f"Status: {'✅ SUCCESS' if success else '❌ FAILED'}")
    print(f"Total time: {elapsed * 1000:.2f}ms")
    print(f"Suggestions: {len(suggestions)}")
    print(f"Vault notes: {len(context.notes())}")

    # Print profiling stats
    stats = context.profile_stats

    if stats["call_counts"]:
        print(f"\n{'─' * 70}")
        print("METHOD CALL STATISTICS")
        print(f"{'─' * 70}")
        print(
            f"{'Method':<20} {'Calls':>8} {'Hits':>8} {'Misses':>8} "
            f"{'Hit Rate':>10} {'Time (ms)':>12}"
        )
        print(f"{'─' * 70}")

        total_time = sum(stats["timings"].values())

        for method in sorted(stats["call_counts"].keys()):
            calls = stats["call_counts"][method]
            hits = stats["cache_hits"].get(method, 0)
            misses = stats["cache_misses"].get(method, 0)
            hit_rate = (hits / calls * 100) if calls > 0 else 0
            method_time = stats["timings"][method]
            # time_pct = (method_time / total_time * 100) if total_time > 0 else 0

            print(
                f"{method:<20} {calls:>8} {hits:>8} {misses:>8} "
                f"{hit_rate:>9.1f}% {method_time * 1000:>11.2f}ms"
            )

        print(f"{'─' * 70}")
        print(
            f"{'TOTAL':<20} {sum(stats['call_counts'].values()):>8} "
            f"{sum(stats['cache_hits'].values()):>8} "
            f"{sum(stats['cache_misses'].values()):>8} "
            f"{'':>10} {total_time * 1000:>11.2f}ms"
        )

        # Cache efficiency summary
        total_hits = sum(stats["cache_hits"].values())
        total_misses = sum(stats["cache_misses"].values())

        if total_hits + total_misses > 0:
            overall_hit_rate = total_hits / (total_hits + total_misses) * 100
            print(f"\n{'─' * 70}")
            print("CACHE EFFICIENCY")
            print(f"{'─' * 70}")
            print(f"Overall hit rate: {overall_hit_rate:.1f}%")
            pct = total_time / elapsed * 100
            print(f"Time in cached methods: {total_time * 1000:.2f}ms ({pct:.1f}% of total)")

    print(f"\n{'=' * 70}\n")

    return {
        "geist_id": geist_id,
        "success": success,
        "elapsed": elapsed,
        "suggestions": len(suggestions),
        "notes": len(context.notes()),
        "stats": stats,
    }


def main():
    parser = argparse.ArgumentParser(description="Profile geist execution")
    parser.add_argument(
        "--vault",
        default="testdata/kepano-obsidian-main",
        help="Path to vault (default: testdata/kepano-obsidian-main)",
    )
    parser.add_argument(
        "--geist",
        default=None,
        help="Specific geist to profile (default: profile common geists)",
    )
    args = parser.parse_args()

    # Default geists to profile (graph-heavy ones that should benefit from caching)
    geists_to_profile = [
        "hidden_hub",
        "stub_expander",
        "bridge_hunter",
    ]

    if args.geist:
        geists_to_profile = [args.geist]

    results: List[Dict[str, Any]] = []

    for geist_id in geists_to_profile:
        result = profile_geist(args.vault, geist_id)
        results.append(result)

    # Print summary
    if len(results) > 1:
        print(f"\n{'=' * 70}")
        print("OVERALL SUMMARY")
        print(f"{'=' * 70}\n")

        for result in results:
            status = "✅" if result["success"] else "❌"
            print(f"{status} {result['geist_id']:<20} {result['elapsed'] * 1000:>8.2f}ms")

        print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()
