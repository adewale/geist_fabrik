# Topic verification and rebase status

This revision rebases the published implementation checkpoint onto main657f856 (schema15), preserving lexical capture and allocating additive schema16 for topics. The richer local repair/evaluation files became inaccessible when the workspace failed and are not included here. The recorded material audit findings remain open in this revision. Do not merge until they are fixed and the actual published revision passes the gates below.

## Session requirements

Automatic topic extraction and derived note tags are the first deliverable. Preserve source Markdown/frontmatter/authored tags, local user-invoked operation, singleton topics, conservative identities, exact evidence, shared VaultContext/Tracery APIs, and CLI inspection. Exclude protected sources before extraction/counts. Keep deterministic suggestion sampling, filtering, preview and explicit --write. Membership is textual evidence, never stance or intention. Do not import newsletter segmentation, public-topic thresholds, aggressive merging, editorial ranking, background/cloud machinery or speculative new geists from Flux/Bobbin.

## Fresh independent audit findings

Storage review reproduced two material defects against the checkpoint with real Vault/SQLite and only the missing YAKE dependency stubbed:

- HIGH: excluded Private/hidden.md can leak its heading through public.md symlink. Persist physical source identities and enforce the shared SourceEligibility policy on sync and reads/reopen.
- MEDIUM: containment/stat PermissionError skips discovery without a failure manifest; reconciliation removes previous rows and falsely reports a complete empty index. Persist eligible discovery failures before continuing.
- MEDIUM: configured-prefix semantics differ from current main; reuse SourceEligibility, including Templates/, independently of suggestion filtering toggles.

Quality review reproduced hidden balanced-link title leakage, comment-contained fences erasing later visible prose, and later H1 headings displacing the primary subject. Parser-owned source spans, physical block boundaries and first-visible-primary-heading evidence are required repairs.

Fresh interface source review found no independent medium/high finding in snapshot scope, model/plugin-free CLI setup, clean JSON, incomplete-result reporting or deterministic bracketed-link sampling. Low: VaultContext.topic_state should apply the CLI's .md fallback for unparsed physical sources.

Prepared local repairs preserve main's lexical transaction and insert topic publication before final filesystem snapshot validation. A local real-SQLite v15->v16 migration/reopen check preserved source content/authored tags. This does not certify the unpublished full revision.

## Verification still required

- Commit the remaining audit repairs, executable evaluation and refreshed YAKE dependency lock.
- Run ./scripts/validate.sh, full CI matrix and offline wheel/sdist smoke on the exact published revision. The execution sandbox has blocked package downloads; a local run completed with dependency-availability failures, not a passing result.
- Restore executable quality evaluation: every assigned label at limit5, precision/recall and frequency baseline, real-source checksums, empty-case failures. Gold fixtures remain unchanged.
- Measure cold/warm sync and positive member-query costs with corpus sizes stated. A synthetic141-character repeated-note benchmark is not representative-vault performance evidence.
- Recheck audit reproductions after code publication and record actual results here.

The synthetic8-case and bundled-real10-case fixtures are source-first model annotations, not human-reviewed representative quality or an untouched holdout after tuning. Broader representative quality remains an open delivery gate.

Historical checkpoint Actions run38657954594 passed offline package smoke for Python3.11 and3.12. Its macOS unit lane had1611 passes and one stale-schema-status failure; other matrix lanes were canceled. This does not certify the rebased revision. The lost workspace's earlier38-test/three-agent results also do not certify current code.
