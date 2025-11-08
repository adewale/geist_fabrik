# Quality Review: Creation Burst Geists

**Reviewer**: WRITING_GOOD_GEISTS.md guidelines
**Date**: 2025-11-08

---

## creation_burst - Questions Analysis

### Current Questions

```python
if count >= 10:
    question = "What conditions created that flow state?"
elif count >= 7:
    question = "What was special about that day?"
else:  # 5-6 notes
    question = "How might we make today equally generative?"
```

---

### ✅ Passes: "What conditions created that flow state?" (10+ notes)

**Why it works:**
- Open-ended question with multiple interpretations
- Speculative, not directive
- Vault-specific (references actual date and notes)
- Asks "what" not "how to replicate"

**Alignment with guidelines:**
- ✅ Uses question framing
- ✅ No directive language
- ✅ Multiple possible answers
- ✅ Would NOT naturally ask this yourself (focuses on "flow state" not just "productivity")

---

### ✅ Passes: "What was special about that day?" (7-9 notes)

**Why it works:**
- Simple, open question
- Invites reflection without prescribing
- Vault-specific (actual date)
- Multiple interpretations possible

**Alignment with guidelines:**
- ✅ Uses question framing
- ✅ No directive language
- ✅ Speculative

**Potential weakness:**
- ⚠️ Might be too natural/obvious - "Would you ask this yourself?" → Maybe yes
- Could be more provocative

**Alternative suggestion:**
```python
"Seven notes in one day. Convergent thinking or scattered exploration?"
```

---

### ❌ FAILS: "How might we make today equally generative?" (5-6 notes)

**Why it fails:**

1. **Too prescriptive/action-oriented**
   - Guideline: ❌ Avoid "you should", "consider", commands
   - This question: Asks HOW to replicate (action-oriented)
   - Feels like: "How can we be productive today?" (task-oriented)

2. **Sounds like productivity advice**
   - Anti-Pattern #1: The Todo List
   - Guideline: "Don't turn geists into task managers"
   - This feels like: "Here's how to optimize your workflow"

3. **Forward-looking command, not retrospective question**
   - GeistFabrik philosophy: "Work retrospectively like Hegel's owl"
   - This question: "Make today equally generative" (future imperative)
   - Should be: Looking back at the pattern, not optimizing forward

4. **Uses "we" which feels like coaching**
   - Guideline: Tone should be curious, not authoritative
   - "How might we" = productivity consultant language
   - Not provocative, it's instructive

**Recommended replacement:**

Option 1 (Provocative):
```python
"Six notes in one day. What conditions aligned that you didn't orchestrate?"
```

Option 2 (Contrast):
```python
"Six notes in one day. Burst or baseline—which reflects your real pace?"
```

Option 3 (Multiple interpretations):
```python
"Six notes emerged in one day. Intentional sprint or natural rhythm surfacing?"
```

All three:
- ✅ Look backward at pattern (retrospective)
- ✅ Ask what the pattern MEANS, not how to repeat it
- ✅ Invite multiple interpretations
- ✅ Use speculative language
- ❌ Don't prescribe action

---

## burst_evolution - Declarative Statements Problem

### Current Output Format

```
On March 15, 2024, you created 7 notes. Since then:
- [[Adaptation]]: 0.51 drift (major evolution)
- [[Systems Thinking]]: 0.42 drift (major evolution)
...

[[Feedback Loops]] and [[Resilience]] are anchors—the stable core
around which other ideas orbit and evolve.
```

### ❌ FAILS: Pure Declarative Statements

**From WRITING_GOOD_GEISTS.md Checklist:**
- [ ] Uses "what if" or question framing (not directives)
- [ ] No value judgments
- [ ] No declarative statements: avoid "."

**The spec says:** "No question - purely declarative observation"

**The guidelines say:**
- "Ask questions, not give answers"
- Language Reference: ❌ Avoid "." (declarative statements)
- Checklist: "Uses 'what if' or question framing"

**Current examples all use periods (declarative):**
```
"That burst was asking questions, not stating answers."
"[[Note]] are anchors—the stable core around which other ideas orbit."
"That burst created foundational concepts that haven't needed revision."
```

**These are statements, not questions.**

---

### Recommended Fix: Add Questions

**Option 1: Observation + Question pattern**

Gold standard from guidelines:
```python
"[[{note_a}]] and [[{note_b}]] seem to contradict each other—what gives?"
```

Applied to burst_evolution:
```
On March 15, 2024, you created 7 notes. Since then:
- [[Adaptation]]: 0.51 drift (major evolution)
- [[Systems Thinking]]: 0.42 drift (major evolution)
- [[Networks]]: 0.38 drift (significant shift)
- [[Emergence]]: 0.31 drift (significant shift)
- [[Complexity]]: 0.29 drift (moderate evolution)
- [[Resilience]]: 0.12 drift (mostly stable)
- [[Feedback Loops]]: 0.08 drift (mostly stable)

[[Feedback Loops]] and [[Resilience]] barely moved while others evolved dramatically.
What if these are your anchors—stable ground while other ideas orbit and shift?
```

**Option 2: Either/Or Questions**

From guidelines - Pattern 5:
```python
"[[{note}]] is brief but referenced often. Hinge concept or placeholder?"
```

Applied:
```
[[Adaptation]] drifted 0.51 while [[Feedback Loops]] stayed at 0.08.
Evolution or divergence—are they growing apart or finding their distance?
```

**Option 3: What If Questions**

Most reliable pattern from guidelines:
```
On March 15, 2024, you created 7 notes. Six months later, some stayed stable
while others evolved dramatically. What if [[Feedback Loops]] (0.08 drift) and
[[Resilience]] (0.12 drift) are foundations—unchanging because they're load-bearing?
```

---

### Specific Issues with Current Declarative Statements

**Statement:** "That burst was asking questions, not stating answers."
- **Issue:** Tells user what their notes were doing (authoritative)
- **Better:** "What if that burst was asking questions you're still exploring?"

**Statement:** "That burst created foundational concepts that haven't needed revision."
- **Issue:** Declares what happened (certain, not speculative)
- **Better:** "These notes haven't moved in 6 months. Foundations or fossils?"

**Statement:** "[[Note]] are anchors—the stable core around which other ideas orbit."
- **Issue:** Declares the role of notes (prescriptive interpretation)
- **Better:** "What if [[Note]] is an anchor—unchanged because everything else orbits it?"

---

## Summary of Issues

### creation_burst
- ✅ Question 1 (10+ notes): PASSES
- ⚠️ Question 2 (7-9 notes): PASSES but could be more provocative
- ❌ Question 3 (5-6 notes): FAILS - too action-oriented/prescriptive

**Fix:** Replace "How might we make today equally generative?" with retrospective provocation

### burst_evolution
- ❌ All outputs: FAIL - Uses declarative statements instead of questions
- ❌ Violates core principle: "Ask questions, not give answers"
- ❌ Violates checklist: "Uses 'what if' or question framing"

**Fix:** Add questions to each declarative observation

---

## Recommended Changes

### For creation_burst (5-6 notes):

Replace:
```python
question = "How might we make today equally generative?"
```

With:
```python
question = "What conditions aligned that you didn't orchestrate?"
```

Or:
```python
question = "Burst or baseline—which reflects your real pace?"
```

### For burst_evolution:

Add question endings to all interpretations:

**Current:**
```python
observation = (
    "That burst was asking questions, not stating answers. "
    "Early explorations that your understanding has completely transformed."
)
```

**Fixed:**
```python
observation = (
    "These notes evolved dramatically (avg drift: 0.58). "
    "What if that burst was asking questions you're still exploring—"
    "early sketches your understanding has completely transformed?"
)
```

**Current:**
```python
observation = (
    f"{stable_titles} are anchors—the stable core "
    f"around which other ideas orbit and evolve."
)
```

**Fixed:**
```python
observation = (
    f"What if {stable_titles} are anchors—unchanged not because they're settled, "
    f"but because everything else orbits them?"
)
```

---

## Guideline Violations Summary

| Issue | Geist | Severity | Guideline |
|-------|-------|----------|-----------|
| Action-oriented question | creation_burst | HIGH | Rule 1: Questions not commands |
| Declarative statements | burst_evolution | HIGH | Core principle: Ask questions |
| "How might we" phrasing | creation_burst | MEDIUM | Tone: playful/curious not coaching |
| Tells user what notes do | burst_evolution | MEDIUM | Rule 2: Speculative not certain |
| Generic "special day" | creation_burst | LOW | Could be more provocative |

---

## Passes Quality Checklist?

**creation_burst:**
- [✅] Uses question framing
- [❌] Employs speculative language (Question 3 is action-oriented)
- [✅] References specific vault notes
- [✅] Multiple interpretations (mostly)
- [⚠️] Provokes vs prescribes (Question 3 feels prescriptive)
- [⚠️] Surprises user (Questions 2-3 feel natural)
- [✅] No "should", "must"
- [✅] No value judgments

**Score: 6/8** - Needs revision on Question 3

**burst_evolution:**
- [❌] Uses question framing (uses declarative statements)
- [⚠️] Employs speculative language (observations are certain)
- [✅] References specific vault notes
- [✅] Multiple interpretations possible
- [❌] Provokes vs prescribes (tells user what happened)
- [✅] Surprises user
- [✅] No directive verbs
- [✅] No value judgments

**Score: 5/8** - Needs questions added

---

## Recommendations

1. **Fix creation_burst Question 3** (HIGH PRIORITY)
   - Remove action-oriented "how might we make" phrasing
   - Replace with retrospective provocation
   - Make less obvious/natural

2. **Fix burst_evolution statements** (HIGH PRIORITY)
   - Add "what if" questions to every interpretation
   - Convert declarative statements to speculative questions
   - Follow "observation + question" pattern from guidelines

3. **Consider making creation_burst Question 2 more provocative** (LOW PRIORITY)
   - Current is fine but could surprise more
   - Not urgent

---

## Next Steps

- Review and approve recommended changes
- Update spec with new questions
- Ensure both geists follow "muses not oracles" philosophy
- Re-run this review after changes
