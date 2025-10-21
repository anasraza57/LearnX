"""
OER (Open Educational Resources) Content Fetcher.

Automatically fetches educational content from multiple free sources:
- Wikipedia articles
- arXiv research papers and tutorials
- MIT OpenCourseWare materials
- Khan Academy articles
- YouTube video transcripts
- General web scraping from educational sites

This module enables automatic content population for teaching modules.
"""

from __future__ import annotations

import re
import time
import json
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from urllib.parse import quote_plus, urlencode

try:
    from ..config import config
except ImportError:
    from src.config import config


# Free OER source APIs and URLs
OER_SOURCES = {
    "arxiv": "http://export.arxiv.org/api/query",
    "khan_academy": "https://www.khanacademy.org",
    "mit_ocw": "https://ocw.mit.edu",
    "openstax": "https://openstax.org",
}


class OERFetcher:
    """
    Fetch educational content from open sources.

    Supports:
    - Wikipedia articles
    - Web page text extraction
    - Markdown conversion
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize OER fetcher.

        Args:
            output_dir: Directory to save fetched content (default: data/documents)
        """
        self.output_dir = output_dir or (
            config.paths.project_root / "data" / "documents"
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_wikipedia_content(
        self,
        topics: List[str],
        module_id: str,
        language: str = "en",
        max_topics: int = 5,
    ) -> List[Path]:
        """
        Fetch Wikipedia articles for given topics.

        Args:
            topics: List of topic keywords to search
            module_id: Module ID for organizing content
            language: Wikipedia language code (default: en)
            max_topics: Maximum number of topics to fetch

        Returns:
            List of paths to created markdown files
        """
        try:
            import wikipedia
        except ImportError:
            print("⚠️  Wikipedia library not installed. Install with: pip install wikipedia-api")
            return []

        wikipedia.set_lang(language)

        # Create module-specific directory
        module_dir = self.output_dir / module_id
        module_dir.mkdir(exist_ok=True)

        created_files = []
        topics_to_fetch = topics[:max_topics]

        print(f"📚 Fetching Wikipedia content for {len(topics_to_fetch)} topics...")

        for topic in topics_to_fetch:
            try:
                # Search for best matching page
                search_results = wikipedia.search(topic, results=1)
                if not search_results:
                    print(f"   ⚠️  No Wikipedia page found for: {topic}")
                    continue

                page_title = search_results[0]

                # Fetch page content
                page = wikipedia.page(page_title, auto_suggest=False)

                # Create markdown file
                safe_filename = self._sanitize_filename(topic)
                filepath = module_dir / f"{safe_filename}.md"

                content = self._format_wikipedia_content(page, topic)

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

                created_files.append(filepath)
                print(f"   ✅ Fetched: {topic} → {filepath.name}")

                # Rate limiting - be respectful
                time.sleep(0.5)

            except wikipedia.exceptions.DisambiguationError as e:
                # Multiple options - pick first one
                try:
                    page = wikipedia.page(e.options[0], auto_suggest=False)
                    safe_filename = self._sanitize_filename(topic)
                    filepath = module_dir / f"{safe_filename}.md"

                    content = self._format_wikipedia_content(page, topic)

                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)

                    created_files.append(filepath)
                    print(f"   ✅ Fetched: {topic} (disambiguated) → {filepath.name}")
                except Exception as inner_e:
                    print(f"   ⚠️  Failed to fetch {topic}: {inner_e}")

            except Exception as e:
                print(f"   ⚠️  Failed to fetch {topic}: {e}")
                continue

        print(f"✅ Successfully fetched {len(created_files)} articles")
        return created_files

    def fetch_content_from_url(
        self,
        url: str,
        module_id: str,
        title: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Fetch and convert web page content to markdown.

        Args:
            url: URL to fetch
            module_id: Module ID for organizing content
            title: Optional custom title (default: extracted from page)

        Returns:
            Path to created markdown file, or None if failed
        """
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            print("⚠️  Required libraries not installed. Install with: pip install requests beautifulsoup4")
            return None

        try:
            # Fetch page
            headers = {
                "User-Agent": "EduGPT-PersonalisedLearning/1.0 (Educational Content Fetcher)"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, "html.parser")

            # Extract title
            if not title:
                title_tag = soup.find("title")
                title = title_tag.get_text() if title_tag else "Untitled"

            # Extract main content (try common content containers)
            content_tags = soup.find_all(["article", "main", "div"], class_=re.compile("content|article|main"))
            if not content_tags:
                # Fallback: get all paragraphs
                content_tags = soup.find_all("p")

            # Extract text
            text_parts = []
            for tag in content_tags:
                text = tag.get_text(separator="\n", strip=True)
                if text:
                    text_parts.append(text)

            if not text_parts:
                print(f"   ⚠️  No content extracted from {url}")
                return None

            # Create markdown file
            module_dir = self.output_dir / module_id
            module_dir.mkdir(exist_ok=True)

            safe_filename = self._sanitize_filename(title)
            filepath = module_dir / f"{safe_filename}.md"

            # Format content
            content = f"# {title}\n\n"
            content += f"**Source:** {url}\n\n"
            content += "---\n\n"
            content += "\n\n".join(text_parts)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"✅ Fetched web content: {title} → {filepath.name}")
            return filepath

        except Exception as e:
            print(f"⚠️  Failed to fetch {url}: {e}")
            return None

    def fetch_arxiv_papers(
        self,
        topics: List[str],
        module_id: str,
        max_results: int = 3,
    ) -> List[Path]:
        """
        Fetch research papers and tutorials from arXiv.

        Args:
            topics: List of topic keywords to search
            module_id: Module ID for organizing content
            max_results: Maximum papers per topic

        Returns:
            List of paths to created markdown files
        """
        try:
            import requests
            import feedparser
        except ImportError:
            print("⚠️  feedparser not installed. Install with: pip install feedparser")
            return []

        module_dir = self.output_dir / module_id
        module_dir.mkdir(exist_ok=True)

        created_files = []

        print(f"📚 Fetching arXiv papers for {len(topics)} topics...")

        for topic in topics[:3]:  # Limit to 3 topics
            try:
                # Search arXiv
                query = quote_plus(topic)
                url = f"{OER_SOURCES['arxiv']}?search_query=all:{query}&start=0&max_results={max_results}&sortBy=relevance"

                response = requests.get(url, timeout=10)
                feed = feedparser.parse(response.content)

                for entry in feed.entries[:max_results]:
                    title = entry.title
                    summary = entry.summary
                    authors = ", ".join(author.name for author in entry.authors) if hasattr(entry, 'authors') else "Unknown"
                    link = entry.link

                    # Create markdown
                    safe_filename = self._sanitize_filename(title)
                    filepath = module_dir / f"arxiv_{safe_filename}.md"

                    content = f"# {title}\n\n"
                    content += f"**Source:** arXiv - {link}\n"
                    content += f"**Authors:** {authors}\n"
                    content += f"**Topic:** {topic}\n\n"
                    content += "## Abstract\n\n"
                    content += summary + "\n"

                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)

                    created_files.append(filepath)
                    print(f"   ✅ arXiv: {title[:50]}...")

                time.sleep(1)  # Rate limiting

            except Exception as e:
                print(f"   ⚠️  Failed to fetch arXiv papers for {topic}: {e}")

        return created_files

    def fetch_youtube_transcript(
        self,
        query: str,
        module_id: str,
        max_videos: int = 2,
    ) -> List[Path]:
        """
        Search YouTube and fetch video transcripts.

        Args:
            query: Search query
            module_id: Module ID
            max_videos: Maximum videos to fetch

        Returns:
            List of paths to created markdown files
        """
        try:
            from youtube_search import YoutubeSearch
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            print("⚠️  YouTube libraries not installed. Install with: pip install youtube-search-python youtube-transcript-api")
            return []

        module_dir = self.output_dir / module_id
        module_dir.mkdir(exist_ok=True)

        created_files = []

        try:
            print(f"🎥 Searching YouTube for: {query}")

            # Search for videos
            results = YoutubeSearch(query, max_results=max_videos).to_dict()

            for video in results:
                try:
                    video_id = video['id']
                    title = video['title']
                    channel = video['channel']

                    # Get transcript
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                    transcript_text = " ".join([item['text'] for item in transcript_list])

                    # Create markdown
                    safe_filename = self._sanitize_filename(title)
                    filepath = module_dir / f"youtube_{safe_filename}.md"

                    content = f"# {title}\n\n"
                    content += f"**Source:** YouTube - https://www.youtube.com/watch?v={video_id}\n"
                    content += f"**Channel:** {channel}\n"
                    content += f"**Query:** {query}\n\n"
                    content += "## Transcript\n\n"
                    content += transcript_text + "\n"

                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)

                    created_files.append(filepath)
                    print(f"   ✅ YouTube: {title[:50]}...")

                except Exception as e:
                    print(f"   ⚠️  Failed to get transcript for {video.get('title', 'video')}: {e}")
                    continue

        except Exception as e:
            print(f"⚠️  YouTube search failed: {e}")

        return created_files

    def search_and_fetch_multiple_sources(
        self,
        topics: List[str],
        module_id: str,
        use_wikipedia: bool = True,
        use_arxiv: bool = True,
        use_youtube: bool = False,  # Disabled by default (requires API)
    ) -> List[Path]:
        """
        Fetch content from multiple OER sources.

        Args:
            topics: List of topics to search
            module_id: Module ID
            use_wikipedia: Fetch from Wikipedia
            use_arxiv: Fetch from arXiv
            use_youtube: Fetch YouTube transcripts

        Returns:
            List of all created file paths
        """
        all_files = []

        # Wikipedia
        if use_wikipedia:
            wiki_files = self.fetch_wikipedia_content(
                topics=topics,
                module_id=module_id,
                max_topics=min(5, len(topics))
            )
            all_files.extend(wiki_files)

        # arXiv
        if use_arxiv:
            arxiv_files = self.fetch_arxiv_papers(
                topics=topics,
                module_id=module_id,
                max_results=2
            )
            all_files.extend(arxiv_files)

        # YouTube (optional)
        if use_youtube and topics:
            # Create combined query from first 2 topics
            query = " ".join(topics[:2])
            youtube_files = self.fetch_youtube_transcript(
                query=query,
                module_id=module_id,
                max_videos=1
            )
            all_files.extend(youtube_files)

        return all_files

    def generate_synthetic_content(
        self,
        module: Dict[str, Any],
        module_id: str,
    ) -> Optional[Path]:
        """
        Generate synthetic educational content using LLM.

        Args:
            module: Module dictionary with title, topics, outcomes
            module_id: Module ID for organizing content

        Returns:
            Path to created markdown file, or None if failed
        """
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            print("⚠️  LangChain not installed")
            return None

        try:
            llm = ChatOpenAI(
                model=config.model.model_name,
                temperature=0.7,
                api_key=config.model.api_key,
            )

            # Build prompt
            topics_list = "\n".join(f"- {topic}" for topic in module.get("topics", []))
            outcomes_list = "\n".join(f"- {outcome}" for outcome in module.get("outcomes", []))

            prompt = f"""Create comprehensive educational content for the following module:

**Module Title:** {module.get('title')}
**Description:** {module.get('description', 'N/A')}

**Topics to Cover:**
{topics_list}

**Learning Outcomes:**
{outcomes_list}

Please generate a detailed educational document covering all topics. Include:
1. Clear explanations of each concept
2. Examples and illustrations
3. Practical applications
4. Key takeaways

Format the content as a well-structured educational text suitable for teaching.
Length: Approximately 2000-3000 words.
"""

            print(f"🤖 Generating synthetic content for: {module.get('title')}...")

            response = llm.invoke(prompt)
            content = response.content

            # Create markdown file
            module_dir = self.output_dir / module_id
            module_dir.mkdir(exist_ok=True)

            filepath = module_dir / f"{module_id}_content.md"

            full_content = f"""# {module.get('title')}

{module.get('description', '')}

---

{content}

---

**Generated by:** EduGPT AI Content Generator
**Topics Covered:** {', '.join(module.get('topics', []))}
"""

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(full_content)

            print(f"✅ Generated synthetic content → {filepath.name}")
            return filepath

        except Exception as e:
            print(f"⚠️  Failed to generate synthetic content: {e}")
            return None

    def _format_wikipedia_content(self, page, topic: str) -> str:
        """Format Wikipedia page as markdown."""
        content = f"# {page.title}\n\n"
        content += f"**Topic:** {topic}\n"
        content += f"**Source:** Wikipedia - {page.url}\n"
        content += f"**Summary:** {page.summary}\n\n"
        content += "---\n\n"
        content += page.content

        return content

    def _sanitize_filename(self, name: str) -> str:
        """Convert string to safe filename."""
        # Remove/replace unsafe characters
        safe = re.sub(r'[^\w\s-]', '', name)
        safe = re.sub(r'[\s_]+', '_', safe)
        safe = safe.strip('_').lower()
        return safe[:50]  # Limit length


def auto_fetch_module_content(
    module: Dict[str, Any],
    module_id: str,
    output_dir: Optional[Path] = None,
    use_wikipedia: bool = True,
    use_arxiv: bool = True,
    use_youtube: bool = False,
    use_synthetic: bool = True,
) -> List[Path]:
    """
    Automatically fetch educational content for a module from multiple OER sources.

    Tries multiple strategies in order:
    1. Wikipedia articles for topics
    2. arXiv research papers (for technical/scientific topics)
    3. YouTube video transcripts (optional)
    4. Synthetic content generation (fallback)

    Args:
        module: Module dictionary from syllabus
        module_id: Module ID
        output_dir: Directory to save content
        use_wikipedia: Whether to fetch from Wikipedia
        use_arxiv: Whether to fetch from arXiv
        use_youtube: Whether to fetch YouTube transcripts
        use_synthetic: Whether to generate synthetic content as fallback

    Returns:
        List of created file paths
    """
    fetcher = OERFetcher(output_dir=output_dir)
    created_files = []

    topics = module.get("topics", [])

    # Strategy 1: Multiple OER sources
    if topics:
        oer_files = fetcher.search_and_fetch_multiple_sources(
            topics=topics,
            module_id=module_id,
            use_wikipedia=use_wikipedia,
            use_arxiv=use_arxiv,
            use_youtube=use_youtube,
        )
        created_files.extend(oer_files)

    # Strategy 2: Synthetic content (if no sources yielded content)
    if use_synthetic and len(created_files) == 0:
        print("   ⚠️  No OER content found, generating synthetic content...")
        synthetic_file = fetcher.generate_synthetic_content(
            module=module,
            module_id=module_id,
        )
        if synthetic_file:
            created_files.append(synthetic_file)

    return created_files
