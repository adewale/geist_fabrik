# Final audit repairs

`summary.json` binds the two repairs to their source commit, exact runtime hashes,
validation results, final microbenchmarks and generated Markdown outputs.
`before.md` and `after.md` are actual bundled-geist questions from the same
72-note fixture. Inspect the disappearance of the hidden `orchard visible` lens
and the clean current passages; question count drops from three to two. This is
targeted correctness evidence, not a utility evaluation.

`receipts.json.xz` contains exact UTF-8 files with per-file SHA-256 hashes. It
retains the initial adversarial audit, independent repair reviews and probes,
regression red/green logs, synthetic memory-mutation proof, final measurements,
validation log/source hashes, and unsuccessful canonical-review status. The
canonical reviewer failed authentication and produced no report. Local scoped
reviews are not a canonical clean verdict.

Restore into an empty directory:

```python
import hashlib
import json
import lzma
from pathlib import Path

data = json.loads(lzma.decompress(Path("receipts.json.xz").read_bytes()))
destination = Path("restored")
for name, item in data["files"].items():
    relative = Path(name)
    assert not relative.is_absolute() and ".." not in relative.parts
    payload = item["text"].encode()
    assert hashlib.sha256(payload).hexdigest() == item["sha256"]
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
```

The scripts retain their original `/workspace` checkout/corpus paths. Adjust
those paths when reproducing elsewhere. Numeric inputs are regenerated from
recorded seeds; binary arrays are not required. The source-only HTML probe
builds its own temporary fictional vault. Performance scripts read original
stress sources without modifying them. The exploratory measurement run is
explicitly excluded from the final comparison because it overlapped development
and independent probes; the final run uses the first 100 stress notes.

For the implementation, arithmetic proof, policy-reset consequences and measured
costs, see [the repair report](../../../docs/WORD_BURST_FINAL_REPAIRS.md).
