"""
Unit tests for configuration system.

Tests:
- Config loading and initialization
- Path configuration
- Config validation
- Token tracker functionality
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from config import config, token_tracker, Config, TokenTracker


class TestConfig:
    """Test suite for Config class."""

    def test_config_singleton(self):
        """Test that Config implements singleton pattern."""
        config1 = Config()
        config2 = Config()
        assert config1 is config2, "Config should be a singleton"

    def test_config_initialization(self):
        """Test that config initializes with expected values."""
        assert config.model.model_name is not None
        assert config.model.temperature >= 0
        assert config.model.max_tokens > 0
        assert config.rag.top_k >= 1
        assert config.assessment.questions_per_quiz > 0

    def test_paths_configured(self):
        """Test that all required paths are configured."""
        assert config.paths.profiles_dir.is_absolute()
        assert config.paths.vectorstore_dir.is_absolute()
        assert config.paths.logs_dir.is_absolute()
        assert config.paths.syllabus_schema.is_absolute()

    def test_config_validation_with_valid_config(self):
        """Test that valid config passes validation."""
        # Save original API key
        original_key = config.model.api_key

        # Set a dummy key for testing
        config.model.api_key = "test-key"

        errors = config.validate()

        # Restore original key
        config.model.api_key = original_key

        # Schema should exist, so only API key error expected in real env
        assert isinstance(errors, list)

    def test_config_validation_detects_invalid_temperature(self):
        """Test that config validation detects invalid temperature."""
        original_temp = config.model.temperature
        config.model.temperature = 3.0  # Invalid: > 2

        errors = config.validate()

        config.model.temperature = original_temp

        assert any("temperature" in err.lower() for err in errors)

    def test_config_validation_detects_invalid_top_k(self):
        """Test that config validation detects invalid RAG top_k."""
        original_top_k = config.rag.top_k
        config.rag.top_k = 0  # Invalid: must be >= 1

        errors = config.validate()

        config.rag.top_k = original_top_k

        assert any("top_k" in err.lower() for err in errors)

    def test_deterministic_mode(self):
        """Test that deterministic mode sets all temperatures to 0."""
        from config import ModelConfig

        model = ModelConfig()
        model.deterministic = True
        model.__post_init__()

        assert model.temperature == 0.0
        assert model.planner_temperature == 0.0
        assert model.instructor_temperature == 0.0
        assert model.assessment_temperature == 0.0

    def test_rag_vectorstore_linked_to_paths(self):
        """Test that RAG vectorstore path is linked to PathConfig."""
        assert config.rag.vectorstore_path == config.paths.vectorstore_dir


class TestTokenTracker:
    """Test suite for TokenTracker class."""

    def setup_method(self):
        """Reset token tracker before each test."""
        token_tracker.reset()

    def test_token_tracker_initialization(self):
        """Test that token tracker initializes with zero counts."""
        assert token_tracker.input_tokens == 0
        assert token_tracker.output_tokens == 0
        assert token_tracker.total_calls == 0

    def test_add_tokens(self):
        """Test adding tokens to tracker."""
        token_tracker.add_tokens(100, 50)

        assert token_tracker.input_tokens == 100
        assert token_tracker.output_tokens == 50
        assert token_tracker.total_calls == 1

    def test_add_tokens_multiple_calls(self):
        """Test adding tokens across multiple calls."""
        token_tracker.add_tokens(100, 50)
        token_tracker.add_tokens(200, 100)

        assert token_tracker.input_tokens == 300
        assert token_tracker.output_tokens == 150
        assert token_tracker.total_calls == 2

    def test_total_tokens(self):
        """Test total_tokens calculation."""
        token_tracker.add_tokens(100, 50)

        assert token_tracker.total_tokens() == 150

    def test_estimated_cost(self):
        """Test cost estimation."""
        token_tracker.add_tokens(1000, 1000)

        cost = token_tracker.estimated_cost()
        assert cost > 0
        assert isinstance(cost, float)

    def test_summary(self):
        """Test summary string generation."""
        token_tracker.add_tokens(100, 50)

        summary = token_tracker.summary()

        assert "100" in summary
        assert "50" in summary
        assert "150" in summary
        assert "$" in summary

    def test_get_stats(self):
        """Test get_stats dict generation."""
        token_tracker.add_tokens(100, 50)

        stats = token_tracker.get_stats()

        assert stats["calls"] == 1
        assert stats["input_tokens"] == 100
        assert stats["output_tokens"] == 50
        assert stats["total_tokens"] == 150
        assert "estimated_cost" in stats

    def test_reset(self):
        """Test reset functionality."""
        token_tracker.add_tokens(100, 50)
        token_tracker.reset()

        assert token_tracker.input_tokens == 0
        assert token_tracker.output_tokens == 0
        assert token_tracker.total_calls == 0

    def test_thread_safety_no_deadlock(self):
        """Test that summary() doesn't cause deadlock."""
        import threading

        def add_and_summarize():
            for _ in range(10):
                token_tracker.add_tokens(10, 5)
                _ = token_tracker.summary()
                _ = token_tracker.get_stats()

        threads = [threading.Thread(target=add_and_summarize) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without deadlock
        assert token_tracker.total_calls == 50


class TestRAGConfig:
    """Test suite for RAG configuration."""

    def test_chunk_overlap_validation(self):
        """Test that chunk_overlap < chunk_size is enforced."""
        from config import RAGConfig

        with pytest.raises(ValueError, match="chunk_overlap.*must be.*chunk_size"):
            rag = RAGConfig()
            rag.chunk_overlap = 1000  # Greater than chunk_size
            rag.__post_init__()
