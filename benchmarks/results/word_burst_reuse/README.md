# Word-burst reuse, storage and phrase-value evidence

Implementation: `8fb86e3dcdcd8cd8bd95dd02448b289d8173e86d`.
Baseline: `6660bfa93b2a10f42d8228e9cea2d26924326785`.

Read [the measured costs](../../../docs/WORD_BURST_REUSE.md) and
[phrase research and usefulness limits](../../../docs/word_burst_phrases.md).
`summary.json` binds exact receipts, source hashes, inputs and archive contents.
`receipts.json.xz` is UTF-8 JSON mapping relative receipt names to their exact
UTF-8 text. Downloaded papers, private credentials, generated vaults and databases
are not included. Primary URLs and downloaded-source hashes are retained.

Restore into a new scratch directory:

```python
import hashlib
import json
import lzma
from pathlib import Path

bundle = Path("benchmarks/results/word_burst_reuse")
summary = json.loads((bundle / "summary.json").read_text())
compressed = (bundle / "receipts.json.xz").read_bytes()
assert hashlib.sha256(compressed).hexdigest() == summary["archive"]["sha256"]
receipts = json.loads(lzma.decompress(compressed))
output = Path("/tmp/word-burst-reuse-receipts")
output.mkdir(exist_ok=False)
for relative, content in receipts.items():
    target = output / relative
    assert target.resolve().is_relative_to(output.resolve())
    encoded = content.encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == summary["receipts"][relative]["sha256"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded)
```

Capacity comparisons use before trials 1–2 and final after trials 3–4. Earlier
after trials are intermediate revisions, retained and excluded. The failed first
capacity attempt asserted that a copied database's first inode reconciliation
was unchanged; its failure log is retained and none of its timings are used.
Sync has one trial per phase. Its measured writer AST and index/schema bytes
match the final revision; later selected-backfill helpers are not invoked by
sync. All capacity dates are synthetic, and these runs use no embedding inference.

The masked comparative study replays actual frozen source snapshots in separate
arms, with equal date seeds and production lexical thresholds. It measures the
individual geist, without downstream filtering or saved history. Separate
complete real-model narrative replay covers all 45 geists and persisted delivery;
its concurrent timings are not latency claims. Current public Blue Book prose
provides static phrase counts only, without invented history or owner usefulness.

Historical and synthetic-mutation failures are labelled separately. The official
canonical reviewer failed authentication and produced no report; independent
reviews do not replace that verdict. The draft PR is not a merge approval.
