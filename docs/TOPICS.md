# Automatic derived topics

Normal vault sync extracts up to five English topic labels per eligible note or
dated entry using local YAKE, short primary headings, and visible wikilink names.
Topics and exact evidence live in SQLite, separate from authored tags; Markdown
and frontmatter are never rewritten. Schema v11 migrates automatically.

```
geistfabrik topics /path/to/vault
geistfabrik topics /path/to/vault --note '[[My note]]' --json
geistfabrik topics /path/to/vault --topic 'paper folding'
geistfabrik topics /path/to/vault --rebuild
```

Exit 0 means complete, 1 command error, 2 incomplete. Incomplete corpus queries
return unavailable counts/memberships rather than false zeroes. Empty successful
extraction remains distinct from pending/error/excluded work. Failed physical
sources are recorded even when parsing could not create a note row. Diagnostics
use stderr so JSON stdout remains readable. Inspection loads no embedding model
or user plugins.

VaultContext exposes `topics_for_note`, `topic_state`, `notes_for_topic`, and
`topic_catalog`. Metadata contains `derived_topics` and `derived_topics_status`.
Tracery functions `note_topics(note)` return label text and `topic_notes(topic,
count=5)` return deterministically sampled, bracketed links. Suggestions retain
the existing sampling, filtering, preview, and explicit `--write` controls.

Keys normalize Unicode, case and whitespace only; no stemming, semantic merging,
public-topic threshold, corpus frequency floor, or popularity ranking. Singleton
topics remain valid. Scores rank labels, not provocations, and are not calibrated
probabilities. Membership is textual evidence, never stance, emotion or intention.

Frontmatter, code, comments, transclusions, authored tags, link destinations and
reference metadata are excluded. Configured boundary prefixes, the geist journal
and managed-state directory are excluded before extraction/counts even when
suggestion boundary filtering is disabled. Raw inputs over 100,000 characters
produce explicit errors, never silently truncated labels. Content/parser/extractor/
settings/boundary changes invalidate cached results; edits and deletions reconcile
memberships during normal sync. Related reads share one database snapshot.

See [verification status](TOPICS_VERIFICATION.md) and the
[guiding principles](../specs/TOPIC_EVIDENCE_SPEC.md).
