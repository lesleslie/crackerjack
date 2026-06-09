"""Unit tests for the EmbeddingService in ``crackerjack.services.ai.embeddings``.

The EmbeddingService uses an ONNX session in production, but when the model is
unavailable it falls back to a deterministic SHA-256-based pseudo-embedding of
length 384. The tests in this file exercise the public API surface and the
fallback path (which is what ``is_model_available()`` returns in the test
environment).

We deliberately avoid loading the real ONNX model — the module already
redirects ``sys.stderr`` at import time and logs a warning when no session is
available, but no network or model download is required because the session
slot stays ``None``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.models.semantic_models import SemanticConfig
from crackerjack.services.ai.embeddings import EmbeddingService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> SemanticConfig:
    return SemanticConfig(
        embedding_model="fake-embedding-model",
        chunk_size=500,
    )


@pytest.fixture
def service(config: SemanticConfig) -> EmbeddingService:
    # Force the service into the "model not loaded" state. _load_model is
    # bypassed entirely so the test does not need a real tokenizer.
    svc = EmbeddingService(config)
    svc._model_loaded = False
    svc._session = None
    svc._tokenizer = None
    return svc


# ---------------------------------------------------------------------------
# Construction / state
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_init_sets_attributes(self, config: SemanticConfig) -> None:
        svc = EmbeddingService(config)
        assert svc.config is config
        assert svc._session is None
        assert svc._tokenizer is None
        assert svc._model_loaded is False

    def test_session_raises_when_unavailable(self, service: EmbeddingService) -> None:
        """``session`` property raises RuntimeError when load leaves session None.

        ``_load_model`` swallows internal exceptions and sets ``_model_loaded = True``
        with ``_session = None``. The session property then re-raises with a
        clear message.
        """
        with patch.object(service, "_load_model") as load:
            load.side_effect = lambda: setattr(service, "_model_loaded", True)
            service._model_loaded = True
            service._session = None
            service._tokenizer = None
            with pytest.raises(RuntimeError, match="Failed to load ONNX model"):
                _ = service.session

    def test_tokenizer_raises_when_unavailable(self, service: EmbeddingService) -> None:
        service._model_loaded = True
        service._session = None
        service._tokenizer = None
        with pytest.raises(RuntimeError, match="Failed to load tokenizer"):
            _ = service.tokenizer


# ---------------------------------------------------------------------------
# _load_model — failure path
# ---------------------------------------------------------------------------


class TestLoadModel:
    def test_load_model_failure_clears_state(self, service: EmbeddingService) -> None:
        """If AutoTokenizer raises, _session/_tokenizer must end up None and
        _model_loaded must flip to True so we don't loop forever."""
        with patch(
            "crackerjack.services.ai.embeddings.AutoTokenizer.from_pretrained",
            side_effect=OSError("boom"),
        ):
            service._load_model()

        assert service._session is None
        assert service._tokenizer is None
        assert service._model_loaded is True

    def test_load_model_success_sets_tokenizer(self, service: EmbeddingService) -> None:
        """When AutoTokenizer returns, _tokenizer is populated and the session
        stays None (no ONNX runtime in test env)."""
        sentinel = object()
        with patch(
            "crackerjack.services.ai.embeddings.AutoTokenizer.from_pretrained",
            return_value=sentinel,
        ):
            service._load_model()

        assert service._tokenizer is sentinel
        assert service._session is None
        assert service._model_loaded is True


# ---------------------------------------------------------------------------
# generate_embedding
# ---------------------------------------------------------------------------


class TestGenerateEmbedding:
    def test_empty_text_raises(self, service: EmbeddingService) -> None:
        with pytest.raises(ValueError, match="empty text"):
            service.generate_embedding("")
        with pytest.raises(ValueError, match="empty text"):
            service.generate_embedding("   \n\t  ")

    def test_returns_384_dim_list(self, service: EmbeddingService) -> None:
        emb = service.generate_embedding("hello world")
        assert isinstance(emb, list)
        assert len(emb) == 384
        for v in emb:
            assert isinstance(v, float)

    def test_embedding_deterministic_for_same_input(
        self, service: EmbeddingService
    ) -> None:
        """The fallback embedding is purely a function of the SHA-256 hash, so
        repeated calls with the same input must produce identical output."""
        a = service.generate_embedding("reproducible")
        b = service.generate_embedding("reproducible")
        assert a == b

    def test_embedding_differs_for_different_inputs(
        self, service: EmbeddingService
    ) -> None:
        a = service.generate_embedding("alpha")
        b = service.generate_embedding("omega")
        assert a != b

    def test_embedding_values_in_unit_range(self, service: EmbeddingService) -> None:
        """All 384 dims should be either 0.0 or in [0, 1] (the fallback
        divides hex pairs by 255 and pads with 0.0)."""
        emb = service.generate_embedding("normalize me")
        for v in emb:
            assert 0.0 <= v <= 1.0

    def test_known_text_produces_known_prefix(
        self, service: EmbeddingService
    ) -> None:
        """The fallback reads 48 hex pairs (96 chars) × 8 = 384 dims, so the
        embedding is fully determined by the SHA-256 of the input."""
        text = "test-prefix-fixture"
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        # First pair is the first 2 hex chars of the hash, divided by 255.
        expected_first = int(text_hash[0:2], 16) / 255.0
        emb = service.generate_embedding(text)
        assert emb[0] == pytest.approx(expected_first)
        # The first 8 values should all be that same first-pair value
        # (the fallback broadcasts each pair 8 times).
        for v in emb[:8]:
            assert v == pytest.approx(expected_first)

    def test_internal_exception_is_wrapped(self, service: EmbeddingService) -> None:
        with patch.object(
            service,
            "_generate_fallback_embedding",
            side_effect=RuntimeError("inner boom"),
        ):
            with pytest.raises(RuntimeError, match="Embedding generation failed"):
                service.generate_embedding("anything")


# ---------------------------------------------------------------------------
# generate_embeddings_batch
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingsBatch:
    def test_empty_list_raises(self, service: EmbeddingService) -> None:
        with pytest.raises(ValueError, match="empty text list"):
            service.generate_embeddings_batch([])

    def test_all_empty_texts_raises(self, service: EmbeddingService) -> None:
        with pytest.raises(ValueError, match="All texts are empty"):
            service.generate_embeddings_batch(["", "   ", "\n"])

    def test_mixed_empty_and_valid(self, service: EmbeddingService) -> None:
        """Empty inputs are skipped in the source; result[i] for an empty
        text i stays as ``[]``. We pin that contract here so the contract
        is visible in the test."""
        result = service.generate_embeddings_batch(["", "valid", "\t", "also"])
        assert len(result) == 4
        # Empty slots stay empty.
        assert result[0] == []
        assert result[2] == []
        # Valid slots get the 384-dim fallback.
        assert len(result[1]) == 384
        assert len(result[3]) == 384

    def test_single_text_batch(self, service: EmbeddingService) -> None:
        result = service.generate_embeddings_batch(["hi"])
        assert len(result) == 1
        assert len(result[0]) == 384

    def test_internal_exception_is_wrapped(self, service: EmbeddingService) -> None:
        with patch.object(
            service,
            "_generate_fallback_embedding",
            side_effect=RuntimeError("inner"),
        ):
            with pytest.raises(RuntimeError, match="Batch embedding generation failed"):
                service.generate_embeddings_batch(["a", "b"])


# ---------------------------------------------------------------------------
# calculate_similarity
# ---------------------------------------------------------------------------


class TestCalculateSimilarity:
    def test_empty_either_side_raises(self, service: EmbeddingService) -> None:
        with pytest.raises(ValueError, match="empty embeddings"):
            service.calculate_similarity([], [1.0, 2.0])
        with pytest.raises(ValueError, match="empty embeddings"):
            service.calculate_similarity([1.0, 2.0], [])

    def test_dimension_mismatch_raises(self, service: EmbeddingService) -> None:
        with pytest.raises(ValueError, match="dimensions mismatch"):
            service.calculate_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_identical_vectors_score_one(self, service: EmbeddingService) -> None:
        v = [0.1, 0.2, 0.3, 0.4]
        assert service.calculate_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self, service: EmbeddingService) -> None:
        # A unit vector and a vector that's a 90-degree rotation
        # produce a dot product of 0 -> similarity 0.
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert service.calculate_similarity(a, b) == pytest.approx(0.0)

    def test_zero_vector_returns_zero(self, service: EmbeddingService) -> None:
        # Division-by-zero is guarded: if either norm is 0, the result is 0.0.
        assert service.calculate_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
        assert service.calculate_similarity([1.0, 0.0], [0.0, 0.0]) == 0.0

    def test_result_clamped_to_unit_range(self, service: EmbeddingService) -> None:
        # Force a hypothetical >1 dot product via a very large vector.
        # The helper clamps to [0, 1].
        big = [10.0, 10.0, 10.0]
        result = service.calculate_similarity(big, big)
        assert 0.0 <= result <= 1.0

    def test_internal_exception_is_wrapped(self, service: EmbeddingService) -> None:
        # Force numpy to blow up inside the helper.
        with patch("crackerjack.services.ai.embeddings.np.dot", side_effect=ValueError("x")):
            with pytest.raises(RuntimeError, match="Similarity calculation failed"):
                service.calculate_similarity([1.0, 2.0], [1.0, 2.0])


# ---------------------------------------------------------------------------
# calculate_similarities_batch
# ---------------------------------------------------------------------------


class TestCalculateSimilaritiesBatch:
    def test_empty_query_raises(self, service: EmbeddingService) -> None:
        with pytest.raises(ValueError, match="Query embedding cannot be empty"):
            service.calculate_similarities_batch([], [[1.0, 2.0]])

    def test_empty_embeddings_raises(self, service: EmbeddingService) -> None:
        with pytest.raises(ValueError, match="Embeddings list cannot be empty"):
            service.calculate_similarities_batch([1.0, 2.0], [])

    def test_returns_one_score_per_input(self, service: EmbeddingService) -> None:
        query = [1.0, 0.0, 0.0]
        embs = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.5, 0.5, 0.0]]
        result = service.calculate_similarities_batch(query, embs)
        assert len(result) == 3
        # Identical vector -> 1.0
        assert result[0] == pytest.approx(1.0)
        # Orthogonal -> 0.0
        assert result[1] == pytest.approx(0.0)

    def test_zero_query_returns_zeros(self, service: EmbeddingService) -> None:
        result = service.calculate_similarities_batch(
            [0.0, 0.0, 0.0], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        )
        assert result == [0.0, 0.0]

    def test_internal_exception_is_wrapped(self, service: EmbeddingService) -> None:
        with patch(
            "crackerjack.services.ai.embeddings.np.dot", side_effect=ValueError("x")
        ):
            with pytest.raises(RuntimeError, match="Batch similarity calculation failed"):
                service.calculate_similarities_batch([1.0, 0.0], [[1.0, 0.0]])


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------


class TestHashes:
    def test_get_text_hash_is_sha256(self, service: EmbeddingService) -> None:
        h = service.get_text_hash("hello")
        assert h == hashlib.sha256(b"hello").hexdigest()
        assert len(h) == 64

    def test_get_text_hash_empty(self, service: EmbeddingService) -> None:
        assert service.get_text_hash("") == hashlib.sha256(b"").hexdigest()

    def test_get_file_hash_utf8(self, service: EmbeddingService, tmp_path: Path) -> None:
        p = tmp_path / "a.txt"
        p.write_text("hello", encoding="utf-8")
        assert service.get_file_hash(p) == service.get_text_hash("hello")

    def test_get_file_hash_binary(
        self, service: EmbeddingService, tmp_path: Path
    ) -> None:
        p = tmp_path / "a.bin"
        p.write_bytes(b"\x00\x01\x02")
        # bytes content read directly via the UnicodeDecodeError branch
        assert service.get_file_hash(p) == hashlib.sha256(b"\x00\x01\x02").hexdigest()


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_empty_returns_empty(self, service: EmbeddingService) -> None:
        assert service.chunk_text("") == []
        assert service.chunk_text("   \n  ") == []

    def test_short_text_single_chunk(self, service: EmbeddingService) -> None:
        chunks = service.chunk_text("This is a sentence.")
        assert chunks == ["This is a sentence."]

    def test_multiple_sentences_stay_under_limit(
        self, service: EmbeddingService,
    ) -> None:
        # config.chunk_size is 500, so two short sentences fit in one chunk.
        chunks = service.chunk_text("First sentence. Second sentence.")
        assert len(chunks) == 1
        assert "First sentence" in chunks[0]

    def test_chunks_respect_size(
        self, config: SemanticConfig,
    ) -> None:
        # Build a service with a tiny chunk_size to force splitting.
        cfg = config.model_copy(update={"chunk_size": 30})
        svc = EmbeddingService(cfg)
        text = "First short. Second short. Third short. Fourth short."
        chunks = svc.chunk_text(text)
        assert len(chunks) >= 2
        for c in chunks:
            assert len(c) <= 30

    def test_no_terminator_returns_single_chunk(
        self, service: EmbeddingService,
    ) -> None:
        # A block with no sentence-ending punctuation becomes one chunk
        # because the helper falls back to the full text.
        chunks = service.chunk_text("no terminators here at all")
        assert chunks == ["no terminators here at all"]


# ---------------------------------------------------------------------------
# is_model_available / get_model_info
# ---------------------------------------------------------------------------


class TestModelAvailability:
    def test_unavailable_when_session_none(self, service: EmbeddingService) -> None:
        assert service._session is None
        # _load_model is patched to swallow the missing tokenizer.
        with patch.object(service, "_load_model") as load:
            load.side_effect = lambda: setattr(service, "_model_loaded", True)
            service._model_loaded = True
            assert service.is_model_available() is False
            load.assert_not_called()  # already loaded -> early return

    def test_get_model_info_unavailable(self, service: EmbeddingService) -> None:
        service._model_loaded = True  # short-circuit the lazy load
        info = service.get_model_info()
        assert info["model_name"] == "fake-embedding-model"
        assert info["loaded"] is False
        assert info["embedding_dimension"] == 384
        assert "error" in info

    def test_get_model_info_loaded_with_fallback(
        self, service: EmbeddingService,
    ) -> None:
        service._model_loaded = True
        service._session = MagicMock(name="onnx-session")
        info = service.get_model_info()
        assert info["model_name"] == "fake-embedding-model"
        assert info["loaded"] is True
        assert info["embedding_dimension"] == 384
        assert info["device"] == "cpu"
        assert info["max_seq_length"] == "unknown"

    def test_get_model_info_loaded_but_fails(
        self, service: EmbeddingService,
    ) -> None:
        service._model_loaded = True
        service._session = MagicMock(name="onnx-session")
        with patch.object(
            service,
            "_generate_fallback_embedding",
            side_effect=RuntimeError("boom"),
        ):
            info = service.get_model_info()
        assert info["loaded"] is True
        assert "error" in info
        assert "boom" in info["error"]
