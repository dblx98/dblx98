from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

import chromadb
from chromadb.utils import embedding_functions

from src.config import Settings
from src.processing import ContentChunk


@dataclass(slots=True)
class StoredChunk:
    id: str
    url: str
    text: str
    content_type: str
    last_updated: datetime


class MetadataStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    last_updated TEXT NOT NULL,
                    checksum TEXT NOT NULL
                );
                """
            )
            conn.commit()

    def save_checksum(self, chunk: ContentChunk, checksum: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chunks (id, url, content_type, last_updated, checksum)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    url=excluded.url,
                    content_type=excluded.content_type,
                    last_updated=excluded.last_updated,
                    checksum=excluded.checksum;
                """,
                (
                    chunk.id,
                    chunk.url,
                    chunk.content_type,
                    chunk.last_updated.isoformat(),
                    checksum,
                ),
            )
            conn.commit()

    def existing_checksums(self) -> dict[str, str]:
        with self._connect() as conn:
            cursor = conn.execute("SELECT id, checksum FROM chunks")
            return {row[0]: row[1] for row in cursor.fetchall()}


class VectorStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = chromadb.PersistentClient(path=str(settings.chroma_path))
        embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embed_model
        )
        self.collection = self.client.get_or_create_collection(
            name="website-knowledge",
            embedding_function=embed_fn,
        )

    def add_chunks(self, chunks: Iterable[ContentChunk]) -> None:
        ids: list[str] = []
        texts: list[str] = []
        metadatas: list[dict] = []
        for chunk in chunks:
            ids.append(chunk.id)
            texts.append(chunk.text)
            metadatas.append(
                {
                    "url": chunk.url,
                    "content_type": chunk.content_type,
                    "last_updated": chunk.last_updated.isoformat(),
                }
            )
        if ids:
            self.collection.add(documents=texts, ids=ids, metadatas=metadatas)

    def search(self, query: str, k: int = 5) -> list[StoredChunk]:
        results = self.collection.query(query_texts=[query], n_results=k)
        stored: list[StoredChunk] = []
        for idx, doc_id in enumerate(results.get("ids", [[]])[0]):
            stored.append(
                StoredChunk(
                    id=doc_id,
                    url=results["metadatas"][0][idx]["url"],
                    text=results["documents"][0][idx],
                    content_type=results["metadatas"][0][idx]["content_type"],
                    last_updated=datetime.fromisoformat(
                        results["metadatas"][0][idx]["last_updated"]
                    ),
                )
            )
        return stored

    def as_json(self) -> str:
        return json.dumps(self.collection.get())
