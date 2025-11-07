#!/usr/bin/env python3
"""Analyze sklearn optimization benchmark results.

This script analyzes the JSON output from benchmark_optimizations.py to:
1. Validate correctness (all configs produce same results)
2. Compare performance across configurations
3. Identify the winning configuration
4. Generate recommendations

Usage:
    python scripts/analyze_benchmarks.py --input benchmark_results.json
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


def load_results(input_path: str) -> Dict[str, Any]:
    """Load benchmark results from JSON file."""
    with open(input_path) as f:
        return json.load(f)


def validate_correctness(results: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Validate that all configurations produce the same results.

    Args:
        results: List of benchmark results

    Returns:
        Dict mapping geist_id to list of unique hashes (should be length 1)
    """
    # Group by geist
    geist_hashes: Dict[str, List[str]] = defaultdict(list)

    for result in results:
        geist = result["geist"]
        hash_val = result["suggestions_hash"]

        # Only include non-timeout, non-error results
        if not result["timeout"] and not result["error"] and hash_val:
            if hash_val not in geist_hashes[geist]:
                geist_hashes[geist].append(hash_val)

    return dict(geist_hashes)


def analyze_performance(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Analyze performance by configuration.

    Args:
        results: List of benchmark results

    Returns:
        Dict mapping config name to performance metrics
    """
    # Group by config
    config_results: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for result in results:
        config_results[result["config"]].append(result)

    # Compute metrics for each config
    metrics: Dict[str, Dict[str, Any]] = {}

    for config, config_data in config_results.items():
        successful = [r for r in config_data if not r["timeout"] and not r["error"]]
        timeouts = [r for r in config_data if r["timeout"]]
        errors = [r for r in config_data if r["error"] and not r["timeout"]]

        if successful:
            avg_time = sum(r["elapsed_time"] for r in successful) / len(successful)
            total_time = sum(r["elapsed_time"] for r in successful)
        else:
            avg_time = 0.0
            total_time = 0.0

        metrics[config] = {
            "successful": len(successful),
            "timeouts": len(timeouts),
            "errors": len(errors),
            "avg_time": avg_time,
            "total_time": total_time,
            "timeout_geists": [r["geist"] for r in timeouts],
        }

    return metrics


def compare_to_baseline(
    results: List[Dict[str, Any]], baseline_config: str = "baseline"
) -> Dict[str, Dict[str, float]]:
    """Compare each configuration to baseline.

    Args:
        results: List of benchmark results
        baseline_config: Name of baseline configuration

    Returns:
        Dict mapping geist to dict of config: speedup ratios
    """
    # Group by geist and config
    geist_times: Dict[str, Dict[str, float]] = defaultdict(dict)

    for result in results:
        if not result["timeout"] and not result["error"]:
            geist = result["geist"]
            config = result["config"]
            time = result["elapsed_time"]
            geist_times[geist][config] = time

    # Compute speedups relative to baseline
    speedups: Dict[str, Dict[str, float]] = {}

    for geist, config_times in geist_times.items():
        if baseline_config in config_times:
            baseline_time = config_times[baseline_config]
            speedups[geist] = {}

            for config, time in config_times.items():
                if config != baseline_config:
                    speedup = baseline_time / time if time > 0 else 0.0
                    speedups[geist][config] = speedup

    return speedups


def identify_winner(metrics: Dict[str, Dict[str, Any]]) -> str:
    """Identify the winning configuration.

    Winner is determined by:
    1. Fewest timeouts
    2. Fastest average time (among configs with same timeout count)

    Args:
        metrics: Performance metrics by configuration

    Returns:
        Name of winning configuration
    """
    # Sort by timeouts (ascending), then avg_time (ascending)
    sorted_configs = sorted(metrics.items(), key=lambda x: (x[1]["timeouts"], x[1]["avg_time"]))

    return sorted_configs[0][0]


def main():
    parser = argparse.ArgumentParser(description="Analyze sklearn optimization benchmarks")
    parser.add_argument(
        "--input",
        required=True,
        help="Input JSON file from benchmark_optimizations.py",
    )
    args = parser.parse_args()

    input_path = args.input

    # Verify input exists
    if not Path(input_path).exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)

    print("=" * 80)
    print("sklearn Optimization Benchmark Analysis")
    print("=" * 80)
    print(f"Input: {input_path}")
    print()

    # Load results
    data = load_results(input_path)
    results = data["results"]
    metadata = data["metadata"]

    print(f"Vault: {metadata['vault']}")
    print(f"Total runs: {len(results)}")
    print(f"Test date: {metadata['test_date']}")
    print()

    # Validate correctness
    print("─" * 80)
    print("CORRECTNESS VALIDATION")
    print("─" * 80)

    geist_hashes = validate_correctness(results)
    correctness_ok = True

    for geist, hashes in sorted(geist_hashes.items()):
        if len(hashes) > 1:
            print(f"❌ {geist}: {len(hashes)} different outputs (INCONSISTENT)")
            correctness_ok = False
        else:
            print(f"✅ {geist}: consistent across all configs")

    if correctness_ok:
        print("\n✅ All configurations produce identical results")
    else:
        print("\n⚠️  WARNING: Some configurations produce different results!")
        print("This may indicate bugs in the optimizations.")

    print()

    # Analyze performance
    print("─" * 80)
    print("PERFORMANCE BY CONFIGURATION")
    print("─" * 80)

    metrics = analyze_performance(results)

    headers = (
        f"{'Configuration':<25} {'Success':>8} {'Timeout':>8} "
        f"{'Errors':>7} {'Avg Time':>10} {'Total':>10}"
    )
    print(headers)
    print("─" * 80)

    for config in sorted(metrics.keys()):
        m = metrics[config]
        print(
            f"{config:<25} {m['successful']:>8} {m['timeouts']:>8} "
            f"{m['errors']:>7} {m['avg_time']:>9.2f}s {m['total_time']:>9.2f}s"
        )

    print()

    # Compare to baseline
    print("─" * 80)
    print("SPEEDUP RELATIVE TO BASELINE")
    print("─" * 80)

    speedups = compare_to_baseline(results)

    # Compute average speedup for each config
    config_speedups: Dict[str, List[float]] = defaultdict(list)

    for geist, config_data in speedups.items():
        for config, speedup in config_data.items():
            config_speedups[config].append(speedup)

    # Print average speedups
    print(f"{'Configuration':<25} {'Avg Speedup':>12} {'Min':>8} {'Max':>8}")
    print("─" * 80)

    for config in sorted(config_speedups.keys()):
        speedup_list = config_speedups[config]
        avg = sum(speedup_list) / len(speedup_list)
        min_speedup = min(speedup_list)
        max_speedup = max(speedup_list)

        speedup_pct = (avg - 1.0) * 100
        sign = "+" if speedup_pct > 0 else ""
        speedup_line = (
            f"{config:<25} {avg:>11.3f}x ({sign}{speedup_pct:.1f}%) "
            f"{min_speedup:>7.2f}x {max_speedup:>7.2f}x"
        )
        print(speedup_line)

    print()

    # Per-geist speedup details
    print("─" * 80)
    print("PER-GEIST SPEEDUP (best config for each geist)")
    print("─" * 80)

    for geist in sorted(speedups.keys()):
        config_data = speedups[geist]
        if config_data:
            best_config = max(config_data.items(), key=lambda x: x[1])
            config, speedup = best_config
            speedup_pct = (speedup - 1.0) * 100
            print(f"{geist:<25} → {config:<25} {speedup:>6.2f}x (+{speedup_pct:.1f}%)")

    print()

    # Identify winner
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    winner = identify_winner(metrics)
    winner_metrics = metrics[winner]

    print(f"🏆 Winner: {winner}")
    print()
    print("Metrics:")
    print(f"  • Successful runs: {winner_metrics['successful']}/{len(results) // len(metrics)}")
    print(f"  • Timeouts: {winner_metrics['timeouts']}")
    print(f"  • Average time: {winner_metrics['avg_time']:.2f}s")

    if winner_metrics["timeout_geists"]:
        print(f"  • Timed out geists: {', '.join(winner_metrics['timeout_geists'])}")

    print()

    # Compute overall speedup
    baseline_metrics = metrics.get("baseline")
    if baseline_metrics and winner != "baseline":
        baseline_avg = baseline_metrics["avg_time"]
        winner_avg = winner_metrics["avg_time"]
        speedup = baseline_avg / winner_avg if winner_avg > 0 else 0.0
        speedup_pct = (speedup - 1.0) * 100

        print(f"Overall speedup: {speedup:.2f}x (+{speedup_pct:.1f}% improvement)")
        print()

    # Implementation instructions
    print("─" * 80)
    print("NEXT STEPS")
    print("─" * 80)
    print()
    print(f"1. Set these environment variables in embeddings.py based on '{winner}':")
    print()

    # Decode winner config
    winner_config = next(
        c
        for c in [
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
        if c["name"] == winner
    )

    print("   SKLEARN_OPTIMIZATIONS = {")
    for key, val in winner_config["env"].items():
        python_key = key.replace("GEIST_", "").lower()
        python_val = "True" if val == "true" else "False"
        print(f'       "{python_key}": {python_val},')
    print("   }")
    print()
    print("2. Remove environment variable reading code")
    print("3. Run validation: ./scripts/validate.sh")
    print("4. Commit changes with performance improvements documented")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
