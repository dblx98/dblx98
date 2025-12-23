from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Iterator, Optional

import trafilatura
from bs4 import BeautifulSoup
from slugify import slugify

from src.config import Settings


@dataclass(slots=True)
class ContentChunk:
    id: str
    url: str
    text: str
    content_type: str
    last_updated: datetime


MAIN_CONTENT_TAGS = {"article", "main", "section"}


def extract_main_content(html: str) -> str:
    downloaded = trafilatura.extract(html, include_comments=False, include_tables=False)
    if downloaded:
        return downloaded

    soup = BeautifulSoup(html, "html.parser")
    main_section = soup.find(MAIN_CONTENT_TAGS)
    text_source = main_section.get_text(" ", strip=True) if main_section else soup.get_text(" ", strip=True)
    return _remove_boilerplate(text_source)


def _remove_boilerplate(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text)
    return cleaned.strip()


def split_into_chunks(text: str, settings: Settings) -> list[str]:
    size = settings.content_chunk_size
    overlap = settings.content_chunk_overlap
    tokens = text.split(" ")
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(" ".join(chunk_tokens))
        start = end - overlap
        if start < 0:
            start = 0
    return [chunk for chunk in chunks if chunk.strip()]


def classify_content(url: str, html: Optional[str]) -> str:
    if html:
        soup = BeautifulSoup(html, "html.parser")
        if soup.find_all("li", attrs={"itemprop": "question"}):
            return "faq"
        if "blog" in url:
            return "blog"
        if any(keyword in url for keyword in ["pricing", "plans"]):
            return "pricing"
        if any(keyword in url for keyword in ["policy", "terms", "legal"]):
            return "policy"
    return "page"


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_chunks(url: str, html: str, settings: Settings, last_modified: Optional[str] = None) -> Iterable[ContentChunk]:
    content_type = classify_content(url, html)
    text = extract_main_content(html)
    for chunk in split_into_chunks(text, settings):
        chunk_id = slugify(f"{url}-{checksum(chunk)[:8]}")
        updated_at = (
            datetime.fromisoformat(last_modified) if last_modified else datetime.utcnow()
        )
        yield ContentChunk(
            id=chunk_id,
            url=url,
            text=chunk,
            content_type=content_type,
            last_updated=updated_at,
        )


def detect_updates(existing_checksums: dict[str, str], new_chunks: Iterable[ContentChunk]) -> Iterator[ContentChunk]:
    for chunk in new_chunks:
        if existing_checksums.get(chunk.id) != checksum(chunk.text):
            yield chunk
