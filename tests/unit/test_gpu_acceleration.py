"""Unit tests for GPU acceleration and device detection."""

from unittest.mock import MagicMock, patch

from geistfabrik import embeddings
from geistfabrik.embeddings import EmbeddingComputer
from tests.stubs import SentenceTransformerStub


class TestDeviceDetection:
    """Test device detection for GPU acceleration."""

    def test_detect_device_returns_valid_device(self):
        """Test that device detection returns a valid device string."""
        computer = EmbeddingComputer()
        device = computer._detect_device()
        assert device in ["cuda", "mps", "cpu"]

    def test_detect_device_cuda_available(self):
        """Test CUDA detection when available."""
        with patch("torch.cuda.is_available", return_value=True):
            computer = EmbeddingComputer()
            device = computer._detect_device()
            assert device == "cuda"

    def test_detect_device_mps_available(self):
        """Test MPS detection when CUDA unavailable but MPS available."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = True

        with patch.dict("sys.modules", {"torch": mock_torch}):
            computer = EmbeddingComputer()
            device = computer._detect_device()
            assert device == "mps"

    def test_detect_device_cpu_fallback_no_torch(self):
        """Test CPU fallback when torch.cuda.is_available raises ImportError."""
        # Can't easily test torch module not being available since it's already imported
        # But we can test the fallback path when GPU checks fail
        computer = EmbeddingComputer()

        # Mock both cuda and mps to be unavailable to force CPU fallback
        with patch("torch.cuda.is_available", return_value=False):
            with patch("torch.backends.mps.is_available", return_value=False):
                device = computer._detect_device()
                assert device == "cpu"

    def test_detect_device_cpu_fallback_no_gpu(self):
        """Test CPU fallback when no GPU available."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False

        with patch.dict("sys.modules", {"torch": mock_torch}):
            computer = EmbeddingComputer()
            device = computer._detect_device()
            assert device == "cpu"

    def test_device_set_on_model_access(self, monkeypatch, tmp_path):
        """Test that device is set when model is first accessed."""
        monkeypatch.setattr(embeddings, "_bundled_model_path", lambda _name: tmp_path)
        computer = EmbeddingComputer()

        assert hasattr(computer, "device")
        assert computer.device is None

        # Access model (this will trigger device detection and the constructor stub)
        _ = computer.model

        # Device should now be set
        assert computer.device is not None
        assert computer.device in ["cuda", "mps", "cpu"]

    def test_device_logged_on_model_load(self, caplog, monkeypatch, tmp_path):
        """Test that device selection is logged."""
        import logging

        monkeypatch.setattr(embeddings, "_bundled_model_path", lambda _name: tmp_path)
        computer = EmbeddingComputer()
        assert hasattr(computer, "device")

        # Set logging level to INFO to capture the log message
        caplog.set_level(logging.INFO, logger="geistfabrik.embeddings")

        # Access model to trigger device detection and the constructor stub
        _ = computer.model

        assert any("Using device:" in record.message for record in caplog.records)

    def test_device_detected_once_and_reused_after_model_reload(self, monkeypatch, tmp_path):
        """Device probing runs once per computer: reloading the model after
        close() reuses the detected device instead of probing torch again,
        and the model is constructed on that device."""
        monkeypatch.setattr(embeddings, "_bundled_model_path", lambda _name: tmp_path)
        computer = EmbeddingComputer()
        detect = MagicMock(return_value="mps")
        monkeypatch.setattr(computer, "_detect_device", detect)

        first = computer.model
        _ = computer.model
        computer.close()
        second = computer.model

        assert detect.call_count == 1
        assert second is not first  # close() really forced a reload
        assert isinstance(first, SentenceTransformerStub)
        assert isinstance(second, SentenceTransformerStub)
        assert first.device == second.device == "mps"
