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

## Future Lessons

_(Add new insights here as they emerge)_

### Template for New Lessons

**Date:** YYYY-MM-DD
**Context:** What prompted this insight?

**The Problem:** What were we trying to solve?

**The Insight:** What did we learn?

**The Principle:** Generalizable rule or heuristic

**Impact:** How does this change our approach?
