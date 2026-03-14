# GeistFabrik Deep Project Audit Report

**Date**: 2026-03-12
**Version Audited**: 0.9.0 (Beta)
**Auditor**: Claude Opus 4.6 (8 parallel sub-agents)
**Scope**: Full codebase (~14,100 lines across 32 source modules + 48 code geists + 9 Tracery geists)

---

## Executive Summary

GeistFabrik is a well-architected project approaching 1.0 readiness. The audit examined 8 dimensions using specialized sub-agents. Overall the codebase is solid: security posture is strong for a local-first tool, design principles are largely followed (8.5/10 compliance), and the feature set is complete relative to specs. The most critical findings are:

1. **Documentation drift** -- Geist counts are stale in 5+ documents; 8 geists missing from `config_loader.py`
2. **Architectural violations** -- 4 geists bypass VaultContext with direct SQL
3. **Duplicated clustering pipeline** -- Same algorithm implemented independently in two files
4. **Performance opportunities** -- Duplicate embedding loading, non-batched diversity filter

**Finding Totals**: 8 Critical/High | 24 Medium | 25 Low

---

## Table of Contents

1. [Code Quality](#1-code-quality)
2. [Security Vulnerabilities](#2-security-vulnerabilities)
3. [Bug Patterns](#3-bug-patterns)
4. [Design Philosophy Compliance](#4-design-philosophy-compliance)
5. [Test Quality](#5-test-quality)
6. [Documentation-Code Sync](#6-documentation-code-sync)
7. [Performance](#7-performance)
8. [Feature Completeness](#8-feature-completeness)
9. [Priority Action Items](#9-priority-action-items)

---

## 1. Code Quality

**17 findings**: 3 High, 9 Medium, 5 Low

### High Severity

| # | Finding | Files |
|---|---------|-------|
| CQ-1 | **Duplicated clustering pipeline** -- `VaultContext.get_clusters()` and `ClusterAnalyser._cluster_hdbscan()` implement nearly identical HDBSCAN pipelines independently. Results could diverge. | `vault_context.py:652-780`, `clustering_analysis.py:134-234` |
| CQ-2 | **Session embedding loading repeated 4 times** -- Same `SELECT note_path, embedding FROM session_embeddings` query appears in 4 locations instead of using a single accessor. | `vault_context.py:127,690,833`, `clustering_analysis.py:149` |
| CQ-3 | **Duplicated `_format_cluster_label`** -- Verbatim copy of Oxford-comma formatting logic in two files. | `vault_context.py:782-799`, `clustering_analysis.py:236-253` |

### Medium Severity

| # | Finding | Files |
|---|---------|-------|
| CQ-4 | `typing` import style inconsistency -- Core modules use `List`/`Dict` from `typing` while CLAUDE.md mandates PEP 585 lowercase syntax | Throughout codebase |
| CQ-5 | Inconsistent error handling: `print()` vs `logger` -- 6 locations use `print()` for diagnostics instead of `logging` | `geist_executor.py`, `embeddings.py` |
| CQ-6 | `stats.py` is a 1627-line monolith with 3 classes and duplicated labeling logic | `stats.py` |
| CQ-7 | Duplicated `get_season()` function defined 4 times across 3 files | `temporal_analysis.py`, `seasonal_patterns.py`, `seasonal_revisit.py` |
| CQ-8 | Duplicated geist loading/discovery logic between code and Tracery loaders | `geist_executor.py:120-173`, `tracery.py:768-828` |
| CQ-9 | Dict-based clusters vs typed `Cluster` dataclass -- two parallel representations | `vault_context.py` vs `clustering_analysis.py` |
| CQ-10 | Config loader hardcodes default geist lists instead of deriving from filesystem | `config_loader.py:13-66` |
| CQ-11 | `contrarian_to()` accesses private `vault._embeddings` directly | `function_registry.py:221-235` |
| CQ-12 | 9 separate cache dictionaries on VaultContext with repeated check/populate patterns | `vault_context.py:88-115` |

### Low Severity

- Dead code: `_expand_vault_functions` method never called (`tracery.py:455-492`)
- Dead code: `compare_with_session` placeholder stub (`clustering_analysis.py:303-329`)
- Dead code: Unused `SKLEARN_OPTIMIZATIONS["vectorize"]` code path (`embeddings.py:622-642`)
- `VaultContext.read()` is a trivial wrapper caching already-in-memory `note.content`
- Inconsistent geist import patterns (module-level vs deferred)

---

## 2. Security Vulnerabilities

**11 findings**: 0 Critical, 1 Medium, 8 Low, 2 Positive

### Positive Practices

- All YAML parsing uses `yaml.safe_load()` (no arbitrary object deserialization)
- Embedding serialization uses safe `np.frombuffer`/`tobytes` (no pickle)
- All SQL uses parameterized queries for user-derived data
- No `eval()`, `exec()`, `os.system()`, `subprocess`, or `pickle.load()`
- Fully local-first -- zero network operations

### Medium Severity

| # | Finding | Files |
|---|---------|-------|
| SEC-1 | **Arbitrary code execution via dynamic module loading** -- 4 subsystems use `importlib exec_module()` to load user-supplied Python from vault directories. Shared/synced vaults from untrusted sources could execute malicious code. | `geist_executor.py:197-208`, `metadata_system.py:98-108`, `function_registry.py:361-383`, `validator.py:84-105` |

**Recommendation**: Document as security consideration; add first-run confirmation prompt for custom modules; validator should parse without executing.

### Low Severity

| # | Finding |
|---|---------|
| SEC-2 | SQL construction with `.format()` -- safe today (placeholders only) but fragile pattern |
| SEC-3 | `sys.modules` pollution -- bare geist_id as module key could shadow stdlib (e.g., geist named `json`) |
| SEC-4 | No path traversal validation on vault paths (could scan `/` if misconfigured) |
| SEC-5 | SQLite database file created with default permissions (0644, not 0600) |
| SEC-6 | Information disclosure in log messages (file paths, stack traces via `exc_info=True`) |
| SEC-7 | `sklearn.set_config(assume_finite=True)` disables NaN/Inf validation globally |
| SEC-8 | SIGALRM signal handler race condition -- could interrupt database writes |
| SEC-9 | No rate limiting on Tracery vault function calls per geist |

---

## 3. Bug Patterns

**15 findings**: 0 High, 6 Medium, 9 Low

### Medium Severity

| # | Finding | Files |
|---|---------|-------|
| BUG-1 | **`GROUP_CONCAT` with `\|` delimiter** -- Note paths containing `\|` will be silently corrupted when split. | `vault_context.py:622-638` |
| BUG-2 | **Global `_GLOBAL_REGISTRY` prevents multiple `FunctionRegistry` instances** -- Second instantiation crashes with `DuplicateFunctionError`. | `function_registry.py:35` |
| BUG-3 | **Config loading swallows ALL exceptions silently** -- `PermissionError`, `MemoryError`, even `KeyboardInterrupt` produce default config with no diagnostic output. | `config_loader.py:229-237` |
| BUG-4 | **`st_ctime` is not creation time on Linux** -- Stored as `created` field but is actually inode change time on Linux, differs from macOS behavior. | `vault.py:118` |
| BUG-5 | **SIGALRM handler is process-global and non-reentrant** -- Fragile timeout mechanism that could interfere with nested usage. | `geist_executor.py:265-268` |
| BUG-6 | **22 instances of bare `except Exception: pass`** in stats/labeling code -- Masks real bugs during development. | `cluster_labeling.py` (5), `stats.py` (10+) |

### Low Severity

| # | Finding |
|---|---------|
| BUG-7 | `np.frombuffer` returns read-only arrays -- latent hazard if any code tries in-place modification |
| BUG-8 | `temporal_analysis.py` snapshot dates are strings but typed as `datetime` -- crash in `drift_direction_by_period` |
| BUG-9 | Division by zero in `unlinked_pairs` for zero-vector embeddings |
| BUG-10 | Vault has no context manager (`__enter__`/`__exit__`) -- connection leaks in library usage |
| BUG-11 | TOCTOU gap in vault sync -- file could be deleted between `rglob` and `read_text` (no `FileNotFoundError` handler) |
| BUG-12 | `%-d` strftime format fails on Windows (`journal_writer.py:84`) |
| BUG-13 | Tracery preprocessing failure leaves grammar in partial state |
| BUG-14 | `unlinked_pairs` uses `self._embeddings` dict instead of backend (inconsistent with rest of codebase) |
| BUG-15 | `sys.modules` pollution -- loaded modules never cleaned up from `sys.modules` |

---

## 4. Design Philosophy Compliance

**Overall Score: 8.5 / 10**

| # | Principle | Status | Score |
|---|-----------|--------|-------|
| 1 | Muses, not oracles | Compliant | 10/10 |
| 2 | Questions, not answers | Compliant | 10/10 |
| 3 | Sample, don't rank | Compliant | 10/10 |
| 4 | Local-first | Compliant | 10/10 |
| 5 | Deterministic randomness | Compliant | 10/10 |
| 6 | Never destructive | Compliant | 10/10 |
| 7 | Extensible at every layer | Compliant | 10/10 |
| 8 | Two-layer architecture | Partial | 7/10 |
| 9 | Geists must use VaultContext, not direct SQL | **Violation** | 4/10 |
| 10 | API consistency (bracketed links) | Compliant | 10/10 |

### Architectural Violations (4 geists use direct SQL)

| Geist | Violation | Impact |
|-------|-----------|--------|
| `drift_velocity_anomaly.py:27` | `vault.db.execute("SELECT COUNT(*) FROM sessions")` | Low |
| `cyclical_thinking.py:27,47-57` | Session count + complex JOIN on `session_embeddings` | Medium |
| `vocabulary_expansion.py:27-34,44-52` | Sessions query + raw embedding deserialization | High |
| `cluster_evolution_tracker.py:31-38,70-77` | Sessions + cluster labels by session | High |

Additionally, `VaultContext` exposes `self.db = vault.db` as a public attribute (`vault_context.py:75`), enabling these violations.

### Missing VaultContext Methods Needed

- `session_count()` -- return number of sessions
- `session_dates_for_note(note)` -- return dates when note had embeddings
- `previous_cluster_assignment(note, session_id)` -- historical cluster label
- `session_embeddings_for_note(note, limit)` -- recent session embeddings

---

## 5. Test Quality

**14 findings**: 3 High, 5 Medium, 6 Low

### High Severity

| # | Finding | Files |
|---|---------|-------|
| TQ-1 | **Tautological assertion** -- `"  " not in sugg.text or "  " in sugg.text` is always True (P or not P). Tests nothing. | `test_code_geists_empty_data.py:449-451` |
| TQ-2 | **`AssertionError` typo** in 3 architectural guard tests -- should be `AssertionError`. If a violation is detected, tests crash with `NameError` instead of meaningful message. | `test_geist_architectural_constraints.py:108,200,287` |
| TQ-3 | **7 source modules have no dedicated tests** -- Most critical: `journal_writer.py` (core output path). Others: `graph_analysis.py`, `content_extraction.py`, `similarity_analysis.py`, `temporal_analysis.py`, `clustering_analysis.py`, `validator.py` | `tests/` |

### Medium Severity

| # | Finding |
|---|---------|
| TQ-4 | `assert True` fallthrough -- 2 tests pass even when expected behavior is never observed (`test_transformation_suggester.py:281,317`) |
| TQ-5 | Manual `vault.close()` without `try/finally` -- 40+ test locations leak DB connections on assertion failure |
| TQ-6 | `time.sleep()` for mtime differentiation -- flaky on fast systems; should use `os.utime()` |
| TQ-7 | CLI test "test_invoke_loads_both_code_and_tracery_geists" only checks file existence, never loads geists |
| TQ-8 | `commands/` subpackage (7 modules) has no dedicated tests beyond CLI argument parsing |

### Low Severity

- `hasattr` checks on typed dataclasses (always pass)
- `np.random.seed(42)` global state in 2 test files
- Timing assertions (`elapsed < 2.0`) brittle on loaded CI
- Missing negative tests for filtering edge cases
- Dual mock implementations for SentenceTransformer
- Duplicated `create_mock_embedding_computer` helper

---

## 6. Documentation-Code Sync

**14 findings**: 5 High, 7 Medium, 3 Low

### High Severity

| # | Finding | Files |
|---|---------|-------|
| DOC-1 | **README.md says "51 default geists" in 3 places** -- Actual: 57 (48 code + 9 Tracery). README contradicts itself (line 14 says 57). | `README.md:116,270,542` |
| DOC-2 | **README claims 38 example geists** -- `examples/` contains 0 geists (5 files total: 3 metadata + 2 vault functions). | `README.md:514,691` |
| DOC-3 | **GEIST_CATALOG.md says "51 default geists"** with "42 code geists" -- stale. | `docs/GEIST_CATALOG.md` |
| DOC-4 | **example_config.yaml lists only 36 code geists** -- 8 are missing from both the example and `config_loader.py`. | `docs/example_config.yaml`, `config_loader.py:13-54` |
| DOC-5 | **`DEFAULT_CODE_GEISTS` in config_loader.py missing 8 geists** -- `burst_evolution`, `cluster_evolution_tracker`, `creation_burst`, `cyclical_thinking`, `definition_harvester`, `drift_velocity_anomaly`, `metadata_outlier_detector`, `seasonal_topic_analysis`. `geistfabrik init` generates incomplete configs. | `config_loader.py:13-54` |

### Medium Severity

| # | Finding |
|---|---------|
| DOC-6 | CLAUDE.md says "15 source modules" -- actually 26+ modules |
| DOC-7 | CLAUDE.md says "All 51 geists" in one sentence -- should be 57 |
| DOC-8 | CLAUDE.md references 3 non-existent doc files: `POST_MORTEM_PR30.md`, `POST_MORTEM_PHASE3B.md`, `JOURNAL_FILES.md` |
| DOC-9 | README.md test count "611 passing" -- actually 1,119 tests |
| DOC-10 | README lists non-existent Tracery geists (`dialectic.yaml`, `scale_shift.yaml`) |
| DOC-11 | README references LICENSE file that does not exist |
| DOC-12 | ARCHITECTURE.md says "5s timeout" -- actual default is 30s |

### Low Severity

- CLAUDE.md `notes_grouped_by_creation_date()` line reference wrong (566 vs 603)
- `models.py` uses `typing.List`/`typing.Optional` despite PEP 585 mandate
- Spec method names differ from code (`get_backlinks` vs `backlinks`)

---

## 7. Performance

**15 findings**: 2 High, 6 Medium, 5 Low

### High Severity

| # | Finding | Files |
|---|---------|-------|
| PERF-1 | **Duplicate embedding loading** -- `VaultContext.__init__` loads ALL embeddings into `self._embeddings` AND the backend loads them again. Double memory (~30MB for 10k notes), double startup I/O. | `vault_context.py:127-137` |
| PERF-2 | **Diversity filter uses individual `compute_semantic()`** instead of `compute_batch_semantic()` -- S separate model forward passes instead of 1 batched call. Could save 10-60s in full mode. | `filtering.py:242` |

### Medium Severity

| # | Finding | Scaling |
|---|---------|---------|
| PERF-3 | N+1 query in `orphans()` -- 3 SQL queries per orphan via `get_note()` | O(k) queries |
| PERF-4 | N+1 query in `old_notes()`/`recent_notes()` | O(k) queries |
| PERF-5 | N+1 query in `get_clusters()` for note lookups | O(C) where C = clustered notes |
| PERF-6 | Redundant embedding table scan in `get_cluster_representatives()` -- reloads all embeddings despite already being in memory | O(N) per call |
| PERF-7 | `find_similar()` computes pairwise similarities with Python loop -- should be vectorized matrix multiplication | O(N) function calls |
| PERF-8 | `outgoing_links()` resolves links one at a time -- up to 6 SQL queries per link | O(L x 6) queries |

### Low Severity

- `hubs()` query uses OR-based JOIN preventing index use
- `filter_boundary()` scans notes table twice
- `vault.sync()` calls `stat()` twice per modified file
- Unbounded session-scoped caches (acceptable for session lifetime)
- Content hash computed twice per uncached embedding

### Top 3 Recommendations by Impact

1. **PERF-2**: Switch diversity filter to `compute_batch_semantic()` -- single-line fix, saves 10-60s
2. **PERF-1**: Remove duplicate `_embeddings` dict -- saves ~15MB and one full table scan
3. **PERF-7**: Pre-compute embedding matrix for vectorized `find_similar()` -- 10-50x speedup

---

## 8. Feature Completeness

**5 findings**: 0 High, 2 Medium, 3 Low

### Medium Severity

| # | Finding | Files |
|---|---------|-------|
| FC-1 | **`DEFAULT_CODE_GEISTS` missing 8 geists** -- `geistfabrik init` generates incomplete config. Geists still run (auto-discovered) but aren't listed for enable/disable. | `config_loader.py:13-54` |
| FC-2 | **`boundaries.exclude_paths` not configurable** -- Spec describes path exclusion config but no binding exists. Users with private notes can't exclude them. | `config_loader.py`, `filtering.py` |

### Low Severity

- Many spec config sections (embeddings, session, quality, filtering) are hardcoded rather than user-configurable -- acceptable for beta
- Spec method names differ from code (`get_backlinks` vs `backlinks`)
- `execution_mode: "serial"` mentioned in spec but only serial exists (parallel not planned for 1.0)

### Fully Implemented Features

All core features verified as implemented:
- All VaultContext API methods from spec
- All 19 CLI commands/flags
- All 3 extensibility dimensions (metadata, vault functions, geists)
- All 4 filtering pipeline stages
- Session journal output with block IDs
- Deterministic replay (`--date`)

---

## 9. Priority Action Items

### P0 -- Fix Before 1.0 Release

| # | Action | Effort | Findings |
|---|--------|--------|----------|
| 1 | **Add 8 missing geists to `DEFAULT_CODE_GEISTS`** in config_loader.py and docs/example_config.yaml | Small | DOC-5, FC-1 |
| 2 | **Fix geist count references** across README.md (3 places), GEIST_CATALOG.md, CLAUDE.md | Small | DOC-1, DOC-3, DOC-7 |
| 3 | **Fix `AssertionError` typo** in architectural guard tests (3 locations) | Tiny | TQ-2 |
| 4 | **Fix tautological assertion** in test_code_geists_empty_data.py | Tiny | TQ-1 |
| 5 | **Fix 4 geists using direct SQL** -- Add VaultContext methods, refactor geists | Medium | Design-9 |
| 6 | **Fix `GROUP_CONCAT` delimiter** -- Use a safer delimiter like `\x1f` (ASCII unit separator) | Small | BUG-1 |
| 7 | **Add logging to silent config load failure** | Tiny | BUG-3 |
| 8 | **Create LICENSE file** | Tiny | DOC-11 |

### P1 -- Important Improvements

| # | Action | Effort | Findings |
|---|--------|--------|----------|
| 9 | Switch diversity filter to batch embedding computation | Tiny | PERF-2 |
| 10 | Remove duplicate `_embeddings` dict from VaultContext | Small | PERF-1, CQ-2 |
| 11 | Consolidate clustering pipeline (delegate VaultContext to ClusterAnalyser) | Medium | CQ-1, CQ-3, CQ-9 |
| 12 | Fix README phantom examples section (38 example geists that don't exist) | Small | DOC-2 |
| 13 | Namespace dynamic module loading in sys.modules | Tiny | SEC-3, BUG-15 |
| 14 | Add TOCTOU handling (FileNotFoundError) in vault sync | Tiny | BUG-11 |
| 15 | Document security model for shared vaults | Small | SEC-1 |

### P2 -- Nice to Have

| # | Action | Effort | Findings |
|---|--------|--------|----------|
| 16 | Standardize on PEP 585 type annotations across core modules | Medium | CQ-4 |
| 17 | Add tests for journal_writer.py and commands/ package | Medium | TQ-3, TQ-8 |
| 18 | Vectorize `find_similar()` with pre-computed embedding matrix | Medium | PERF-7 |
| 19 | Replace `print()` with `logging` in geist_executor/embeddings | Small | CQ-5 |
| 20 | Split stats.py monolith into 2-3 focused modules | Medium | CQ-6 |
| 21 | Extract shared `get_season()` utility | Tiny | CQ-7 |
| 22 | Fix `vault.close()` leak patterns in tests (use fixtures) | Medium | TQ-5 |
| 23 | Replace `time.sleep()` with `os.utime()` in tests | Small | TQ-6 |
| 24 | Remove dead code (3 locations) | Tiny | CQ low findings |
| 25 | Set restrictive permissions on SQLite database file | Tiny | SEC-5 |

---

*Report generated by 8 parallel audit agents analyzing the full GeistFabrik codebase.*
