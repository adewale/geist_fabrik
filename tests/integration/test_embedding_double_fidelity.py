"""The fast-lane embedding stub must keep the real model's encode contract.

Every test outside the ``production_model`` tier embeds text with
``tests.stubs.SentenceTransformerStub``. This file states, once, the parts of
``SentenceTransformer.encode`` that GeistFabrik relies on, through the
``EmbeddingComputer`` methods that call it (float32 storage, unit length, batch/single
agreement, and "shared topic is closer than unrelated topic") and checks the
stub and the bundled real model against the same assertions. The real case
runs in the weekly ``production_model`` tier, so a drift between the double
and the runtime it stands in for fails there instead of hiding in every fast
test.
"""

from pathlib import Path

import numpy as np
import pytest

from geistfabrik import embeddings
from geistfabrik.config import SEMANTIC_DIM
from geistfabrik.embeddings import EmbeddingComputer
from tests.stubs import SentenceTransformerStub

BREAD = "Sourdough bread needs a long, slow fermentation."
BREAD_AGAIN = "Fermentation is what gives sourdough bread its flavour."
ORBITS = "Orbital mechanics decides when a satellite can launch."


def _computer(kind: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> EmbeddingComputer:
    if kind == "stub":
        stub = SentenceTransformerStub(tmp_path, device="cpu", local_files_only=True)
        return EmbeddingComputer(model=stub)
    monkeypatch.setenv("GEISTFABRIK_OFFLINE", "1")
    computer = EmbeddingComputer()
    # Guard against a vacuous pass: the autouse fixture must have left this
    # session on the real constructor.
    assert embeddings.SentenceTransformer is not SentenceTransformerStub
    assert not isinstance(computer.model, SentenceTransformerStub)
    return computer


@pytest.mark.parametrize(
    "kind",
    ["stub", pytest.param("real", marks=[pytest.mark.production_model, pytest.mark.slow])],
)
def test_encode_contract_matches_the_real_model(
    kind: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    computer = _computer(kind, monkeypatch, tmp_path)

    # The two production paths into encode().
    single = computer.compute_semantic(BREAD)
    batch = computer.compute_batch_semantic([BREAD, BREAD_AGAIN, ORBITS], batch_size=2)

    assert isinstance(single, np.ndarray)
    assert single.shape == (SEMANTIC_DIM,)
    assert single.dtype == np.float32  # session embeddings are stored as float32 BLOBs
    assert isinstance(batch, np.ndarray)
    assert batch.shape == (3, SEMANTIC_DIM)
    assert batch.dtype == np.float32

    # Batching (and batch_size) does not change a text's vector.
    np.testing.assert_allclose(batch[0], single, atol=1e-5)

    # Unit length, like the real model's Normalize module.
    np.testing.assert_allclose(np.linalg.norm(batch, axis=1), [1.0, 1.0, 1.0], atol=1e-5)

    # Deterministic: the same text always gets the same vector.
    np.testing.assert_array_equal(computer.compute_semantic(BREAD), single)

    # Known answer: two notes about sourdough are closer than either is to a
    # note about orbits. Fixtures throughout the suite build on this.
    same_topic = float(batch[0] @ batch[1])
    unrelated = float(batch[0] @ batch[2])
    assert same_topic > unrelated + 0.1, (same_topic, unrelated)
