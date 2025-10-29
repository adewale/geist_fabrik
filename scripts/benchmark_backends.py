#!/usr/bin/env python3
"""Benchmark script for vector search backends.

This script compares performance between InMemoryVectorBackend and SqliteVecBackend
across different vault sizes and query patterns.

Usage:
    python scripts/benchmark_backends.py
    python scripts/benchmark_backends.py --sizes 100,500,1000
    python scripts/benchmark_backends.py --queries 10,50,100
"""

import argparse
import sqlite3
import time
from datetime import datetime
from typing import Dict, Tuple

import numpy as np

from geistfabrik.schema import init_db
from geistfabrik.vector_search import InMemoryVectorBackend, SqliteVecBackend


def generate_synthetic_embeddings(num_notes: int, dim: int = 387) -> Dict[str, np.ndarray]:
    """Generate synthetic embeddings for benchmarking.

    Args:
        num_notes: Number of note embeddings to generate
        dim: Embedding dimension

    Returns:
        Dictionary mapping note paths to embeddings
    """
    embeddings = {}
    for i in range(num_notes):
        path = f"note_{i:05d}.md"
        # Generate random normalized embedding
        vec = np.random.randn(dim).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        embeddings[path] = vec
    return embeddings


def setup_test_db(num_notes: int) -> Tuple[sqlite3.Connection, str, Dict[str, np.ndarray]]:
    """Set up test database with synthetic embeddings.

    Args:
        num_notes: Number of notes to create

    Returns:
        Tuple of (connection, session_date, embeddings_dict)
    """
    db = init_db(db_path=None)  # In-memory database

    # Load sqlite-vec extension if available (needed for SqliteVecBackend)
    try:
        import sqlite_vec

        db.enable_load_extension(True)
        sqlite_vec.load(db)
    except (ImportError, sqlite3.OperationalError):
        # sqlite-vec not available, SqliteVecBackend will be skipped
        pass

    # Create notes
    now = datetime.now()
    for i in range(num_notes):
        path = f"note_{i:05d}.md"
        db.execute(
            "INSERT INTO notes (path, title, content, created, modified, file_mtime) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (path, f"Note {i}", f"Content for note {i}", now, now, 0.0),
        )

    # Create session
    session_date = "2025-01-15"
    created_at = now.isoformat()
    db.execute("INSERT INTO sessions (date, created_at) VALUES (?, ?)", (session_date, created_at))
    cursor = db.execute("SELECT session_id FROM sessions WHERE date = ?", (session_date,))
    session_id = cursor.fetchone()[0]

    # Generate and store embeddings
    embeddings = generate_synthetic_embeddings(num_notes)
    for path, embedding in embeddings.items():
        db.execute(
            "INSERT INTO session_embeddings (session_id, note_path, embedding) VALUES (?, ?, ?)",
            (session_id, path, embedding.tobytes()),
        )

    db.commit()
    return db, session_date, embeddings


def benchmark_backend(
    backend_name: str,
    backend,
    session_date: str,
    embeddings: Dict[str, np.ndarray],
    num_queries: int = 100,
) -> Dict[str, float]:
    """Benchmark a single backend.

    Args:
        backend_name: Name of backend for reporting
        backend: Backend instance to benchmark
        session_date: Session date for loading
        embeddings: Embeddings dict for query selection
        num_queries: Number of queries to run

    Returns:
        Dictionary of timing results
    """
    results = {}

    # Benchmark: Load embeddings
    start = time.perf_counter()
    backend.load_embeddings(session_date)
    load_time = time.perf_counter() - start
    results["load_time"] = load_time

    # Benchmark: find_similar queries
    paths = list(embeddings.keys())
    query_times = []
    for _ in range(num_queries):
        # Pick random note as query
        query_path = paths[np.random.randint(0, len(paths))]
        query_embedding = embeddings[query_path]

        start = time.perf_counter()
        backend.find_similar(query_embedding, k=10)
        query_time = time.perf_counter() - start
        query_times.append(query_time)

    results["avg_query_time"] = np.mean(query_times)
    results["p50_query_time"] = np.percentile(query_times, 50)
    results["p95_query_time"] = np.percentile(query_times, 95)
    results["p99_query_time"] = np.percentile(query_times, 99)

    # Benchmark: get_similarity
    similarity_times = []
    for _ in range(num_queries):
        # Pick two random notes
        path_a = paths[np.random.randint(0, len(paths))]
        path_b = paths[np.random.randint(0, len(paths))]

        start = time.perf_counter()
        backend.get_similarity(path_a, path_b)
        sim_time = time.perf_counter() - start
        similarity_times.append(sim_time)

    results["avg_similarity_time"] = np.mean(similarity_times)

    return results


def print_results(size: int, backend_name: str, results: Dict[str, float]) -> None:
    """Print benchmark results in formatted table.

    Args:
        size: Vault size
        backend_name: Backend name
        results: Results dictionary
    """
    print(f"\n{backend_name} (n={size}):")
    print(f"  Load time:         {results['load_time'] * 1000:>8.2f} ms")
    print(f"  Avg query time:    {results['avg_query_time'] * 1000:>8.3f} ms")
    print(f"  P50 query time:    {results['p50_query_time'] * 1000:>8.3f} ms")
    print(f"  P95 query time:    {results['p95_query_time'] * 1000:>8.3f} ms")
    print(f"  P99 query time:    {results['p99_query_time'] * 1000:>8.3f} ms")
    print(f"  Avg similarity:    {results['avg_similarity_time'] * 1000:>8.3f} ms")


def main() -> None:
    """Run benchmarks."""
    parser = argparse.ArgumentParser(description="Benchmark vector search backends")
    parser.add_argument(
        "--sizes",
        type=str,
        default="100,500,1000,2000",
        help="Comma-separated vault sizes to test (default: 100,500,1000,2000)",
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=100,
        help="Number of queries per benchmark (default: 100)",
    )
    parser.add_argument(
        "--skip-sqlite-vec",
        action="store_true",
        help="Skip sqlite-vec benchmark (if not installed)",
    )
    args = parser.parse_args()

    sizes = [int(s.strip()) for s in args.sizes.split(",")]
    num_queries = args.queries

    print("=" * 70)
    print("Vector Search Backend Benchmarks")
    print("=" * 70)
    print(f"Queries per test: {num_queries}")
    print("Embedding dimension: 387")

    # Check if sqlite-vec is available
    has_sqlite_vec = False
    if not args.skip_sqlite_vec:
        try:
            import sqlite_vec

            test_db = init_db(db_path=None)
            test_db.enable_load_extension(True)
            sqlite_vec.load(test_db)
            test_db.execute("SELECT vec_version()")
            has_sqlite_vec = True
        except (ImportError, sqlite3.OperationalError):
            print("\n⚠️  sqlite-vec not installed - skipping SqliteVecBackend benchmarks")
            print("    Install with: uv pip install -e '.[vector-search]'")

    for size in sizes:
        print(f"\n{'=' * 70}")
        print(f"Vault size: {size} notes")
        print("=" * 70)

        # Set up test database
        db, session_date, embeddings = setup_test_db(size)

        # Benchmark InMemoryVectorBackend
        in_memory = InMemoryVectorBackend(db)
        results_mem = benchmark_backend(
            "InMemoryVectorBackend",
            in_memory,
            session_date,
            embeddings,
            num_queries,
        )
        print_results(size, "InMemoryVectorBackend", results_mem)

        # Benchmark SqliteVecBackend (if available)
        if has_sqlite_vec:
            sqlite_vec = SqliteVecBackend(db)
            results_vec = benchmark_backend(
                "SqliteVecBackend",
                sqlite_vec,
                session_date,
                embeddings,
                num_queries,
            )
            print_results(size, "SqliteVecBackend", results_vec)

            # Print comparison
            speedup_load = results_mem["load_time"] / results_vec["load_time"]
            speedup_query = results_mem["avg_query_time"] / results_vec["avg_query_time"]
            print("\n  Speedup (InMemory vs SqliteVec):")
            print(f"    Load:  {speedup_load:>6.2f}x")
            print(f"    Query: {speedup_query:>6.2f}x")

        db.close()

    print(f"\n{'=' * 70}")
    print("Benchmarks complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
