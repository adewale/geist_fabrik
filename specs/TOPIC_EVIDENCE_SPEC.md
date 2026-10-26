# Automatic topics for GeistFabrik

**Status**: Implemented in draft PR #96. A local grammar repair meets the broader proxies' frozen numeric thresholds, but the LYT empty-form gate and representative human-reviewed quality remain open; the index is not ready to ship. See [verification](../docs/TOPICS_VERIFICATION.md), [repair decisions](../docs/TOPIC_QUALITY_REPAIR.md) and [corpus evidence](../docs/TOPIC_CORPUS_EVALUATION.md).

Automatically extract useful topics from notes and assign derived topic tags, following the [GeistFabrik vision](geistfabrik_vision.md). The first deliverable is a usable local topic index. Existing and future geists can consume it; new geists are not required to establish its value.

## First delivery

1. **Extract topics automatically.** Process eligible note prose and dated entries during normal vault sync/invocation. Use local YAKE-family extraction to propose labels, then reject malformed phrases, markup artifacts, and boilerplate. Calibrate for personal notes, including short notes.

2. **Assign derived tags.** Maintain a conservative canonical topic vocabulary and note-to-topic memberships in the existing SQLite database. Preserve display wording, matched source text, location, and extraction provenance. A useful topic may belong to just one note. Keep inferred topic tags distinct from author-written tags.

3. **Make the index usable.** Expose a note’s topics and a topic’s source notes through `VaultContext`, with suitable registered functions for Tracery. Provide a CLI inspection view with source links so users can inspect labels and find notes by topic without installing a new interface.

4. **Keep it current.** Incrementally update memberships after edits and deletions. Version extraction by source content, parser, extractor, and configuration; make the index rebuildable. Mark incomplete extraction explicitly rather than treating it as absence.

## Guiding principles and mandatory constraints

- **Borrow the capability, calibrate the policy.** Adopt Flux Search and Bobbin’s automatic extraction, topic identities, and source memberships. Do not transplant newsletter segmentation, domain-specific stopwords, public-topic promotion thresholds, aggressive merging, cloud queues, or editorial ranking. Singleton topics must remain possible in personal vaults.

- **Preserve source notes.** Topic tags are derived local metadata. Do not rewrite Markdown, frontmatter, or authored tags. Use the existing portable database and additive, versioned migrations.

- **Local and deliberate.** Introduce no network or external LLM requirement, background monitoring, or topic dashboard. Keep routine use automatic and configuration light.

- **Shared intelligence.** Extraction and topic queries belong behind `VaultContext`; geists must not query storage directly or repeat corpus processing.

- **Respect boundaries.** Exclude the geist journal and configured excluded paths before extraction and aggregation. Keep atomic notes and dated entries independently addressable.

- **Score labels; sample provocations.** Extractor scores may select useful topic labels. Geist suggestions must retain deterministic sampling, bounded filtered output, preview by default, and the existing `--write` flow.

- **Muses, not oracles.** Topic membership describes observed text; it does not establish stance, contradiction, emotion, or intention. Preserve the lesson from the [retired opposition geists](research/OPPOSITION_GEISTS_RESEARCH.md). Any later temporal feature must use reliable dates and observed text, not reconstruct history from timestamps or vectors.

## Verification and delivery gates

1. **Topic quality:** use a frozen, manually labelled sample of representative notes. Report precision and recall at the chosen label limit against a simple extraction baseline. Inspect missed topics and noisy labels, including short notes, rare topics, phrase variants, boilerplate, and Markdown artifacts. Set acceptance thresholds before tuning.

2. **Correctness:** known-answer fixtures must verify topic memberships, conservative normalization, source evidence, exclusions, and empty/incomplete results. Identical inputs must reproduce labels; incremental updates must match a clean rebuild after edits, deletions, and extractor changes.

3. **Operation:** run `./scripts/validate.sh`, verify offline packaged extraction, confirm source files remain unchanged, and measure cold/warm indexing cost and topic-query latency on representative vault sizes.

Ship the topic index only after these gates pass. Evaluate additional generative uses separately, reusing existing geists where their purposes overlap.
