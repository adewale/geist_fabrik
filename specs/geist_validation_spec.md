# Geist Validation Specification

## Overview

This document specifies all validation mechanisms for GeistFabrik geists, both currently implemented and planned. The goal is to enforce geist quality, safety, and correctness at multiple stages: development time, load time, runtime, and post-execution.

**Validation Philosophy**: GeistFabrik should be permissive during development but strict about preventing broken or dangerous geists from executing. Validation should provide clear error messages and actionable feedback.

**Context**: GeistFabrik is at version 0.9.0 (98% complete) approaching 1.0. This spec supports the **"Enhanced error messages and debugging"** roadmap item for 1.0 by documenting current validation and prioritizing improvements for early adopters.

**Relationship to Other Specs**:
- `specs/acceptance_criteria.md` - AC-4.* defines geist execution validation requirements
- `README.md` - Roadmap to 1.0 includes enhanced error messages
- `STATUS.md` - Tracks implementation status of validation features

---

## Key Takeaways

**For 1.0 Release**:
- ✅ Current validation is **robust and sufficient** for stable release
- ✅ Meets 18/20 AC-4.* criteria (90%)
- 🔧 **3 enhancements needed** for 1.0: Better error messages, CLI validate command, error documentation
- ⏱️ Estimated effort: 1-2 days

**For Post-1.0**:
- 📋 Advanced validation features (static analysis, security, performance tracking)
- 📋 Developer convenience tools (pre-commit hooks, auto-documentation)
- ℹ️ These are enhancements, not requirements

**Answer to "How do we enforce geist validity?"**:
GeistFabrik enforces validity through **4-stage validation**: development-time (planned), load-time (✅ implemented), runtime (✅ implemented), and post-execution filtering (✅ implemented). Current mechanisms catch most errors; 1.0 improvements will make errors clearer for early adopters.

---

## Validation Stages

GeistFabrik validates geists at four distinct stages:

1. **Development Time** - Static analysis before geists are committed
2. **Load Time** - Structural validation when loading geist files
3. **Runtime** - Execution validation and constraint enforcement
4. **Post-Execution** - Quality filtering of generated suggestions

---

## Acceptance Criteria Coverage

GeistFabrik's validation already satisfies most acceptance criteria from `specs/acceptance_criteria.md`:

**Geist Execution (AC-4.*)** - Status: ✅ **18/20 implemented**
- ✅ AC-4.1-4.6: Core execution, timeout, failure tracking
- ✅ AC-4.7-4.9: Syntax/import/format error handling
- ✅ AC-4.12: Duplicate ID prevention
- ✅ AC-4.13: Missing directory handling
- ✅ AC-4.14: Infinite loop timeout
- ✅ AC-4.16-4.19: Edge cases (unicode, exceptions, state isolation)
- ⚠️ AC-4.10: Vault modification prevention (needs explicit test)
- ⚠️ AC-4.11: Segfault isolation (advanced, optional for 1.0)
- ⚠️ AC-4.15: Memory limits (optional for 1.0)
- ⚠️ AC-4.20: Parallel execution (not planned - serial only)

**Verdict**: Current validation meets 1.0 requirements. Missing items are advanced edge cases that can be addressed post-1.0.

---

## Current Implementation (✅)

### 1. Code Geist Load-Time Validation

**Location**: `src/geistfabrik/geist_executor.py:76-108`

**Validations**:
- ✅ **Duplicate ID prevention** (line 89)
  - Prevents multiple geists with same filename
  - Raises `ValueError` if duplicate detected

- ✅ **Module importability** (lines 93-95)
  - Validates Python module can be loaded
  - Raises `ImportError` if module spec cannot be created

- ✅ **Function existence** (lines 102-103)
  - Requires `suggest()` function to be present
  - Raises `AttributeError` if missing

- ✅ **Error logging** (lines 66-74)
  - Load errors captured but don't stop other geists loading
  - Logs include traceback for debugging

**What's NOT validated at load time**:
- Function signature (parameter count, type hints)
- Dangerous imports (os.system, subprocess, eval, etc.)
- Docstring presence
- Naming conventions

### 2. Code Geist Runtime Validation

**Location**: `src/geistfabrik/geist_executor.py:110-176`

**Validations**:
- ✅ **Execution timeout** (lines 134-136, timeout_handler)
  - 5-second default limit (configurable)
  - Raises `GeistTimeoutError` on timeout
  - Unix-only (uses SIGALRM)

- ✅ **Return type checking** (lines 143-144)
  - Must return a `list`
  - Raises `TypeError` if wrong type

- ✅ **Suggestion type validation** (lines 147-152)
  - Each item must be `Suggestion` instance
  - Raises `TypeError` if wrong type
  - Includes item index in error message

- ✅ **Failure tracking** (lines 195-235)
  - Increments failure count per geist
  - Auto-disables after 3 failures (configurable)
  - Logs include geist_id, error type, traceback

- ✅ **Disabled geist skipping** (lines 126-130)
  - Skips execution if geist disabled
  - Logs skip reason

**What's NOT validated at runtime**:
- Suggestion content quality (checked in filtering)
- Note reference validity (checked in filtering)
- Execution performance metrics (no warnings for slow geists)

### 3. Tracery Geist Load-Time Validation

**Location**: `src/geistfabrik/tracery.py:203-234`

**Validations**:
- ✅ **YAML parsability** (line 224-225)
  - Uses `yaml.safe_load()`
  - Raises `YAMLError` if invalid

- ✅ **Type field** (lines 227-228)
  - Must be "geist-tracery"
  - Raises `ValueError` if wrong type

- ✅ **Required fields** (lines 230-232)
  - `id` field must exist
  - `tracery` grammar dict must exist
  - Raises `KeyError` if missing

- ✅ **Optional count field** (line 232)
  - Defaults to 1 if not specified

**What's NOT validated at load time**:
- Grammar structure (origin symbol presence)
- Symbol references (undefined symbols)
- ID naming conventions
- Description field presence

### 4. Tracery Geist Runtime Validation

**Location**: `src/geistfabrik/tracery.py:18-179`

**Validations**:
- ✅ **Recursion depth limit** (lines 54-55)
  - Max depth of 50 (prevents infinite loops)
  - Raises `RecursionError` if exceeded

- ✅ **Vault function error handling** (lines 151-152)
  - Catches exceptions from `$vault.*` calls
  - Returns error message in text: `[Error calling {func}: {e}]`

- ✅ **Expansion error handling** (lines 264-267)
  - Catches and logs expansion failures
  - Prints warning but continues
  - Skips failed suggestions

**What's NOT validated at runtime**:
- Symbol reference validity (undefined symbols returned unchanged)
- Vault function parameter types
- Suggestion quality

### 5. Post-Execution Filtering (All Geist Types)

**Location**: `src/geistfabrik/filtering.py`

**Four-stage pipeline**:

#### a) Boundary Filter (lines 93-115)
- ✅ **Note existence** - Referenced notes must exist in vault
- ✅ **Exclusion boundaries** - Notes can't be in excluded paths

#### b) Novelty Filter (lines 117-169)
- ✅ **Embedding similarity** - Compare to recent session history
- ✅ **Configurable threshold** - Default 0.85 cosine similarity
- ✅ **Time window** - Default 60-day lookback
- ✅ **Method swappable** - Can switch to text matching

#### c) Diversity Filter (lines 171-215)
- ✅ **Within-batch deduplication** - Remove similar suggestions
- ✅ **Embedding-based** - Cosine similarity comparison
- ✅ **First-seen preference** - Keeps earlier suggestion

#### d) Quality Filter (lines 217-276)
- ✅ **Length validation**
  - Min: 10 characters (default)
  - Max: 2000 characters (default)
- ✅ **Repetition checking**
  - Detects word repetition patterns
  - Configurable sensitivity

**Filter Configuration**:
All filters can be:
- Enabled/disabled via config
- Reordered via config
- Have thresholds tuned

---

## Planned Validation (📋)

### 1. Static Analysis (Development Time)

**Priority**: High
**Complexity**: Medium
**Implementation**: New module `src/geistfabrik/validation.py`

#### Code Geist Static Validation

- 📋 **AST parsing for syntax errors**
  - Parse file before load attempt
  - Provide clear syntax error messages
  - Prevents runtime import failures

- 📋 **Function signature validation**
  - `suggest()` must take exactly 1 parameter
  - Parameter should be named `vault` or `context`
  - Should have type hints (warning if missing)

- 📋 **Dangerous import detection**
  - Warn on: `os.system`, `subprocess`, `eval`, `exec`, `__import__`
  - Block on: `socket`, `http`, network libraries
  - Rationale: Geists should be local-only and safe

- 📋 **Docstring requirements**
  - Module-level docstring required
  - `suggest()` function docstring recommended
  - Improves geist discoverability

- 📋 **Naming convention enforcement**
  - File/ID should be lowercase with underscores
  - Should not start with underscore (reserved for internal)
  - Should be alphanumeric + underscores only

#### Tracery Geist Static Validation

- 📋 **Grammar structure validation**
  - `origin` symbol must exist
  - Warn if `origin` is empty

- 📋 **Symbol reference checking**
  - Find all `#symbol#` references in rules
  - Warn if symbol not defined in grammar
  - Detect potential typos

- 📋 **Vault function validation**
  - Validate `$vault.function()` calls
  - Check function exists in registry
  - Validate parameter count/types

- 📋 **Suggestions count limits**
  - Warn if `suggestions_per_invocation` > 10
  - Suggest using sampling instead of generation

- 📋 **Description field requirement**
  - Require `description` field for documentation
  - Used in `geistfabrik list` command

### 2. CLI Validation Command

**Priority**: High
**Complexity**: Low
**Implementation**: New command in `src/geistfabrik/cli.py`

```bash
# Validate all geists in a vault
uv run geistfabrik validate

# Validate specific geist
uv run geistfabrik validate --geist temporal_drift

# Validate with strict mode (warnings = errors)
uv run geistfabrik validate --strict

# Output formats
uv run geistfabrik validate --format json
uv run geistfabrik validate --format summary
```

**Output format**:
```
Validating geists in /vault/_geistfabrik/geists/...

✅ code/temporal_drift.py
   - All checks passed

⚠️  code/experimental_idea.py
   - Warning: Missing type hints on suggest()
   - Warning: No module docstring

❌ code/broken_geist.py
   - Error: Missing suggest() function
   - Error: Syntax error on line 15

✅ tracery/what_if.yaml
   - All checks passed

⚠️  tracery/random_ideas.yaml
   - Warning: Undefined symbol 'ideasss' (typo for 'ideas'?)

Summary: 3 passed, 2 warnings, 1 error
```

### 3. Pre-commit Hook Integration

**Priority**: Medium
**Complexity**: Low
**Implementation**: Template in `docs/hooks/pre-commit.sample`

- 📋 Validate only staged geist files
- 📋 Block commit if errors found
- 📋 Allow commit with warnings (logged)
- 📋 Configurable strict mode

### 4. Test Coverage Enforcement

**Priority**: High
**Complexity**: Low
**Implementation**: New test in `tests/test_geist_coverage.py`

- 📋 **Coverage test**
  - Scan `examples/geists/code/` and `examples/geists/tracery/`
  - Check each geist appears in `tests/integration/test_example_geists.py`
  - Fail CI if geist has no test
  - Enforces AC-4.1 (all geists must have tests)

- 📋 **Test quality checks**
  - Test must invoke the geist
  - Test must assert on output
  - Test must use real vault (no mocks)

### 5. Performance Benchmarking

**Priority**: Medium
**Complexity**: Low
**Implementation**: Enhance `GeistExecutor.execute_geist()`

- 📋 **Execution time tracking**
  - Log execution time for all geists
  - Warn if > 2 seconds (below 5s timeout)
  - Include in `geistfabrik invoke --verbose` output

- 📋 **Performance regression tests**
  - Benchmark suite for all geists
  - Alert if geist becomes 2x slower
  - Track performance over time

- 📋 **Resource usage monitoring**
  - Track memory allocation (if feasible)
  - Warn on excessive memory use

### 6. Enhanced Suggestion Quality Validation

**Priority**: Medium
**Complexity**: Medium
**Implementation**: New method in `GeistExecutor`

Pre-filtering quality checks (before suggestions reach filtering pipeline):

- 📋 **Placeholder detection**
  - Detect: `TODO`, `FIXME`, `#symbol#`, `$vault`, `[ERROR]`
  - Indicates incomplete template expansion
  - Filter out or log warning

- 📋 **Note reference validation**
  - If text contains `[[note]]`, ensure `notes` list populated
  - Detect inconsistencies

- 📋 **Text quality heuristics**
  - Minimum length: 10 chars (filter already has this)
  - Maximum length: 2000 chars (filter already has this)
  - No excessive punctuation (e.g., `!!!!!!`)
  - No all-caps text

- 📋 **Geist ID validation**
  - Must match executing geist's ID
  - Prevents copy-paste errors

### 7. Security Validation

**Priority**: High
**Complexity**: High
**Implementation**: New module `src/geistfabrik/security.py`

- 📋 **Sandbox execution** (future consideration)
  - Execute geists in restricted environment
  - Limit filesystem access to vault only
  - No network access
  - Requires significant architecture changes

- 📋 **Import whitelist**
  - Maintain list of allowed imports
  - Standard library: `re`, `datetime`, `random`, etc.
  - GeistFabrik: `geistfabrik.*`
  - Blocked: anything network-related, `subprocess`, etc.

- 📋 **Code pattern scanning**
  - AST-based analysis
  - Flag suspicious patterns: `open(..., 'w')`, `os.remove()`, etc.
  - Vault is read-only except for session notes

### 8. Documentation Generation

**Priority**: Low
**Complexity**: Low
**Implementation**: New command `geistfabrik docs`

- 📋 **Auto-generate geist catalog**
  - Scan all geists
  - Extract: ID, description, type, required functions
  - Generate markdown documentation

- 📋 **Dependency graph**
  - Show which geists use which vault functions
  - Show which vault functions use which metadata

---

## Validation Error Handling

### Error Severity Levels

1. **ERROR** - Blocks execution/loading
   - Missing `suggest()` function
   - Invalid return type
   - Syntax errors
   - Missing required YAML fields

2. **WARNING** - Logs but allows execution
   - Missing type hints
   - Missing docstrings
   - Slow execution (>2s)
   - Undefined Tracery symbols

3. **INFO** - Logged for developer awareness
   - Performance metrics
   - Execution times
   - Suggestion counts

### Error Message Format

All validation errors should include:
- **What**: Clear description of the problem
- **Where**: File path and line number (if applicable)
- **Why**: Explanation of why this is a problem
- **How**: Suggestion for fixing it

**Example**:
```
❌ ERROR in code/broken_geist.py
   Line 15: Missing suggest() function

   Why: All code geists must export a suggest(vault) function
   Fix: Add this function to your geist:

   def suggest(vault: VaultContext) -> List[Suggestion]:
       """Generate suggestions."""
       return []
```

### Test Command Generation

For runtime failures, generate reproducible test command:

```
❌ Geist 'temporal_drift' failed with timeout

   Test command:
   uv run geistfabrik test temporal_drift --vault ~/vault --date 2025-10-21

   This command will help you debug the issue locally.
```

---

## Configuration

All validation can be configured via `config.yaml`:

```yaml
validation:
  # Enable/disable validation stages
  load_time: true
  runtime: true
  static_analysis: true

  # Static analysis settings
  static:
    require_docstrings: true
    require_type_hints: false  # Only warn
    check_dangerous_imports: true
    enforce_naming: true

  # Runtime settings
  runtime:
    timeout: 5
    max_failures: 3
    track_performance: true
    warn_slow_threshold: 2.0  # seconds

  # Quality settings
  quality:
    min_length: 10
    max_length: 2000
    check_placeholders: true
    check_note_refs: true

  # Security settings
  security:
    import_whitelist_enabled: false  # Not implemented yet
    allowed_imports:
      - re
      - datetime
      - random
      - geistfabrik.*
```

---

## Testing Strategy

### Unit Tests Required

Each validation type must have unit tests:

- ✅ Code geist load validation - `tests/unit/test_geist_executor.py:60-90`
- ✅ Code geist timeout - `tests/unit/test_geist_executor.py:92-115`
- ✅ Tracery YAML parsing - `tests/unit/test_tracery.py`
- ✅ Filtering pipeline - `tests/unit/test_filtering.py`
- 📋 Static analysis validators
- 📋 CLI validate command
- 📋 Performance benchmarking

### Integration Tests Required

- ✅ Example geists - `tests/integration/test_example_geists.py`
- 📋 End-to-end validation workflow
- 📋 Pre-commit hook behavior

---

## Implementation Priority

### For 1.0 Release (Roadmap: "Enhanced error messages and debugging")

**Essential for early adopters**:
1. **Improved error messages** - Current errors work but could be clearer
   - Better formatting for load/runtime errors
   - Include file paths and line numbers
   - Suggest fixes for common problems
   - Generate test commands for reproduction (partially implemented)

2. **CLI validation command** - `geistfabrik validate`
   - Validate geist files before runtime
   - Catch common errors early
   - Developer-friendly output

3. **Documentation for common errors** - Help early adopters debug issues
   - Common error patterns and solutions
   - Validation troubleshooting guide

**Estimated effort**: 1-2 days for items 1-3 above

### Post-1.0: Enhanced Validation

**Nice to have, but not blocking 1.0**:
4. Static analysis module - AST parsing, dangerous imports
5. Test coverage enforcement - Ensure all geists have tests
6. Performance benchmarking - Track slow geists
7. Pre-commit hooks - Validate before commits
8. Security validation - Import whitelisting, sandboxing
9. Documentation generation - Auto-generate geist catalog

**Note**: Current validation (AC-4.* criteria) is **sufficient for 1.0**. These enhancements improve developer experience but aren't required for stable release.

---

## Success Metrics

Validation system succeeds when:

1. **Zero runtime failures** in production vaults
   - All structural errors caught at load time
   - All dangerous code caught at development time

2. **Clear error messages** for developers
   - Developers can fix errors without reading code
   - Test commands provided for reproduction

3. **Fast feedback loops**
   - Validation runs in <1 second for typical vaults
   - Errors shown before commit, not after

4. **High geist quality**
   - All geists have tests
   - All geists have documentation
   - No broken or slow geists in examples

5. **Developer confidence**
   - Easy to add new geists
   - Clear expectations and guidelines
   - Validation helps rather than hinders

---

## Open Questions

1. **Sandbox execution**: Is it worth the complexity to sandbox geist execution, or is import whitelisting sufficient?

2. **Windows timeout support**: Current timeout uses Unix signals. Should we implement Windows-compatible timeout?

3. **Performance budget**: Should we enforce a strict performance budget (e.g., all geists must complete in <1s)?

4. **Automatic fixes**: Should validation offer automatic fixes for common issues (e.g., add missing docstrings)?

5. **Validation levels**: Should users be able to run validation at different strictness levels (permissive/normal/strict)?

---

## Related Documents

- `specs/geistfabrik_spec.md` - Main specification including error handling philosophy
- `specs/acceptance_criteria.md` - AC-4.x covers geist execution and error handling
- `specs/testing_plan.md` - Test coverage requirements
- `CLAUDE.md` - Error handling philosophy and development patterns
- `docs/GEIST_CATALOG.md` - Current geist inventory
