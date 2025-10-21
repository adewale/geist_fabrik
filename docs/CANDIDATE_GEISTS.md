# Candidate Geists

This document contains geist ideas that follow the "ask better questions" principle. These are candidates for implementation—ideas that can be evaluated, refined, and potentially added to the GeistFabrik geist catalogue.

All of these follow the Tracery approach: simple templates that ask provocative questions rather than trying to compute answers.

---

## 1. Analogy

**Purpose:** Encourage cross-domain thinking and metaphorical connections

**Prompts:**
- "[[note]] - what is this like in a completely different domain?"
- "If [[note]] were a pattern, where else does it appear?"
- "[[note]] reminds you of... what?"
- "What's a good metaphor for [[note]]?"
- "[[note]] - if this were a story, what story would it be?"
- "What does [[note]] have in common with something totally unrelated?"
- "[[note]] is similar to _____ in an unexpected way."
- "If you had to explain [[note]] to a child, what would you compare it to?"
- "[[note]] - what's the natural world equivalent?"
- "What historical event mirrors [[note]]?"

---

## 2. Scale

**Purpose:** Shift perspective through size, scope, and magnitude

**Prompts:**
- "[[note]] - what if this were 10x bigger?"
- "What if [[note]] were 100x smaller?"
- "[[note]] at global scale looks like...?"
- "What's the atomic-level version of [[note]]?"
- "If [[note]] expanded to affect everyone, what happens?"
- "[[note]] - zoom out. What's the bigger pattern?"
- "[[note]] - zoom in. What are the tiny details?"
- "What if [[note]] lasted only one second?"
- "What if [[note]] continued for a thousand years?"
- "[[note]] - what changes if you shift the scope?"

---

## 3. Time Travel

**Purpose:** Explore temporal dimensions and evolution

**Prompts:**
- "[[note]] - what will this look like in 10 years?"
- "How would someone in 1950 understand [[note]]?"
- "[[note]] in 2050 - better or worse?"
- "What's the prehistory of [[note]]?"
- "[[note]] - what did this look like before it had a name?"
- "Fast forward: where does [[note]] lead eventually?"
- "[[note]] - what will people in the future find strange about this?"
- "Rewind 100 years: does [[note]] still make sense?"
- "What's the evolutionary next step for [[note]]?"
- "[[note]] - when will this become obsolete?"

---

## 4. Audience

**Purpose:** Consider different stakeholders and perspectives

**Prompts:**
- "[[note]] - who else should care about this?"
- "What would a teenager think of [[note]]?"
- "[[note]] - which industry ignores this but shouldn't?"
- "Who is threatened by [[note]]?"
- "[[note]] - what would your grandmother say?"
- "Which community needs to hear about [[note]]?"
- "[[note]] - who profits if this spreads?"
- "What would an anthropologist notice about [[note]]?"
- "[[note]] - which expert would disagree?"
- "Who is this NOT for, and why does that matter?"

---

## 5. Bridge

**Purpose:** Find connections between two random notes

**Prompts:**
- "[[note1]] and [[note2]] - what connects them?"
- "How does [[note1]] lead to [[note2]]?"
- "[[note1]] meets [[note2]] - what happens?"
- "What's the missing link between [[note1]] and [[note2]]?"
- "[[note1]] contradicts [[note2]] - or does it?"
- "What would merge [[note1]] with [[note2]]?"
- "[[note1]] is to [[note2]] as _____ is to _____?"
- "If [[note1]] is the question, is [[note2]] the answer?"
- "[[note1]] and [[note2]] - what do they both ignore?"
- "What pattern contains both [[note1]] and [[note2]]?"

**Note:** This geist uses two random notes instead of one.

---

## 6. Concrete

**Purpose:** Move from abstract to specific, from theory to practice

**Prompts:**
- "[[note]] - what's a specific, real example?"
- "Can you see [[note]] or touch it? What would that look like?"
- "[[note]] - describe this to someone who's never heard of it."
- "What's a concrete case study of [[note]]?"
- "[[note]] - show, don't tell. What would you show?"
- "What does [[note]] look like in practice, not theory?"
- "[[note]] - what's the smallest possible demonstration?"
- "How would you prove [[note]] exists to a skeptic?"
- "[[note]] - what's a story that illustrates this?"
- "What sensory details capture [[note]]?"

---

## 7. Abstract

**Purpose:** Extract patterns, principles, and generalizations

**Prompts:**
- "[[note]] - what's the underlying pattern?"
- "If [[note]] is an instance, what's the class?"
- "[[note]] - what principle does this exemplify?"
- "What category does [[note]] belong to?"
- "[[note]] - strip away the details. What remains?"
- "What's the general rule behind [[note]]?"
- "[[note]] - what would the textbook chapter be called?"
- "If [[note]] is the data point, what's the curve?"
- "[[note]] - what's this a symptom of?"
- "What framework explains [[note]]?"

---

## 8. Missing

**Purpose:** Identify gaps, silences, and unwritten thoughts

**Prompts:**
- "[[note]] - what's missing from this picture?"
- "What haven't you written about [[note]] yet?"
- "[[note]] - what question aren't you asking?"
- "What would complete [[note]]?"
- "[[note]] - what's the gap this creates?"
- "What's the unwritten sequel to [[note]]?"
- "[[note]] - what are you avoiding saying?"
- "What needs to exist before [[note]] makes sense?"
- "[[note]] - what's the piece you don't have yet?"
- "What silence surrounds [[note]]?"

---

## 9. Merge

**Purpose:** Combinatorial creativity through synthesis

**Prompts:**
- "[[note1]] + [[note2]] = ?"
- "What if you combined [[note1]] and [[note2]]?"
- "[[note1]] borrows an idea from [[note2]] - which one?"
- "Mash up [[note1]] with [[note2]]. What emerges?"
- "[[note1]] is the peanut butter, [[note2]] is the chocolate. What's the result?"
- "What happens at the intersection of [[note1]] and [[note2]]?"
- "[[note1]] × [[note2]] - what's this hybrid?"
- "Blend [[note1]] and [[note2]]. What new thing appears?"
- "[[note1]] and [[note2]] - what would their child look like?"
- "What synthesis emerges from [[note1]] and [[note2]]?"

**Note:** This geist uses two random notes instead of one.

---

## 10. Constraint

**Purpose:** Force clarity and creativity through limitations

**Prompts:**
- "[[note]] - what if you had to explain this in one sentence?"
- "[[note]] but you can only use 10 words."
- "[[note]] - what if you couldn't use abstractions?"
- "Explain [[note]] without using jargon."
- "[[note]] - draw it, don't write it. What would you draw?"
- "[[note]] in exactly three bullet points."
- "[[note]] - what if you could only tell it as a story?"
- "[[note]] for someone who has 30 seconds."
- "[[note]] - express this through questions only."
- "What's the haiku version of [[note]]?"

---

## Implementation Notes

All of these geists can be implemented as simple Tracery YAML files following this pattern:

```yaml
type: geist-tracery
id: geist_name
count: 1

tracery:
  origin: "#suggestion#"
  suggestion:
    - "Prompt variation 1"
    - "Prompt variation 2"
    # ... more variations
  note:
    - "$vault.random_note_title()"
```

For geists that use two notes (Bridge, Merge), use:

```yaml
  note1:
    - "$vault.random_note_title()"
  note2:
    - "$vault.random_note_title()"
```

## Evaluation Criteria

Before promoting a candidate geist to the main catalogue, consider:

1. **Universal applicability** - Does it work for any note title?
2. **Divergence quality** - Does it open up thinking rather than close it?
3. **Non-redundancy** - Is this distinct from existing geists?
4. **Provocation value** - Does it ask questions you wouldn't ask yourself?
5. **Clarity** - Are the prompts clear and actionable?

## Adding New Candidates

When you have an idea for a new geist:

1. Add it to this document with the same format
2. Write 5-10 prompt variations
3. Note any special requirements (e.g., multiple notes, vault functions)
4. Test it mentally against various note titles
5. Consider: does this ask better questions, or try to answer them?
