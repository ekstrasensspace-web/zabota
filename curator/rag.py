"""
RAG (Retrieval-Augmented Generation) module.
Uses BM25 full-text search over Markdown knowledge files.
No external embedding API or heavy ML models required.
"""

import re
import logging
from pathlib import Path
from typing import Optional

from rank_bm25 import BM25Okapi

from config import KNOWLEDGE_DIR, CHUNK_SIZE, CHUNK_OVERLAP, TOP_K

logger = logging.getLogger(__name__)

# In-memory index (built once at startup)
_bm25: Optional[BM25Okapi] = None
_chunks: list[str] = []
_metadata: list[dict] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Simple word tokenizer for Russian + English text."""
    return re.findall(r"[а-яёa-z0-9]+", text.lower())


def _split_text(text: str) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph breaks."""
    if len(text) <= CHUNK_SIZE:
        return [text] if text.strip() else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        if end < len(text):
            # Try to break at a paragraph boundary
            bp = text.rfind("\n\n", start, end)
            if bp > start + CHUNK_SIZE // 2:
                end = bp
        chunk = text[start:end].strip()
        if len(chunk) > 80:
            chunks.append(chunk)
        start = end - CHUNK_OVERLAP
        if start >= len(text):
            break
    return chunks


def _course_name(path: str) -> str:
    """Infer course name from file path."""
    p = path.lower()
    if any(k in p for k in ("друид", "druid")):
        return "Магия Друидов"
    if any(k in p for k in ("ченнелинг", "channeling")):
        return "Ченнелинг"
    if any(k in p for k in ("7-луч", "7_луч", "лучей", "rays")):
        return "7 Лучей"
    if "предсказан" in p:
        return "Мастер Предсказаний"
    if any(k in p for k in ("рун", "rune")):
        return "Магия Рун"
    if any(k in p for k in ("рейки", "reiki", "тибет", "tibeт", "bон", "bon")):
        return "Тибетский Рейки Бон"
    return "Общее"


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

def build_index() -> None:
    """
    Load all .md files from KNOWLEDGE_DIR, split into chunks,
    and build the BM25 index. Called once at bot startup.
    """
    global _bm25, _chunks, _metadata

    kd = Path(KNOWLEDGE_DIR)
    if not kd.exists():
        logger.error("Knowledge directory not found: %s", kd)
        return

    raw_chunks: list[tuple[str, dict]] = []
    file_count = 0

    for md_file in sorted(kd.rglob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
            rel = str(md_file.relative_to(kd))
            course = _course_name(rel)
            for chunk in _split_text(text):
                raw_chunks.append((chunk, {"source": rel, "course": course}))
            file_count += 1
        except Exception as exc:
            logger.warning("Skipping %s: %s", md_file, exc)

    if not raw_chunks:
        logger.warning("No knowledge chunks loaded — check KNOWLEDGE_DIR=%s", kd)
        return

    _chunks = [c[0] for c in raw_chunks]
    _metadata = [c[1] for c in raw_chunks]
    tokenized = [_tokenize(c) for c in _chunks]
    _bm25 = BM25Okapi(tokenized)

    logger.info(
        "Knowledge index ready: %d chunks from %d files in %s",
        len(_chunks), file_count, kd,
    )


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def query_knowledge(question: str, top_k: int = TOP_K) -> list[str]:
    """
    Return the top-k most relevant text chunks for the given question.
    Each result is prefixed with its course + source path.
    Returns an empty list if the index is not built or no match found.
    """
    if _bm25 is None:
        logger.warning("BM25 index not built yet")
        return []

    tokens = _tokenize(question)
    if not tokens:
        return []

    scores = _bm25.get_scores(tokens)
    top_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results: list[str] = []
    for idx in top_idx:
        if scores[idx] <= 0:
            continue
        meta = _metadata[idx]
        results.append(f"[{meta['course']}]\n{_chunks[idx]}")

    return results
