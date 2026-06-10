# GeistFabrik Deep Project Audit Report

**Date**: 2026-03-14
**Version Audited**: 0.9.0 (Beta)
**Auditor**: Claude Opus 4.6 (4 parallel sub-agents)
**Scope**: Full codebase (~14,100 lines across 32 source modules + 48 code geists + 9 Tracery geists)
**Prior Audit**: 2026-03-12 (docs/DEEP_AUDIT_REPORT.md) -- 34 findings fixed in commit cf0c511

---

## Executive Summary

This follow-up audit validates fixes from the prior audit and identifies remaining and new issues. The codebase is in strong shape: CI passes cleanly (949 unit + 161 integration tests), all type checking passes (`mypy --strict`), and no linting issues exist.

**Overall Health**: 8.5/10 (up from ~7.5 at prior audit)

**Key Findings**:
- 8 of 8 P0 items from prior audit are **fixed**
- 7 remaining issues from prior audit still present (P1/P2 level)
- 3 documentation accuracy issues found and fixed in this audit
- 0 new security vulnerabilities found
- 0 new bugs found

---

## 1. Prior Audit Fix Verification

### P0 Items (All Fixed)

| # | Item | Status |
|---|------|--------|
| 1 | Missing geists in DEFAULT_CODE_GEISTS | Fixed (cf0c511) |
| 2 | Geist count references | Fixed (cf0c511) |
| 3 | AssertionError typo | Fixed (cf0c511) |
| 4 | Tautological assertion | Fixed (cf0c511) |
| 5 | 4 geists using direct SQL | Fixed (cf0c511) -- VaultContext methods added |
| 6 | GROUP_CONCAT delimiter | Fixed (cf0c511) -- using \x1f |
| 7 | Silent config load failure | Fixed (cf0c511) -- logging added |
| 8 | Missing LICENSE file | Fixed (cf0c511) |

### Remaining Issues (P1/P2)

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| CQ-1 | Duplicated clustering pipeline (VaultContext vs ClusterAnalyser) | Medium | **Still present** |
| CQ-2 | Session embedding loading repeated 4x | Medium | **Still present** (4 locations in vault_context.py + clustering_analysis.py) |
| CQ-3 | Duplicated `_format_cluster_label` | Low | **Still present** (vault_context.py + clustering_analysis.py) |
| CQ-6 | stats.py monolith (1657 lines) | Low | **Still present** |
| CQ-11 | `contrarian_to()` accesses private `vault._embeddings` | Low | **Still present** (function_registry.py:221,235) |
| Dead code | `compare_with_session` placeholder stub | Low | **Still present** (clustering_analysis.py:303-329) |
| CQ-10 | Config loader hardcodes default geist lists | Low | **Partially fixed** -- 8 missing geists added, but still hardcoded |

---

## 2. New Findings

### Documentation Accuracy (Fixed in This Audit)

| # | Finding | Action Taken |
|---|---------|-------------|
| DOC-NEW-1 | CLAUDE.md claimed "~11,900 lines across 26 source modules" -- actual is ~14,100 lines across 32 modules | **Fixed**: Updated to correct numbers |
| DOC-NEW-2 | README.md project tree claimed "26 modules" | **Fixed**: Updated to 32 |
| DOC-NEW-3 | DEEP_AUDIT_REPORT.md scope line had outdated counts | **Fixed**: Updated to correct numbers |

### Code Quality (Informational)

| # | Finding | Severity | Notes |
|---|---------|----------|-------|
| CQ-NEW-1 | `vault_context.py:619-632` uses f-string SQL with hardcoded filter clause | Informational | Safe (internal constant), but inconsistent with parameterized query pattern |
| CQ-NEW-2 | `schema.py:142` uses f-string for `PRAGMA user_version` | Informational | Safe (integer constant), minor consistency issue |
| CQ-NEW-3 | No `PRAGMA journal_mode = WAL` configured | Informational | Fine for single-process model, could improve future concurrent access |
| CQ-NEW-4 | Magic number `1000` in embeddings.py:133 for LFS detection threshold | Low | Should be named constant |

### Security

| # | Finding | Severity | Notes |
|---|---------|----------|-------|
| - | No new security vulnerabilities found | - | Prior SEC-1 (dynamic module loading) is inherent to extensibility design |

### Test Health

| # | Finding | Notes |
|---|---------|-------|
| - | All 1110 tests pass (949 unit + 161 integration) | Clean |
| - | No TODO/FIXME/HACK debt in source code | Clean (only in todo_harvester geist which is *about* TODOs) |
| - | No skipped tests in standard run | 9 tests marked `slow` (require real model) are deselected |
| - | mypy --strict passes with 0 issues across 85 source files | Clean |
| - | Ruff linting passes with 0 issues | Clean |

---

## 3. Metrics Summary

| Metric | Value |
|--------|-------|
| Source modules (excl. default geists) | 32 |
| Lines of code (excl. default geists) | ~14,100 |
| Lines of code (total incl. geists) | ~18,800 |
| Default code geists | 48 |
| Default Tracery geists | 9 |
| Total default geists | 57 |
| Unit tests | 949 |
| Integration tests | 161 |
| Total tests | 1,110 |
| Version | 0.9.0 |
| Python target | 3.11 |
| Schema version | 6 |

---

## 4. Remaining Recommendations (Pre-1.0)

### Should Fix

1. **Consolidate embedding loading** (CQ-2) -- Extract a single `_load_session_embeddings()` method in VaultContext, used by all 4 call sites
2. **Consolidate clustering pipeline** (CQ-1, CQ-3) -- Have VaultContext delegate to ClusterAnalyser instead of reimplementing

### Nice to Have

3. **Remove dead code** -- `compare_with_session` stub in clustering_analysis.py
4. **Add `contrarian_to()` public accessor** (CQ-11) -- Add a VaultContext method for embedding access instead of touching private `_embeddings`
5. **Name magic constant** -- `MIN_MODEL_FILE_SIZE = 1000` in embeddings.py
6. **Split stats.py** (CQ-6) -- 1657 lines is manageable but could be cleaner as 2-3 modules

---

*Report generated by deep audit with 4 parallel sub-agents analyzing the full GeistFabrik codebase.*
