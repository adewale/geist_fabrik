# GeistFabrik Acceptance Criteria

This document contains all acceptance criteria for each implementation phase.

## How this file is verified (read before editing)

`scripts/check_phase_completion.py` **runs** these criteria; it does not trust
them. It is wired into `scripts/validate.sh` and CI, so this table cannot drift
away from the code without turning CI red. Two rules follow from that:

- **The Status column is informational only.** Pass/fail comes from *running*
  the Verification cell, never from the emoji. (Historically the checker counted
  a criterion done because the row said ✅ and silently dropped any row whose
  cell it couldn't parse — that is precisely how the spec drifted from reality.
  See `LESSONS_LEARNED.md` → "Acceptance-criteria drift".)
- **Every criterion is AUTO or MANUAL, and nothing is skipped:**
  - **AUTO** — the Verification cell *starts with* a backtick-wrapped command
    (an optional human annotation may follow). The checker executes it; a
    non-zero exit fails the gate. `uv run pytest …` commands are run the way the
    project always runs them — the checker expands `{a,b}` node lists and
    appends the canonical `-m "not slow and not benchmark"` filter (which
    activates the embedding stub), so do **not** repeat the marker here.
  - **MANUAL** — any cell that is prose. Use this for criteria that genuinely
    need human judgement, a platform we can't run in CI, or a behaviour with no
    dedicated automated test. MANUAL criteria are reported and counted but do
    not fail the gate. A cell that *looks* like a command but isn't
    backtick-wrapped is a hard parse error (so a real check can't hide as prose).

When a test is renamed, point the cell at the surviving test or its file; when a
behaviour loses its only test, make the cell MANUAL with an honest reason.

**Status Legend (planning marker only — not used for pass/fail):**
- ⬜ Not Started
- 🔄 In Progress
- ✅ Complete
- ⚠️ Blocked
- ❌ Failed

---

## Phase 0: Project Scaffolding

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-0.1 | ⬜ | Project structure exists | `test -d src/geistfabrik && test -f pyproject.toml && test -f pytest.ini && test -d tests/` |
| AC-0.2 | ⬜ | Dependencies install cleanly | `test -f uv.lock && uv run python -c "import sentence_transformers, yaml, scipy, sklearn, sqlite3"` |
| AC-0.3 | ⬜ | Tests can run | `uv run pytest --collect-only` (exit code 0) |
| AC-0.4 | ⬜ | Linting passes | `uv run ruff check src/ && uv run mypy src/ --strict` |
| AC-0.5 | ⬜ | CI pipeline runs | `test -f .github/workflows/test.yml` |
| AC-0.6 | ⬜ | Phase completion checker exists | `test -f scripts/check_phase_completion.py` |
| AC-0.7 | ⬜ | Phase checker verifies Phase 0 | `uv run python scripts/check_phase_completion.py --list` |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-0.8 | ⬜ | uv configuration correct | `test -f uv.lock && uv run python -c "import geistfabrik"` |
| AC-0.9 | ⬜ | Python version enforcement | `uv run python -c "import sys; assert sys.version_info >= (3, 11)"` |
| AC-0.10 | ⬜ | Development dependencies separate | Manual: dev/prod dependency separation; verified by the CI install steps, not the gate (uv sync would mutate the developer's environment) |
| AC-0.11 | ⬜ | Git initialisation | `test -d .git && test -f .gitignore && grep "^\.venv$" .gitignore` |
| AC-0.12 | ⬜ | Editable install works | `uv run python -c "import geistfabrik; assert 'src' in geistfabrik.__file__"` (points to src/) |
| AC-0.13 | ⬜ | Pre-commit hooks | `test -f .pre-commit-config.yaml` |
| AC-0.14 | ⬜ | Package metadata complete | Verify project.name, version, dependencies in pyproject.toml |

### Exit Criteria
- All AC-0.* checks pass
- `uv run pytest` runs without errors (even with no tests)
- Linting and type checking configured
- uv environment fully functional
- Phase completion checker functional

---

## Phase 1: Vault Parsing & SQLite Persistence

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-1.1 | ⬜ | Unit tests pass (20+ tests) | `uv run pytest tests/unit/test_vault.py tests/unit/test_markdown_parser.py tests/unit/test_sqlite_persistence.py -v` |
| AC-1.2 | ⬜ | Load kepano vault | `uv run pytest tests/integration/test_kepano_vault.py::test_load_kepano_vault -v` (8 notes loaded) |
| AC-1.3 | ⬜ | Parse all kepano note types | `uv run pytest tests/integration/test_kepano_vault.py::test_parse_{evergreen_notes,daily_note,meeting_note} -v` |
| AC-1.4 | ⬜ | Database schema valid | `uv run pytest tests/integration/test_kepano_vault.py -v` |
| AC-1.5 | ⬜ | Incremental sync works | `uv run pytest tests/unit/test_vault.py::test_sync_{modified_file,no_changes} -v` (only changed files reprocessed) |
| AC-1.6 | ⬜ | Link graph builds correctly | `uv run pytest tests/integration/test_kepano_vault.py::test_kepano_link_graph -v` |
| AC-1.7 | ⬜ | Performance target met | `uv run pytest tests/integration/test_scenarios.py::test_scenario_first_time_setup -v` (8 notes synced in <5s) |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-1.8 | ⬜ | Broken markdown handling | `uv run pytest tests/unit/test_markdown_parser.py::test_parse_malformed_frontmatter tests/unit/test_markdown_parser.py::test_parse_unclosed_code_blocks tests/unit/test_markdown_parser.py::test_extract_links_invalid -v` |
| AC-1.9 | ⬜ | Empty vault handling | `uv run pytest tests/integration/test_scenarios.py::test_scenario_empty_vault -v` |
| AC-1.10 | ⬜ | Large file handling | `uv run pytest tests/unit/test_vault.py::test_large_note -v` (handle notes >1MB) |
| AC-1.11 | ⬜ | Invalid UTF-8 handling | `uv run pytest tests/unit/test_markdown_parser.py::test_parse_invalid_utf8 -v` |
| AC-1.12 | ⬜ | Circular link detection | `uv run pytest tests/unit/test_vault.py::test_circular_links -v` (A→B→C→A handled) |
| AC-1.13 | ⬜ | Broken link tracking | `uv run pytest tests/unit/test_vault.py::test_broken_links -v` |
| AC-1.14 | ⬜ | Database corruption recovery | `uv run pytest tests/unit/test_sqlite_persistence.py::test_corrupted_database_recovery -v` |
| AC-1.15 | ⬜ | Filesystem error handling | `uv run pytest tests/unit/test_vault.py::test_{permission_denied,vault_path_not_exists,vault_path_is_file} -v` |
| AC-1.16 | ⬜ | Case sensitivity handling | `uv run pytest tests/unit/test_vault.py::test_case_insensitive_links -v` |
| AC-1.17 | ⬜ | Duplicate note titles | `uv run pytest tests/unit/test_vault.py::test_duplicate_titles_different_folders -v` |
| AC-1.18 | ⬜ | Concurrent database access | `uv run pytest tests/integration/test_vault.py::test_concurrent_sync -v` |
| AC-1.19 | ⬜ | Database migration | Verify PRAGMA user_version > 0 |
| AC-1.20 | ⬜ | Self-links handling | `uv run pytest tests/unit/test_vault.py::test_self_referencing_notes -v` |

### Test Coverage Target
- `src/geistfabrik/vault.py`: >90%
- `src/geistfabrik/markdown_parser.py`: >90%
- `src/geistfabrik/persistence.py`: >85%

### Exit Criteria
- All AC-1.* checks pass
- Kepano vault loads completely
- Database contains all notes, links, tags
- Incremental sync demonstrably faster
- Edge cases handled gracefully

---

## Phase 2: Basic Embeddings

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-2.1 | ⬜ | Embedding tests pass | `uv run pytest tests/unit/test_embeddings.py -v` (15+ tests) |
| AC-2.2 | ⬜ | Embeddings computed for kepano vault | `uv run pytest tests/integration/test_kepano_vault.py::test_kepano_embeddings -v` (16 embeddings: 8×2) |
| AC-2.3 | ⬜ | Embedding dimensions correct | Verify content_embedding has 384 dimensions |
| AC-2.4 | ⬜ | Similarity search works | Verify neighbours() returns ≤k results, excludes query note |
| AC-2.5 | ⬜ | Performance target | Manual: embedding-computation benchmark; measured via benchmarks/ scripts, no non-slow pytest |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-2.6 | ⬜ | Empty content handling | Create note with only frontmatter, verify handles gracefully |
| AC-2.7 | ⬜ | Very long note handling | `uv run pytest tests/unit/test_embeddings.py -v` (truncate, don't crash) |
| AC-2.8 | ⬜ | Image-only note handling | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-2.9 | ⬜ | Model download failure | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-2.10 | ⬜ | Embedding cache invalidation | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-2.11 | ⬜ | Memory limits | Manual: embedding memory ceiling; perf-only, not gate-enforced |
| AC-2.12 | ⬜ | Batch processing | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-2.13 | ⬜ | Similarity edge cases | Verify same note similarity ≈ 1.0 |
| AC-2.14 | ⬜ | Zero vector handling | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-2.15 | ⬜ | Embedding persistence verification | Verify embeddings persist across reloads |

### Test Coverage Target
- `src/geistfabrik/embeddings.py`: >85%

### Exit Criteria
- All AC-2.* checks pass
- Embeddings stored in SQLite via sqlite-vec
- Semantic search returns sensible results
- Model loads once and caches
- Edge cases handled gracefully

---

## Phase 3: VaultContext & Query Operations

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-3.1 | ✅ | VaultContext tests pass | `uv run pytest tests/unit/test_vault_context.py -v` (25+ tests) |
| AC-3.2 | ⬜ | Semantic search via context | Verify neighbours() via VaultContext returns ≤k results |
| AC-3.3 | ⬜ | Graph operations work | Verify orphans(), hubs(), unlinked_pairs() return correct types |
| AC-3.4 | ⬜ | Deterministic sampling | Same seed = same sample results |
| AC-3.5 | ⬜ | Temporal queries | `uv run pytest tests/unit/test_vault_context.py::test_{old_notes,recent_notes} -v` |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-3.6 | ⬜ | Empty vault context | `uv run pytest tests/unit/test_vault_context.py -v` |
| AC-3.7 | ⬜ | Single note vault | `uv run pytest tests/unit/test_vault_context.py -v` |
| AC-3.8 | ⬜ | Vault with no links | `uv run pytest tests/unit/test_vault_context.py -v` |
| AC-3.9 | ⬜ | Sampling edge cases | Verify sample(k>n) returns all, sample(k=0) returns empty |
| AC-3.10 | ⬜ | Graph with cycles | `uv run pytest tests/unit/test_vault_context.py -v` |
| AC-3.11 | ⬜ | Disconnected components | `uv run pytest tests/unit/test_vault_context.py -v` |
| AC-3.12 | ⬜ | Metadata caching | `uv run pytest tests/unit/test_vault_context.py -v` |
| AC-3.13 | ⬜ | Context serialization | `uv run pytest tests/unit/test_vault_context.py -v` (optional) |
| AC-3.14 | ⬜ | Thread safety | `uv run pytest tests/unit/test_vault_context.py -v` |
| AC-3.15 | ⬜ | Query result stability | Multiple calls to same query return same results |

### Test Coverage Target
- `src/geistfabrik/vault_context.py`: >90%

### Exit Criteria
- All AC-3.* checks pass
- VaultContext provides all query methods
- Deterministic sampling verified
- Kepano vault queries work end-to-end
- Edge cases handled gracefully

---

## Phase 4: Code Geist Execution

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-4.1 | ⬜ | Geist executor tests pass | `uv run pytest tests/unit/test_geist_executor.py -v` (15+ tests) |
| AC-4.2 | ⬜ | Load sample geists | Verify geist loader discovers .py files in geists/code/ |
| AC-4.3 | ⬜ | Execute geist | Verify simple geist returns suggestions |
| AC-4.4 | ⬜ | Timeout works | `uv run pytest tests/unit/test_geist_executor.py::test_code_geist_timeout -v` (5s timeout) |
| AC-4.5 | ⬜ | Failure tracking | `uv run pytest tests/unit/test_geist_executor.py::test_disable_after_three_failures -v` |
| AC-4.6 | ⬜ | Integration scenario | `uv run pytest tests/integration/test_scenarios.py -v` |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-4.7 | ⬜ | Geist with syntax errors | `uv run pytest tests/unit/test_geist_executor.py::test_geist_syntax_error -v` |
| AC-4.8 | ⬜ | Geist with import errors | `uv run pytest tests/unit/test_geist_executor.py::test_geist_import_error -v` |
| AC-4.9 | ⬜ | Geist returns invalid format | `uv run pytest tests/unit/test_geist_executor.py::test_geist_invalid_return -v` |
| AC-4.10 | ⬜ | Geist attempts vault modification | `uv run pytest tests/unit/test_geist_executor.py -v` |
| AC-4.11 | ⬜ | Geist crashes interpreter | `uv run pytest tests/unit/test_geist_executor.py -v` (advanced) |
| AC-4.12 | ⬜ | Duplicate geist IDs | `uv run pytest tests/unit/test_geist_executor.py::test_duplicate_geist_ids -v` |
| AC-4.13 | ⬜ | Geist directory doesn't exist | `uv run pytest tests/unit/test_geist_executor.py::test_missing_geist_directory -v` |
| AC-4.14 | ⬜ | Infinite loop timeout verification | `uv run pytest tests/unit/test_geist_executor.py::test_infinite_loop_timeout -v` |
| AC-4.15 | ⬜ | Memory-intensive geist | `uv run pytest tests/unit/test_geist_executor.py -v` (optional) |
| AC-4.16 | ⬜ | Geist returns many suggestions | `uv run pytest tests/unit/test_geist_executor.py::test_geist_excessive_suggestions -v` |
| AC-4.17 | ⬜ | Unicode in suggestions | `uv run pytest tests/unit/test_geist_executor.py::test_geist_unicode_suggestions -v` |
| AC-4.18 | ⬜ | Cross-geist state isolation | `uv run pytest tests/unit/test_geist_executor.py::test_geist_state_isolation -v` |
| AC-4.19 | ⬜ | Geist exception details | `uv run pytest tests/unit/test_geist_executor.py::test_geist_exception_logging -v` |
| AC-4.20 | ⬜ | Parallel geist execution | `uv run pytest tests/unit/test_geist_executor.py -v` (if implemented) |

### Test Coverage Target
- `src/geistfabrik/geist_executor.py`: >85%

### Exit Criteria
- All AC-4.* checks pass
- Sample geists execute successfully
- Timeout mechanism verified
- Error handling robust
- Edge cases handled gracefully

---

## Phase 5: Filtering & Session Notes

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-5.1 | ⬜ | Filtering tests pass | `uv run pytest tests/unit/test_filtering.py -v` (15+ tests) |
| AC-5.2 | ⬜ | Session tests pass | Manual: session-note writing exercised end-to-end by the integration scenarios; no dedicated journal_writer unit suite |
| AC-5.3 | ⬜ | Write session note | `uv run pytest tests/integration/test_scenarios.py -v` |
| AC-5.4 | ⬜ | Session note format correct | Verify title, block IDs in format `^gYYYYMMDD-NNN` |
| AC-5.5 | ⬜ | Filtering works | Verify duplicates and short suggestions filtered |
| AC-5.6 | ⬜ | Multi-day sessions | `uv run pytest tests/integration/test_scenarios.py -v` |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-5.7 | ⬜ | Session file already exists | Manual: session overwrite protection in journal_writer.py; no dedicated test |
| AC-5.8 | ⬜ | Session directory creation | Manual: session directory creation in journal_writer.py; no dedicated test |
| AC-5.9 | ⬜ | Session directory not writable | Manual: read-only session directory handling; no dedicated test |
| AC-5.10 | ⬜ | All suggestions filtered out | `uv run pytest tests/unit/test_filtering.py -v` |
| AC-5.11 | ⬜ | Block ID collision prevention | Manual: block-ID uniqueness in journal_writer.py; no dedicated test |
| AC-5.12 | ⬜ | Very long suggestions | `uv run pytest tests/unit/test_filtering.py -v` |
| AC-5.13 | ⬜ | Suggestions with invalid markdown | Manual: Markdown escaping in session output; no dedicated test |
| AC-5.14 | ⬜ | Malicious content in suggestions | `uv run pytest tests/unit/test_filtering.py -v` |
| AC-5.15 | ⬜ | Future date sessions | Manual: far-future session date; no dedicated edge test |
| AC-5.16 | ⬜ | Very old date sessions | Manual: ancient session date; no dedicated edge test |
| AC-5.17 | ⬜ | Novelty window edge cases | `uv run pytest tests/unit/test_filtering.py -v` |
| AC-5.18 | ⬜ | Diversity threshold extremes | Verify threshold=1.0 keeps only first of identical suggestions |
| AC-5.19 | ⬜ | Empty suggestion text | `uv run pytest tests/unit/test_filtering.py -v` |
| AC-5.20 | ⬜ | Broken links in suggestions | `uv run pytest tests/unit/test_filtering.py -v` |

### Test Coverage Target
- `src/geistfabrik/filtering.py`: >85%
- `src/geistfabrik/session.py`: >85%
- `src/geistfabrik/journal_writer.py`: >90%

### Exit Criteria
- All AC-5.* checks pass
- Session notes written correctly
- Filtering removes duplicates and low-quality
- Block IDs unique and stable
- Edge cases handled gracefully

---

## Phase 6: Tracery Integration

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-6.1 | ⬜ | Tracery tests pass | `uv run pytest tests/unit/test_tracery.py -v` (20+ tests) |
| AC-6.2 | ⬜ | Parse Tracery YAML | Verify TraceryGeist.from_file() loads YAML correctly |
| AC-6.3 | ⬜ | Expand grammar | Verify grammar expansion includes `[[links]]` |
| AC-6.4 | ⬜ | Vault function calls work | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.5 | ⬜ | Deterministic expansion | Same seed = same expansion text |
| AC-6.6 | ⬜ | Integration with vault | `uv run pytest tests/integration/test_scenarios.py -v` |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-6.7 | ⬜ | Invalid YAML structure | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.8 | ⬜ | Malformed grammar | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.9 | ⬜ | Infinite recursion | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.10 | ⬜ | Grammar syntax errors | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.11 | ⬜ | Non-existent vault function | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.12 | ⬜ | Vault function exception | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.13 | ⬜ | Grammar produces empty string | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.14 | ⬜ | Unicode in grammar | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.15 | ⬜ | Missing symbol reference | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.16 | ⬜ | Deep recursion near limit | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.17 | ⬜ | Tracery file not found | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.18 | ⬜ | Duplicate Tracery geist IDs | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.19 | ⬜ | Grammar with modifiers | `uv run pytest tests/unit/test_tracery.py -v` |
| AC-6.20 | ⬜ | Vault function with wrong args | `uv run pytest tests/unit/test_tracery.py -v` |

### Test Coverage Target
- `src/geistfabrik/tracery.py`: >85%

### Exit Criteria
- All AC-6.* checks pass
- Tracery geists execute and generate suggestions
- Vault functions callable from grammars
- Expansion deterministic
- Edge cases handled gracefully

---

## Phase 7: Temporal Embeddings

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-7.1 | ⬜ | Temporal embedding tests pass | `uv run pytest tests/unit/test_embeddings.py -v` etc. |
| AC-7.2 | ⬜ | Session embeddings computed | Verify all notes have session embeddings |
| AC-7.3 | ⬜ | Temporal features included | Verify embeddings are 387 dims (384+3) |
| AC-7.4 | ⬜ | Multi-session tracking | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-7.5 | ⬜ | Temporal geists work | `uv run pytest tests/integration/test_scenarios.py -v` |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-7.6 | ⬜ | Duplicate session date | Manual: duplicate session-date handling; no dedicated edge test |
| AC-7.7 | ⬜ | Invalid session date | Manual: invalid session-date handling; no dedicated edge test |
| AC-7.8 | ⬜ | Future date temporal features | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-7.9 | ⬜ | Very old note temporal features | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-7.10 | ⬜ | Season calculation | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-7.11 | ⬜ | Drift with no previous session | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-7.12 | ⬜ | Drift with identical notes | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-7.13 | ⬜ | Session pruning | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-7.14 | ⬜ | Storage limits | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-7.15 | ⬜ | Cross-session consistency | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-7.16 | ⬜ | Deleted note handling | `uv run pytest tests/unit/test_embeddings.py -v` |
| AC-7.17 | ⬜ | Session comparison API | Manual: cross-session comparison; no dedicated test |
| AC-7.18 | ⬜ | Temporal geist robustness | `uv run pytest tests/unit/test_embeddings.py -v` |

### Test Coverage Target
- `src/geistfabrik/temporal_embeddings.py`: >85%

### Exit Criteria
- All AC-7.* checks pass
- Session embeddings include temporal features
- Multiple sessions can be stored and compared
- Drift detection utilities work
- Edge cases handled gracefully

---

## Phase 8: Metadata Extensibility

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-8.1 | ⬜ | Metadata system tests pass | `uv run pytest tests/unit/test_metadata_system.py -v` (15+ tests) |
| AC-8.2 | ⬜ | Load metadata modules | Verify module discovery from metadata_inference/ |
| AC-8.3 | ⬜ | Infer metadata | Verify ctx.metadata(note) returns computed properties |
| AC-8.4 | ⬜ | Conflict detection | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.5 | ⬜ | E2E with geists | Manual: metadata+function+geist wired end-to-end; covered piecewise by the metadata and function-registry suites, no single e2e test |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-8.6 | ⬜ | Module with syntax errors | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.7 | ⬜ | Module with import errors | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.8 | ⬜ | Module exception during inference | `uv run pytest tests/unit/test_metadata_system.py::test_module_runtime_error -v` |
| AC-8.9 | ⬜ | Module returns non-dict | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.10 | ⬜ | Module returns invalid value types | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.11 | ⬜ | Module timeout | `uv run pytest tests/unit/test_metadata_system.py -v` (optional) |
| AC-8.12 | ⬜ | Module directory doesn't exist | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.13 | ⬜ | Unicode in metadata keys | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.14 | ⬜ | Metadata persistence | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.15 | ⬜ | Metadata invalidation | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.16 | ⬜ | Circular module dependencies | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.17 | ⬜ | Module ordering correctness | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.18 | ⬜ | Large metadata values | `uv run pytest tests/unit/test_metadata_system.py -v` |
| AC-8.19 | ⬜ | Metadata query performance | Manual: metadata query performance; perf-only, not gate-enforced |

### Test Coverage Target
- `src/geistfabrik/metadata_system.py`: >85%

### Exit Criteria
- All AC-8.* checks pass
- Metadata modules loadable from directory
- Conflict detection prevents key collisions
- Metadata accessible via VaultContext
- Edge cases handled gracefully

---

## Phase 9: Function Extensibility

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-9.1 | ⬜ | Function registry tests pass | `uv run pytest tests/unit/test_function_registry.py -v` (15+ tests) |
| AC-9.2 | ⬜ | Register functions | Verify @vault_function decorator registers correctly |
| AC-9.3 | ⬜ | Call from Python | Verify ctx.call_function() works |
| AC-9.4 | ⬜ | Call from Tracery | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.5 | ⬜ | Built-in functions work | Verify sample_notes, old_notes, orphans callable |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-9.6 | ⬜ | Function with syntax errors | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.7 | ⬜ | Function exception during execution | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.8 | ⬜ | Function with invalid signature | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.9 | ⬜ | Function returns wrong type | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.10 | ⬜ | Function modifies vault | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.11 | ⬜ | Function timeout | `uv run pytest tests/unit/test_function_registry.py -v` (optional) |
| AC-9.12 | ⬜ | Duplicate function name | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.13 | ⬜ | Unicode function names | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.14 | ⬜ | Function with no docstring | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.15 | ⬜ | Tracery wrong args | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.16 | ⬜ | Function directory doesn't exist | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.17 | ⬜ | Function dependency on metadata | `uv run pytest tests/unit/test_function_registry.py -v` |
| AC-9.18 | ⬜ | Function caching | `uv run pytest tests/unit/test_function_registry.py -v` (optional) |
| AC-9.19 | ⬜ | Function with default args | `uv run pytest tests/unit/test_function_registry.py -v` |

### Test Coverage Target
- `src/geistfabrik/function_registry.py`: >85%

### Exit Criteria
- All AC-9.* checks pass
- Functions discoverable and callable
- Tracery can invoke functions
- Built-in functions implemented
- Edge cases handled gracefully

---

## Phase 10: CLI & Invocation Modes

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-10.1 | ⬜ | CLI tests pass | `uv run pytest tests/unit/test_cli.py -v` (15+ tests) |
| AC-10.2 | ⬜ | CLI installed | `uv run geistfabrik --help` |
| AC-10.3 | ⬜ | Default invocation | `uv run pytest tests/unit/test_cli.py -v` |
| AC-10.4 | ⬜ | Single geist mode | `uv run pytest tests/unit/test_cli.py -v` |
| AC-10.5 | ⬜ | Full mode | `uv run pytest tests/unit/test_cli.py -v` |
| AC-10.6 | ⬜ | Test command | `uv run pytest tests/unit/test_cli.py -v` |
| AC-10.7 | ⬜ | Deterministic replay | `uv run pytest tests/unit/test_vault_context.py::test_vault_context_deterministic_seed -v` |
| AC-10.8 | ⬜ | Config loading | Verify config.yaml settings applied |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-10.9 | ⬜ | Invalid vault path | Verify clear error message |
| AC-10.10 | ⬜ | Vault path is file | Verify error: not a directory |
| AC-10.11 | ⬜ | Invalid YAML config | Verify parse error |
| AC-10.12 | ⬜ | Missing config fields | Verify defaults used |
| AC-10.13 | ⬜ | CLI with no arguments | Verify shows help/usage |
| AC-10.14 | ⬜ | CLI with invalid arguments | Verify error with usage hint |
| AC-10.15 | ⬜ | Multiple exclusive flags | Verify error: conflicting options |
| AC-10.16 | ⬜ | Non-existent geist | Verify error: geist not found |
| AC-10.17 | ⬜ | Invalid date format | Verify parse error |
| AC-10.18 | ⬜ | Future date | Verify allows or warns |
| AC-10.19 | ⬜ | Concurrent invocations | Verify file locking prevents conflicts |
| AC-10.20 | ⬜ | Config not found | Verify uses defaults, warns |
| AC-10.21 | ⬜ | Relative vs absolute paths | Verify both handled correctly |
| AC-10.22 | ⬜ | Symlinks in path | Verify follows symlinks |
| AC-10.23 | ⬜ | Unicode in vault path | Verify handles Unicode paths |
| AC-10.24 | ⬜ | Exit codes | Verify non-zero for errors |
| AC-10.25 | ⬜ | Verbose output | Manual: --verbose logging flag; set in cli _configure_logging, no dedicated test |
| AC-10.26 | ⬜ | Quiet mode | Manual: --quiet logging flag; set in cli _configure_logging, no dedicated test |

### Test Coverage Target
- `src/geistfabrik/cli.py`: >85%

### Exit Criteria
- All AC-10.* checks pass
- CLI commands work as specified
- Config file properly loaded
- All invocation modes functional
- Edge cases handled gracefully

---

## Phase 11: Polish & Optimisation

### Core Acceptance Criteria

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-11.1 | ⬜ | Performance benchmarks pass | `uv run pytest tests/unit/test_performance_regression.py tests/unit/test_phase1_benchmarks.py -v` |
| AC-11.2 | ⬜ | Test coverage target | Manual: coverage target is not gate-enforced (see pyproject fail_under note); run with --cov locally |
| AC-11.3 | ⬜ | All E2E tests pass | `uv run pytest tests/integration/test_scenarios.py -v` |
| AC-11.4 | ⬜ | Large vault performance | 1000 notes processable in <3 minutes |
| AC-11.5 | ⬜ | Documentation builds | Manual: no mkdocs site; documentation is plain Markdown under docs/ |
| AC-11.6 | ⬜ | Example geists work | ≥20 examples, all execute without errors |
| AC-11.7 | ⬜ | Linting clean | `uv run ruff check src/ && uv run mypy src/ --strict` |
| AC-11.8 | ⬜ | Security scan | `uv run bandit -c pyproject.toml -r src/geistfabrik -ll -q` |

### Edge Cases & Error Handling

| ID | Status | Criteria | Verification |
|----|--------|----------|--------------|
| AC-11.9 | ⬜ | Schema migration | `uv run pytest tests/unit/test_sqlite_persistence.py -v` |
| AC-11.10 | ⬜ | Backward compatibility | Old vaults work with new code |
| AC-11.11 | ⬜ | Example geist variety | Examples at beginner/intermediate/advanced levels |
| AC-11.12 | ⬜ | Documentation completeness | All features and config options documented |
| AC-11.13 | ⬜ | Error message clarity | Manual: error-message clarity is a qualitative review; partial coverage in the CLI suite |
| AC-11.14 | ⬜ | Logging configuration | Manual: logging configuration via cli _configure_logging; no dedicated test_logging suite |
| AC-11.15 | ⬜ | Memory profiling | Manual: memory profiling; perf-only, not gate-enforced |
| AC-11.16 | ⬜ | Resource cleanup | Manual: resource cleanup verified indirectly by the test_db fixture; no dedicated suite |
| AC-11.17 | ⬜ | Platform-specific tests | Tests for Windows, macOS, Linux |
| AC-11.18 | ⬜ | CLI help completeness | All commands/options documented in help |
| AC-11.19 | ⬜ | Configuration examples | Minimal, standard, advanced config examples |
| AC-11.20 | ⬜ | Upgrade guide | docs/UPGRADING.md exists |
| AC-11.21 | ⬜ | Troubleshooting guide | docs/TROUBLESHOOTING.md exists |
| AC-11.22 | ⬜ | Performance regression tests | `uv run pytest tests/unit/test_performance_regression.py -v` |
| AC-11.23 | ⬜ | Load testing | Handles 10K+ notes |
| AC-11.24 | ⬜ | Recovery from corruption | `uv run pytest tests/unit/test_sqlite_persistence.py::test_corrupted_database_recovery -v` |
| AC-11.25 | ⬜ | Observability | Metrics exposed (if implemented) |

### Test Coverage Target
- Overall project: >85%
- Critical paths: >95%

### Exit Criteria
- All AC-11.* checks pass
- Documentation complete
- Performance targets met
- Ready for public release

---

## Summary Statistics

### By Phase

| Phase | Core AC | Edge Case AC | Total AC | % Complete |
|-------|---------|--------------|----------|------------|
| 0 | 7 | 7 | 14 | 0% |
| 1 | 7 | 13 | 20 | 0% |
| 2 | 5 | 10 | 15 | 0% |
| 3 | 5 | 10 | 15 | 0% |
| 4 | 6 | 14 | 20 | 0% |
| 5 | 6 | 14 | 20 | 0% |
| 6 | 6 | 14 | 20 | 0% |
| 7 | 5 | 13 | 18 | 0% |
| 8 | 5 | 14 | 19 | 0% |
| 9 | 5 | 14 | 19 | 0% |
| 10 | 8 | 18 | 26 | 0% |
| 11 | 8 | 17 | 25 | 0% |
| **Total** | **73** | **158** | **231** | **0%** |

### By Category

| Category | Count | % Complete |
|----------|-------|------------|
| Core Functionality | 73 | 0% |
| Edge Cases | 89 | 0% |
| Error Handling | 42 | 0% |
| Performance | 13 | 0% |
| Documentation | 8 | 0% |
| Security | 6 | 0% |

---

## How to Use This Document

### For Developers

1. **Mark progress**: Update status symbols as you complete each AC
2. **Run verification**: Copy/paste verification commands to test
3. **Track blockers**: Use ⚠️ to mark ACs that are blocked
4. **Document failures**: Use ❌ and add notes about why tests failed

### For Project Managers

1. **Overall progress**: Check phase completion percentages
2. **Risk assessment**: Review failed (❌) and blocked (⚠️) items
3. **Planning**: Use this to estimate remaining work

### For QA

1. **Test suite**: Each AC maps to specific test commands
2. **Regression**: Re-run ACs when bugs are fixed
3. **Release criteria**: All core ACs must be ✅ before release

### Update Frequency

- **Daily**: Individual developers update their AC status
- **Weekly**: Team reviews phase completion percentages
- **Per Phase**: Full review before marking phase complete
- **Pre-Release**: Complete audit of all ACs

---

Last Updated: 2025-01-19
