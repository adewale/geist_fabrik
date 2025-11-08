# Creation Burst Geist Specification

**Date**: 2025-11-08
**Status**: Proposed - Specification Only

## Overview

A geist that identifies days when you created multiple notes (5+) and asks what was special about those moments of creative productivity. The basic version lists the notes; the temporal version shows how much those notes have evolved since that burst day.

---

## Core Idea

**Basic provocation:**
> "On March 15, 2024, you created 7 notes: [[Systems Thinking]], [[Emergence]], [[Feedback Loops]], [[Complexity]], [[Adaptation]], [[Resilience]], [[Networks]]. What was special about that day?"

**Temporal evolution provocation:**
> "On March 15, 2024, you created 7 notes. Since then:
> - [[Systems Thinking]] has drifted 0.42 (major evolution)
> - [[Emergence]] has drifted 0.31 (significant shift)
> - [[Feedback Loops]] has drifted 0.08 (mostly stable)
> - [[Complexity]] has drifted 0.29 (moderate evolution)
> - [[Adaptation]] has drifted 0.51 (major evolution)
> - [[Resilience]] has drifted 0.12 (mostly stable)
> - [[Networks]] has drifted 0.38 (significant shift)
>
> What if some ideas from that burst crystallized while others are still searching?"

---

## Detection Method

### Step 1: Find Burst Days

```sql
SELECT DATE(created) as creation_date,
       COUNT(*) as note_count,
       GROUP_CONCAT(title, '|') as note_titles,
       GROUP_CONCAT(path, '|') as note_paths
FROM notes
WHERE NOT path LIKE 'geist journal/%'
GROUP BY DATE(created)
HAVING note_count >= 5
ORDER BY note_count DESC
```

### Step 2: For Selected Burst Day

**Basic version:**
- List the notes created that day
- Ask: "What was special about that day?"

**Temporal version:**
- For each note created on burst day:
  - Get embedding from session closest to creation date (or first appearance in session_embeddings)
  - Get embedding from current session
  - Calculate drift: `1 - cosine_similarity(creation_embedding, current_embedding)`
- Show drift scores for each note
- Ask: "What if some ideas crystallized while others are still searching?"

---

## Drift Interpretation

```
Drift < 0.10  →  "mostly stable" (understanding hasn't changed much)
Drift 0.10-0.25  →  "moderate evolution" (some shifts in understanding)
Drift 0.25-0.40  →  "significant shift" (notable evolution)
Drift > 0.40  →  "major evolution" (fundamentally different understanding)
```

### What Drift Reveals

**Low drift across all notes:**
```
"All 7 notes from March 15 have remained stable (avg drift: 0.09).
That burst created foundational concepts that haven't needed revision?"
```

**High drift across all notes:**
```
"All 7 notes from March 15 have evolved significantly (avg drift: 0.43).
That burst was exploratory—initial sketches that developed into something else?"
```

**Mixed drift (most interesting):**
```
"Some notes from March 15 crystallized ([[Feedback Loops]]: 0.08),
while others keep evolving ([[Adaptation]]: 0.51).
What if that day planted seeds that grew at different rates?"
```

---

## Example Outputs

### Scenario 1: Recent Burst (2 weeks ago)

**Basic:**
```
On October 25, 2024, you created 6 notes: [[Mushrooms]], [[Mycelium]],
[[Decomposition]], [[Forest Networks]], [[Symbiosis]], [[Nutrient Cycling]].
What was special about that day?
```

**Temporal (limited history):**
```
On October 25, 2024, you created 6 notes. Only 2 weeks have passed,
but already some are evolving:
- [[Mycelium]] has drifted 0.18 (moderate evolution)
- [[Forest Networks]] has drifted 0.22 (moderate evolution)

Early signs of which ideas are settling vs. still moving?
```

### Scenario 2: Old Burst (6 months ago)

**Basic:**
```
On March 15, 2024, you created 7 notes about systems thinking.
What was special about that day?
```

**Temporal (full trajectory):**
```
On March 15, 2024, you created 7 notes. Six months later:
- [[Systems Thinking]]: 0.42 drift (major evolution)
- [[Emergence]]: 0.31 drift (significant shift)
- [[Feedback Loops]]: 0.08 drift (mostly stable)
- [[Complexity]]: 0.29 drift (significant shift)
- [[Adaptation]]: 0.51 drift (major evolution)
- [[Resilience]]: 0.12 drift (mostly stable)
- [[Networks]]: 0.38 drift (significant shift)

Average drift: 0.30 (moderate to significant evolution)

What if [[Feedback Loops]] and [[Resilience]] are your anchors—
the stable core around which other ideas orbit and evolve?
```

### Scenario 3: Burst with Exceptional Drift

**Temporal:**
```
On January 12, 2024, you created 5 notes about consciousness.
Ten months later, they've all evolved dramatically (avg drift: 0.58).

What if that burst was asking questions, not stating answers?
Early explorations that your understanding has completely transformed?
```

---

## Implementation Sketch

### Basic Version (Metadata Only)

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find burst days and list the notes created."""

    # Find days with 5+ notes
    cursor = vault.db.execute("""
        SELECT DATE(created), GROUP_CONCAT(title, '|')
        FROM notes
        WHERE NOT path LIKE 'geist journal/%'
        GROUP BY DATE(created)
        HAVING COUNT(*) >= 5
    """)

    burst_days = cursor.fetchall()
    if not burst_days:
        return []

    # Pick random burst day
    date, titles_str = vault.sample(burst_days, k=1)[0]
    titles = titles_str.split('|')

    # Generate provocation
    title_list = ", ".join([f"[[{t}]]" for t in titles[:8]])
    if len(titles) > 8:
        title_list += f", and {len(titles) - 8} more"

    text = f"On {date}, you created {len(titles)} notes: {title_list}. What was special about that day?"

    return [Suggestion(text=text, notes=titles, geist_id="creation_burst")]
```

### Temporal Version (Using Session Embeddings)

```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    """Find burst days and show how notes have evolved since creation."""

    # Find burst days
    burst_days = _get_burst_days(vault)
    if not burst_days:
        return []

    # Pick burst day that has temporal history
    for date, paths in vault.sample(burst_days, k=len(burst_days)):
        # Get creation embeddings (earliest session with these notes)
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

        if len(drifts) >= 3:  # Need at least 3 notes with drift data
            return [_generate_drift_provocation(date, drifts)]

    # Fallback to basic version if no temporal data
    return _basic_version(vault)


def _generate_drift_provocation(date: str, drifts: List[Tuple[str, float]]) -> Suggestion:
    """Generate provocation based on drift patterns."""

    # Sort by drift (highest first)
    drifts_sorted = sorted(drifts, key=lambda x: x[1], reverse=True)

    avg_drift = sum(d for _, d in drifts) / len(drifts)

    # Build drift listing
    drift_lines = []
    for path, drift in drifts_sorted[:7]:  # Show up to 7
        note = vault.get_note(path)
        label = _drift_label(drift)
        drift_lines.append(f"- [[{note.title}]]: {drift:.2f} drift ({label})")

    drift_text = "\n".join(drift_lines)

    # Generate interpretation based on pattern
    if avg_drift > 0.45:
        interpretation = (
            "What if that burst was asking questions, not stating answers? "
            "Early explorations that your understanding has completely transformed?"
        )
    elif avg_drift < 0.15:
        interpretation = (
            "That burst created foundational concepts that haven't needed revision?"
        )
    else:
        # Mixed drift - find stable vs evolving
        stable = [t for t, d in drifts if d < 0.15]
        evolving = [t for t, d in drifts if d > 0.35]

        if stable and evolving:
            stable_titles = ", ".join([f"[[{vault.get_note(p).title}]]" for p in stable[:2]])
            interpretation = (
                f"What if {stable_titles} are your anchors—"
                f"the stable core around which other ideas orbit and evolve?"
            )
        else:
            interpretation = (
                "What if some ideas from that burst crystallized while others are still searching?"
            )

    text = f"On {date}, you created {len(drifts)} notes. Since then:\n{drift_text}\n\n{interpretation}"

    return Suggestion(
        text=text,
        notes=[vault.get_note(p).title for p, _ in drifts],
        geist_id="creation_burst"
    )


def _drift_label(drift: float) -> str:
    """Human-readable drift label."""
    if drift < 0.10:
        return "mostly stable"
    elif drift < 0.25:
        return "moderate evolution"
    elif drift < 0.40:
        return "significant shift"
    else:
        return "major evolution"
```

---

## Key Questions

### 1. What counts as "creation" for temporal comparison?

**Option A: First appearance in session_embeddings**
- Pro: Precise, reflects when embedding was first computed
- Con: May not match file creation date if vault sync happened later

**Option B: Closest session to file creation date**
- Pro: More intuitive alignment with burst day
- Con: May have lag between creation and first session

**Recommendation: Option B** - Use session closest to (but not before) creation date

### 2. Should we show drift for ALL notes or just top/bottom?

**Show all notes** when:
- Small burst (5-7 notes)
- Clear pattern emerges

**Show extremes** when:
- Large burst (10+ notes)
- Focus on most stable vs most evolved

### 3. How do we handle notes that haven't been embedded yet?

**Fallback gracefully:**
- If <50% of burst notes have embeddings → use basic version
- If ≥50% have embeddings → show temporal version with available data

---

## Why This Works

### Immediate Value (Basic)
- Surfaces forgotten productive days
- Zero computation, works day 1
- Simple, clear provocation

### Long-term Value (Temporal)
- Shows which ideas from bursts became stable foundations
- Reveals which ideas kept evolving
- Demonstrates temporal embeddings showing what metadata cannot:
  - Not "did you edit these notes?" (metadata)
  - But "how has your understanding evolved?" (embeddings)

### Natural Evolution Path
```
Week 1:    "You created 7 notes on this day. What was special?"
           ↓
Month 6:   "Those 7 notes have evolved differently—some stable, some shifting."
           ↓
Year 1:    "Looking back, 3 notes became foundations, 4 kept searching."
```

The geist grows with the vault's temporal history.

---

## Connection to Research

This implements the core temporal embeddings insight from TEMPORAL_GEISTS_RESEARCH.md:

> "Temporal embeddings are a DETECTION MECHANISM, not the SUGGESTION ITSELF.
> These geists detect patterns in how understanding evolves, then ask what those patterns MEAN."

**Detection:** Notes from burst day have drifted 0.08 to 0.51
**Provocation:** "What if some ideas crystallized while others are still searching?"

Not analytics. Questions.

---

## Success Criteria

**Basic version succeeds if:**
- Surfaces burst days user had forgotten
- Provokes "oh yeah, what WAS happening then?" reflection
- Runs in <10ms

**Temporal version succeeds if:**
- Drift scores feel meaningful (correlate with user's sense of evolution)
- Distinguishes stable anchors from evolving explorations
- Demonstrates value of temporal embeddings history
- Runs in <500ms

---

## Next Steps

1. Review this spec
2. Decide: implement basic only, or basic + temporal together?
3. Determine drift threshold tuning through testing
4. Consider: should this be a default geist or example?
