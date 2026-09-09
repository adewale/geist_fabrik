# Sentence-Transformers Model Snapshot

GeistFabrik redistributes a materialized snapshot of
[`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
for reproducible local inference. It produces normalized 384-dimensional
sentence embeddings and occupies roughly 88 MB before Python dependencies.

## Distribution and loading

- **Release wheels:** Hatch maps this directory into the importable
  `geistfabrik.model_data` resource package. Standard wheel installers unpack
  it into `site-packages`; `EmbeddingComputer` resolves it with
  `importlib.resources`.
- **Source checkouts:** the same files remain here and the loader retains a
  repository-layout fallback. Git LFS must materialize `model.safetensors` and
  `tokenizer.json` (`git lfs pull`).
- **Online fallback:** when neither packaged nor source resources are usable,
  the loader may resolve `all-MiniLM-L6-v2` through HuggingFace.
- **Strict offline mode:** set `GEISTFABRIK_OFFLINE=1` (or
  `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1`) to forbid downloads. A wheel
  installed normally from an official artifact works in this mode.

Directly zip-importing an uninstalled wheel is not supported by
sentence-transformers; install the wheel normally.

## Provenance and license

The exact upstream repository, snapshot revision, Git LFS checksums, and
redistribution notice are in `all-MiniLM-L6-v2/NOTICE`. The model is licensed
under Apache-2.0; its license is packaged as
`all-MiniLM-L6-v2/LICENSE.apache-2.0`. The upstream model card remains in the
snapshot's `README.md`. These terms are separate from GeistFabrik's MIT
license.

## Refreshing the snapshot

```bash
uv run python scripts/download_model.py
git lfs status
```

When changing the snapshot, update `NOTICE` revision/checksums and run
`./scripts/test_wheel.sh` before release. The artifact check rejects Git LFS
pointers, incomplete resources, wheels/source distributions at or above the
95,000,000-byte policy ceiling, and installed wheels that cannot perform real
offline inference.
