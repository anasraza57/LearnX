"""
Embedding generation utilities for RAG system.

Supports multiple embedding models:
- OpenAI embeddings (ada-002)
- Sentence Transformers (local, free)
- Caching for performance
"""

from __future__ import annotations

import hashlib
import pickle
from pathlib import Path
from typing import List, Optional, Literal

import numpy as np

try:
    from ..config import config
except ImportError:
    from src.config import config


EmbeddingModel = Literal["openai", "sentence-transformers"]


class EmbeddingGenerator:
    """
    Generate embeddings for text using various models.

    Supports caching to avoid re-computing embeddings.
    """

    def __init__(
        self,
        model_type: EmbeddingModel = "sentence-transformers",
        model_name: Optional[str] = None,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize embedding generator.

        Args:
            model_type: Type of embedding model
            model_name: Specific model name (default from config)
            cache_dir: Directory for caching embeddings
        """
        self.model_type = model_type
        self.model_name = model_name or config.rag.embedding_model
        self.cache_dir = cache_dir or (config.paths.project_root / "data" / "embeddings_cache")

        # Ensure cache directory exists
        if config.rag.persist_embeddings:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._model = None
        self._client = None

    def _load_model(self):
        """Lazy load the embedding model."""
        if self._model is not None or self._client is not None:
            return

        if self.model_type == "sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )

        elif self.model_type == "openai":
            try:
                import openai
                self._client = openai.OpenAI(api_key=config.model.api_key)
            except ImportError:
                raise ImportError(
                    "openai not installed. "
                    "Install with: pip install openai"
                )

    def embed_text(self, text: str, use_cache: bool = True) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use cached embeddings

        Returns:
            Embedding vector as list of floats
        """
        # Check cache first
        if use_cache and config.rag.persist_embeddings:
            cached = self._load_from_cache(text)
            if cached is not None:
                return cached

        # Load model if needed
        self._load_model()

        # Generate embedding
        if self.model_type == "sentence-transformers":
            embedding = self._model.encode(text, convert_to_numpy=True)
            embedding = embedding.tolist()

        elif self.model_type == "openai":
            response = self._client.embeddings.create(
                model=self.model_name or "text-embedding-ada-002",
                input=text
            )
            embedding = response.data[0].embedding

        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        # Cache the result
        if use_cache and config.rag.persist_embeddings:
            self._save_to_cache(text, embedding)

        return embedding

    def embed_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        use_cache: bool = True,
        show_progress: bool = False,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            use_cache: Whether to use cached embeddings
            show_progress: Whether to show progress bar

        Returns:
            List of embedding vectors
        """
        embeddings = []

        # Check cache for all texts first
        if use_cache and config.rag.persist_embeddings:
            cached_embeddings = {}
            uncached_indices = []

            for i, text in enumerate(texts):
                cached = self._load_from_cache(text)
                if cached is not None:
                    cached_embeddings[i] = cached
                else:
                    uncached_indices.append(i)

            # If all cached, return immediately
            if not uncached_indices:
                return [cached_embeddings[i] for i in range(len(texts))]

            # Compute embeddings for uncached texts
            uncached_texts = [texts[i] for i in uncached_indices]
            new_embeddings = self._compute_batch(uncached_texts, batch_size, show_progress)

            # Combine cached and new embeddings
            new_embed_iter = iter(new_embeddings)
            for i in range(len(texts)):
                if i in cached_embeddings:
                    embeddings.append(cached_embeddings[i])
                else:
                    emb = next(new_embed_iter)
                    embeddings.append(emb)
                    if config.rag.persist_embeddings:
                        self._save_to_cache(texts[i], emb)

        else:
            # Compute all embeddings without caching
            embeddings = self._compute_batch(texts, batch_size, show_progress)

        return embeddings

    def _compute_batch(
        self,
        texts: List[str],
        batch_size: int,
        show_progress: bool,
    ) -> List[List[float]]:
        """Compute embeddings for a batch of texts."""
        self._load_model()

        if self.model_type == "sentence-transformers":
            # Sentence transformers handles batching internally
            embeddings = self._model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=show_progress,
                convert_to_numpy=True,
            )
            return [emb.tolist() for emb in embeddings]

        elif self.model_type == "openai":
            # OpenAI API batching
            all_embeddings = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = self._client.embeddings.create(
                    model=self.model_name or "text-embedding-ada-002",
                    input=batch
                )
                batch_embeddings = [data.embedding for data in response.data]
                all_embeddings.extend(batch_embeddings)

                if show_progress:
                    print(f"Processed {min(i + batch_size, len(texts))}/{len(texts)} texts")

            return all_embeddings

        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text."""
        # Include model name in hash to avoid collisions between models
        content = f"{self.model_type}:{self.model_name}:{text}"
        return hashlib.md5(content.encode()).hexdigest()

    def _load_from_cache(self, text: str) -> Optional[List[float]]:
        """Load embedding from cache if exists."""
        cache_key = self._get_cache_key(text)
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        if cache_file.exists():
            try:
                with open(cache_file, "rb") as f:
                    return pickle.load(f)
            except Exception:
                # Cache corrupted, ignore
                return None

        return None

    def _save_to_cache(self, text: str, embedding: List[float]) -> None:
        """Save embedding to cache."""
        cache_key = self._get_cache_key(text)
        cache_file = self.cache_dir / f"{cache_key}.pkl"

        try:
            with open(cache_file, "wb") as f:
                pickle.dump(embedding, f)
        except Exception as e:
            # Non-critical, just warn
            print(f"Warning: Failed to cache embedding: {e}")

    def clear_cache(self) -> int:
        """
        Clear all cached embeddings.

        Returns:
            Number of cache files deleted
        """
        if not self.cache_dir.exists():
            return 0

        count = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                cache_file.unlink()
                count += 1
            except Exception:
                pass

        return count


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity in range [-1, 1]
    """
    v1 = np.array(vec1)
    v2 = np.array(vec2)

    dot_product = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


# Convenience functions

def embed_documents(
    documents: List,
    model_type: EmbeddingModel = "sentence-transformers",
    show_progress: bool = True,
) -> List:
    """
    Embed a list of Document objects in-place.

    Args:
        documents: List of Document objects
        model_type: Embedding model to use
        show_progress: Whether to show progress

    Returns:
        Same list with embeddings filled in
    """
    generator = EmbeddingGenerator(model_type=model_type)

    texts = [doc.content for doc in documents]
    embeddings = generator.embed_batch(texts, show_progress=show_progress)

    for doc, embedding in zip(documents, embeddings):
        doc.embedding = embedding

    return documents
