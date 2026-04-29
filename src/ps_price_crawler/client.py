from __future__ import annotations

import time
from pathlib import Path

import httpx


LOCALE = "zh-hant-tw"
BASE_URL = "https://store.playstation.com"
ALL_GAMES_CATEGORY_ID = "28c9c2b2-cecc-415c-9a08-482a605cb104"


class PlayStationStoreClient:
    def __init__(self, delay_seconds: float = 1.5, timeout_seconds: float = 30.0) -> None:
        self.delay_seconds = delay_seconds
        self._last_request_at = 0.0
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "accept-language": "zh-TW,zh-Hant;q=0.9,en-US;q=0.7,en;q=0.6",
                "user-agent": "ps-price-crawler/0.1 self-hosted research",
            },
        )

    def close(self) -> None:
        self._client.close()

    def fetch_catalog_page(self, page: int) -> tuple[str, str]:
        url = catalog_page_url(page)
        return url, self._get(url)

    def fetch_concept(self, concept_id: str) -> tuple[str, str]:
        url = concept_url(concept_id)
        return url, self._get(url)

    def _get(self, url: str) -> str:
        self._sleep_before_request()
        response = self._client.get(url)
        response.raise_for_status()
        return response.text

    def _sleep_before_request(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def __enter__(self) -> "PlayStationStoreClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def catalog_page_url(page: int) -> str:
    if page < 1:
        raise ValueError("Catalog page must be 1 or greater")
    return f"{BASE_URL}/{LOCALE}/category/{ALL_GAMES_CATEGORY_ID}/{page}"


def concept_url(concept_id: str) -> str:
    return f"{BASE_URL}/{LOCALE}/concept/{concept_id}"


def save_fixture(directory: Path, name: str, html: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(html, encoding="utf-8")
    return path
