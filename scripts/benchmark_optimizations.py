#!/usr/bin/env python3
"""Benchmark sklearn optimizations for GeistFabrik.

This script tests different optimization combinations to find the best configuration
for large vault performance. It tests 8 configurations × 9 geists = 72 runs.

Usage:
    python scripts/benchmark_optimizations.py --vault /path/to/vault --output results.json
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Test matrix: 8 configurations
CONFIGS = [
    {
        "name": "baseline",
        "env": {
            "GEIST_ASSUME_FINITE": "false",
            "GEIST_FAST_PATH": "false",
            "GEIST_VECTORIZE": "false",
        },
    },
    {
        "name": "opt1_assume_finite",
        "env": {
            "GEIST_ASSUME_FINITE": "true",
            "GEIST_FAST_PATH": "false",
            "GEIST_VECTORIZE": "false",
        },
    },
    {
        "name": "opt2_fast_path",
        "env": {
            "GEIST_ASSUME_FINITE": "false",
            "GEIST_FAST_PATH": "true",
            "GEIST_VECTORIZE": "false",
        },
    },
    {
        "name": "opt3_vectorize",
        "env": {
            "GEIST_ASSUME_FINITE": "false",
            "GEIST_FAST_PATH": "false",
            "GEIST_VECTORIZE": "true",
        },
    },
    {
        "name": "opt1+2",
        "env": {
            "GEIST_ASSUME_FINITE": "true",
            "GEIST_FAST_PATH": "true",
            "GEIST_VECTORIZE": "false",
        },
    },
    {
        "name": "opt1+3",
        "env": {
            "GEIST_ASSUME_FINITE": "true",
            "GEIST_FAST_PATH": "false",
            "GEIST_VECTORIZE": "true",
        },
    },
    {
        "name": "opt2+3",
        "env": {
            "GEIST_ASSUME_FINITE": "false",
            "GEIST_FAST_PATH": "true",
            "GEIST_VECTORIZE": "true",
        },
    },
    {
        "name": "all_optimizations",
        "env": {
            "GEIST_ASSUME_FINITE": "true",
            "GEIST_FAST_PATH": "true",
            "GEIST_VECTORIZE": "true",
        },
    },
]

# Test geists: 6 problem geists + 3 control geists
GEISTS = [
    # Problem geists (timeout or slow on 10k vault)
    "antithesis_generator",
    "hidden_hub",
    "pattern_finder",
    "bridge_hunter",
    "method_scrambler",
    "columbo",
    # Control geists (fast, should stay fast)
    "scale_shifter",
    "stub_expander",
    "recent_focus",
]


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    config: str
    geist: str
    elapsed_time: float
    timeout: bool
    suggestion_count: int
    suggestions_hash: str
    error: Optional[str] = None


def compute_suggestions_hash(suggestions: List[str]) -> str:
    """Compute MD5 hash of suggestions for correctness validation."""
    content = "\n".join(sorted(suggestions))
    return hashlib.md5(content.encode()).hexdigest()


def run_geist(
    geist_id: str, vault_path: str, config_env: Dict[str, str], timeout: int = 120
) -> BenchmarkResult:
    """Run a single geist with given environment configuration.

    Args:
        geist_id: ID of geist to test
        vault_path: Path to vault
        config_env: Environment variables to set
        timeout: Timeout in seconds

    Returns:
        BenchmarkResult with timing and correctness data
    """
    # Build environment with optimization flags
    env = os.environ.copy()
    env.update(config_env)

    # Fixed date for determinism
    test_date = "2025-01-15"

    # Build command
    cmd = [
        "uv",
        "run",
        "geistfabrik",
        "invoke",
        vault_path,
        "--geist",
        geist_id,
        "--date",
        test_date,
        "--timeout",
        str(timeout),
    ]

    # Execute
    start_time = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout + 10,  # Give extra time for subprocess cleanup
        )
        elapsed = time.perf_counter() - start_time

        # Parse output to extract suggestions
        suggestions = []
        timed_out = False

        for line in result.stdout.split("\n"):
            if line.strip().startswith("-"):
                # Suggestion line
                suggestions.append(line.strip())
            elif "timed out" in line.lower():
                timed_out = True

        # Check for errors
        error = None
        if result.returncode != 0 and not timed_out:
            error = result.stderr or "Unknown error"

        return BenchmarkResult(
            config=config_env.get("name", "unknown"),
            geist=geist_id,
            elapsed_time=elapsed,
            timeout=timed_out,
            suggestion_count=len(suggestions),
            suggestions_hash=compute_suggestions_hash(suggestions),
            error=error,
        )

    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - start_time
        return BenchmarkResult(
            config=config_env.get("name", "unknown"),
            geist=geist_id,
            elapsed_time=elapsed,
            timeout=True,
            suggestion_count=0,
            suggestions_hash="",
            error="Process timeout",
        )


def main():
    parser = argparse.ArgumentParser(description="Benchmark sklearn optimizations")
    parser.add_argument(
        "--vault",
        required=True,
        help="Path to vault (e.g., /tmp/10000-markdown-files/10000 markdown files/)",
    )
    parser.add_argument(
        "--output",
        default="benchmark_results.json",
        help="Output JSON file (default: benchmark_results.json)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout per geist in seconds (default: 120)",
    )
    args = parser.parse_args()

    vault_path = args.vault
    output_path = args.output

    # Verify vault exists
    if not Path(vault_path).exists():
        print(f"ERROR: Vault not found: {vault_path}")
        sys.exit(1)

    print("=" * 80)
    print("GeistFabrik sklearn Optimization Benchmark")
    print("=" * 80)
    print(f"Vault: {vault_path}")
    print(f"Output: {output_path}")
    print(f"Configurations: {len(CONFIGS)}")
    print(f"Geists: {len(GEISTS)}")
    print(f"Total runs: {len(CONFIGS) * len(GEISTS)}")
    print(f"Timeout: {args.timeout}s per geist")
    print("=" * 80)
    print()

    results: List[Dict[str, Any]] = []
    total_runs = len(CONFIGS) * len(GEISTS)
    current_run = 0

    for config in CONFIGS:
        config_name = config["name"]
        config_env = config["env"]

        print(f"\n{'─' * 80}")
        print(f"Configuration: {config_name}")
        print(f"{'─' * 80}")
        print(f"  GEIST_ASSUME_FINITE={config_env['GEIST_ASSUME_FINITE']}")
        print(f"  GEIST_FAST_PATH={config_env['GEIST_FAST_PATH']}")
        print(f"  GEIST_VECTORIZE={config_env['GEIST_VECTORIZE']}")
        print()

        for geist in GEISTS:
            current_run += 1
            print(
                f"[{current_run}/{total_runs}] Running {geist:<25} with {config_name:<20} ... ",
                end="",
                flush=True,
            )

            result = run_geist(geist, vault_path, config_env, timeout=args.timeout)

            # Print result
            if result.timeout:
                print(f"⏱️  TIMEOUT ({result.elapsed_time:.1f}s)")
            elif result.error:
                print(f"❌ ERROR: {result.error[:50]}")
            else:
                print(
                    f"✅ {result.elapsed_time:6.2f}s "
                    f"({result.suggestion_count} suggestions, "
                    f"hash: {result.suggestions_hash[:8]})"
                )

            # Add to results
            results.append(
                {
                    "config": config_name,
                    "geist": geist,
                    "elapsed_time": result.elapsed_time,
                    "timeout": result.timeout,
                    "suggestion_count": result.suggestion_count,
                    "suggestions_hash": result.suggestions_hash,
                    "error": result.error,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Save intermediate results after each geist
            with open(output_path, "w") as f:
                json.dump(
                    {
                        "metadata": {
                            "vault": vault_path,
                            "timeout": args.timeout,
                            "test_date": "2025-01-15",
                            "completed_runs": current_run,
                            "total_runs": total_runs,
                        },
                        "results": results,
                    },
                    f,
                    indent=2,
                )

    # Print summary
    print(f"\n{'=' * 80}")
    print("BENCHMARK COMPLETE")
    print(f"{'=' * 80}")
    print(f"Total runs: {len(results)}")
    print(f"Results saved to: {output_path}")
    print()
    print("Next step: Run analyze_benchmarks.py to analyze results")
    print(f"  python scripts/analyze_benchmarks.py --input {output_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
