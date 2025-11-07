"""Shared configuration for sklearn optimization benchmarks.

This module defines the test matrix and geist list used by both
benchmark_optimizations.py and analyze_benchmarks.py to ensure
consistency and eliminate code duplication.
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
GEISTS: List[str] = [
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
