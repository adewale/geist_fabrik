"""Reproducible synthetic topic-index timings; no production performance claim."""

import argparse
import json
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from geistfabrik import Vault
from geistfabrik.topics import TopicIndex


def benchmark(count: int) -> dict[str, int | float | str]:
    """Measure cold/warm sync and positive queries against identical short prose."""
    if count < 1:
        raise ValueError("counts must be positive")
    content = (
        "# Distributed systems\n\nDistributed systems use consensus and replication. "
        "Consensus protects consistency. Replication supports availability.\n"
    )
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for number in range(count):
            (root / f"note-{number}.md").write_text(content)
        with closing(Vault(root)) as vault:
            start = perf_counter()
            vault.sync()
            cold = perf_counter() - start
            start = perf_counter()
            vault.sync()
            warm = perf_counter() - start
            index = TopicIndex(vault.db)
            start = perf_counter()
            catalog = index.catalog()
            catalog_time = perf_counter() - start
            start = perf_counter()
            matches = index.paths("distributed systems")
            lookup_time = perf_counter() - start
            if len(matches) != count:
                raise AssertionError("Positive lookup must return every source")
    return {
        "corpus": "synthetic repeated short prose",
        "notes": count,
        "characters_per_note": len(content),
        "cold_sync_seconds": cold,
        "warm_sync_seconds": warm,
        "catalog_seconds": catalog_time,
        "positive_lookup_seconds": lookup_time,
        "matches": len(matches),
        "vocabulary": len(catalog),
    }


def main() -> int:
    """Use small stated corpus sizes and report single-run costs as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("counts", nargs="*", type=int, default=[100, 1000])
    args = parser.parse_args()
    if any(count < 1 for count in args.counts):
        parser.error("counts must be positive")
    print(json.dumps([benchmark(count) for count in args.counts], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
