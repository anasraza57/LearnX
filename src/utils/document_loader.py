"""
Document loading and chunking utilities for RAG system.

Features:
- Load documents from multiple formats (PDF, TXT, Markdown)
- Smart chunking with overlap
- Metadata extraction (filename, page numbers, source)
- Deduplication
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    from ..config import config
except ImportError:
    from src.config import config


@dataclass
class Document:
    """
    Document chunk with content and metadata.

    Attributes:
        content: Text content of the chunk
        metadata: Dict with source, page, chunk_id, etc.
        embedding: Optional embedding vector (computed later)
    """
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def __post_init__(self):
        """Ensure required metadata exists."""
        if "source" not in self.metadata:
            self.metadata["source"] = "unknown"
        if "chunk_id" not in self.metadata:
            # Generate unique ID from content hash
            self.metadata["chunk_id"] = hashlib.md5(
                self.content.encode()
            ).hexdigest()[:12]

    def __repr__(self) -> str:
        source = self.metadata.get("source", "unknown")
        preview = self.content[:50].replace("\n", " ")
        return f"Document(source={source}, preview='{preview}...')"


class DocumentLoader:
    """
    Load and chunk documents from various file formats.

    Supports:
    - Plain text (.txt)
    - Markdown (.md)
    - PDF (.pdf) - requires pypdf or pypdf2
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ):
        """
        Initialize document loader.

        Args:
            chunk_size: Maximum chunk size in characters (default from config)
            chunk_overlap: Overlap between chunks (default from config)
        """
        self.chunk_size = chunk_size or config.rag.chunk_size
        self.chunk_overlap = chunk_overlap or config.rag.chunk_overlap

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be < "
                f"chunk_size ({self.chunk_size})"
            )

    def load_file(self, filepath: Path | str) -> List[Document]:
        """
        Load a single file and return document chunks.

        Args:
            filepath: Path to file

        Returns:
            List of Document chunks

        Raises:
            ValueError: If file type is unsupported
            FileNotFoundError: If file doesn't exist
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        suffix = filepath.suffix.lower()

        if suffix == ".txt":
            return self._load_text(filepath)
        elif suffix == ".md":
            return self._load_markdown(filepath)
        elif suffix == ".pdf":
            return self._load_pdf(filepath)
        else:
            raise ValueError(
                f"Unsupported file type: {suffix}. "
                f"Supported: .txt, .md, .pdf"
            )

    def load_directory(
        self,
        directory: Path | str,
        pattern: str = "**/*",
        recursive: bool = True,
    ) -> List[Document]:
        """
        Load all supported documents from a directory.

        Args:
            directory: Path to directory
            pattern: Glob pattern for files (default: all files)
            recursive: Whether to search subdirectories

        Returns:
            List of all Document chunks
        """
        directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        documents = []

        # Find all files matching pattern
        files = directory.glob(pattern) if not recursive else directory.rglob(pattern)

        for filepath in files:
            if filepath.is_file() and filepath.suffix.lower() in [".txt", ".md", ".pdf"]:
                try:
                    docs = self.load_file(filepath)
                    documents.extend(docs)
                except Exception as e:
                    print(f"Warning: Failed to load {filepath}: {e}")

        return documents

    def _load_text(self, filepath: Path) -> List[Document]:
        """Load plain text file."""
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        chunks = self._chunk_text(content)

        documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                content=chunk,
                metadata={
                    "source": str(filepath.name),
                    "filepath": str(filepath),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "type": "text",
                }
            )
            documents.append(doc)

        return documents

    def _load_markdown(self, filepath: Path) -> List[Document]:
        """Load markdown file and extract metadata including original URLs."""
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Extract title from first heading if exists
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else filepath.stem

        # Extract original URL from markdown (common patterns from OER fetcher)
        original_url = None

        # Try to extract URL from **Source:** line first
        source_match = re.search(r'\*\*Source:\*\*\s*(?:Wikipedia|arXiv|YouTube)?\s*-?\s*(https?://[^\s\n]+)', content[:1000])
        if source_match:
            original_url = source_match.group(1).strip()
        else:
            # Fallback: look for any URL in first 1000 chars
            url_patterns = [
                r'https?://en\.wikipedia\.org/wiki/[^\s\)\n]+',       # Wikipedia URLs
                r'https?://arxiv\.org/[^\s\)\n]+',                    # arXiv URLs
                r'https?://[^\s\)\n]+',                               # Any other URL
            ]

            for pattern in url_patterns:
                url_match = re.search(pattern, content[:1000])
                if url_match:
                    original_url = url_match.group(0).strip()
                    break

        # Determine source type from URL or filename
        source_type = "document"
        if original_url:
            if "wikipedia.org" in original_url:
                source_type = "wikipedia"
            elif "arxiv.org" in original_url:
                source_type = "paper"
            elif "khanacademy.org" in original_url:
                source_type = "course"
            elif "youtube.com" in original_url or "youtu.be" in original_url:
                source_type = "video"
            elif any(domain in original_url for domain in ["realpython.com", "w3schools.com", "tutorialspoint.com"]):
                source_type = "tutorial"
            else:
                source_type = "website"
        elif "arxiv_" in filepath.name:
            source_type = "paper"
        elif "youtube_" in filepath.name:
            source_type = "video"
        elif "resource_" in filepath.name:
            source_type = "book"  # Resources from agent recommendations

        chunks = self._chunk_text(content)

        documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                content=chunk,
                metadata={
                    "source": title,  # Use title as source name instead of filename
                    "filepath": str(filepath),
                    "title": title,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "type": "markdown",
                    "original_url": original_url,  # Store original URL
                    "source_type": source_type,    # Store source type
                }
            )
            documents.append(doc)

        return documents

    def _load_pdf(self, filepath: Path) -> List[Document]:
        """Load PDF file."""
        try:
            import pypdf
            PdfReader = pypdf.PdfReader
        except ImportError:
            try:
                import PyPDF2
                PdfReader = PyPDF2.PdfReader
            except ImportError:
                raise ImportError(
                    "PDF support requires pypdf or PyPDF2. "
                    "Install with: pip install pypdf"
                )

        documents = []

        try:
            pdf = PdfReader(str(filepath))

            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()

                if not text.strip():
                    continue  # Skip empty pages

                chunks = self._chunk_text(text)

                for i, chunk in enumerate(chunks):
                    doc = Document(
                        content=chunk,
                        metadata={
                            "source": str(filepath.name),
                            "filepath": str(filepath),
                            "page": page_num + 1,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "type": "pdf",
                        }
                    )
                    documents.append(doc)

        except Exception as e:
            raise ValueError(f"Failed to load PDF {filepath}: {e}")

        return documents

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Strategy:
        - Split on paragraph boundaries when possible
        - Respect chunk_size and chunk_overlap
        - Avoid splitting mid-sentence when possible

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        last_start = -1  # Track previous start position to prevent infinite loop

        while start < len(text):
            # Get chunk
            end = start + self.chunk_size

            # If not at end, try to break at sentence/paragraph boundary
            if end < len(text):
                # Look for paragraph break
                paragraph_break = text.rfind("\n\n", start, end)
                if paragraph_break > start + self.chunk_size // 2:
                    end = paragraph_break + 2
                else:
                    # Look for sentence break
                    sentence_break = max(
                        text.rfind(". ", start, end),
                        text.rfind("! ", start, end),
                        text.rfind("? ", start, end),
                    )
                    if sentence_break > start + self.chunk_size // 2:
                        end = sentence_break + 2

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start forward with overlap
            start = end - self.chunk_overlap

            # Prevent infinite loop with proper numeric guard
            if start <= last_start:
                start = end
            last_start = start

        return chunks

    def deduplicate_documents(self, documents: List[Document]) -> List[Document]:
        """
        Remove duplicate documents based on content hash.

        Args:
            documents: List of documents

        Returns:
            Deduplicated list
        """
        seen_hashes = set()
        unique_docs = []

        for doc in documents:
            content_hash = hashlib.md5(doc.content.encode()).hexdigest()

            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_docs.append(doc)

        return unique_docs


def load_documents_from_directory(
    directory: Path | str,
    chunk_size: int = None,
    chunk_overlap: int = None,
    deduplicate: bool = True,
) -> List[Document]:
    """
    Convenience function to load all documents from a directory.

    Args:
        directory: Path to documents directory
        chunk_size: Chunk size (default from config)
        chunk_overlap: Chunk overlap (default from config)
        deduplicate: Whether to remove duplicates

    Returns:
        List of Document chunks

    Example:
        >>> docs = load_documents_from_directory("data/documents")
        >>> print(f"Loaded {len(docs)} document chunks")
    """
    loader = DocumentLoader(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    documents = loader.load_directory(directory)

    if deduplicate:
        documents = loader.deduplicate_documents(documents)

    return documents
