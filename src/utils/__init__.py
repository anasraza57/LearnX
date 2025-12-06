"""
Utility modules for LearnX.

This module contains utility functions:
- validation: JSON Schema validation with auto-repair
- progress: Analytics and progress tracking helpers
- document_loader: Load and chunk documents for RAG
- embeddings: Generate embeddings for semantic search
- vector_store: ChromaDB vector store for RAG
"""

from .validation import (
    SyllabusValidator,
    LearnerProfileValidator,
    validate_syllabus,
    validate_learner_profile,
)
from .progress import (
    mastery_histogram,
    mastery_summary,
    mastery_percentile,
    mastery_by_category,
    learning_velocity,
)
from .document_loader import (
    Document,
    DocumentLoader,
    load_documents_from_directory,
)
from .embeddings import (
    EmbeddingGenerator,
    cosine_similarity,
    embed_documents,
)
from .vector_store import (
    VectorStore,
    initialize_vector_store_from_directory,
)
from .persistence import (
    TeachingSessionPersistence,
    get_persistence_manager,
    save_teaching_session,
    load_teaching_session,
)

__all__ = [
    # Validation
    "SyllabusValidator",
    "LearnerProfileValidator",
    "validate_syllabus",
    "validate_learner_profile",
    # Progress analytics
    "mastery_histogram",
    "mastery_summary",
    "mastery_percentile",
    "mastery_by_category",
    "learning_velocity",
    # RAG - Document loading
    "Document",
    "DocumentLoader",
    "load_documents_from_directory",
    # RAG - Embeddings
    "EmbeddingGenerator",
    "cosine_similarity",
    "embed_documents",
    # RAG - Vector store
    "VectorStore",
    "initialize_vector_store_from_directory",
    # Persistence
    "TeachingSessionPersistence",
    "get_persistence_manager",
    "save_teaching_session",
    "load_teaching_session",
]
