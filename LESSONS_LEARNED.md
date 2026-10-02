# Lessons Learned

This document captures key insights and design decisions discovered during GeistFabrik development. It should evolve as we learn more about what makes great geists.

## Muses, Not Oracles: The Case for Asking Over Answering

**Date:** 2025-10-21
**Context:** Contradictor geist implementation

### The Problem

Initial implementations of the Contradictor geist tried to algorithmically generate opposite note titles:

```python
# 100+ lines of pattern matching
opposite = _generate_opposite(title)
text = f"[[{title}]] exists - what about '{opposite}'?"
```

**Results:**
- "Benefits of Morning Routines" → "Costs of Morning Routines" ✓ (works)
- "Evergreen notes" → "The opposite of Evergreen notes" ✗ (useless)
- "Meeting with Sarah" → "The opposite of Meeting with Sarah" ✗ (nonsensical)
- "2023-09-12" → "The opposite of 2023-09-12" ✗ (absurd)

**Success rate:** ~10% (only titles with specific patterns)

### The Insight

**Simple questions beat complex answers:**

```yaml
# 13 lines of YAML
suggestion:
  - "[[#note#]] exists. But what about the opposite?"
  - "What contradicts [[#note#]]?"
```

**Success rate:** 100% (works for ANY note)

### Why Questions Win

1. **Universal application** - Works on any note title regardless of content
2. **Opens possibility space** - User generates multiple opposites, not just one
3. **Engages thinking** - Forces active cognitive engagement
4. **Honest about uncertainty** - Doesn't pretend to know what the opposite is
5. **More divergent** - User explores wider range than algorithm could generate

### The Principle

**"A well-asked question is better than a poorly-computed answer."**

Geists should provoke thinking, not try to think for the user. This is especially true when:
- The problem space is subjective (meaning, opposites, analogies)
- Human creativity exceeds algorithmic capability
- Multiple valid answers exist
- The goal is divergence, not convergence

### When to Use Code vs Tracery

#### Use Code Geists When:
- **Computation is needed**: Statistics, graph algorithms, similarity scores
- **Objective analysis**: Finding orphans, calculating embeddings, counting links
- **Complex queries**: Multi-step database operations
- **Performance matters**: Caching, optimisation, batch processing
- **Integration required**: External APIs, ML models, system calls

#### Use Tracery Geists When:
- **Asking questions**: Provocations that engage user thinking
- **Template variations**: Multiple phrasings of similar prompts
- **Subjective exploration**: Analogies, opposites, connections
- **Accessibility**: Non-programmers should be able to create/modify
- **Rapid iteration**: Testing different prompt phrasings

#### Hybrid Approach (Best Practice):
1. **Write reusable vault functions** (Python) for objective operations
2. **Compose Tracery geists** that combine functions with questions
3. **Reserve pure code geists** for when computation is truly necessary

### Examples of "Ask Better Questions" Patterns

All of these work as simple Tracery geists without any complex logic:

- **Inversion**: "What contradicts [[note]]?"
- **Analogy**: "What is [[note]] like in a different domain?"
- **Scale**: "What if [[note]] were 10x bigger?"
- **Time**: "What will [[note]] look like in 10 years?"
- **Audience**: "Who else should care about [[note]]?"
- **Bridge**: "What connects [[note1]] and [[note2]]?"
- **Concrete**: "What's a real example of [[note]]?"
- **Abstract**: "What pattern does [[note]] exemplify?"
- **Missing**: "What's missing from [[note]]?"
- **Merge**: "What if you combined [[note1]] and [[note2]]?"
- **Constraint**: "Explain [[note]] in one sentence."

### Complexity Comparison

| Aspect | Code Approach | Question Approach |
|--------|---------------|-------------------|
| Lines of code | 100+ | 10-15 |
| Maintenance | High | Minimal |
| Success rate | 10-20% | 100% |
| Divergence quality | Narrow | Wide |
| User engagement | Passive | Active |
| Works for edge cases | No | Yes |
| Non-programmer friendly | No | Yes |

### Impact on Design Philosophy

This insight reinforces the core GeistFabrik principle: **Muses, not oracles.**

- **Oracle behaviour**: "I will tell you what the opposite is"
- **Muse behaviour**: "Have you considered the opposite?"

The geist's job is not to know the answer. Its job is to ask questions you wouldn't ask yourself.

---

## API Consistency Over Avoiding Breaking Changes

**Date:** 2025-11-09
**Context:** Bug discovered in `semantic_neighbours` Tracery geist where neighbour note references were missing `[[...]]` brackets

### The Problem

GeistFabrik had an API inconsistency where vault functions followed two different patterns:

- **Simple functions** (sample_notes, orphans, etc.): Returned bare text `"Note Title"`
  - Templates had to add brackets: `"Check out [[#note#]]"`
- **Cluster functions** (semantic_clusters): Returned bracketed text `"[[Note Title]]"`
  - Templates used as-is: `"#seed# connects to #neighbours#"`

**Why it existed:**
- Cluster functions bundle multiple notes with delimiters (`"[[Seed]]|||[[N1]], [[N2]]"`)
- Adding brackets to delimiter-separated values in templates seemed difficult
- The exception was documented as "intentional architectural decision"

**The bug:**
- Missing brackets in `semantic_neighbours` neighbour references
- Developers forgot which pattern applied where
- Two-pattern API caused confusion and bugs

### The Investigation

The bug prompted a three-step process:

1. **Immediate fix** (commit 3efc96c):
   - Documented the API inconsistency as intentional
   - Added comprehensive tests to prevent regression
   - Fixed the immediate bug

2. **Root cause analysis**:
   - Realized the two-pattern API was a **design flaw**, not a necessary trade-off
   - Templates don't need to add brackets to delimited values - the function already added them
   - The "difficulty" was imagined, not real

3. **Better solution** (commit d080f66):
   - Breaking change: ALL vault functions now return bracketed links
   - Updated 7 vault functions and 7 Tracery geists
   - Result: **Consistent single-pattern API**

### The Insight

**Fix fundamental design flaws immediately, don't document them as "intentional."**

When you discover an API inconsistency:
1. Don't accept it as "necessary" without thorough analysis
2. Don't document it as "intentional" just because it's been there a while
3. Consider whether fixing it (even with breaking changes) is better than preserving it
4. In beta/pre-1.0, breaking changes are **acceptable and expected**

### The Principle

**"API consistency is more important than avoiding breaking changes in beta."**

Benefits of the consistent API:
- ✅ **Eliminates confusion**: Single pattern, no exceptions to remember
- ✅ **Prevents bugs**: No more forgetting to add brackets to specific references
- ✅ **Simplifies templates**: Just use `#symbol#`, never `[[#symbol#]]`
- ✅ **Better onboarding**: New developers learn one pattern, not two

### Why This Was The Right Call

**Timing matters:**
- Pre-1.0: Breaking changes expected, users understand things may change
- Post-1.0: Would require migration guides, deprecation warnings, version bumps
- **Fix design flaws in beta**, preserve stability after 1.0

**Scope matters:**
- 7 functions updated (out of ~15 total vault functions)
- 7 Tracery geists updated (out of 9 total)
- No user-facing geists in production yet
- **Small breaking change now** vs. permanent technical debt

**Quality matters:**
- Bugs from API inconsistency cost more than fixing the API
- Documentation complexity ("remember the exception") is cognitive overhead
- **Consistent APIs are easier to learn, use, and maintain**

### Impact

**Before (two-pattern API):**
```yaml
# Simple functions - template adds brackets
note: ["$vault.sample_notes(1)"]  # Returns "Note Title"
origin: "Check out [[#note#]]"     # Template adds [[...]]

# Cluster functions - function adds brackets
cluster: ["$vault.semantic_clusters(2, 3)"]  # Returns "[[Seed]]|||[[N1]], [[N2]]"
origin: "#seed# connects to #neighbours#"     # Template uses as-is
```

**After (single-pattern API):**
```yaml
# ALL functions - function adds brackets, template uses as-is
note: ["$vault.sample_notes(1)"]         # Returns "[[Note Title]]"
origin: "Check out #note#"                # Template uses as-is

cluster: ["$vault.semantic_clusters(2, 3)"]  # Returns "[[Seed]]|||[[N1]], [[N2]]"
origin: "#seed# connects to #neighbours#"     # Template uses as-is
```

**Lesson applied to:**
- All vault function implementations (src/geistfabrik/function_registry.py)
- All Tracery geist templates (src/geistfabrik/default_geists/tracery/*.yaml)
- Documentation (CLAUDE.md, specs/tracery_research.md)
- Tests (tests/unit/test_tracery_geists.py)

**See also:**
- Commit 3efc96c: Initial documentation of inconsistency
- Commit d080f66: Breaking change implementing consistent API
- Commit 113e718: Documentation updates reflecting new API
- `specs/tracery_research.md`: Technical documentation of vault functions
- `tests/unit/test_tracery_geists.py`: Regression tests

---

## A Test That Cannot Fail Is Worse Than No Test

**Date:** 2026-06-10
**Context:** Quality deep-dive found ~7 default geists shipping dead with green tests

**The Problem:** Several geists gated on metadata keys (`staleness`,
`has_tasks`, `days_since_modified`) that only an optional `examples/` module
provided. In a default install the gates never opened and the geists silently
produced nothing — for months. Their tests stayed green the whole time,
because the testing template taught `for s in suggestions: assert ...`
(vacuous on an empty list) and `assert len(x) >= 0` (always true). One geist
(`cluster_evolution_tracker`) queried a database column that **never existed
in any schema version**; its OperationalError was swallowed by the executor's
fail-soft handling and its tests, asserting nothing about non-emptiness,
never noticed.

**The Insight:** Coverage measured execution, not verification. A test whose
assertions all live inside a loop over possibly-empty output verifies only
that the geist didn't crash — which the executor already guarantees. The
failure mode wasn't missing tests; it was tests with no oracle.

**The Principle:** Every geist's happy-path test runs on a fixture *designed
to trigger* (with the trigger arithmetic stated in a comment) and asserts
NON-EMPTY output. Exclusion tests verify both directions (planted good notes
appear, banned notes don't). If you can't build a fixture that makes the
geist fire, you don't understand the trigger condition yet.

**Impact:** GEIST_TESTING_TEMPLATE.md rewritten around designed-to-trigger
fixtures + `tests/fixtures/helpers.assert_valid_suggestions()`; built-in
metadata now provides the keys geists gate on; revived geists carry
non-empty regression tests.

---

## Determinism Dies By A Thousand Wall-Clocks

**Date:** 2026-06-10
**Context:** "Same date + vault = same output" (principle 6) was violated in five separate ways

**The Problem:** Built-in metadata used `datetime.now()`; five geists used
`datetime.now()` instead of the session date; `semantic_clusters` seeded with
Python's `hash()` (randomised per process via PYTHONHASHSEED); the unit-test
mock encoder also seeded with `hash()` (different mock embeddings every
pytest run — latent flakes near similarity thresholds); and test fixtures
built sessions at `datetime.now()` even though session-season is literally an
embedding feature, so tests computed different embeddings depending on the
calendar day they ran.

**The Insight:** Determinism is not a property you declare once — every new
call site re-decides it. `datetime.now()` and `hash()` both look innocent and
both silently break replay. Nothing enforced the principle, so it eroded.

**The Principle:** "Now" is always the session date (`vault.session.date`),
never the wall clock. Seeds derive from the session date via `hashlib`, never
`hash()`. Test fixtures pin both. When a principle matters, grep for its
violations and consider lint-banning the offending calls.

**Impact:** `--date` replays are reproducible again; the testing template
mandates pinned dates/seeds.

**0.11.0 follow-up:** A stable seed was necessary but insufficient. Timestamp
conversion could still select a different calendar day, and replay could still
read sessions written after the requested date. Preview, write, replay, tests,
Tracery, and vault functions now share one canonical calendar date, `YYYYMMDD`
seed, and as-of history boundary. Reproducibility includes every input read by
the computation, not only its random-number generator.

---

## Specs Are Promises: Audit the Diff Between Spec and Ship

**Date:** 2026-06-10
**Context:** Three separate "the spec said X, the code does nothing" discoveries

**The Problem:** (1) The spec specified a `geist_status` table persisting
failure counts across sessions ("disable after 3 failures") — never built;
the shipped in-memory counter can never reach 3, so the documented
auto-disable feature is unreachable dead code. (2) The reuse-abstractions
spec promised three geists showcasing `GraphPatternFinder` (structural holes,
path-length anomaly, bridge redundancy) — the module shipped, documented as a
public API, with zero consumers and zero tests, carrying latent O(N²) bombs.
(3) `cluster_evolution_tracker` was written against a schema column that was
specified but never created.

**The Insight:** When implementation pauses partway through a spec, the
gap is invisible: docs describe the spec, tests exercise the code, and
nothing compares the two. "Documented" came to mean "specified", not
"working".

**The Principle:** A spec item is either implemented, explicitly deferred
(tracked), or deleted from the docs. When adding an abstraction, ship at
least one consumer and its tests in the same change — an API with zero
consumers is a liability, not an investment.

**Impact:** The three promised graph geists now exist as
`examples/geists/code/`; graph_analysis is tested and de-bombed; the
auto-disable gap is documented as a missing `geist_status` abstraction
pending a decision.

---

## One Definition Per Concept (Link Resolution Edition)

**Date:** 2026-06-10
**Context:** Three code paths disagreed about "does this link point to this note"

**The Problem:** `links_between`/`backlinks` matched `{path, path-no-ext,
title}`; `graph_analysis` and `similarity_analysis.is_bridge` matched titles
only (path-form links invisible to bridge detection); `orphans()` had an
inline variant. Backlink and bridge detection silently disagreed depending on
which API a geist called.

**The Insight:** The same domain question implemented three times will drift
three ways — and each copy looks locally correct in review.

**The Principle:** Domain predicates get ONE canonical definition
(`models.link_target_forms()`), every consumer calls it, and an agreement
test locks the code paths together so the next copy-paste divergence fails
CI.

**Impact:** All link-resolution consumers unified; `tests/unit/
test_graph_analysis.py::TestLinkResolutionAgreement` enforces agreement.

---

## Specified But Never Built: Self-Attesting Status Is Not Verification

**Date:** 2026-06-10
**Context:** ~20 spec promises had no implementation — the largest being most of
the config.yaml schema (exclude_paths, filtering thresholds, timeout, logging…).

**The Problem:** The spec described features that were never wired, and nothing
caught it. The worst case: `filtering.boundary.exclude_paths` (a privacy
control — keep `Private/` notes out of suggestions) was *documented as
implemented* (`geist_validation_spec.md:186`) but did nothing, for months.

**How it happened (commit evidence, shallow history from 2025-11-01):**
1. **Self-attesting verification.** `scripts/check_phase_completion.py` skips
   any acceptance criterion the spec marks `✅` (`if status == "✅": passed += 1;
   continue`) — it counts an item done because the *document says so*, never
   running the verification command. The spec attests its own completion.
2. **The checker wasn't even in CI** (no reference in `.github/` or
   `validate.sh`) — a manual script that, even if run, trusted the ✅ marks.
3. **Config-by-demand + silent ignore.** Config sections were added only when a
   feature PR needed one (`ClusterConfig` with cluster-labeling, `VectorSearch`/
   `DateCollection` later). Spec keys nothing needed never got wired, and
   `data.get(key, default)` *silently ignores* unparsed keys — no signal.
4. **No mechanical spec→code link.** No test parsed the spec schema; the spec
   was a write-once aspirational doc with zero tie to the code.

**The Principle:** Status must be *verified*, not *asserted*. A document
claiming "implemented" is worth nothing unless a test re-derives it from the
code. Unrecognised config keys must warn, not vanish. "Phase complete" must run
the acceptance check, not read a checkbox.

**What we built to prevent recurrence:**
- `specs/SPEC_STATUS.md` — one reviewed ledger of every spec config key's true
  status, enforced by `tests/unit/test_spec_config_sync.py`: a spec edit that
  adds a key fails CI until its status is recorded (the
  test_geist_count_consistency pattern, applied to the spec).
- `load_config()` warns on unknown top-level keys (a typo or unwired spec key
  is now visible).
- `tests/unit/test_doc_links.py` fails on dead internal doc links (the failure
  mode behind never-written referenced docs).
- bandit in CI/validate.sh (a real security-scan AC, made true).
- Replaced two hardcoded geist counts in tests with the programmatic constant.

**What we built next — the checker now verifies, never trusts** (2026-06-11):
`scripts/check_phase_completion.py` was rewritten and wired into both
`scripts/validate.sh` and CI, so the spec table can no longer drift from the
code without turning CI red.

- **The silent drop was bigger than the ✅-skip.** Auditing the old checker, the
  `if status == "✅"` shortcut never even fired — every row was `⬜`. The real
  leak was its rigid regex, which **silently dropped 95 of 231 criteria** (41%)
  whose verification cell had a trailing annotation or was prose. "All criteria
  pass" was true while two-fifths were never looked at. *Lesson: a parser that
  skips what it can't match is worse than one that errors — make unparseable a
  hard failure.* The new checker parses every row, classifies each as **AUTO**
  (runs a real command) or **MANUAL** (prose, reported but not gating), and
  fails on any unparseable row or any command smuggled into prose.
- **Reconciling 231 criteria surfaced the drift.** ~120 commands referenced
  test nodes that had been renamed/removed. Dead `::node`s were coarsened to
  their (drift-resistant) test file; behaviours with no surviving test became
  honest MANUAL entries; the count of MANUAL criteria *is* the visible ledger of
  what we don't pinpoint-test.
- **A verification gate must be non-destructive and deterministic.** Several ACs
  "verified" setup by *running* it — `uv sync --only-dev`, `uv pip install -e .`,
  `pre-commit run --all-files`. Executed by the gate they mutated the dev's
  environment (one left torch half-installed; `pre-commit` auto-reformatted 12
  unrelated files). *Lesson: a check that changes the thing it checks isn't a
  check.* Those became non-mutating import probes or MANUAL.
- **One process, not N.** `conftest.py` imports the embedding stack (~5s) per
  process, so spawning a pytest per criterion took ~5 min; batching all targets
  into one run (like validate.sh) brought it to ~30s while still catching a
  renamed target (pytest exits non-zero on an unmatched node).

**Still recommended (process, not mechanised):** a PR-template "spec touched?
update SPEC_STATUS" checkbox; "no abstraction without a consumer + its test" as
review policy.

---

## Observable Signals Beat Speculative Labels

**Date:** 2026-06-12
**Context:** Replacing the sentiment-analysis plan with the reflective-lenses framework

**The Problem:** The sentiment-geists plan tried to infer emotional state from
notes. That creates three bad pressures at once: weak accuracy on short,
personal notes; a temptation to overclaim what the model knows; and licensing /
network / model-weight complexity that conflicts with GeistFabrik's local-first
principles. A low-confidence label like "sad" or "angry" would read like an
oracle, not a muse.

**The Insight:** The useful question was not "what emotion is this note?" but
"what observable pattern is this note showing?" Tense, pronouns, questions,
hedging, sentence-length variance, semantic surprisal, and attention shift are
measurable signals. They still support provocative prompts, but the prompt can
name the evidence: "you hedged eight times", "this note points futureward",
"this note is semantically surprising".

**The Principle:** Prefer reflective lenses over psychological labels. If a
geist cannot observe the thing directly, phrase it as a question or choose a
proxy signal it can honestly measure. Evidence-backed provocations are more
trustworthy than confident guesses about inner state.

**Impact:** `voice_analysis.py` and the reflective geists use pure-Python,
local, testable measurements instead of sentiment classification. The new
tests assert known-answer voice features, hostile-input totality, metamorphic
properties, and cached/vectorised surprisal behaviour.

**0.11.0 follow-up:** The same rule applies to temporal embeddings. Calendar
features cannot establish semantic movement, and a change in representation
cannot establish a change in understanding. Temporal geists now compare only
semantic dimensions and name the dispersion, direction, or neighbour-set
change they actually measure before inviting the user to inspect source notes.

---

## Vault Sync Correctness Lives In Operation Sequences

**Date:** 2026-08-31
**Context:** Adding stateful property coverage for incremental vault synchronization

**The Problem:** Parser properties and one-shot sync examples could show that an individual note
was understood, but not that the vault stayed correct across batches, renames, create, update,
delete, regular/date-collection transitions, and repeated sync operations. Reading a file-backed
store through its writer connection also could not prove that synchronization had committed.

**The Insight:** Incremental synchronization is a state machine, not a collection of independent
calls. After every generated operation, an external shadow model must check exact paths, raw
content, parsed fields, relationships, and dependent-row lifecycle. The file-backed writer must
remain alive across the trace so connection-scoped bugs stay observable, while a fresh raw read-only
connection checks committed state without running application initialization. A second sync with no
filesystem change must report no work, and clean restart is a separate transition.

**The Principle:** Test mutable storage workflows with shrinkable operation sequences, a model
outside the implementation, and invariants after every step. When the project offers multiple
storage modes for the same contract, run the same trace through all of them, compare each with the
independent model, and use a passive connection to observe committed state.

**Impact:** `tests/unit/test_property_vault_stateful.py` now exercises independently modeled regular
and virtual notes, native nested and Unicode paths, fixed coarse-filesystem-safe modification times,
batched updates, renames, deletion, regular/date-collection transitions, quiescent idempotence,
processed counts, foreign-key integrity, relationship cleanup, semantic-cache invalidation,
historical-embedding preservation and deletion cascades, fresh-reader commit visibility, and
explicit clean restarts.

---

## SQLite Names Are Not SQLite Contracts

**Date:** 2026-09-10
**Context:** Following the stateful vault-sync review into production transaction and history bugs

**The Problem:** Three shortcuts created false confidence. `INSERT OR REPLACE` was read as an update
although SQLite implements it as delete-then-insert, cascading away temporal history. Multi-step
methods relied on sqlite3's implicit transaction and caught only final `commit()` errors, so an
earlier exception left partial work pending for another component to commit. A test named
"corruption recovery" discarded its damaged in-memory connection and proved only that a new empty
database could be initialized; acceptance criteria trusted the name and exit code.

**The Insight:** Database correctness is defined by observable transaction and data-lifecycle
contracts, not convenient SQL keywords, a final `commit()`, or a test's name. Current-content caches
and historical records need separate models. Each top-level writer needs exclusive ownership from
`BEGIN IMMEDIATE` through commit, rollback on every escaping failure, and a passive connection as the
commit oracle. Recovery claims require reopening the same damaged artifact or an explicit backup;
fresh initialization is not recovery.

**The Principle:** Translate storage features into exact lifecycle semantics before coding: which
rows survive an update, who owns the transaction, what an independent reader can observe, and what
artifact is recovered. Write a failing test for each contract and sabotage the critical operation to
prove the oracle detects the old behavior.

**Impact:** Note upserts preserve temporal history while explicitly invalidating semantic caches;
date collections delete only vanished virtual paths. Shared SQLite writers use one owned-transaction
primitive and embedding inference happens before the writer lock. Corrupt databases fail without
being overwritten, acceptance criteria no longer claim automatic recovery, and troubleshooting
requires a known-good backup or an explicit history-losing rebuild.

---

## The Proof Boundary Must Match the Guarantee Boundary

**Date:** 2026-09-11
**Context:** Multi-agent review of the SQLite hardening changes

**The Problem:** Fixing transaction rollback made each write atomic, but review still found races
outside those transaction boundaries. Embeddings were computed from one database version and could
be committed after another connection published newer state. Every sqlite-vec backend projected its
session into one global table, so a later backend changed what an earlier instance queried. Schema
version checks happened before the migration lock. Recovery tests manufactured persisted-looking
state without crossing a real process boundary.

**The Insight:** The recurring defect was a **scope mismatch**: the state or test oracle lived at a
narrower scope than the guarantee. Operation-local atomicity cannot prove freshness across time;
one global projection cannot represent instance-local session state; an unlocked check cannot guard
a locked mutation; and an in-process reconstruction cannot prove process-restart recovery.

**The Principle:** Draw the full proof boundary before implementing persistence behavior: identity,
transaction, connection, process, and time. Scope derived state no wider than its owner, validate
optimistic work again after acquiring the write lock, perform check-and-mutate under the same lock,
and make tests cross every boundary named by the claim.

**Impact:** Sessions capture SQLite's `data_version` before production note snapshots, recheck it at
method entry and under the writer lock, and compare supplied note fields with committed rows before
publishing embeddings. sqlite-vec projections are instance-private TEMP tables with explicit
lifecycle cleanup; schema metadata is validated under `BEGIN IMMEDIATE`; rollback is fault-injected
after writes begin; v4 migration uses a frozen file-backed fixture; and journal recovery is exercised
through an actual abruptly terminated child process.

Follow-up review extended the same principle beyond SQLite state. Vault deletion now depends on a
writer-owned, twice-validated filesystem snapshot; vector loaders resolve sessions only after lock
acquisition; metric caches carry exact source and algorithm provenance; Sessions own temporary
projection lifetime; migration support has an explicit v3 floor; and CI asserts the interpreter it
claims to test. Project-wide Hypothesis review also replaced properties whose generators or oracles
made the claimed invariant vacuous.

---

## Validation and Execution Must Share One Gate

**Date:** 2026-09-13
**Context:** Standalone Tracery validation accepted definitions that runtime loading rejected

**The Problem:** The validator and loader independently implemented overlapping structural and
grammar checks. Each looked reasonable in isolation, but they disagreed on malformed identifiers,
counts, missing origins, grammar shapes, and vault calls containing unresolved symbols. A green
validation command therefore did not prove that the same file could execute.

**The Insight:** Two implementations of one admission rule are two contracts, even when they begin
with identical intentions. They drift because fixes land at different boundaries and because one
path sees details the other has reconstructed differently.

**The Principle:** Put every blocking check in the production preflight and make validators call it.
Validation wrappers may add advisory policy checks, but they must not reimplement runtime
acceptance. Run the same invalid-definition table through both entry points and assert agreement.

**Impact:** `TraceryGeist.preflight_definition()` is now the canonical blocking gate used by both
`from_yaml()` and `geistfabrik validate`; parameterized parity tests cover every structural field,
grammar expansion, and unsafe vault-symbol case.

---

## Empty Is a Result; Failure Is a Different State

**Date:** 2026-09-13
**Context:** Fail-soft execution and statistics made broken geists look successfully quiet

**The Problem:** Summaries counted only emitted suggestions. A geist that legitimately found
nothing, one that failed to load, one that raised during execution, and one disabled by policy could
all appear as zero output. That protected a batch from one plugin failure, but it removed the
evidence needed to understand whether the engine behaved correctly.

**The Insight:** Fail-soft behavior requires stronger observability, not weaker reporting. Empty,
failed, skipped, configured-off, and automatically disabled are domain states with different causes
and different operator actions; collapsing them creates false confidence.

**The Principle:** Model execution outcomes explicitly and report aggregates without leaking note
content. Treat healthy-empty as success, preserve failures even when execution continues, and make
configuration state distinguishable from failure history.

**Impact:** Invocation summaries now classify produced, healthy-empty, failed, and skipped geists;
load failures affect exit status; statistics separate configuration from automatic disablement; and
`invoke --explain` exposes selection and filter counts without printing rejected suggestions.

---

## Release the Bytes You Tested

**Date:** 2026-09-13
**Context:** Completing an offline, reproducible GitHub Release path

**The Problem:** Passing tests in a source checkout did not prove that an installed wheel contained
the bundled model, licenses, entry points, or correct metadata. Rebuilding packages in a later
release job would create different bytes from the artifacts that passed smoke tests, breaking the
evidence chain even if the source revision was unchanged.

**The Insight:** A release artifact is an output under test, not a disposable by-product of source
tests. Confidence attaches to exact bytes plus their provenance: source commit, version, build
inputs, contents, installation behavior, and checksum.

**The Principle:** Build once in the release lane, install and exercise those artifacts outside the
checkout, retain the passing files, and promote them without rebuilding. Fail closed when the tag,
source declarations, filenames, or required bundled resources disagree.

**Impact:** Tag CI smoke-tests wheel and sdist on Python 3.11 and 3.12, performs real offline model
inference, rebuilds a wheel from the sdist, verifies version agreement, generates `SHA256SUMS`, and
publishes the retained Python 3.11 artifacts directly to GitHub Releases.

---

## Fix the Harness Before Blaming the Tests

**Date:** 2026-09-30
**Context:** Test audit (PR #92): ~15 bundled geists never produced output in any test

**The Problem:** The per-geist tests could not make their geists fire, so every
assertion sat inside a loop over `[]`. Three harness defects made the right
fixture impossible to write:
- The embedding stub hashed whole texts, so only identical notes were ever
  similar. The template even warned that "similar but different" was "not
  controllable under the stub".
- `Note.created` came from `st_ctime`, which Linux and macOS reset on every
  write. Nineteen test files "backdated" notes with `os.utime`, which changed
  nothing (and real users saw every edited note as brand new).
- Fixtures used `datetime.now()`.

Authors who could not make a geist fire weakened the assertion until it passed.

**The Insight:** When many tests are weak in the same way, look for the
constraint that forced the weakness before rewriting tests one by one. Each
harness defect also hid a product defect: the `st_ctime` bug was real, and
once geists fired, dozens of real bugs surfaced (journal leaks, duplicate
suggestions, wrong period labels, mis-linked journal entries).

**The Principle:** Make the test harness able to express every production
condition you need to test. Prefer a stub that models the property under test
(shared vocabulary means similarity) over one that only guarantees
determinism. If a fixture cannot trigger the code, fix the harness or the
product; never relax the oracle.

**Impact:** Bag-of-words stub, `VaultBuilder` (real vault, in-memory SQLite,
pinned dates), corrected creation dates, and per-geist files rebuilt around
designed-to-trigger fixtures with exact caps, boundary pairs and two-way
journal exclusion.

---

## A Rewritten Template Does Not Rewrite Its Copies

**Date:** 2026-09-30
**Context:** The June lesson above was learned, but the tests it describes stayed

**The Problem:** In June the testing template was rewritten to forbid the
vacuous patterns, and `assert_valid_suggestions()` was added to require
non-empty output. By September the helper had zero callers. Thirty-nine
per-geist files still carried the old eight-test template (one seed,
20240315, appeared about 400 times across 43 files). Separately, BUG-4 (`st_ctime` is not creation time) sat in an
audit report, unfixed.

**The Insight:** Fixing the generator, the guidance or the report is not
fixing the instances. Copies keep passing, so nothing forces migration.

**The Principle:** When guidance changes, either migrate every existing
instance in the same change or add a gate that fails on the old pattern.
A finding is closed when the code changes, not when it is written down.

**Impact:** The per-geist files were migrated, and a suite-hygiene gate now
rejects the vacuous patterns.

---

## Invariants Belong in the Shared Layer, Not in Every Caller

**Date:** 2026-09-30
**Context:** Journal exclusion was opt-in per geist; 26 geists forgot it

**The Problem:** "Geist journal notes are engine output, not the user's
writing" was enforced by each geist calling `notes_excluding_journal()` or
filtering lookup results itself. Twenty-six geists leaked journal notes into
suggestions, some counted journal backlinks as "connections", and several went
silent once near-identical session notes filled a top-N result before the
geist's own filter ran. Each geist's journal test only checked that no
journal note appeared, which an empty result also satisfies.

**The Insight:** A rule that every caller must remember will be forgotten by
some callers. Filtering after a top-N cut is not equivalent to filtering
before it. An exclusion test that passes on empty output proves nothing.

**The Principle:** Put an invariant that must hold everywhere in the shared
layer, on by default, with explicit access for the rare caller that needs
the exception. Exclusion tests must plant both the excluded item and a
qualifying item, and assert both directions.

**Impact:** `VaultContext` excludes journal notes from every vault-wide
lookup before any cut; per-geist filters were deleted. When the change
landed, disabling the central rule failed 44 journal tests.

---

## Evidence Gates Must Prove Their Own Evidence

**Date:** 2026-09-30
**Context:** Five acceptance criteria reported "verified" by an empty-vault test

**The Problem:** When the acceptance gate started running criteria instead of
trusting the status column, five criteria pointed at scenario tests that did
not exist. To make them runnable, they were widened to the whole
`test_scenarios.py` file. The gate appends the fast marker filter, under which
that file ran one test, an empty-vault sync. "Write session note",
"multi-day sessions", "Tracery integration" and "temporal geists" all passed
on it. The spec's own rule (point at the surviving test, or make the
criterion manual) was skipped.

**The Insight:** A gate that runs a command proves only that the command
passed, not that it exercised the claim. Widening a broken reference until
it goes green turns a visible gap into a false pass.

**The Principle:** An evidence gate must check that its evidence is
specific: the referenced tests exist, are selected under the gate's filters,
and are the tests that exercise the claim. When a reference breaks, repair it
or downgrade the claim; never widen it.

**Impact:** Real end-to-end scenarios now back those criteria, and the gate
rejects criteria whose pytest target is partially deselected or selects
nothing.

---

## Prove a Test Can Fail, Without Mutation Testing

**Date:** 2026-09-30
**Context:** 1,519 green tests, many of which could not fail

**The Problem:** No test was ever shown failing, so tests that could not fail
were indistinguishable from tests that worked. Coverage (a 70% branch gate)
counted lines executed, and a geist that runs then returns `[]` still covers
its lines. The executor swallowed every exception, so a "does not crash" test
could not fail either. Migration-proof tests that compared old and new
algorithms written inline in the test, never importing GeistFabrik, outlived
the migration and kept counting as tests.

**The Insight:** Passing is not evidence of protection. Mutation testing would
measure it, but we rejected it, automated or hand-made: mutants routinely
create runaway tests (infinite loops and hangs that stall the suite), which
costs more than it finds here.

**The Principle:** Use cheap, deterministic proofs instead:
- a regression test must fail on the pre-fix code (a control run) before the
  fix lands;
- every bundled geist must produce output somewhere in the suite (firing gate);
- static hygiene rules reject assertion-free tests, always-true asserts, and
  asserts that only run inside loops over possibly-empty output;
- assert outcomes the production path cannot fake, such as execution-log
  status instead of "returned a list";
- delete scaffolding tests once the change they proved has landed.

**Impact:** Firing and hygiene gates run in `validate.sh` and CI with empty
allowlists: all bundled geists fire (writing the missing firing tests exposed
six more product bugs). The acceptance gate rejects criteria whose pytest
target selects nothing or is partly deselected. The executor-backed crash test
asserts every execution-log entry succeeded; migration-proof files were
replaced by oracle and property tests of the real functions.

---

## A Green Suite Tests the Code Against Itself, Not Against Its Claims

**Date:** 2026-10-02
**Context:** Auditing every bundled geist against what its suggestion text says

**The Problem:** After the test suite was made able to fail, every geist
fired and every test passed, yet a real-model run on a 77-note vault showed
suggestion text that was false about the notes it named. "Central to your
vault" named notes whose only backlink was themselves. "Different domains"
was any pair with similarity 0.15-0.5 (70% of all pairs). The definition
harvester's output was 98.6% bold field labels. "Look forward" required a
future-tense ratio no note in the vault reached. Tests asserted what the code
computed, so they could not notice that the computation did not measure the
claim. The commonest causes were shared, not per-geist: links parsed from
inside code, self-links counted as backlinks, `sample()` returning input
order, and every Tracery geist sharing one seed.

**The Insight:** Test audits check that tests can fail. They do not check that
the product's words are true. A geist's output text is a claim, and words like
"recent", "similar", "central" and "opposite" each need a check in code.

**The Principle:** For every adjective or count in output text, find the line
that verifies it; if there is none, measure it or delete the word. Audit
against real data as well as fixtures, and look for the shared cause before
fixing a symptom in every geist.

**Impact:** Five shared causes were fixed once (parser, link graph, sampling,
Tracery seeding and dedupe, frontmatter word counts). Over fifty geists had
overclaiming text removed or a missing check added, each proven by a control
run. Retire-or-redesign decisions went to the maintainer.

---

## Be Consistent With the Host App, Not Just With Yourself

**Date:** 2026-10-02
**Context:** Journal links that resolved inside GeistFabrik but not in Obsidian

**The Problem:** `Note.link_text` used a note's H1 or frontmatter title.
GeistFabrik's link resolver accepts titles as aliases, so every internal
round trip worked and every test passed. Obsidian resolves `[[...]]` by file
name or alias only, so for any note whose title differed from its file name,
each journal link was dead, and clicking it created an empty note.

**The Insight:** A system whose producer and consumer share one definition is
internally consistent by construction. Tests that check round trips through
our own resolver cannot find a mismatch with the external application that
actually reads the output.

**The Principle:** When output is consumed by another program, test it
against that program's rules (here: link by file name, show the title with
`[[file|Title]]`), not against our own parser.

**Impact:** `link_text` targets the file name and shows the title when they
differ; resolution and privacy boundaries accept the alias form.

---

## Hostile-Input Regexes Need an Anchor

**Date:** 2026-10-02
**Context:** macOS CI timed out on a 50,000-character input

**The Problem:** A new pattern, `\w+(?:/\w+)+` (to drop "I/O" from voice
analysis), retried from every offset of a long run of letters with no slash,
which is quadratic. Locally the hostile-input test finished just inside its
30-second timeout; the slower macOS runner did not.

**The Insight:** A test that passes close to its timeout is not passing.
Unanchored `\w+` followed by a required separator is a classic quadratic
pattern.

**The Principle:** Anchor such patterns (`\b`, a lookbehind, or possessive
quantifiers), and time new regexes on the hostile corpus before pushing.

**Impact:** The pattern is anchored (3 ms on 50k characters), and a
linear-time test guards it.

---

## Future Lessons

_(Add new insights here as they emerge)_

### Template for New Lessons

**Date:** YYYY-MM-DD
**Context:** What prompted this insight?

**The Problem:** What were we trying to solve?

**The Insight:** What did we learn?

**The Principle:** Generalizable rule or heuristic

**Impact:** How does this change our approach?
