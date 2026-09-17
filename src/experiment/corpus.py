"""
Build the fixed introductory Python corpus used by every experiment.

The corpus covers four curriculum strands. For each strand it gathers:
- automatic OER: the system's own OERFetcher (Wikipedia and arXiv), queried
  with the topic keywords that LearnX syllabi actually produced for that strand;
- curated OER: the matching chapters of the official Python 3.11 tutorial.

Every fetched document is recorded in a manifest with an automatic relevance
label. Only documents labelled on-topic are indexed, but the manifest keeps the
rest so the off-topic rate of automatic keyword retrieval can be reported.

Usage:
    python -m src.experiment.corpus fetch     # download into data/corpus/<version>/documents
    python -m src.experiment.corpus label     # write/refresh relevance labels
    python -m src.experiment.corpus index     # purge and rebuild the vector index
    python -m src.experiment.corpus stats     # print corpus statistics
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from ..config import config
from ..utils.document_loader import DocumentLoader
from ..utils.oer_fetcher import OERFetcher

CORPUS_VERSION = "python_v1"
COLLECTION_NAME = f"learnx_{CORPUS_VERSION}"
CORPUS_DIR = config.paths.data_dir / "corpus" / CORPUS_VERSION
DOCUMENTS_DIR = CORPUS_DIR / "documents"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"
LABELS_PATH = CORPUS_DIR / "relevance_labels.csv"
INDEX_REPORT_PATH = CORPUS_DIR / "index_report.json"

PYTHON_DOCS = "https://docs.python.org/3.11/tutorial/"

# Query topics are the ones LearnX syllabi generated for these strands
# (data/sessions/syllabi, "Learn Python Programming" and "Python for beginners").
STRANDS: Dict[str, Dict[str, Any]] = {
    "py01-basics": {
        "title": "Python basics",
        "description": "Python syntax, variables, numbers, strings, operators, data types and basic input and output.",
        "query_topics": ["Python basics", "Data types", "Variables", "Variables and operators", "Basic input/output"],
        "curated_urls": [PYTHON_DOCS + "introduction.html", PYTHON_DOCS + "inputoutput.html"],
    },
    "py02-control-flow": {
        "title": "Control flow and functions",
        "description": "Conditional statements, for and while loops, break and continue, and defining and calling functions in Python.",
        "query_topics": ["Conditional statements", "Loops", "Functions", "Indentation", "Flow control"],
        "curated_urls": [PYTHON_DOCS + "controlflow.html"],
    },
    "py03-data-structures": {
        "title": "Data structures",
        "description": "Python lists, tuples, dictionaries, sets and list comprehensions.",
        "query_topics": ["Lists", "Tuples", "Dictionaries", "Sets", "List comprehensions"],
        "curated_urls": [PYTHON_DOCS + "datastructures.html"],
    },
    "py04-oop": {
        "title": "Object-oriented programming",
        "description": "Python classes and objects, attributes and methods, inheritance, polymorphism and encapsulation.",
        "query_topics": ["Classes", "Objects", "Inheritance", "Polymorphism", "Encapsulation and abstraction"],
        "curated_urls": [PYTHON_DOCS + "classes.html"],
    },
}

# Relevance rule for automatically retrieved documents (see label_documents).
PYTHON_MENTION_MIN = 2
PROGRAMMING_TERMS = re.compile(
    r"\b(programming language|source code|python|compiler|interpreter|object-oriented|"
    r"data type|control flow|subroutine|syntax)\b",
    re.IGNORECASE,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _curated_markdown(url: str) -> str:
    """Fetch a Python docs page and convert its main body to Markdown, keeping code blocks."""
    import requests
    from bs4 import BeautifulSoup

    response = requests.get(url, headers={"User-Agent": "LearnX/1.0 (research corpus build)"}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    body = soup.select_one('div[role="main"]') or soup.select_one("div.body")
    for link in body.select("a.headerlink"):
        link.decompose()

    title = soup.find("h1").get_text(strip=True)
    lines = [f"# {title}", "", f"**Source:** {url}", "", "---", ""]
    for element in body.find_all(["h2", "h3", "h4", "p", "pre", "li", "dt"]):
        # Skip elements nested inside another captured element (e.g. <p> inside <li>)
        if element.find_parent(["li", "pre", "dt"]):
            continue
        text = element.get_text("" if element.name == "pre" else " ", strip=element.name != "pre")
        if not text.strip():
            continue
        if element.name in ("h2", "h3", "h4"):
            lines += ["#" * int(element.name[1]) + " " + text, ""]
        elif element.name == "pre":
            lines += ["```python", text.rstrip(), "```", ""]
        elif element.name in ("li", "dt"):
            lines += [f"- {text}"]
        else:
            lines += [re.sub(r"\s+", " ", text), ""]
    return "\n".join(lines) + "\n"


def fetch_documents() -> None:
    """Download all documents for every strand and write the manifest."""
    if DOCUMENTS_DIR.exists():
        sys.exit(f"{DOCUMENTS_DIR} already exists. The corpus is fetched once; delete it to refetch.")
    DOCUMENTS_DIR.mkdir(parents=True)
    fetcher = OERFetcher(output_dir=DOCUMENTS_DIR)
    fetched_at = datetime.now(timezone.utc).isoformat()
    entries: List[Dict[str, Any]] = []

    for strand_id, strand in STRANDS.items():
        print(f"\n=== {strand_id}: {strand['title']}")
        # Automatic OER, exactly as the system fetches it for a syllabus module
        files = fetcher.search_and_fetch_multiple_sources(
            topics=strand["query_topics"],
            module_id=strand_id,
            use_wikipedia=True,
            use_arxiv=True,
            use_youtube=False,
        )
        wikipedia_files = [f for f in files if not f.name.startswith("arxiv_")]
        if not wikipedia_files:
            sys.exit(f"No Wikipedia articles fetched for {strand_id}; refusing to build a partial corpus.")
        for path in files:
            entries.append({"strand": strand_id, "path": path, "origin": "automatic"})

        # Curated OER
        for url in strand["curated_urls"]:
            path = DOCUMENTS_DIR / strand_id / f"pydocs_{Path(url).stem}.md"
            path.write_text(_curated_markdown(url), encoding="utf-8")
            print(f"   ✅ Curated: {url}")
            entries.append({"strand": strand_id, "path": path, "origin": "curated"})

    manifest_docs = []
    loader = DocumentLoader()
    seen = set()
    for entry in entries:
        path = entry["path"]
        # The fetcher overwrites files that sanitise to the same name; record each file once
        if path in seen:
            continue
        seen.add(path)
        text = path.read_text(encoding="utf-8")
        meta = loader._load_markdown(path)[0].metadata
        manifest_docs.append({
            "doc_id": f"{entry['strand']}/{path.stem}",
            "strand": entry["strand"],
            "origin": entry["origin"],
            "path": str(path.relative_to(CORPUS_DIR)),
            "title": meta["title"],
            "url": meta["original_url"],
            "source_type": meta["source_type"],
            "query_topic": _field(text, "Topic"),
            "chars": len(text),
            "sha256": _sha256(path),
        })

    manifest = {
        "corpus_version": CORPUS_VERSION,
        "fetched_at": fetched_at,
        "strands": STRANDS,
        "fetch_settings": {
            "wikipedia_max_topics": 5,
            "arxiv_topics": 3,
            "arxiv_results_per_topic": 2,
            "youtube": False,
            "synthetic_fallback": False,
        },
        "documents": sorted(manifest_docs, key=lambda d: d["doc_id"]),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nManifest: {MANIFEST_PATH} ({len(manifest_docs)} documents)")


def _field(text: str, name: str) -> str | None:
    match = re.search(rf"^\*\*{name}:\*\*\s*(.+)$", text[:2000], re.MULTILINE)
    return match.group(1).strip() if match else None


def label_documents() -> None:
    """
    Apply the automatic relevance rule and write relevance_labels.csv.

    Rule: curated Python documentation is on-topic. An automatically retrieved
    document is on-topic if it mentions Python at least PYTHON_MENTION_MIN times,
    or it is a Wikipedia article about a programming concept (it uses general
    programming vocabulary at least three times). Anything else is off-topic.

    A human reviewer can override any row in the `reviewed_label` column; the
    override wins when indexing. Existing reviews are preserved on refresh.
    """
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    previous = {}
    if LABELS_PATH.exists():
        with LABELS_PATH.open(encoding="utf-8") as f:
            previous = {row["doc_id"]: row for row in csv.DictReader(f)}

    rows = []
    for doc in manifest["documents"]:
        text = (CORPUS_DIR / doc["path"]).read_text(encoding="utf-8")
        python_mentions = len(re.findall(r"\bpython\b", text, re.IGNORECASE))
        programming_terms = len(PROGRAMMING_TERMS.findall(text))
        if doc["origin"] == "curated":
            label, reason = "on_topic", "curated Python documentation"
        elif python_mentions >= PYTHON_MENTION_MIN:
            label, reason = "on_topic", f"mentions Python {python_mentions} times"
        elif doc["source_type"] == "wikipedia" and programming_terms >= 3:
            label, reason = "on_topic", f"Wikipedia, {programming_terms} programming terms"
        else:
            label, reason = "off_topic", f"python={python_mentions}, programming_terms={programming_terms}"
        prior = previous.get(doc["doc_id"], {})
        rows.append({
            "doc_id": doc["doc_id"],
            "strand": doc["strand"],
            "origin": doc["origin"],
            "source_type": doc["source_type"],
            "query_topic": doc["query_topic"] or "",
            "title": doc["title"],
            "auto_label": label,
            "auto_reason": reason,
            "reviewed_label": prior.get("reviewed_label", ""),
            "reviewer_note": prior.get("reviewer_note", ""),
        })

    with LABELS_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    on = sum(1 for r in rows if r["auto_label"] == "on_topic")
    print(f"Labelled {len(rows)} documents: {on} on-topic, {len(rows) - on} off-topic -> {LABELS_PATH}")


def _final_labels() -> Dict[str, str]:
    with LABELS_PATH.open(encoding="utf-8") as f:
        return {row["doc_id"]: (row["reviewed_label"] or row["auto_label"]) for row in csv.DictReader(f)}


def build_index() -> None:
    """Purge the vector store and index every on-topic document into one collection."""
    from ..utils.vector_store import VectorStore

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    labels = _final_labels()
    store_dir = config.rag.vectorstore_path

    # Rebuild from empty: move whatever is there aside rather than appending to it
    if store_dir.exists() and any(p.name != ".gitkeep" for p in store_dir.iterdir()):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = config.paths.data_dir / "_archive" / f"vectorstore_{stamp}"
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(store_dir), str(archive))
        print(f"Moved previous vector store to {archive}")
    store_dir.mkdir(parents=True, exist_ok=True)

    loader = DocumentLoader()
    chunks = []
    for doc in manifest["documents"]:  # manifest order is sorted, so indexing is deterministic
        if labels[doc["doc_id"]] != "on_topic":
            continue
        for chunk in loader._load_markdown(CORPUS_DIR / doc["path"]):
            chunk.metadata.update({
                "chunk_id": f"{doc['doc_id']}#{chunk.metadata['chunk_index']}",
                "doc_id": doc["doc_id"],
                "strand": doc["strand"],
                "origin": doc["origin"],
                "corpus_version": CORPUS_VERSION,
                "filepath": doc["path"],
            })
            chunks.append(chunk)

    store = VectorStore(collection_name=COLLECTION_NAME, persist_directory=store_dir)
    store.add_documents(chunks, show_progress=True)

    report = {
        "corpus_version": CORPUS_VERSION,
        "collection": COLLECTION_NAME,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": config.rag.embedding_model,
        "chunk_size": config.rag.chunk_size,
        "chunk_overlap": config.rag.chunk_overlap,
        "top_k": config.rag.top_k,
        "similarity_threshold": config.rag.similarity_threshold,
        "documents_indexed": sum(1 for d in manifest["documents"] if labels[d["doc_id"]] == "on_topic"),
        "chunks_indexed": store.get_count(),
        "stats": corpus_stats(),
    }
    INDEX_REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Indexed {report['chunks_indexed']} chunks into '{COLLECTION_NAME}'. Report: {INDEX_REPORT_PATH}")


def corpus_stats() -> Dict[str, Any]:
    """Documents and chunks per strand, by origin and source type, before and after filtering."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    labels = _final_labels()
    loader = DocumentLoader()
    stats: Dict[str, Any] = {}
    for doc in manifest["documents"]:
        s = stats.setdefault(doc["strand"], {"fetched": {}, "indexed": {}, "chunks_indexed": 0})
        key = f"{doc['origin']}:{doc['source_type']}"
        s["fetched"][key] = s["fetched"].get(key, 0) + 1
        if labels[doc["doc_id"]] == "on_topic":
            s["indexed"][key] = s["indexed"].get(key, 0) + 1
            s["chunks_indexed"] += len(loader._load_markdown(CORPUS_DIR / doc["path"]))

    automatic = [d for d in manifest["documents"] if d["origin"] == "automatic"]
    off = [d for d in automatic if labels[d["doc_id"]] != "on_topic"]
    return {
        "per_strand": stats,
        "automatic_documents": len(automatic),
        "automatic_off_topic": len(off),
        "automatic_off_topic_by_source": {
            t: sum(1 for d in off if d["source_type"] == t) for t in sorted({d["source_type"] for d in automatic})
        },
    }


def load_corpus_store():
    """Open the indexed corpus collection (read-only use)."""
    from ..utils.vector_store import VectorStore

    store = VectorStore(collection_name=COLLECTION_NAME)
    if store.get_count() == 0:
        raise RuntimeError(f"Collection '{COLLECTION_NAME}' is empty. Run: python -m src.experiment.corpus index")
    # Load the embedding model now, before any worker threads need it
    store.embedding_generator.embed_text("warm up")
    return store


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["fetch", "label", "index", "stats"])
    args = parser.parse_args()
    if args.command == "fetch":
        fetch_documents()
    elif args.command == "label":
        label_documents()
    elif args.command == "index":
        build_index()
    else:
        print(json.dumps(corpus_stats(), indent=2))


if __name__ == "__main__":
    main()
