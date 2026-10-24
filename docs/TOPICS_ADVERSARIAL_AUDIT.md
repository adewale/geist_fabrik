# Adversarial audit of PR #96

Audited commit: `16d0adba380c306b3ff19f455ae3f4787aa78e68`.
Base: `657f85675bc05d3f353ed88940f36efe604b0367`.
Verdict: **do not merge**. The findings below are present in the published code,
regardless of fixes prepared in a different local working tree.

Three agents completed independent privacy, extraction, and interface/verification
reviews. A fourth supplied a partial storage review; the primary agent independently
reran its storage reproductions. The audit used 391 files whose Git blob hashes were
checked against the immutable published tree.

## High severity

1. **Protected physical sources leak through public symlinks.**
   `topics.py:303` checks only the stored logical identity, while `vault.py:217`
   resolves and reads a symlink target and persists its candidate path.
   With `exclude_paths=["Private/"]`, `public.md -> Private/secret.md` publishes
   the private heading as a complete topic membership under `public.md`.
   An alias to `_geistfabrik/internal.md` similarly publishes its topic. The
   result survives closing/reopening the database without another sync.
   Persist and validate physical provenance alongside logical identities, including
   on reads. Public hardlinks were not classified independently as a defect:
   the established contract does not explicitly exclude inode aliases.

2. **The committed lock omits the mandatory extractor.**
   `pyproject.toml:38` requires YAKE, but `uv.lock:236-281` has neither its root
   dependency/metadata requirement nor any YAKE package record.
   `topics.py:17` imports it unconditionally. Frozen synchronization therefore
   does not supply the declared dependency graph. Later plain `uv run` commands
   in `scripts/validate.sh:47` onward can silently refresh the lock and install
   YAKE, masking this defect. Regenerate and commit the lock; validation must
   reject drift rather than repair it invisibly.

## Medium severity

3. **Topic exclusions weaken the shared source policy and discard virtual IDs.**
   `topics.py:262-269` uses a separate directory-only matcher. Proven bypasses:
   default `Templates/template.md`; `["Private"]` with `Private ideas.md`;
   `["./Private/"]` or `["X/../Private/"]` with `Private/hidden.md`.
   Existing SourceEligibility rejects these corresponding sources.
   Additionally, `source_file or path` at lines303/334 discards a virtual entry's
   identity. Excluding `Diary.md/2025-01-01` still publishes that entry and its
   protected heading with count1. Apply shared policy to both identities before
   extraction and aggregation, independently of the suggestion-filter toggle.

4. **Source failures and late oversized files establish false completeness.**
   A containment/stat PermissionError at `vault.py:219-221` skips an existing
   source without a failure record. Reconciliation removes its old row, and
   `states()=={}`, `catalog()==[]` succeed although the file still exists.
   Separately, creating a file larger than MAX_NOTE_BYTES after initial discovery
   is ignored by final validation at `vault.py:200-208`: the index reports complete
   with no error for it. The next sync, with the same file unchanged, records an
   error and rejects the catalog. Include failure status in source reconciliation
   and revalidate the same completeness population immediately before commit.

5. **Hidden metadata and non-prose code become topic evidence.**
   The regex at `topics.py:31` leaks the hidden title in valid Markdown:
   `[Visible](https://example.test/path(inner) "Hidden subject")`.
   The reference pattern at line33 also leaks valid next-line reference titles.
   Explicit candidate injection publishes the leaked phrase with exact raw spans.
   More strongly, these inputs produce a heading topic with ZERO keyword candidates:

   ~~~~markdown
   - ```
     # Hidden subject
     ```
   ~~~~

   ~~~~html
   <script>
   # Hidden subject
   </script>
   ~~~~

   List-contained fences are missed by `topics.py:143-146`; HTML masking at
   line164 strips tags while retaining their hidden/code contents. Ordered lists
   and pre elements reproduce the respective defects. Use parser-owned block,
   container, link/reference and non-prose HTML spans, preserving source offsets.

6. **The promised quality gate is not executable.**
   Both gold JSON files declare thresholds and source hashes, but neither filename
   is referenced by any test/script and no topic evaluator exists in this commit.
   Validation cannot enforce precision/recall, score all five assigned labels,
   compare the baseline, or detect fixture-source drift. Wire those checks without
   changing the oracle to match output. These small model annotations do not
   replace the separately promised representative human-reviewed quality study.

## Evidence and limits

The primary agent reran the privacy, extraction and storage scripts successfully.
Storage probes used real published Vault/TopicIndex/SQLite. Missing YAKE was an
empty extractor; lexical processing was disabled or stubbed and the distribution
digest fixed. Extraction probes used injected candidates, with no candidates at
all for the list-fence/HTML heading cases. These prove the stated paths, not
end-to-end YAKE accuracy. Full pytest/type/lint validation was not run locally.

Authored source hashes remained unchanged. Ordinary top-level fenced-code
exclusion, singleton headings and Windows separator normalization controls passed.
No independent medium/high defect was established in read-snapshot scope,
model/plugin-free CLI setup, clean JSON, null versus empty states, argument limits,
or deterministic bracketed-link sampling.

CI run39864334199 for the same commit passed both offline package smoke lanes.
All three unit lanes failed three direct-SQL Windows-spelling fixture cases:
the fixture updates notes.path after sync while retaining topic foreign-key
children (`test_word_burst_integration.py:164`). Linux lanes had2210 passes.
This is a fixture integration failure, not proof that ordinary Windows sync fails.
Prepare the intended identity initially or reconcile dependent fixture state;
do not weaken foreign keys merely to make the fixture pass.
