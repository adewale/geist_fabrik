# Topic implementation verification

This is a recovery checkpoint on draft PR #96, saved before full validation at
explicit user request so source changes survive an ephemeral workspace.
**Do not merge this checkpoint.**

The earlier workspace had 38 passing focused tests and three independent audit
agents reported no unresolved medium/high findings. Those local files and its
unfinished canonical-validation log were lost. The implementation in this commit
was reconstructed from recorded requirements, contracts and audit findings.
**The previous audit results do not certify this reconstructed revision.**

Current revision: Python source compilation passed. Full tests, lint/type gates,
lock refresh, package smoke and fresh audit are still pending. This document will
be updated with observed results, never inferred success.

The frozen synthetic and bundled real-note fixtures were produced by an
independent model agent reading source first, without extractor output. They are
model annotations, not human annotations. The evaluator must score every assigned
label at the shipped five-label cap, against a frequency baseline, and check source
checksums. Real-note samples are small calibration/regression evidence, not broad
production accuracy or a held-out evaluation after tuning.

Required checks: `./scripts/validate.sh`, focused topic tests, offline built-package
extraction, source immutability, v10 migration, incremental/rebuild equivalence,
exclusions, explicit source failures, coherent WAL reads, and cold/warm/query cost
measurements with corpus sizes stated. Audit focus: storage correctness, API/CLI
behavior and extraction/source grounding. No new geists or production accuracy
claims are included.
