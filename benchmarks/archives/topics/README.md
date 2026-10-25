# Historical topic evidence

These checked-in ASCII archives preserve the original report and review bytes.
Compressed payloads are omitted from line diffs; these remain ordinary durable
Git blobs, with their readable inventories available through the utility below.
They are durable Git files, not expiring CI artifacts. Each JSON envelope lists
the original paths, byte counts and SHA256 checksums beside a bounded compressed
payload. No source vault Markdown bodies are included. Review keyphrases and
evidence snippets are retained; review records remain unrated, not approvals.

| Archive | Original evidence |
| --- | --- |
| [baseline](baseline.archive.json) | Initial corpus benchmark reports |
| [property-mask-probe](property-mask-probe.archive.json) | Early masking probe reports |
| [final](final.archive.json) | Historical final checkpoint reports |
| [all-snapshots](all-snapshots.archive.json) | Historical replay reports |
| [quality-repair-probe](quality-repair-probe.archive.json) | Comparative quality probe reports |
| [initial-review](initial-review.archive.json) | Initial pending starter review record |
| [grammar-repair-review](grammar-repair-review.archive.json) | Pending source-first review packet and ambiguity evidence |
| [fresh annotations](fresh-annotations.archive.json) | Two independent source-only model annotation passes; not human judgments |
| [calibration 0530](calibration-0530.archive.json) | Failed calibration of 128 local policy variants plus the published baseline; no eligible local policy |

The readable [grammar repair reports](../../results/topics/corpora/grammar-repair/index.json)
and [corpus receipt](../../results/topics/corpora/receipt.json) remain available.
An archive's filename and historical `final` labels do not establish current
runtime validity; use the current verification summary for delivery status.

From the repository root, with Python 3.11+ on Linux or macOS:

```sh
python scripts/topic_evidence_archive.py list benchmarks/archives/topics/baseline.archive.json
python scripts/topic_evidence_archive.py verify benchmarks/archives/topics/baseline.archive.json
python scripts/topic_evidence_archive.py extract benchmarks/archives/topics/baseline.archive.json ./topic-evidence-restored
```

Extraction recreates the original repository-relative paths under the selected
directory, verifies every checksum before writing, rejects symlink traversal,
and refuses to overwrite files. Use a fresh destination to inspect another run.
The utility uses only Python's standard library and limits archives to 500,000
bytes and expanded payloads to 32 MiB. Creation sorts paths, omits timestamps and
retains exact bytes, including original line endings and provenance fields:

```sh
python scripts/topic_evidence_archive.py create ./review.archive.json \
  benchmarks/reviews/topics/pending.json --root ./topic-evidence-restored
```

Gzip is the default; `create --compression xz` uses XZ for highly repetitive
reports. Readers accept both codecs and limit XZ decoder memory to 64 MiB.
The calibration archive preserves the complete original
`benchmarks/results/topics/policy-experiments/calibration-0530.json`, including
its source-localization evidence and failed selection outcome. The 128 local
variants found no eligible policy; the selected local policy is diagnostic
only, simplification failed, and the published implementation was retained.
This historical failure is calibration evidence, not a fresh-source result or
an eligible replacement policy. The original report remains byte-exact inside
the archive rather than adding its 10.8 MB plain JSON to the review.

Historical references should name the archive and original path; `list` exposes
the original checksum. Restore historical paths before running tools that expect
them on disk. Do not rewrite old records' input hashes, source commits, run IDs
or report hashes to describe current code. A new run needs its own evidence.
