# Creation Burst Geists Specification

**Date**: 2025-11-08
**Status**: Proposed - Specification Only

## Overview

Two complementary geists that focus on "burst days" - specific moments when you created multiple notes (5+) in a single day. Together they reveal productive moments and track how those creative bursts evolved.

---

## Geist 1: creation_burst (Basic, Metadata Only)

### Purpose
Surface forgotten productive days by listing notes created together in burst moments.

### Detection Method
```sql
SELECT DATE(created) as creation_date,
       COUNT(*) as note_count,
       GROUP_CONCAT(title, '|') as note_titles
FROM notes
WHERE NOT path LIKE 'geist journal/%'
GROUP BY DATE(created)
HAVING note_count >= 3
ORDER BY note_count DESC
```

### Output Format
**Single suggestion** listing the burst day notes with a provocative question.

### Examples

**Small burst (3-5 notes):**
```
On March 15, 2024, you created 4 notes in one day: [[Systems Thinking]],
[[Emergence]], [[Feedback Loops]], [[Complexity]].
Does today feel generative?
```

**Larger burst (6+ notes):**
```
On October 12, 2024, you created 8 notes: [[Mushrooms]], [[Mycelium]],
[[Decomposition]], [[Forest Networks]], [[Symbiosis]], [[Nutrient Cycling]],
[[Soil]], [[Fungi]]. What was special about that day?
```

### Implementation Notes
- Returns exactly 1 suggestion
- Randomly samples one burst day (deterministic via vault seed)
- Limits displayed titles to 8 (shows "and N more" for larger bursts)
- Zero dependencies, works immediately on any vault
- Execution time: <10ms

---

## Geist 2: burst_evolution (Temporal, Uses Embeddings)

### Purpose
Show numerically how much notes from burst days have evolved since creation.

### Detection Method

1. Find burst days (same SQL as creation_burst: 3+ notes)
2. For selected burst day, get each note's embeddings:
   - Creation embedding: from session closest to burst date
   - Current embedding: from current session
3. Calculate drift for each note: `1 - cosine_similarity(creation, current)`
4. Present drift scores in descending order

### Output Format
**Single suggestion** showing numerical drift for each note. **No question** - purely declarative observation.

### Examples

**Mixed drift (most interesting):**
```
On March 15, 2024, you created 7 notes. Since then:
- [[Adaptation]]: 0.51 drift (major evolution)
- [[Systems Thinking]]: 0.42 drift (major evolution)
- [[Networks]]: 0.38 drift (significant shift)
- [[Emergence]]: 0.31 drift (significant shift)
- [[Complexity]]: 0.29 drift (moderate evolution)
- [[Resilience]]: 0.12 drift (mostly stable)
- [[Feedback Loops]]: 0.08 drift (mostly stable)

[[Feedback Loops]] and [[Resilience]] are anchors—the stable core
around which other ideas orbit and evolve.
```

**High drift across all notes:**
```
On January 12, 2024, you created 5 notes about consciousness.
Ten months later, they've all evolved dramatically (avg drift: 0.58).

That burst was asking questions, not stating answers. Early explorations
that your understanding has completely transformed.
```

**Low drift across all notes:**
```
On June 3, 2024, you created 6 notes about complexity science.
Four months later, all remain stable (avg drift: 0.09).

That burst created foundational concepts that haven't needed revision.
```

**Recent burst (limited history):**
```
On October 25, 2024, you created 6 notes about mycelium networks.
Only 2 weeks have passed, but already some are evolving:
- [[Mycelium]]: 0.18 drift (moderate evolution)
- [[Forest Networks]]: 0.22 drift (moderate evolution)
- [[Symbiosis]]: 0.14 drift (moderate evolution)

Early signs of which ideas are settling vs. still moving.
```

### Drift Interpretation

```
Drift < 0.10  →  "mostly stable"
Drift 0.10-0.25  →  "moderate evolution"
Drift 0.25-0.40  →  "significant shift"
Drift > 0.40  →  "major evolution"
```

### Declarative Statements (Not Questions)

The geist makes **observations** based on drift patterns:

**When avg drift > 0.45:**
> "That burst was asking questions, not stating answers. Early explorations that your understanding has completely transformed."

**When avg drift < 0.15:**
> "That burst created foundational concepts that haven't needed revision."

**When mixed (some stable, some evolving):**
> "[[StableNote1]] and [[StableNote2]] are anchors—the stable core around which other ideas orbit and evolve."

**When recent (< 1 month ago):**
> "Early signs of which ideas are settling vs. still moving."

### Implementation Notes
- Returns exactly 1 suggestion
- Requires session_embeddings history
- Fallback: if <50% of burst notes have embeddings → skip to next burst day or return empty
- Uses session closest to (but not before) creation date as baseline
- Shows up to 7 notes with drift scores
- Execution time: <500ms

---

## How These Differ from Existing Geists

### vs. temporal_clustering
**Existing:** Groups ALL notes by quarters, finds semantic clusters per time period
```
"Your Q2-2024 notes form a distinct cluster separate from Q4-2024. Different seasons?"
```
- Focuses on: Time periods (quarters)
- Compares: Different eras
- Pattern: Broad temporal grouping

**New (creation_burst + burst_evolution):** Focuses on SPECIFIC DAYS when multiple notes were created
```
"On March 15, you created 7 notes. [[Note A]] stable, [[Note B]] evolved."
```
- Focuses on: Creation events (burst days with 3+ notes)
- Compares: Notes from same moment
- Pattern: Cohort from single productive day

**Key difference:** temporal_clustering asks "do notes from different quarters cluster differently?" while burst_evolution asks "what happened to notes born together on the same day?"

---

### vs. concept_drift
**Existing:** Tracks INDIVIDUAL notes over time, shows what they're drifting toward
```
"[[Systems Thinking]] has migrated since 2024-03. Now drifting toward [[Emergence]]."
```
- Focuses on: Single notes
- Metric: Directional drift (toward what?)
- Output: One note + its drift target

**New (burst_evolution):** Shows how GROUPS OF NOTES from specific days evolved
```
"On March 15, you created 7 notes. 2 stable (0.08, 0.12), 5 evolved (0.29-0.51)."
```
- Focuses on: Note cohorts (created same day)
- Metric: Magnitude of drift (how much?)
- Output: Multiple notes + their drift scores

**Key difference:** concept_drift tracks individual trajectories, burst_evolution tracks cohort evolution.

---

### vs. recent_focus
**Existing:** Compares recently modified notes to old similar notes
```
"Your recent work on [[Note A]] connects to older [[Note B]]. Thinking evolved?"
```
- Focuses on: Modification recency
- Compares: Recent vs old
- Temporal anchor: Modification dates

**New (creation_burst):** Surfaces burst days regardless of recency
```
"On March 15, you created 7 notes. What sparked that productivity?"
```
- Focuses on: Creation moments
- Compares: Notes from same burst
- Temporal anchor: Creation dates

**Key difference:** recent_focus is modification-based, creation_burst is creation-based.

---

### vs. on_this_day
**Existing:** Anniversary pattern - notes from same calendar date in previous years
```
"One year ago today, you wrote [[Note]]. What's changed since then?"
```
- Pattern: Calendar anniversary (March 15, 2023 → March 15, 2024)
- Temporal: Annual cycle
- Focus: Single note per year

**New (creation_burst):** Multiple notes from same day (any date, not anniversary)
```
"On March 15, 2024, you created 7 notes in one day. What was special?"
```
- Pattern: Burst activity (3+ notes, single day)
- Temporal: Any productive day
- Focus: Multiple notes from one moment

**Key difference:** on_this_day is calendar-based anniversary, creation_burst is productivity-based detection.

---

## The Unique Insight: Cohort Analysis

These two geists together provide **cohort analysis** - tracking groups of notes born at the same moment:

1. **creation_burst** identifies the cohort: "These 7 notes were created together"
2. **burst_evolution** tracks the cohort: "Some stayed stable, some evolved dramatically"

**Why this matters:**

- Notes created together often share context (same reading, same event, same insight)
- Tracking cohorts reveals which ideas from that moment crystallized vs. evolved
- Different from tracking individual notes (concept_drift) or time periods (temporal_clustering)

**Analogy:**
- **temporal_clustering** = "Students who started school in Fall 2024"
- **concept_drift** = "Where did Alice go after graduation?"
- **burst_evolution** = "What happened to the 7 students who all enrolled on the same day?"

**The cohort matters** because notes born together may have shared origins but divergent fates.

---

## Implementation Sketch

### creation_burst.py (Basic)

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find burst days and list the notes created."""

    cursor = vault.db.execute("""
        SELECT DATE(created), COUNT(*), GROUP_CONCAT(title, '|')
        FROM notes
        WHERE NOT path LIKE 'geist journal/%'
        GROUP BY DATE(created)
        HAVING COUNT(*) >= 5
    """)

    burst_days = cursor.fetchall()
    if not burst_days:
        return []

    date, count, titles_str = vault.sample(burst_days, k=1)[0]
    titles = titles_str.split('|')

    # Format title list
    display = ", ".join([f"[[{t}]]" for t in titles[:8]])
    if len(titles) > 8:
        display += f", and {len(titles) - 8} more"

    # Generate question based on count
    if count >= 6:
        question = "What was special about that day?"
    else:  # 3-5 notes
        question = "Does today feel generative?"

    text = f"On {date}, you created {count} notes: {display}. {question}"

    return [Suggestion(text=text, notes=titles, geist_id="creation_burst")]
```

### burst_evolution.py (Temporal)

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Show how burst-day notes have evolved since creation."""

    # Find burst days
    burst_days = _get_burst_days(vault)
    if not burst_days:
        return []

    # Try burst days until we find one with enough embedding history
    for date, paths in vault.sample(burst_days, k=len(burst_days)):
        # Find earliest session with these notes
        creation_session = _find_earliest_session_with_notes(vault, paths, date)
        if not creation_session:
            continue

        # Calculate drift for each note
        drifts = []
        for path in paths:
            creation_emb = _get_embedding_from_session(vault, path, creation_session)
            current_emb = vault.embedding(vault.get_note(path))

            if creation_emb is not None and current_emb is not None:
                drift = 1 - cosine_similarity(creation_emb, current_emb)
                drifts.append((path, drift))

        # Need at least 3 notes with drift data
        if len(drifts) >= 3:
            return [_generate_drift_observation(vault, date, drifts)]

    return []


def _generate_drift_observation(vault, date, drifts) -> Suggestion:
    """Generate declarative observation based on drift patterns."""

    # Sort by drift (highest first)
    drifts_sorted = sorted(drifts, key=lambda x: x[1], reverse=True)
    avg_drift = sum(d for _, d in drifts) / len(drifts)

    # Build drift listing
    drift_lines = []
    for path, drift in drifts_sorted[:7]:
        note = vault.get_note(path)
        label = _drift_label(drift)
        drift_lines.append(f"- [[{note.title}]]: {drift:.2f} drift ({label})")

    drift_text = "\n".join(drift_lines)

    # Generate declarative interpretation
    if avg_drift > 0.45:
        observation = (
            "That burst was asking questions, not stating answers. "
            "Early explorations that your understanding has completely transformed."
        )
    elif avg_drift < 0.15:
        observation = (
            "That burst created foundational concepts that haven't needed revision."
        )
    else:
        # Find stable anchors
        stable = [p for p, d in drifts if d < 0.15]
        if stable:
            stable_titles = ", ".join([f"[[{vault.get_note(p).title}]]" for p in stable[:2]])
            observation = (
                f"{stable_titles} are anchors—the stable core "
                f"around which other ideas orbit and evolve."
            )
        else:
            observation = "Early signs of which ideas are settling vs. still moving."

    # Calculate time elapsed
    days_ago = (datetime.now() - datetime.fromisoformat(date)).days
    if days_ago < 30:
        time_phrase = f"Only {days_ago} days have passed"
    elif days_ago < 365:
        months = days_ago // 30
        time_phrase = f"{months} months later"
    else:
        years = days_ago // 365
        time_phrase = f"{years} year{'s' if years > 1 else ''} later"

    text = f"On {date}, you created {len(drifts)} notes. {time_phrase}:\n{drift_text}\n\n{observation}"

    return Suggestion(
        text=text,
        notes=[vault.get_note(p).title for p, _ in drifts],
        geist_id="burst_evolution"
    )
```

---

## Success Criteria

### creation_burst succeeds if:
- Surfaces burst days user had forgotten
- Provokes "oh yeah, what WAS happening then?" reflection
- Runs in <10ms
- Works from day 1 on any vault

### burst_evolution succeeds if:
- Drift scores feel meaningful (match user's intuition about evolution)
- Distinguishes stable anchors from evolving explorations
- Demonstrates value of temporal embeddings
- Declarative observations feel insightful without asking questions
- Runs in <500ms

---

## Why Two Geists Instead of One?

**Design principle:** GeistFabrik geists should each do one thing clearly.

**creation_burst:**
- Simple, immediate value
- Works without temporal data
- Asks questions

**burst_evolution:**
- Complex, requires history
- Shows temporal patterns
- Makes observations

**Together:** Complementary perspectives on the same phenomenon (burst days)

**Separately:** Each stands alone as useful
- creation_burst: "What was special about that day?"
- burst_evolution: "Here's what happened to those notes"

**Compare to rejected approach:**
One geist with two modes would be:
- More complex to implement
- Harder to test
- Less clear about what it does
- Violates single responsibility principle

---

## Open Questions

1. **Threshold tuning:** Is 3 notes the right threshold for "burst"?
   - Current: 3+ notes qualifies as burst day
   - Consider: vault-size dependent threshold in future?

2. **Creation date baseline:** For burst_evolution, should we use:
   - Option A: First session with notes (precise)
   - Option B: Closest session to creation date (intuitive)
   - **Recommendation: B** for clarity

3. **Fallback behavior:** What if burst_evolution finds no burst days with embeddings?
   - Return empty list (let creation_burst handle basic case)
   - Don't try to merge concerns

---

## Next Steps

1. Review this spec for clarity
2. Decide if burst detection threshold should be configurable
3. Confirm declarative observation style (no questions) works for burst_evolution
4. Plan implementation order (creation_burst first, then burst_evolution)
