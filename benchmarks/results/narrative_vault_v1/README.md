# Narrative evaluation receipts

See [the report](../../../docs/NARRATIVE_VAULT_EVALUATION.md) and
[summary.json](summary.json). The measured engine/harness checkpoint is `73c3393`.
The later documentation and test-oracle repair do not change those code hashes.

`receipts.json.xz` decompresses to a JSON object mapping relative names to exact
UTF-8 file contents. Each value encoded as UTF-8 recovers the original bytes.
The summary binds the compressed and decompressed archive with SHA-256 hashes.
It contains both final mode reports and all invocation logs, the frozen corpus
manifest, all explicit assessments, diagnostic checks and superseded clock runs.

For example, inspect the final dated report without restoring source notes:

```python
import json
import lzma
from pathlib import Path

archive = json.loads(lzma.decompress(Path("receipts.json.xz").read_bytes()))
dated = json.loads(archive["final-dated.json"])
print(dated["snapshots"][0]["selected"])
```

The checked-in sources and compiler reproduce the content-addressed corpus;
duplicating its Markdown objects here is unnecessary. Outputs remain fiction.
The assessment script records explicit judgments for this fixed output, not a
quality oracle for future runs. See the external ledger for the review rules.
