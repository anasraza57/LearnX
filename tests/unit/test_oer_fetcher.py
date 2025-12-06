"""
Unit tests for OER content fetcher.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.utils.oer_fetcher import OERFetcher, auto_fetch_module_content


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create temporary output directory."""
    return tmp_path / "documents"


@pytest.fixture
def oer_fetcher(temp_output_dir):
    """Create OER fetcher instance."""
    return OERFetcher(output_dir=temp_output_dir)


@pytest.fixture
def sample_module():
    """Sample module dictionary."""
    return {
        "id": "m01-python-basics",
        "title": "Introduction to Python",
        "description": "Learn Python fundamentals",
        "topics": ["Variables", "Data Types", "Control Flow"],
        "outcomes": [
            "Understand Python syntax",
            "Write basic programs",
            "Use control structures"
        ],
        "estimated_hours": 10.0
    }


class TestOERFetcher:
    """Test OER content fetcher."""

    def test_init_creates_output_directory(self, temp_output_dir):
        """Test that initialization creates output directory."""
        fetcher = OERFetcher(output_dir=temp_output_dir)
        assert temp_output_dir.exists()
        assert fetcher.output_dir == temp_output_dir

    def test_sanitize_filename(self, oer_fetcher):
        """Test filename sanitization."""
        # Test with special characters
        assert oer_fetcher._sanitize_filename("Hello World!") == "hello_world"
        assert oer_fetcher._sanitize_filename("Python 3.9") == "python_39"
        assert oer_fetcher._sanitize_filename("Data/Types") == "datatypes"

        # Test length limiting
        long_name = "a" * 100
        result = oer_fetcher._sanitize_filename(long_name)
        assert len(result) <= 50

    @patch('src.utils.oer_fetcher.wikipedia')
    def test_fetch_wikipedia_content_success(self, mock_wikipedia, oer_fetcher, temp_output_dir):
        """Test successful Wikipedia content fetching."""
        # Mock Wikipedia page
        mock_page = Mock()
        mock_page.title = "Python (programming language)"
        mock_page.url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
        mock_page.summary = "Python is a high-level programming language."
        mock_page.content = "Python was created by Guido van Rossum..."

        mock_wikipedia.search.return_value = ["Python (programming language)"]
        mock_wikipedia.page.return_value = mock_page

        # Fetch content
        topics = ["Python"]
        module_id = "m01-python"

        result = oer_fetcher.fetch_wikipedia_content(
            topics=topics,
            module_id=module_id
        )

        # Verify
        assert len(result) == 1
        assert result[0].exists()
        assert result[0].suffix == ".md"

        # Check content
        content = result[0].read_text()
        assert "Python (programming language)" in content
        assert "Python is a high-level programming language" in content

    @patch('src.utils.oer_fetcher.wikipedia')
    def test_fetch_wikipedia_no_results(self, mock_wikipedia, oer_fetcher):
        """Test Wikipedia fetch with no results."""
        mock_wikipedia.search.return_value = []

        result = oer_fetcher.fetch_wikipedia_content(
            topics=["NonexistentTopic12345"],
            module_id="m01-test"
        )

        assert result == []

    @patch('src.utils.oer_fetcher.wikipedia')
    def test_fetch_wikipedia_max_topics_limit(self, mock_wikipedia, oer_fetcher):
        """Test that max_topics parameter limits fetching."""
        mock_page = Mock()
        mock_page.title = "Test"
        mock_page.url = "https://test.com"
        mock_page.summary = "Test"
        mock_page.content = "Test content"

        mock_wikipedia.search.return_value = ["Test"]
        mock_wikipedia.page.return_value = mock_page

        topics = ["Topic1", "Topic2", "Topic3", "Topic4", "Topic5", "Topic6"]

        result = oer_fetcher.fetch_wikipedia_content(
            topics=topics,
            module_id="m01-test",
            max_topics=3
        )

        # Should only fetch 3 topics
        assert len(result) <= 3

    @patch('src.utils.oer_fetcher.requests.get')
    @patch('src.utils.oer_fetcher.BeautifulSoup')
    def test_fetch_content_from_url_success(self, mock_bs, mock_requests, oer_fetcher):
        """Test successful URL content fetching."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"<html><body><p>Test content</p></body></html>"
        mock_requests.return_value = mock_response

        # Mock BeautifulSoup
        mock_soup = Mock()
        mock_soup.find.return_value = Mock(get_text=lambda: "Test Page")
        mock_soup.find_all.return_value = [Mock(get_text=lambda **kwargs: "Test content")]
        mock_bs.return_value = mock_soup

        result = oer_fetcher.fetch_content_from_url(
            url="https://example.com/article",
            module_id="m01-test",
            title="Test Article"
        )

        assert result is not None
        assert result.exists()
        assert result.suffix == ".md"

    @patch('src.utils.oer_fetcher.ChatOpenAI')
    def test_generate_synthetic_content_success(self, mock_llm_class, oer_fetcher, sample_module):
        """Test synthetic content generation."""
        # Mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "This is comprehensive educational content about Python..."
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        result = oer_fetcher.generate_synthetic_content(
            module=sample_module,
            module_id=sample_module["id"]
        )

        assert result is not None
        assert result.exists()
        assert result.suffix == ".md"

        content = result.read_text()
        assert sample_module["title"] in content
        assert "Generated by: LearnX AI Content Generator" in content

    @patch('src.utils.oer_fetcher.ChatOpenAI')
    def test_generate_synthetic_content_includes_topics(self, mock_llm_class, oer_fetcher, sample_module):
        """Test that synthetic content generation includes all topics."""
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Educational content"
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm

        result = oer_fetcher.generate_synthetic_content(
            module=sample_module,
            module_id=sample_module["id"]
        )

        # Check that prompt included topics
        call_args = mock_llm.invoke.call_args[0][0]
        for topic in sample_module["topics"]:
            assert topic in call_args


class TestAutoFetchModuleContent:
    """Test auto_fetch_module_content convenience function."""

    @patch('src.utils.oer_fetcher.OERFetcher')
    def test_auto_fetch_uses_wikipedia_by_default(self, mock_fetcher_class, sample_module, tmp_path):
        """Test that auto_fetch uses Wikipedia by default."""
        mock_fetcher = Mock()
        mock_fetcher.fetch_wikipedia_content.return_value = [Path("test.md")]
        mock_fetcher_class.return_value = mock_fetcher

        result = auto_fetch_module_content(
            module=sample_module,
            module_id=sample_module["id"],
            output_dir=tmp_path
        )

        # Should call Wikipedia fetcher
        mock_fetcher.fetch_wikipedia_content.assert_called_once()
        assert len(result) > 0

    @patch('src.utils.oer_fetcher.OERFetcher')
    def test_auto_fetch_fallback_to_synthetic(self, mock_fetcher_class, sample_module, tmp_path):
        """Test fallback to synthetic when Wikipedia fails."""
        mock_fetcher = Mock()
        mock_fetcher.fetch_wikipedia_content.return_value = []  # Wikipedia fails
        mock_fetcher.generate_synthetic_content.return_value = Path("synthetic.md")
        mock_fetcher_class.return_value = mock_fetcher

        result = auto_fetch_module_content(
            module=sample_module,
            module_id=sample_module["id"],
            output_dir=tmp_path,
            use_wikipedia=True,
            use_synthetic=True
        )

        # Should call both methods
        mock_fetcher.fetch_wikipedia_content.assert_called_once()
        mock_fetcher.generate_synthetic_content.assert_called_once()
        assert len(result) > 0

    @patch('src.utils.oer_fetcher.OERFetcher')
    def test_auto_fetch_respects_disable_flags(self, mock_fetcher_class, sample_module, tmp_path):
        """Test that disabling strategies is respected."""
        mock_fetcher = Mock()
        mock_fetcher_class.return_value = mock_fetcher

        result = auto_fetch_module_content(
            module=sample_module,
            module_id=sample_module["id"],
            output_dir=tmp_path,
            use_wikipedia=False,
            use_synthetic=False
        )

        # Should not call either method
        mock_fetcher.fetch_wikipedia_content.assert_not_called()
        mock_fetcher.generate_synthetic_content.assert_not_called()
        assert len(result) == 0
