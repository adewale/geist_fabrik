#!/usr/bin/env python3
"""Profile congruence_mirror geist performance on different vault sizes.

This script generates synthetic vaults and measures execution time
for each quadrant finder function to validate performance targets.
"""

# Import the geist directly for profiling
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

from geistfabrik.embeddings import Session
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext

sys.path.insert(
    0, str(Path(__file__).parent.parent / "src" / "geistfabrik" / "default_geists" / "code")
)
from congruence_mirror import (
    find_connected_pair,
    find_detached_pair,
    find_explicit_pair,
    find_implicit_pair,
    suggest,
)


def generate_synthetic_vault(size: int, link_density: float = 0.1) -> Path:
    """Generate a synthetic vault with specified number of notes.

    Args:
        size: Number of notes to generate
        link_density: Proportion of possible links to create (0.0-1.0)

    Returns:
        Path to temporary vault directory
    """
    vault_dir = Path(tempfile.mkdtemp(prefix=f"profile_vault_{size}_"))

    # Generate notes with varied content
    topics = [
        "machine learning",
        "psychology",
        "cooking",
        "history",
        "music",
        "physics",
        "literature",
        "architecture",
        "biology",
        "philosophy",
    ]

    for i in range(size):
        topic = topics[i % len(topics)]
        note_path = vault_dir / f"note_{i:04d}.md"

        # Create content with some variation
        content = f"""# Note {i:04d} - {topic.title()}

This is a note about {topic}. It contains various thoughts and ideas
related to the subject matter.

## Section 1

Some detailed content here about {topic} concepts and theories.
This helps create semantic similarity between notes on the same topic.

## Section 2

Additional content to increase note length and provide more
material for embedding computation.
"""

        # Add links based on density
        if i > 0:
            # Link to previous notes with probability
            import random

            random.seed(42 + i)  # Deterministic
            num_links = int(i * link_density)
            link_targets = random.sample(range(i), min(num_links, i))

            if link_targets:
                content += "\n## Links\n\n"
                for target in link_targets:
                    content += f"- [[note_{target:04d}]]\n"

        note_path.write_text(content)

    return vault_dir


def profile_vault_size(size: int, link_density: float = 0.1) -> Dict[str, float]:
    """Profile congruence_mirror on vault of given size.

    Args:
        size: Number of notes
        link_density: Link density

    Returns:
        Dict of timing results
    """
    print(f"\n{'=' * 60}")
    print(f"Profiling vault size: {size} notes (link density: {link_density:.1%})")
    print(f"{'=' * 60}")

    # Generate vault
    print("Generating synthetic vault...")
    vault_dir = generate_synthetic_vault(size, link_density)

    try:
        # Initialize vault
        print("Initializing vault...")
        vault = Vault(vault_dir)
        vault.sync()

        # Create session with embeddings
        print("Computing embeddings...")
        embedding_start = time.perf_counter()
        session = Session(date=datetime(2025, 1, 15), db=vault.db)
        session.compute_embeddings(vault.all_notes())
        embedding_time = time.perf_counter() - embedding_start
        print(f"  Embeddings computed in {embedding_time:.2f}s")

        # Create vault context
        vault_context = VaultContext(vault, session, seed=20250115)

        # Profile each finder function
        results = {
            "vault_size": size,
            "link_density": link_density,
            "num_links": len([link for note in vault.all_notes() for link in note.links]),
            "embedding_time": embedding_time,
        }

        # Profile find_explicit_pair
        print("\nProfiling find_explicit_pair()...")
        start = time.perf_counter()
        explicit_pair = find_explicit_pair(vault_context)
        explicit_time = time.perf_counter() - start
        results["explicit_time"] = explicit_time
        results["explicit_found"] = explicit_pair is not None
        print(f"  Time: {explicit_time:.3f}s | Found: {explicit_pair is not None}")

        # Profile find_implicit_pair
        print("\nProfiling find_implicit_pair()...")
        start = time.perf_counter()
        implicit_pair = find_implicit_pair(vault_context)
        implicit_time = time.perf_counter() - start
        results["implicit_time"] = implicit_time
        results["implicit_found"] = implicit_pair is not None
        print(f"  Time: {implicit_time:.3f}s | Found: {implicit_pair is not None}")

        # Profile find_connected_pair
        print("\nProfiling find_connected_pair()...")
        start = time.perf_counter()
        connected_pair = find_connected_pair(vault_context)
        connected_time = time.perf_counter() - start
        results["connected_time"] = connected_time
        results["connected_found"] = connected_pair is not None
        print(f"  Time: {connected_time:.3f}s | Found: {connected_pair is not None}")

        # Profile find_detached_pair
        print("\nProfiling find_detached_pair()...")
        start = time.perf_counter()
        detached_pair = find_detached_pair(vault_context)
        detached_time = time.perf_counter() - start
        results["detached_time"] = detached_time
        results["detached_found"] = detached_pair is not None
        print(f"  Time: {detached_time:.3f}s | Found: {detached_pair is not None}")

        # Profile full suggest() function
        print("\nProfiling full suggest() function...")
        start = time.perf_counter()
        suggestions = suggest(vault_context)
        total_time = time.perf_counter() - start
        results["total_time"] = total_time
        results["num_suggestions"] = len(suggestions)
        print(f"  Time: {total_time:.3f}s | Suggestions: {len(suggestions)}")

        # Print summary
        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        print(f"Vault Size: {size} notes")
        print(f"Link Density: {link_density:.1%} ({results['num_links']} links)")
        print(f"Embedding Time: {embedding_time:.2f}s")
        print("\nFinder Function Times:")
        print(f"  explicit:  {explicit_time:.3f}s")
        print(f"  implicit:  {implicit_time:.3f}s")
        print(f"  connected: {connected_time:.3f}s")
        print(f"  detached:  {detached_time:.3f}s")
        print(f"  TOTAL:     {total_time:.3f}s")
        print(f"\nSuggestions Generated: {len(suggestions)}")

        return results

    finally:
        # Cleanup
        import shutil

        shutil.rmtree(vault_dir)


def main():
    """Run performance profiling across different vault sizes."""
    import json

    print("=" * 70)
    print("CONGRUENCE MIRROR PERFORMANCE PROFILING")
    print("=" * 70)

    # Test sizes
    sizes = [10, 50, 100, 500, 1000]
    link_density = 0.1  # 10% of possible links

    all_results = []

    for size in sizes:
        results = profile_vault_size(size, link_density)
        all_results.append(results)

    # Print consolidated report
    print("\n\n")
    print("=" * 70)
    print("CONSOLIDATED PERFORMANCE REPORT")
    print("=" * 70)
    print()
    # Header row - split to avoid line length limit
    print(
        f"{'Size':<8} | {'Links':<8} | {'Explicit':<10} | "
        f"{'Implicit':<10} | {'Connected':<10} | "
        f"{'Detached':<10} | {'Total':<10}"
    )
    print("-" * 90)

    for r in all_results:
        print(
            f"{r['vault_size']:<8} | "
            f"{r['num_links']:<8} | "
            f"{r['explicit_time']:.3f}s{' ' * 5} | "
            f"{r['implicit_time']:.3f}s{' ' * 5} | "
            f"{r['connected_time']:.3f}s{' ' * 5} | "
            f"{r['detached_time']:.3f}s{' ' * 5} | "
            f"{r['total_time']:.3f}s"
        )

    # Compare to spec projections
    print("\n\n")
    print("=" * 70)
    print("COMPARISON TO SPEC PROJECTIONS")
    print("=" * 70)
    print()
    print("From specs/CONGRUENCE_MIRROR_GEIST_SPEC.md:")
    print("  10 notes:   <0.1s")
    print("  50 notes:   <0.3s")
    print("  100 notes:  <1.0s")
    print("  500 notes:  <5.0s")
    print("  1000 notes: <15s")
    print()
    print("Actual Results:")

    spec_targets = {10: 0.1, 50: 0.3, 100: 1.0, 500: 5.0, 1000: 15.0}

    for r in all_results:
        size = r["vault_size"]
        actual = r["total_time"]
        target = spec_targets.get(size, 0)

        if target > 0:
            status = "✅ PASS" if actual < target else "❌ FAIL"
            percent = (actual / target) * 100
            print(f"  {size:<4} notes: {actual:.3f}s / {target:.1f}s ({percent:.0f}%) {status}")

    # Save results
    output_file = Path(__file__).parent.parent / "docs" / "congruence_mirror_profile_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
