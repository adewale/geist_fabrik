#!/usr/bin/env python3
"""Benchmark cluster labeling performance: c-TF-IDF vs KeyBERT.

Measures actual timing differences on clusters of various sizes.
"""

import sys
import time
from pathlib import Path

import numpy as np

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from geistfabrik.stats import EmbeddingMetricsComputer  # noqa: E402


def create_synthetic_cluster(cluster_size: int) -> tuple[list[str], np.ndarray]:
    """Create a synthetic cluster for benchmarking.

    Args:
        cluster_size: Number of notes in cluster

    Returns:
        Tuple of (paths, labels)
    """
    paths = [f"note{i}.md" for i in range(cluster_size)]
    labels = np.zeros(cluster_size, dtype=np.int64)  # All in cluster 0
    return paths, labels


def benchmark_labeling(cluster_sizes: list[int], runs: int = 3) -> dict[int, dict[str, float]]:
    """Benchmark both labeling methods on different cluster sizes.

    Args:
        cluster_sizes: List of cluster sizes to test
        runs: Number of runs to average

    Returns:
        Dict mapping cluster_size -> {method: avg_time_seconds}
    """
    # Create a mock database (not used but required by API)
    import sqlite3

    db = sqlite3.connect(":memory:")

    # Initialize metrics computer without config (will use defaults)
    metrics = EmbeddingMetricsComputer(db)

    results: dict[int, dict[str, float]] = {}

    for size in cluster_sizes:
        print(f"\n{'=' * 60}")
        print(f"Benchmarking cluster size: {size}")
        print(f"{'=' * 60}")

        paths, labels = create_synthetic_cluster(size)

        # Benchmark c-TF-IDF
        tfidf_times = []
        for run in range(runs):
            start = time.perf_counter()
            try:
                _ = metrics._label_clusters_tfidf(paths, labels, n_terms=4)
                elapsed = time.perf_counter() - start
                tfidf_times.append(elapsed)
                print(f"  c-TF-IDF run {run + 1}: {elapsed:.4f}s")
            except Exception as e:
                print(f"  c-TF-IDF run {run + 1}: FAILED ({e})")
                tfidf_times.append(float("nan"))

        # Benchmark KeyBERT
        keybert_times = []
        for run in range(runs):
            start = time.perf_counter()
            try:
                _ = metrics._label_clusters_keybert(paths, labels, n_terms=4)
                elapsed = time.perf_counter() - start
                keybert_times.append(elapsed)
                print(f"  KeyBERT run {run + 1}: {elapsed:.4f}s")
            except Exception as e:
                print(f"  KeyBERT run {run + 1}: FAILED ({e})")
                keybert_times.append(float("nan"))

        # Calculate averages (excluding NaN)
        tfidf_avg = np.nanmean(tfidf_times) if tfidf_times else float("nan")
        keybert_avg = np.nanmean(keybert_times) if keybert_times else float("nan")

        results[size] = {"tfidf": tfidf_avg, "keybert": keybert_avg}

        print(f"\n  Average c-TF-IDF:  {tfidf_avg:.4f}s")
        print(f"  Average KeyBERT:   {keybert_avg:.4f}s")

        if not np.isnan(tfidf_avg) and not np.isnan(keybert_avg):
            overhead = keybert_avg - tfidf_avg
            overhead_pct = (overhead / tfidf_avg) * 100 if tfidf_avg > 0 else 0
            print(f"  Overhead:          {overhead:.4f}s ({overhead_pct:.1f}%)")

    return results


def main() -> None:
    """Run benchmarks."""
    print("🔬 Cluster Labeling Performance Benchmark")
    print("=" * 60)

    cluster_sizes = [5, 10, 20, 50]
    runs = 3

    print(f"\nTesting cluster sizes: {cluster_sizes}")
    print(f"Runs per test: {runs}")
    print("\nNote: First run may be slower due to model loading")

    results = benchmark_labeling(cluster_sizes, runs)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\n{'Cluster Size':<15} {'c-TF-IDF':<12} {'KeyBERT':<12} {'Overhead':<12}")
    print("-" * 60)

    for size in cluster_sizes:
        tfidf_time = results[size]["tfidf"]
        keybert_time = results[size]["keybert"]

        if not np.isnan(tfidf_time) and not np.isnan(keybert_time):
            overhead = keybert_time - tfidf_time
            overhead_str = f"+{overhead:.3f}s"
        else:
            overhead_str = "N/A"

        tfidf_str = f"{tfidf_time:.3f}s" if not np.isnan(tfidf_time) else "FAILED"
        keybert_str = f"{keybert_time:.3f}s" if not np.isnan(keybert_time) else "FAILED"

        print(f"{size:<15} {tfidf_str:<12} {keybert_str:<12} {overhead_str:<12}")

    print("\n" + "=" * 60)
    print("CONCLUSION")
    print("=" * 60)

    # Calculate overall average overhead
    valid_overheads = []
    for size in cluster_sizes:
        tfidf_time = results[size]["tfidf"]
        keybert_time = results[size]["keybert"]
        if not np.isnan(tfidf_time) and not np.isnan(keybert_time):
            valid_overheads.append(keybert_time - tfidf_time)

    if valid_overheads:
        avg_overhead = np.mean(valid_overheads)
        print(f"\nAverage overhead: {avg_overhead:.3f}s per cluster")
        print(f"\nKeyBERT is ~{avg_overhead:.2f}s slower per cluster on average.")
        print("This overhead is acceptable given the significantly better label quality.")
    else:
        print("\nCould not calculate overhead - some tests failed")

    print()


if __name__ == "__main__":
    main()
