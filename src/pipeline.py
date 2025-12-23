from __future__ import annotations

from datetime import datetime

from src.config import settings_from_env
from src.crawler import WebsiteCrawler
from src.processing import build_chunks, checksum, detect_updates
from src.storage import MetadataStore, VectorStore


def run_full_refresh() -> None:
    settings = settings_from_env()
    crawler = WebsiteCrawler(settings)
    metadata = MetadataStore(settings.metadata_db_path)
    vector_store = VectorStore(settings)

    checksums = metadata.existing_checksums()
    new_chunks = []

    for page in crawler.crawl():
        if not page.html:
            continue
        chunks = build_chunks(
            page.url,
            page.html,
            settings=settings,
            last_modified=page.last_modified,
        )
        for chunk in detect_updates(checksums, chunks):
            new_chunks.append(chunk)
            metadata.save_checksum(chunk, checksum(chunk.text))

    vector_store.add_chunks(new_chunks)
    print(f"Indexed {len(new_chunks)} new or updated chunks @ {datetime.utcnow().isoformat()}" )


if __name__ == "__main__":
    run_full_refresh()
