from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.config import Settings, allowed_domain


@dataclass(slots=True)
class CrawlResult:
    url: str
    status_code: int
    content_type: str | None
    html: str | None
    last_modified: str | None


class WebsiteCrawler:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.visited: set[str] = set()
        self.to_visit: deque[tuple[str, int]] = deque()

    def crawl(self, start_url: Optional[str] = None) -> Iterator[CrawlResult]:
        seed = start_url or str(self.settings.base_url)
        self.to_visit.append((seed, 0))

        while self.to_visit and self._within_limit():
            url, depth = self.to_visit.popleft()
            if url in self.visited or depth > self.settings.max_depth:
                continue

            if not allowed_domain(url, self.settings.allowed_domains):
                continue

            self.visited.add(url)
            response = self._fetch(url)
            if response is None:
                continue

            html = response.text if "text/html" in response.headers.get("content-type", "") else None
            yield CrawlResult(
                url=url,
                status_code=response.status_code,
                content_type=response.headers.get("content-type"),
                html=html,
                last_modified=response.headers.get("last-modified"),
            )

            if html:
                for link in self._extract_links(url, html):
                    self.to_visit.append((link, depth + 1))

    def _within_limit(self) -> bool:
        if self.settings.max_pages is None:
            return True
        return len(self.visited) < self.settings.max_pages

    def _fetch(self, url: str) -> Optional[requests.Response]:
        time.sleep(1 / self.settings.rate_limit_per_second)
        headers = {"User-Agent": self.settings.user_agent}
        try:
            response = requests.get(url, headers=headers, timeout=self.settings.request_timeout)
            response.raise_for_status()
            return response
        except requests.RequestException:
            return None

    def _extract_links(self, base_url: str, html: str) -> Iterable[str]:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if allowed_domain(normalized, self.settings.allowed_domains):
                yield normalized
