"""Offline smoke check executed with isolated Python from an installed wheel."""

import importlib.resources
import tempfile
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

import geistfabrik
from geistfabrik.embeddings import EmbeddingComputer, Session
from geistfabrik.vault import Vault

package_file = Path(geistfabrik.__file__).resolve()
assert ".venv" not in package_file.parts, package_file
assert "site-packages" in package_file.parts, package_file
assert version("geistfabrik") == geistfabrik.__version__

model_directory = importlib.resources.files("geistfabrik.model_data").joinpath("all-MiniLM-L6-v2")
weights = model_directory.joinpath("model.safetensors")
assert weights.is_file()
with weights.open("rb") as model_file:
    assert not model_file.read(64).startswith(b"version https://git-lfs.github.com/spec/v1")

computer = EmbeddingComputer()
real_model = computer.model
assert isinstance(real_model, SentenceTransformer), type(real_model)
loaded_model_path = Path(real_model.tokenizer.name_or_path).resolve()
assert loaded_model_path == Path(str(model_directory)).resolve(), loaded_model_path

phrases = [
    "Artificial intelligence and machine learning systems",
    "Machine learning is a branch of artificial intelligence",
    "Bake a chocolate cake with flour and sugar",
]
embeddings = computer.compute_batch_semantic(phrases)
assert isinstance(embeddings, np.ndarray)
assert embeddings.shape == (3, 384)
assert np.isfinite(embeddings).all()
norms = np.linalg.norm(embeddings, axis=1)
assert np.all(norms > 0.0), norms

normalised = embeddings / norms[:, np.newaxis]
related_similarity = float(np.dot(normalised[0], normalised[1]))
unrelated_similarity = float(np.dot(normalised[0], normalised[2]))
assert related_similarity > unrelated_similarity, (
    related_similarity,
    unrelated_similarity,
)

# Exercise the installed wheel's real Session cache/persistence/vector path,
# not only direct model encoding.
with tempfile.TemporaryDirectory() as temporary_directory:
    vault_path = Path(temporary_directory)
    (vault_path / "related-a.md").write_text(f"# Related A\n\n{phrases[0]}")
    (vault_path / "related-b.md").write_text(f"# Related B\n\n{phrases[1]}")
    (vault_path / "unrelated.md").write_text(f"# Unrelated\n\n{phrases[2]}")
    vault = Vault(vault_path)
    assert vault.sync() == 3
    notes = vault.all_notes()
    session = Session(datetime(2026, 1, 15), vault.db, computer=computer)
    session.compute_embeddings(notes)
    stored = {note.path: session.get_embedding(note.path) for note in notes}
    assert all(value is not None and value.shape == (387,) for value in stored.values())
    query = stored["related-a.md"]
    assert query is not None
    matches = session.get_backend().find_similar(query, count=3)
    assert {path for path, _ in matches} == set(stored)
    vault.close()

print(
    "offline real-model inference passed: "
    f"{package_file} shape={embeddings.shape} "
    f"related={related_similarity:.3f} unrelated={unrelated_similarity:.3f}"
)
