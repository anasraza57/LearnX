"""
Configuration management for EduGPT-PersonalisedLearning.

This module centralizes all configuration settings following 12-factor app principles:
- Secrets loaded from environment variables
- Sensible defaults for development
- Type hints for IDE support
- Single source of truth for all settings
- Thread-safe token tracking
- Production-ready validation
"""

import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional


@dataclass
class ModelConfig:
    """LLM model configuration with OpenAI API settings."""

    # OpenAI settings (env-driven for flexibility)
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model_name: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    )
    base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL")
    )
    organization: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_ORG")
    )
    project: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_PROJECT"))

    temperature: float = 0.7
    max_tokens: int = 2000

    # Agent-specific temperatures
    planner_temperature: float = 0.9
    instructor_temperature: float = 0.7
    assessment_temperature: float = 0.5

    # Guardrails
    max_turns: int = 10
    max_retries: int = 3
    retry_delay: float = field(
        default_factory=lambda: float(os.getenv("RETRY_DELAY", "1.0"))
    )
    request_timeout: float = field(
        default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT", "60.0"))
    )
    retry_backoff: float = field(
        default_factory=lambda: float(os.getenv("RETRY_BACKOFF", "2.0"))
    )

    # Reproducibility
    deterministic: bool = False  # Set to True for reproducible outputs (temp=0)
    random_seed: int = 42  # Used in deterministic mode

    def __post_init__(self):
        """Apply deterministic mode if enabled with full seed locking."""
        if self.deterministic:
            # Zero all temperatures
            self.temperature = 0.0
            self.planner_temperature = 0.0
            self.instructor_temperature = 0.0
            self.assessment_temperature = 0.0

            # Set global random seeds for reproducibility
            try:
                import random

                random.seed(self.random_seed)
            except ImportError:
                pass

            try:
                import numpy as np

                np.random.seed(self.random_seed)
            except ImportError:
                pass


@dataclass
class RAGConfig:
    """Retrieval-Augmented Generation configuration."""

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384  # Dimension for all-MiniLM-L6-v2

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 150

    # Retrieval
    top_k: int = 5
    top_k_fallback: int = 8  # Retry with more docs if first attempt fails
    min_citations: int = 1
    similarity_threshold: float = 0.5  # Minimum similarity score (0, 1]

    # Embeddings cache
    persist_embeddings: bool = True  # Cache embeddings by file hash

    # Vector store path (set from PathConfig to avoid duplication)
    vectorstore_path: Optional[Path] = None

    def __post_init__(self):
        """Validate and set vectorstore path from PathConfig."""
        # Sanity check: chunk_overlap must be less than chunk_size
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be < chunk_size ({self.chunk_size})"
            )

        # Set vectorstore_path from PathConfig (single source of truth)
        if self.vectorstore_path is None:
            # Lazy import to avoid circular dependency
            # This will be set properly when Config initializes
            pass


@dataclass
class AssessmentConfig:
    """Assessment and quiz configuration."""

    # Difficulty levels
    difficulty_levels: tuple = ("easy", "medium", "hard")
    initial_difficulty: str = "medium"

    # Adaptive parameters
    questions_per_quiz: int = 5
    difficulty_up_threshold: float = 0.8  # 80% correct → increase difficulty
    difficulty_down_threshold: float = 0.5  # <50% correct → decrease difficulty

    # Mastery tracking
    mastery_increase_correct: float = 10.0  # +10% for correct answer
    mastery_decrease_wrong: float = 5.0  # -5% for wrong answer
    mastery_min: float = 0.0
    mastery_max: float = 100.0

    # Reproducibility
    random_seed: Optional[int] = None  # Set for reproducible quizzes


@dataclass
class PathConfig:
    """File system paths - single source of truth for all directories."""

    # Base paths
    project_root: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "data")

    # Data subdirectories (computed from data_dir)
    profiles_dir: Path = field(init=False)
    vectorstore_dir: Path = field(init=False)
    logs_dir: Path = field(init=False)
    documents_dir: Path = field(init=False)

    # Schema and config
    schemas_dir: Path = field(init=False)
    syllabus_schema: Path = field(init=False)

    def __post_init__(self):
        """Initialize computed paths."""
        self.profiles_dir = self.data_dir / "profiles"
        self.vectorstore_dir = self.data_dir / "vectorstore"
        self.logs_dir = self.data_dir / "logs"
        self.documents_dir = self.data_dir / "documents"
        self.schemas_dir = self.project_root / "schemas"
        self.syllabus_schema = self.schemas_dir / "syllabus.schema.json"

    def prepare_filesystem(self):
        """
        Create directories if they don't exist.

        Separated from __post_init__ to avoid side-effects on import.
        Call this explicitly from your app entrypoint.
        """
        for directory in [
            self.data_dir,
            self.profiles_dir,
            self.vectorstore_dir,
            self.logs_dir,
            self.documents_dir,
            self.schemas_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


@dataclass
class LoggingConfig:
    """Logging and metrics configuration with env-driven pricing."""

    log_level: str = "INFO"
    log_tokens: bool = True
    log_costs: bool = True

    # Cost estimation (env-driven for easy model switching)
    cost_per_1k_input: float = field(
        default_factory=lambda: float(os.getenv("COST_PER_1K_INPUT", "0.0015"))
    )
    cost_per_1k_output: float = field(
        default_factory=lambda: float(os.getenv("COST_PER_1K_OUTPUT", "0.0020"))
    )


class Config:
    """
    Main configuration class. Singleton pattern.

    Usage:
        from config import config

        # Access settings
        api_key = config.model.api_key
        top_k = config.rag.top_k

        # Enable deterministic mode for testing
        config.model.deterministic = True

        # Prepare filesystem (call once at startup)
        config.prepare_fs()
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.paths = PathConfig()
            cls._instance.model = ModelConfig()
            cls._instance.rag = RAGConfig()
            cls._instance.assessment = AssessmentConfig()
            cls._instance.logging = LoggingConfig()

            # Link RAG vectorstore to PathConfig (single source of truth)
            cls._instance.rag.vectorstore_path = cls._instance.paths.vectorstore_dir

        return cls._instance

    def prepare_fs(self):
        """Prepare filesystem (create directories). Call once at startup."""
        self.paths.prepare_filesystem()

    def validate(self) -> list[str]:
        """
        Validate configuration and return list of errors.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Model validation
        if not self.model.api_key:
            errors.append("OPENAI_API_KEY not set in environment")

        if not (0 <= self.model.temperature <= 2):
            errors.append(f"temperature must be in [0, 2], got {self.model.temperature}")

        if self.model.max_tokens <= 0:
            errors.append(f"max_tokens must be > 0, got {self.model.max_tokens}")

        if self.model.retry_delay < 0:
            errors.append(f"retry_delay must be >= 0, got {self.model.retry_delay}")

        # RAG validation
        if self.rag.top_k < 1:
            errors.append(f"RAG top_k must be >= 1, got {self.rag.top_k}")

        if not (0 < self.rag.similarity_threshold <= 1):
            errors.append(
                f"RAG similarity_threshold must be in (0, 1], got {self.rag.similarity_threshold}"
            )

        if self.rag.embedding_dimension <= 0:
            errors.append(
                f"RAG embedding_dimension must be > 0, got {self.rag.embedding_dimension}"
            )

        if self.rag.chunk_size <= 0:
            errors.append(f"RAG chunk_size must be > 0, got {self.rag.chunk_size}")

        if self.rag.chunk_overlap < 0:
            errors.append(
                f"RAG chunk_overlap must be >= 0, got {self.rag.chunk_overlap}"
            )

        if self.rag.chunk_overlap >= self.rag.chunk_size:
            errors.append(
                f"RAG chunk_overlap ({self.rag.chunk_overlap}) must be < chunk_size ({self.rag.chunk_size})"
            )

        # Path validation
        if not self.paths.syllabus_schema.exists():
            errors.append(
                f"Syllabus schema not found: {self.paths.syllabus_schema}"
            )

        # Assessment validation
        if not (0 <= self.assessment.difficulty_up_threshold <= 1):
            errors.append(
                f"Assessment difficulty_up_threshold must be in [0, 1], got {self.assessment.difficulty_up_threshold}"
            )

        if not (0 <= self.assessment.difficulty_down_threshold <= 1):
            errors.append(
                f"Assessment difficulty_down_threshold must be in [0, 1], got {self.assessment.difficulty_down_threshold}"
            )

        return errors


# Global config instance
config = Config()


# Thread-safe token tracking utility
class TokenTracker:
    """
    Thread-safe tracker for token usage and estimated costs.

    Usage:
        from config import token_tracker

        token_tracker.add_tokens(input_tokens=100, output_tokens=50)
        print(token_tracker.summary())

        # Or use context manager
        with track_tokens(100, 50):
            # Your LLM call here
            pass
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_calls = 0

    def add_tokens(self, input_tokens: int, output_tokens: int):
        """Add tokens from an API call (thread-safe)."""
        with self._lock:
            self.input_tokens += input_tokens
            self.output_tokens += output_tokens
            self.total_calls += 1

    def total_tokens(self) -> int:
        """Get total tokens used (thread-safe)."""
        with self._lock:
            return self.input_tokens + self.output_tokens

    def estimated_cost(self) -> float:
        """
        Calculate estimated cost in USD (thread-safe).

        Returns:
            Estimated cost based on current token counts
        """
        with self._lock:
            input_cost = (
                self.input_tokens / 1000
            ) * config.logging.cost_per_1k_input
            output_cost = (
                self.output_tokens / 1000
            ) * config.logging.cost_per_1k_output
            return input_cost + output_cost

    def summary(self) -> str:
        """Get formatted summary of usage (thread-safe, no deadlock)."""
        # Acquire lock once, compute everything inline to avoid nested locking
        with self._lock:
            input_tokens = self.input_tokens
            output_tokens = self.output_tokens
            total_calls = self.total_calls
            # Compute cost inline (don't call estimated_cost which would re-acquire lock)
            input_cost = (input_tokens / 1000) * config.logging.cost_per_1k_input
            output_cost = (output_tokens / 1000) * config.logging.cost_per_1k_output
            est_cost = input_cost + output_cost
            total_tokens = input_tokens + output_tokens

        # Build string outside lock
        return (
            "Token Usage Summary:\n"
            f"  API Calls: {total_calls}\n"
            f"  Input Tokens: {input_tokens:,}\n"
            f"  Output Tokens: {output_tokens:,}\n"
            f"  Total Tokens: {total_tokens:,}\n"
            f"  Estimated Cost: ${est_cost:.4f}"
        )

    def reset(self):
        """Reset counters (thread-safe)."""
        with self._lock:
            self.input_tokens = 0
            self.output_tokens = 0
            self.total_calls = 0

    def get_stats(self) -> dict:
        """Get current stats as dict (thread-safe, no deadlock)."""
        # Acquire lock once, compute everything inline
        with self._lock:
            input_tokens = self.input_tokens
            output_tokens = self.output_tokens
            total_calls = self.total_calls
            # Compute cost inline to avoid nested locking
            input_cost = (input_tokens / 1000) * config.logging.cost_per_1k_input
            output_cost = (output_tokens / 1000) * config.logging.cost_per_1k_output
            est_cost = input_cost + output_cost

        return {
            "calls": total_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_cost": est_cost,
        }


# Global token tracker instance
token_tracker = TokenTracker()


# Context manager for one-shot token tracking
@contextmanager
def track_tokens(input_tokens: int, output_tokens: int):
    """
    Context manager for tracking tokens from a single LLM call.

    Usage:
        with track_tokens(100, 50):
            # Your LLM call here
            pass
    """
    try:
        yield
    finally:
        token_tracker.add_tokens(input_tokens, output_tokens)
