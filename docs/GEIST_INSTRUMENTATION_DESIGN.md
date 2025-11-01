# Geist Instrumentation and Debugging System

## Problem

Users encounter timeout errors with no visibility into what's causing them:
```
✗ cluster_mirror: Execution timed out (>5s)
  → Test with longer timeout: geistfabrik test cluster_mirror <vault>
  → Check for infinite loops or expensive operations in ...
```

This provides limited actionable information. Users can't easily:
- Identify which operation is slow
- Provide meaningful bug reports
- Debug performance issues without code inspection

## Goal

Enable users to diagnose geist performance issues with detailed instrumentation and provide maintainers with actionable bug reports.

## Design

### 1. Enhanced Timing Instrumentation

Track execution time at multiple levels:

```python
@dataclass
class GeistExecutionProfile:
    """Detailed execution profile for a geist."""

    geist_id: str
    status: str  # "success", "timeout", "error"
    total_time: float  # seconds

    # Optional profiling data (only collected in verbose mode)
    function_calls: Optional[Dict[str, ProfileStats]] = None
    stack_trace: Optional[str] = None  # Stack at timeout

@dataclass
class ProfileStats:
    """Statistics for a function call."""

    name: str  # Function name
    calls: int  # Number of calls
    total_time: float  # Total time in seconds
    cumulative_time: float  # Including subcalls
```

### 2. Verbose Mode Enhancements

When `--verbose` is enabled:

**For all geists:**
```
Executing geist: cluster_mirror
  ✓ cluster_mirror completed in 1.234s (5 suggestions)
```

**For timeouts:**
```
Executing geist: cluster_mirror
  ✗ cluster_mirror timed out after 5.000s

  Performance profile:
    3.542s  vault.get_clusters (1 call)
      2.891s  HDBSCAN.fit (sklearn.cluster.HDBSCAN.fit)
      0.401s  c-TF-IDF computation (stats.get_cluster_labels)
      0.250s  centroid calculation
    1.203s  vault.semantic_search (3 calls)
    0.255s  Other operations

  Top expensive operations:
    1. sklearn.cluster.HDBSCAN.fit - 2.891s (57.8%)
    2. stats.get_cluster_labels - 0.401s (8.0%)
    3. cosine_similarity - 0.305s (6.1%)

  Suggestions:
    → HDBSCAN clustering is expensive - consider caching results
    → Clustering 847 notes took 2.9s, expected ~1.5s for this size
    → Test with: geistfabrik test cluster_mirror <vault> --timeout 10 --verbose
```

**For slow geists (>2s but <5s):**
```
  ⚠ cluster_mirror completed in 4.123s (5 suggestions)
    Warning: Approaching timeout threshold (82% of 5s limit)
    → Run with --verbose for detailed performance breakdown
```

### 3. Implementation Strategy

#### 3.1 Add Profiling to GeistExecutor

```python
class GeistExecutor:
    def __init__(self, ..., verbose: bool = False):
        self.verbose = verbose
        self.execution_profiles: List[GeistExecutionProfile] = []

    def execute_geist(self, geist_id: str, context: VaultContext) -> List[Suggestion]:
        """Execute with timing and optional profiling."""

        start_time = time.perf_counter()

        if self.verbose:
            # Run with cProfile for detailed breakdown
            import cProfile
            import pstats
            import io

            profiler = cProfile.Profile()
            profiler.enable()

        try:
            # Execute geist (existing code)
            suggestions = geist.func(context)

            if self.verbose:
                profiler.disable()

            end_time = time.perf_counter()
            execution_time = end_time - start_time

            # Log profile
            profile = GeistExecutionProfile(
                geist_id=geist_id,
                status="success",
                total_time=execution_time,
                function_calls=self._extract_profile_stats(profiler) if self.verbose else None
            )
            self.execution_profiles.append(profile)

            # Warn if slow
            if execution_time > self.timeout * 0.8:
                self._warn_slow_geist(geist_id, execution_time, profile)

            return suggestions

        except GeistTimeoutError:
            if self.verbose:
                profiler.disable()

            # Capture profile at timeout
            profile = GeistExecutionProfile(
                geist_id=geist_id,
                status="timeout",
                total_time=self.timeout,
                function_calls=self._extract_profile_stats(profiler) if self.verbose else None,
                stack_trace=self._get_current_stack()
            )
            self.execution_profiles.append(profile)

            # Show detailed timeout diagnostic
            if self.verbose:
                self._show_timeout_diagnostic(geist_id, profile)
            else:
                # Standard timeout message
                self._handle_failure(geist_id, "timeout", ...)

            return []
```

#### 3.2 Diagnostic Formatting

```python
def _show_timeout_diagnostic(self, geist_id: str, profile: GeistExecutionProfile) -> None:
    """Show detailed timeout diagnostic in verbose mode."""

    print(f"\n  ✗ {geist_id} timed out after {self.timeout:.3f}s\n")

    if profile.function_calls:
        print("  Performance profile:")

        # Group by vault method calls
        vault_methods = self._group_vault_calls(profile.function_calls)
        for method, stats in sorted(vault_methods.items(), key=lambda x: x[1].total_time, reverse=True):
            print(f"    {stats.total_time:.3f}s  {method} ({stats.calls} calls)")

            # Show subcalls if significant
            subcalls = self._get_subcalls(method, profile.function_calls)
            for subcall, subcall_stats in subcalls[:3]:  # Top 3
                print(f"      {subcall_stats.total_time:.3f}s  {subcall}")

        # Show top expensive operations overall
        print("\n  Top expensive operations:")
        top_funcs = sorted(profile.function_calls.items(),
                          key=lambda x: x[1].total_time,
                          reverse=True)[:5]

        for i, (name, stats) in enumerate(top_funcs, 1):
            pct = (stats.total_time / self.timeout) * 100
            print(f"    {i}. {name} - {stats.total_time:.3f}s ({pct:.1f}%)")

    # Actionable suggestions
    print("\n  Suggestions:")
    suggestions = self._generate_suggestions(geist_id, profile)
    for suggestion in suggestions:
        print(f"    → {suggestion}")
```

#### 3.3 Smart Suggestions

```python
def _generate_suggestions(self, geist_id: str, profile: GeistExecutionProfile) -> List[str]:
    """Generate actionable suggestions based on profile."""

    suggestions = []

    if not profile.function_calls:
        suggestions.append(f"Run with --verbose for detailed performance breakdown")
        suggestions.append(f"Test with: geistfabrik test {geist_id} <vault> --timeout 10")
        return suggestions

    # Detect common patterns

    # Pattern 1: Expensive clustering
    if any("HDBSCAN" in name or "cluster" in name.lower()
           for name in profile.function_calls.keys()):
        suggestions.append("HDBSCAN clustering is expensive - consider caching results")

    # Pattern 2: Many semantic searches
    search_calls = sum(stats.calls for name, stats in profile.function_calls.items()
                      if "semantic_search" in name)
    if search_calls > 10:
        suggestions.append(f"{search_calls} semantic searches - consider batching or limiting")

    # Pattern 3: Large note processing
    if any("all_notes" in name for name in profile.function_calls.keys()):
        suggestions.append("Processing all notes - consider using queries or sampling")

    # Generic suggestions
    suggestions.append(f"Test with longer timeout: geistfabrik test {geist_id} <vault> --timeout 10 --verbose")

    return suggestions
```

### 4. CLI Integration

No new flags needed - use existing `--verbose`:

```bash
# Current behavior (minimal output)
uv run geistfabrik invoke ~/vault --geist cluster_mirror
# Output:
#   ✗ cluster_mirror: Execution timed out (>5s)

# With verbose (detailed diagnostics)
uv run geistfabrik invoke ~/vault --geist cluster_mirror --verbose
# Output:
#   Executing geist: cluster_mirror
#   ✗ cluster_mirror timed out after 5.000s
#
#   Performance profile:
#     [detailed breakdown as shown above]
```

### 5. Bug Report Template

When users report timeout issues, they can provide:

```
Geist: cluster_mirror
Vault size: 847 notes
Timeout: 5s

Performance profile (from --verbose):
  3.542s  vault.get_clusters (1 call)
    2.891s  HDBSCAN.fit
    0.401s  c-TF-IDF computation
  1.203s  vault.semantic_search (3 calls)

Top operations:
  1. sklearn.cluster.HDBSCAN.fit - 2.891s (57.8%)
  2. stats.get_cluster_labels - 0.401s (8.0%)
```

This is actionable! We can immediately see that HDBSCAN is the bottleneck.

## Implementation Plan

1. ✅ Design document (this file)
2. Add `GeistExecutionProfile` dataclass to `geist_executor.py`
3. Add profiling support to `execute_geist` method
4. Add diagnostic formatting methods
5. Add smart suggestion generation
6. Update CLI to pass `verbose` flag to GeistExecutor
7. Test with cluster_mirror and other slow geists
8. Update documentation

## Benefits

1. **Users**: Clear visibility into performance issues
2. **Maintainers**: Actionable bug reports with profiling data
3. **Debugging**: Identify bottlenecks without code inspection
4. **Performance**: Data-driven optimization decisions

## Non-Goals

- This is not replacing the timeout mechanism
- This is not adding automatic performance optimization
- This is not changing the geist execution model

## Future Enhancements

- Export profiles to JSON for analysis
- Aggregate performance data across sessions
- Performance regression detection
- Automated performance benchmarks
