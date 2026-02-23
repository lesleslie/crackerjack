import hashlib
import logging
import os
import sys
import typing as t
import warnings
from io import StringIO
from pathlib import Path

import numpy as np

try:
    import onnxruntime as ort

    ONNXRUNTIME_AVAILABLE = True
except ImportError:
    ort: t.Any = None  # type: ignore[assignment]:  # type: ignore[comment]:  # type: ignore[comment]:  # type: ignore[comment]:  # type: ignore[comment]:  # type: ignore[comment]
    ONNXRUNTIME_AVAILABLE = False

_original_stderr = sys.stderr
sys.stderr = StringIO()

os.environ["TRANSFORMERS_VERBOSITY"] = "error"

try:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        from transformers import AutoTokenizer
finally:
    sys.stderr = _original_stderr

from crackerjack.models.semantic_models import SemanticConfig

TokenizerType = AutoTokenizer | object

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, config: SemanticConfig) -> None:
        self.config = config
        self._session: t.Any = None
        self._tokenizer: TokenizerType | None = None
        self._model_loaded = False
        self._backend: t.Literal["onnxruntime", "ollama", "fallback"] = (
            self._determine_backend()
        )
        self._ollama_available: bool = False

    def _determine_backend(self) -> t.Literal["onnxruntime", "ollama", "fallback"]:
        requested = self.config.embedding_backend

        if requested == "fallback":
            return "fallback"

        if requested == "ollama":
            return "ollama"

        if requested == "onnxruntime":
            if ONNXRUNTIME_AVAILABLE:
                return "onnxruntime"
            logger.warning(
                "onnxruntime requested but not available, falling back to fallback"
            )
            return "fallback"

        if ONNXRUNTIME_AVAILABLE:
            logger.info("Using onnxruntime backend (auto-detected)")
            return "onnxruntime"

        if self._check_ollama_available():
            logger.info("Using Ollama backend (auto-detected)")
            return "ollama"

        logger.info("Using fallback backend (no other backend available)")
        return "fallback"

    def _check_ollama_available(self) -> bool:
        try:
            import urllib.request

            req = urllib.request.Request(
                f"{self.config.ollama_base_url}/api/tags",
                method="GET",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    self._ollama_available = True
                    return True
        except Exception:
            self._ollama_available = False
            return False
        return False

    @property
    def session(self) -> t.Any:
        if not self._model_loaded:
            self._load_model()
        if self._session is None and self._backend == "onnxruntime":
            msg = f"Failed to load ONNX model: {self.config.embedding_model}"
            raise RuntimeError(msg)
        return self._session

    @property
    def tokenizer(self) -> TokenizerType:
        if not self._model_loaded:
            self._load_model()
        if self._tokenizer is None and self._backend == "onnxruntime":
            msg = f"Failed to load tokenizer: {self.config.embedding_model}"
            raise RuntimeError(msg)
        return self._tokenizer

    def _load_model(self) -> None:
        if self._backend == "onnxruntime":
            self._load_onnx_model()
        elif self._backend == "ollama":
            self._load_ollama_model()
        else:
            self._load_fallback_model()

    def _load_onnx_model(self) -> None:
        try:
            logger.info(f"Loading ONNX embedding model: {self.config.embedding_model}")

            model_name = self.config.embedding_model

            self._tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                revision="main",  # nosec B615
            )

            self._session = None
            self._model_loaded = True

            logger.info(
                f"Successfully loaded tokenizer for: {self.config.embedding_model}",
            )
            logger.warning(
                "ONNX session not implemented yet - using fallback embeddings",
            )

        except Exception as e:
            logger.exception(
                f"Failed to load embedding model {self.config.embedding_model}: {e}",
            )
            self._session = None
            self._tokenizer = None
            self._model_loaded = True

    def _load_ollama_model(self) -> None:
        logger.info(f"Using Ollama backend at {self.config.ollama_base_url}")
        if not self._ollama_available:
            if not self._check_ollama_available():
                logger.warning(
                    f"Ollama not available at {self.config.ollama_base_url}, falling back to hash-based embeddings"
                )
                self._backend = "fallback"
        self._model_loaded = True

    def _load_fallback_model(self) -> None:
        logger.info("Using fallback hash-based embeddings")
        self._model_loaded = True

    def generate_embedding(self, text: str) -> list[float]:
        if not text.strip():
            msg = "Cannot generate embedding for empty text"
            raise ValueError(msg)

        try:
            if self._backend == "ollama":
                return self._generate_ollama_embedding(text)
            elif self._backend == "onnxruntime":
                return self._generate_onnx_embedding(text)
            else:
                return self._generate_fallback_embedding(text)

        except Exception as e:
            logger.exception(f"Failed to generate embedding for text: {e}")
            msg = f"Embedding generation failed: {e}"
            raise RuntimeError(msg) from e

    def _generate_onnx_embedding(self, text: str) -> list[float]:

        return self._generate_fallback_embedding(text)

    def _generate_ollama_embedding(self, text: str) -> list[float]:
        try:
            import json
            import urllib.request

            if not self._ollama_available and not self._check_ollama_available():
                logger.warning(
                    "Ollama became unavailable, falling back to hash-based embeddings"
                )
                self._backend = "fallback"
                return self._generate_fallback_embedding(text)

            data = {
                "model": self.config.embedding_model,
                "prompt": text,
            }

            req = urllib.request.Request(
                f"{self.config.ollama_base_url}/api/embeddings",
                method="POST",
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(
                req, timeout=30, data=json.dumps(data).encode()
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"Ollama returned status {response.status}")

                result = json.loads(response.read().decode())
                embedding = result.get("embedding")

                if not embedding:
                    raise RuntimeError("Ollama returned no embedding")

                logger.debug(
                    f"Generated Ollama embedding with dimension {len(embedding)}"
                )
                return embedding

        except Exception as e:
            logger.exception(f"Failed to generate Ollama embedding: {e}")

            return self._generate_fallback_embedding(text)

    def _generate_fallback_embedding(self, text: str) -> list[float]:
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        embedding = []
        for i in range(0, min(len(text_hash), 96), 2):
            hex_pair = text_hash[i : i + 2]
            value = int(hex_pair, 16) / 255.0
            embedding.extend([value] * 8)

        while len(embedding) < 384:
            embedding.append(0.0)

        return embedding[:384]

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            msg = "Cannot generate embeddings for empty text list"
            raise ValueError(msg)

        valid_texts = []
        valid_indices = []

        for i, text in enumerate(texts):
            if text.strip():
                valid_texts.append(text)
                valid_indices.append(i)

        if not valid_texts:
            msg = "All texts are empty - cannot generate embeddings"
            raise ValueError(msg)

        try:
            logger.debug(
                f"Generating embeddings for {len(valid_texts)} texts using {self._backend} backend"
            )

            result: list[list[float]] = [[] for _ in texts]

            for i, text in enumerate(valid_texts):
                original_index = valid_indices[i]
                embedding = self.generate_embedding(text)
                result[original_index] = embedding

            return result

        except Exception as e:
            logger.exception(f"Failed to generate batch embeddings: {e}")
            msg = f"Batch embedding generation failed: {e}"
            raise RuntimeError(msg) from e

    def calculate_similarity(
        self,
        embedding1: list[float],
        embedding2: list[float],
    ) -> float:
        if not embedding1 or not embedding2:
            msg = "Cannot calculate similarity for empty embeddings"
            raise ValueError(msg)

        if len(embedding1) != len(embedding2):
            msg = (
                f"Embedding dimensions mismatch: {len(embedding1)} vs {len(embedding2)}"
            )
            raise ValueError(msg)

        try:
            vec1 = np.array(embedding1, dtype=np.float32)
            vec2 = np.array(embedding2, dtype=np.float32)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if 0 in (norm1, norm2):
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            return max(0.0, min(1.0, float(similarity)))

        except Exception as e:
            logger.exception(f"Failed to calculate similarity: {e}")
            msg = f"Similarity calculation failed: {e}"
            raise RuntimeError(msg) from e

    def calculate_similarities_batch(
        self,
        query_embedding: list[float],
        embeddings: list[list[float]],
    ) -> list[float]:
        if not query_embedding:
            msg = "Query embedding cannot be empty"
            raise ValueError(msg)

        if not embeddings:
            msg = "Embeddings list cannot be empty"
            raise ValueError(msg)

        try:
            query_vec = np.array(query_embedding, dtype=np.float32)
            embedding_matrix = np.array(embeddings, dtype=np.float32)

            dot_products = np.dot(embedding_matrix, query_vec)
            query_norm = np.linalg.norm(query_vec)
            embedding_norms = np.linalg.norm(embedding_matrix, axis=1)

            if query_norm == 0:
                return [0.0] * len(embeddings)

            similarities = dot_products / (query_norm * embedding_norms)

            similarities = np.nan_to_num(similarities, nan=0.0)
            similarities = np.clip(similarities, 0.0, 1.0)

            return similarities.tolist()

        except Exception as e:
            logger.exception(f"Failed to calculate batch similarities: {e}")
            msg = f"Batch similarity calculation failed: {e}"
            raise RuntimeError(msg) from e

    def get_text_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get_file_hash(self, file_path: Path) -> str:
        try:
            content = file_path.read_text(encoding="utf-8")
            return self.get_text_hash(content)
        except UnicodeDecodeError:
            content_bytes = file_path.read_bytes()
            return hashlib.sha256(content_bytes).hexdigest()

    def chunk_text(self, text: str) -> list[str]:
        if not text.strip():
            return []

        sentences = self._split_into_sentences(text)
        chunks = []

        current_chunk = ""
        overlap_sentences: list[str] = []

        for sentence in sentences:
            potential_chunk = current_chunk + sentence

            if len(potential_chunk) <= self.config.chunk_size:
                current_chunk = potential_chunk
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())

                overlap_text = (
                    "".join(overlap_sentences[-2:]) if overlap_sentences else ""
                )
                current_chunk = overlap_text + sentence

            overlap_sentences.append(sentence)

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _split_into_sentences(self, text: str) -> list[str]:
        sentences = []
        current_sentence = ""

        for char in text:
            current_sentence += char
            if char in ".!?" and len(current_sentence.strip()) > 1:
                sentences.append(current_sentence.strip())
                current_sentence = ""

        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        return sentences or [text]

    def get_model_info(self) -> dict[str, t.Any]:
        if not self._model_loaded:
            try:
                self._load_model()
            except Exception as e:
                return {
                    "backend": self._backend,
                    "model_name": self.config.embedding_model,
                    "loaded": False,
                    "error": str(e),
                    "embedding_dimension": self.config.embedding_dimension,
                }

        try:
            if self._backend == "ollama":
                return {
                    "backend": "ollama",
                    "model_name": self.config.embedding_model,
                    "loaded": self._ollama_available,
                    "embedding_dimension": None,
                    "device": "ollama-server",
                    "base_url": self.config.ollama_base_url,
                }
            elif self._backend == "onnxruntime":
                test_embedding = self._generate_fallback_embedding("test")
                return {
                    "backend": "onnxruntime",
                    "model_name": self.config.embedding_model,
                    "loaded": self._session is not None,
                    "max_seq_length": "unknown",
                    "embedding_dimension": len(test_embedding),
                    "device": "cpu",
                }
            else:
                test_embedding = self._generate_fallback_embedding("test")
                return {
                    "backend": "fallback",
                    "model_name": "hash-based",
                    "loaded": True,
                    "embedding_dimension": len(test_embedding),
                    "device": "cpu",
                }
        except Exception as e:
            return {
                "backend": self._backend,
                "model_name": self.config.embedding_model,
                "loaded": False,
                "error": str(e),
            }

    def is_model_available(self) -> bool:
        if not self._model_loaded:
            try:
                self._load_model()
            except Exception:
                return False

        if self._backend == "onnxruntime":
            return self._session is not None
        elif self._backend == "ollama":
            return self._ollama_available
        else:
            return True
