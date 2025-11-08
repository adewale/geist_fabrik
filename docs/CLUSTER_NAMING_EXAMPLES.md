# Cluster Naming: Before & After Examples

**Before**: c-TF-IDF (frequency-based keyword extraction)
**After**: KeyBERT (semantic similarity to cluster centroid)

## About These Examples

These are **realistic synthetic examples** based on common note patterns. Real examples require a vault with 10+ notes to form meaningful clusters (HDBSCAN's minimum cluster size is 5).

**To generate real examples from your vault**:
```bash
python scripts/compare_cluster_labeling.py /path/to/your/vault
```

This will show side-by-side comparisons of both labeling methods on your actual clusters.

---

## Example 1: Personal Knowledge Management Cluster

**Cluster size**: 12 notes
**Sample notes**:
- Evergreen notes
- Zettelkasten method
- Note-taking systems
- Building a second brain

### Before (c-TF-IDF)
```
notes, knowledge, system, management
```
**Formatted**: "Notes about notes, knowledge, system, and management"

**Why**: Picks most frequent terms across cluster texts

### After (KeyBERT)
```
knowledge management systems, evergreen note-taking, personal knowledge
```
**Formatted**: "Notes about knowledge management systems, evergreen note-taking, and personal knowledge"

**Why**: Semantically closest phrases to cluster centroid
**Improvement**: More descriptive, captures conceptual theme

---

## Example 2: Software Development Cluster

**Cluster size**: 8 notes
**Sample notes**:
- React component patterns
- State management strategies
- Frontend architecture
- TypeScript best practices

### Before (c-TF-IDF)
```
react, component, state, typescript
```
**Formatted**: "Notes about react, component, state, and typescript"

**Why**: Individual high-frequency terms

### After (KeyBERT)
```
react component architecture, frontend state management, typescript patterns
```
**Formatted**: "Notes about react component architecture, frontend state management, and typescript patterns"

**Why**: Multi-word phrases semantically central to cluster
**Improvement**: Complete phrases vs individual keywords

---

## Example 3: Writing & Content Creation Cluster

**Cluster size**: 15 notes
**Sample notes**:
- Writing process
- Content strategy
- Audience development
- Storytelling techniques

### Before (c-TF-IDF)
```
writing, content, audience, process
```
**Formatted**: "Notes about writing, content, audience, and process"

**Why**: Most common words in cluster

### After (KeyBERT)
```
content writing strategies, audience development techniques, storytelling process
```
**Formatted**: "Notes about content writing strategies, audience development techniques, and storytelling process"

**Why**: Phrases with high semantic similarity to cluster meaning
**Improvement**: Actionable phrases vs abstract nouns

---

## Example 4: Research & Learning Cluster

**Cluster size**: 10 notes
**Sample notes**:
- Research methodology
- Academic writing
- Literature review
- Citation management

### Before (c-TF-IDF)
```
research, academic, writing, literature
```
**Formatted**: "Notes about research, academic, writing, and literature"

**Why**: Frequent terms appear together

### After (KeyBERT)
```
academic research methodology, literature review writing, citation practices
```
**Formatted**: "Notes about academic research methodology, literature review writing, and citation practices"

**Why**: Domain-specific phrases closest to cluster centroid
**Improvement**: Specific practices vs general terms

---

## Example 5: Project Management Cluster

**Cluster size**: 7 notes
**Sample notes**:
- Agile workflows
- Sprint planning
- Project tracking
- Team coordination

### Before (c-TF-IDF)
```
project, team, sprint, agile
```
**Formatted**: "Notes about project, team, sprint, and agile"

**Why**: High TF-IDF scores for these terms

### After (KeyBERT)
```
agile project management, sprint planning workflows, team coordination
```
**Formatted**: "Notes about agile project management, sprint planning workflows, and team coordination"

**Why**: Coherent phrases representing cluster theme
**Improvement**: Workflow context vs isolated terms

---

## Example 6: Health & Wellness Cluster

**Cluster size**: 9 notes
**Sample notes**:
- Nutrition basics
- Exercise routines
- Sleep hygiene
- Stress management

### Before (c-TF-IDF)
```
health, exercise, nutrition, sleep
```
**Formatted**: "Notes about health, exercise, nutrition, and sleep"

**Why**: Topic keywords with highest frequency

### After (KeyBERT)
```
nutrition and exercise, sleep hygiene practices, stress management
```
**Formatted**: "Notes about nutrition and exercise, sleep hygiene practices, and stress management"

**Why**: Natural phrases from actual note content
**Improvement**: Actionable areas vs general topics

---

## Example 7: Obsidian Customization Cluster

**Cluster size**: 13 notes
**Sample notes**:
- Custom CSS snippets
- Plugin development
- Themes and styling
- Workspace customization

### Before (c-TF-IDF)
```
obsidian, plugin, css, theme
```
**Formatted**: "Notes about obsidian, plugin, css, and theme"

**Why**: Tool-specific frequent terms

### After (KeyBERT)
```
obsidian plugin development, custom css theming, workspace customization
```
**Formatted**: "Notes about obsidian plugin development, custom css theming, and workspace customization"

**Why**: Activity-focused phrases semantically central
**Improvement**: What you're doing vs what tools you're using

---

## Example 8: Philosophy & Ideas Cluster

**Cluster size**: 11 notes
**Sample notes**:
- Stoic philosophy
- Existential questions
- Ethics frameworks
- Philosophical paradoxes

### Before (c-TF-IDF)
```
philosophy, ideas, ethics, questions
```
**Formatted**: "Notes about philosophy, ideas, ethics, and questions"

**Why**: Abstract terms appear frequently

### After (KeyBERT)
```
stoic philosophy principles, ethical frameworks, existential questions
```
**Formatted**: "Notes about stoic philosophy principles, ethical frameworks, and existential questions"

**Why**: Specific philosophical domains from cluster content
**Improvement**: Schools of thought vs generic "philosophy"

---

## Key Differences Summary

| Aspect | c-TF-IDF | KeyBERT |
|--------|----------|---------|
| **Phrase length** | Mostly single words | 2-3 word phrases |
| **Semantic coherence** | Low (frequency-based) | High (meaning-based) |
| **Interpretability** | Generic keywords | Specific concepts |
| **Context** | Missing | Preserved in phrases |
| **User value** | Know topics exist | Understand what cluster is about |

## Pattern Analysis

### What c-TF-IDF Does Well
- Fast computation
- Identifies key terms
- Works with any language
- No model dependencies

### What c-TF-IDF Struggles With
- Single-word limitation (with default settings)
- Misses semantic relationships
- Generic/vague labels
- Context-free keywords

### What KeyBERT Does Well
- Multi-word descriptive phrases
- Semantically coherent labels
- Captures cluster "essence"
- More interpretable to users

### What KeyBERT Costs
- Slightly slower (~0.5-1s per cluster)
- Requires embedding model
- Model-dependent quality

---

## Real-World Impact

When a user sees clusters in the `cluster_mirror` geist:

**Before (c-TF-IDF)**:
> "You have clusters about: notes, project, writing..."
>
> User thinks: "Well yes, but what KIND of notes? What aspect of projects?"

**After (KeyBERT)**:
> "You have clusters about: knowledge management systems, agile project workflows, content writing strategies..."
>
> User thinks: "Oh! I have a clear theme around knowledge management. My project notes are specifically about agile workflows."

**The difference**: Users can immediately understand what each cluster represents without reading sample notes.

---

## Technical Notes

### N-gram Comparison

**c-TF-IDF**: Uses `ngram_range=(1, 2)` → 1-2 word phrases
- Example output: "note taking", "knowledge", "system"

**KeyBERT**: Uses `ngram_range=(1, 3)` → 1-3 word phrases
- Example output: "knowledge management systems", "note taking strategies"

### Scoring Comparison

**c-TF-IDF**:
```
Score = (term frequency in cluster) × log(total clusters / clusters with term)
```
Favors: Terms frequent in cluster, rare across clusters

**KeyBERT**:
```
Score = cosine_similarity(phrase_embedding, cluster_centroid_embedding)
```
Favors: Phrases semantically similar to cluster's conceptual center

### Selection Process

**Both methods**: Apply MMR (Maximal Marginal Relevance) for diversity
- Prevents redundant terms like "writing, writer, written"
- Ensures variety in selected labels

---

## Conclusion

**KeyBERT produces cluster names that are**:
- ✅ More descriptive (multi-word phrases)
- ✅ More semantically coherent (meaning-based)
- ✅ More interpretable (clear conceptual themes)
- ✅ More useful (understand clusters at a glance)

**Trade-off**: Slightly slower, but the quality improvement is worth the ~1 second per cluster.

**Recommendation**: Use KeyBERT as default for all cluster labeling going forward.
