"""
Vector store management for RAG system using ChromaDB.

Features:
- Store and retrieve document embeddings
- Semantic search
- Metadata filtering
- Persistence
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

try:
    from ..config import config
    from .document_loader import Document
    from .embeddings import EmbeddingGenerator
except ImportError:
    from src.config import config
    from src.utils.document_loader import Document
    from src.utils.embeddings import EmbeddingGenerator


class VectorStore:
    """
    Vector store for document embeddings using ChromaDB.

    Provides semantic search over document collection.
    """

    def __init__(
        self,
        collection_name: str = "documents",
        persist_directory: Optional[Path] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize vector store.

        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory for persistence (default from config)
            embedding_generator: Custom embedding generator (optional)
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory or config.rag.vectorstore_path or (
            config.paths.project_root / "data" / "vectorstore"
        )
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.embedding_generator = embedding_generator or EmbeddingGenerator()

        # Lazy load ChromaDB
        self._client = None
        self._collection = None

    def _get_client(self):
        """Lazy load ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings

                self._client = chromadb.PersistentClient(
                    path=str(self.persist_directory),
                    settings=Settings(anonymized_telemetry=False)
                )
            except ImportError:
                raise ImportError(
                    "chromadb not installed. "
                    "Install with: pip install chromadb"
                )

        return self._client

    def _get_collection(self):
        """Get or create ChromaDB collection."""
        if self._collection is None:
            client = self._get_client()

            # Get or create collection
            try:
                self._collection = client.get_collection(name=self.collection_name)
            except:
                self._collection = client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "EduGPT RAG document store"}
                )

        return self._collection

    def add_documents(
        self,
        documents: List[Document],
        show_progress: bool = True,
    ) -> int:
        """
        Add documents to the vector store.

        Args:
            documents: List of Document objects
            show_progress: Whether to show progress

        Returns:
            Number of documents added
        """
        if not documents:
            return 0

        collection = self._get_collection()

        # Generate embeddings if not already present
        docs_to_embed = [doc for doc in documents if doc.embedding is None]

        if docs_to_embed:
            if show_progress:
                print(f"Generating embeddings for {len(docs_to_embed)} documents...")

            texts = [doc.content for doc in docs_to_embed]
            embeddings = self.embedding_generator.embed_batch(
                texts,
                show_progress=show_progress
            )

            for doc, embedding in zip(docs_to_embed, embeddings):
                doc.embedding = embedding

        # Prepare data for ChromaDB
        ids = []
        contents = []
        embeddings = []
        metadatas = []

        for doc in documents:
            doc_id = doc.metadata.get("chunk_id", doc.metadata.get("source", "unknown"))

            ids.append(doc_id)
            contents.append(doc.content)
            embeddings.append(doc.embedding)

            # ChromaDB metadata must be flat dict with simple types
            metadata = {
                k: v for k, v in doc.metadata.items()
                if isinstance(v, (str, int, float, bool))
            }
            metadatas.append(metadata)

        # Add to collection
        collection.add(
            ids=ids,
            documents=contents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        if show_progress:
            print(f"Added {len(documents)} documents to vector store")

        return len(documents)

    def search(
        self,
        query: str,
        top_k: int = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
        min_similarity: Optional[float] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Semantic search over document collection.

        Args:
            query: Search query
            top_k: Number of results to return (default from config)
            metadata_filter: Filter by metadata (e.g., {"source": "file.pdf"})
            min_similarity: Minimum similarity threshold

        Returns:
            List of (Document, similarity_score) tuples, sorted by relevance
        """
        top_k = top_k or config.rag.top_k
        min_similarity = min_similarity or config.rag.similarity_threshold

        collection = self._get_collection()

        # Generate query embedding
        query_embedding = self.embedding_generator.embed_text(query)

        # Search
        where_filter = metadata_filter if metadata_filter else None

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
        )

        # Parse results
        documents = []

        if results and results["ids"] and len(results["ids"]) > 0:
            for i in range(len(results["ids"][0])):
                content = results["documents"][0][i]
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i] if "distances" in results else None

                # Convert distance to similarity (assuming cosine distance)
                # ChromaDB returns L2 distance by default, convert to similarity
                similarity = 1.0 - (distance / 2.0) if distance is not None else 1.0

                # Filter by minimum similarity
                if similarity < min_similarity:
                    continue

                doc = Document(content=content, metadata=metadata)
                documents.append((doc, similarity))

        return documents

    def delete_all(self) -> int:
        """
        Delete all documents from the collection.

        Returns:
            Number of documents deleted
        """
        collection = self._get_collection()

        # Get all IDs
        all_data = collection.get()
        count = len(all_data["ids"]) if all_data["ids"] else 0

        if count > 0:
            collection.delete(ids=all_data["ids"])

        return count

    def get_count(self) -> int:
        """Get number of documents in the collection."""
        collection = self._get_collection()
        return collection.count()

    def get_all_documents(self) -> List[Document]:
        """
        Retrieve all documents from the collection.

        Returns:
            List of all Document objects
        """
        collection = self._get_collection()

        all_data = collection.get()

        documents = []
        if all_data and all_data["ids"]:
            for i in range(len(all_data["ids"])):
                content = all_data["documents"][i]
                metadata = all_data["metadatas"][i]

                doc = Document(content=content, metadata=metadata)
                documents.append(doc)

        return documents


# Convenience functions

def initialize_vector_store_from_directory(
    directory: Path | str,
    collection_name: str = "documents",
    force_reload: bool = False,
    show_progress: bool = True,
) -> VectorStore:
    """
    Initialize vector store with documents from a directory.

    Args:
        directory: Directory containing documents
        collection_name: Name for the collection
        force_reload: If True, delete existing collection and reload
        show_progress: Whether to show progress

    Returns:
        Initialized VectorStore

    Example:
        >>> store = initialize_vector_store_from_directory("data/documents")
        >>> results = store.search("machine learning")
    """
    from .document_loader import load_documents_from_directory

    store = VectorStore(collection_name=collection_name)

    # Check if already initialized
    if force_reload or store.get_count() == 0:
        if force_reload and store.get_count() > 0:
            if show_progress:
                print(f"Deleting {store.get_count()} existing documents...")
            store.delete_all()

        # Load documents
        if show_progress:
            print(f"Loading documents from {directory}...")

        documents = load_documents_from_directory(directory)

        if not documents:
            print(f"Warning: No documents found in {directory}")
            return store

        if show_progress:
            print(f"Loaded {len(documents)} document chunks")

        # Add to vector store
        store.add_documents(documents, show_progress=show_progress)

    else:
        if show_progress:
            print(f"Vector store already initialized with {store.get_count()} documents")

    return store
