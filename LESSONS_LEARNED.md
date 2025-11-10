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
- **Performance matters**: Caching, optimization, batch processing
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

- **Oracle behavior**: "I will tell you what the opposite is"
- **Muse behavior**: "Have you considered the opposite?"

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

## Future Lessons

_(Add new insights here as they emerge)_

### Template for New Lessons

**Date:** YYYY-MM-DD
**Context:** What prompted this insight?

**The Problem:** What were we trying to solve?

**The Insight:** What did we learn?

**The Principle:** Generalizable rule or heuristic

**Impact:** How does this change our approach?
