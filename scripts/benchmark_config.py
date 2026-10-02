"""Shared configuration for sklearn optimization benchmarks.

This module defines the test matrix and geist list used by both
benchmark_optimizations.py and analyze_benchmarks.py to ensure
consistency and eliminate code duplication.

Note (2026-10): src/geistfabrik no longer reads the GEIST_ASSUME_FINITE,
GEIST_FAST_PATH or GEIST_VECTORIZE variables, so every configuration below now
runs the same code; the matrix is kept for reproducing the historical study
(docs/SKLEARN_OPTIMIZATION_BENCHMARK.md).
"""

from typing import Any, Dict, List

# Test matrix: 8 configurations testing different sklearn optimization combinations
CONFIGS: List[Dict[str, Any]] = [
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

# Test geists: 6 problem geists (timeout or slow on 10k vault) + 3 control geists (fast)
# (2026-10: the retired antithesis_generator and columbo were replaced by
# assumption_challenger, slow in the Phase 3B 10k-vault runs, and bridge_builder,
# which absorbed the formerly slow island_hopper.)
GEISTS: List[str] = [
    # Problem geists (timeout or slow on 10k vault)
    "assumption_challenger",
    "hidden_hub",
    "pattern_finder",
    "bridge_hunter",
    "method_scrambler",
    "bridge_builder",
    # Control geists (fast, should stay fast)
    "scale_shifter",
    "stub_expander",
    "recent_focus",
]
