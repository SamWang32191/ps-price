# PS Price Crawler Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate that Taiwan PlayStation Store catalog pages and concept detail pages can be fetched and parsed into stable product and price records.

**Architecture:** Build a small Python package inside `/Users/samwang/code/github.com/SamWang32191/ps-price` before creating the full Django app. The spike fetches SSR PlayStation Store HTML, extracts embedded Next.js and MFE JSON script state, parses catalog/concept/product/price fields, and saves sample fixtures for repeatable tests.

**Tech Stack:** Python 3.12, `httpx`, `beautifulsoup4`, `pytest`, `pytest-httpx`, stdlib `dataclasses`, stdlib `argparse`.

---

## Scope

This plan covers only the first milestone from the approved spec: crawler spike. It does not create the Django app, database models, Docker Compose deployment, UI, scheduler, or admin pages. Those belong in follow-up plans after this spike proves the data source shape.

Run every command from:

```bash
cd /Users/samwang/code/github.com/SamWang32191/ps-price
```

The current repo is clean and contains only `README.md`. Create a feature branch before editing:

```bash
git switch -c feat/crawler-spike
```

Expected:

```text
Switched to a new branch 'feat/crawler-spike'
```

## File Map

- Create: `pyproject.toml`
  - Project metadata, runtime dependencies, pytest configuration.
- Create: `.gitignore`
  - Exclude local virtualenv, pytest cache, Python bytecode, and large live HTML captures.
- Modify: `README.md`
  - Add spike commands and current data-source assumptions.
- Create: `src/ps_price_crawler/__init__.py`
  - Package marker and version.
- Create: `src/ps_price_crawler/models.py`
  - Dataclasses for catalog pages, products, prices, and parse results.
- Create: `src/ps_price_crawler/next_data.py`
  - Extract `__NEXT_DATA__` and `env:*` JSON scripts from SSR HTML.
- Create: `src/ps_price_crawler/catalog.py`
  - Parse PlayStation category grid pages and concept tiles.
- Create: `src/ps_price_crawler/product.py`
  - Parse concept detail pages and product-level fields.
- Create: `src/ps_price_crawler/client.py`
  - Conservative HTTP client and URL builders.
- Create: `src/ps_price_crawler/cli.py`
  - Command-line spike runner for fetching catalog pages and concept details.
- Create: `tests/test_next_data.py`
  - Unit tests for embedded JSON extraction.
- Create: `tests/test_catalog.py`
  - Unit tests for category grid parsing.
- Create: `tests/test_product.py`
  - Unit tests for concept detail parsing.
- Create during execution: `tests/fixtures/live/`
  - Captured sample HTML from current PS Store pages. Keep this local and ignored by git.
- Create during execution: `docs/spikes/ps-store-crawler-spike.md`
  - Short evidence report with URLs tested, product counts, sample IDs, and parse gaps.

---

## Task 1: Python Package Skeleton

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `src/ps_price_crawler/__init__.py`
- Modify: `README.md`

- [ ] **Step 1: Create git ignore rules**

Create `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
tests/fixtures/live/
```

- [ ] **Step 2: Create package metadata**

Create `pyproject.toml`:

```toml
[project]
name = "ps-price"
version = "0.1.0"
description = "Self-hosted PlayStation Store Taiwan price tracker"
requires-python = ">=3.12"
dependencies = [
  "beautifulsoup4>=4.12.3",
  "httpx>=0.27.2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.3",
  "pytest-httpx>=0.30.0",
]

[project.scripts]
ps-price-crawler = "ps_price_crawler.cli:main"

[build-system]
requires = ["hatchling>=1.25.0"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ps_price_crawler"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-q"
```

- [ ] **Step 3: Create package marker**

Create `src/ps_price_crawler/__init__.py`:

```python
"""PlayStation Store Taiwan crawler spike package."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Update README with spike purpose**

Replace `README.md` with:

```markdown
# ps-price

Self-hosted PlayStation Store Taiwan price tracker.

## Current milestone

The first milestone is a crawler spike. It validates that Taiwan PlayStation Store SSR pages expose enough embedded JSON to parse:

- catalog page totals and concept IDs
- concept/product names
- platform and product category fields
- visible public price fields

## Spike commands

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
ps-price-crawler catalog --pages 2 --save-fixtures tests/fixtures/live
ps-price-crawler concept 223118 --save-fixtures tests/fixtures/live
```
```

- [ ] **Step 5: Install package locally**

Run:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Expected:

```text
Successfully installed ps-price
```

- [ ] **Step 6: Verify package import**

Run:

```bash
python -c "import ps_price_crawler; print(ps_price_crawler.__version__)"
```

Expected:

```text
0.1.0
```

- [ ] **Step 7: Commit skeleton**

Run:

```bash
git add .gitignore README.md pyproject.toml src/ps_price_crawler/__init__.py
git commit -m "chore: scaffold crawler spike package"
```

Expected:

```text
[feat/crawler-spike ...] chore: scaffold crawler spike package
```

---

## Task 2: Embedded JSON Extraction

**Files:**
- Create: `src/ps_price_crawler/next_data.py`
- Create: `tests/test_next_data.py`

- [ ] **Step 1: Write failing tests for script extraction**

Create `tests/test_next_data.py`:

```python
import json

from ps_price_crawler.next_data import EmbeddedState, extract_embedded_state


def test_extracts_next_data_script():
    html = """
    <html>
      <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"apolloState":{"ROOT_QUERY":{"__typename":"Query"}}}}}
      </script>
    </html>
    """

    state = extract_embedded_state(html)

    assert isinstance(state, EmbeddedState)
    assert state.next_data["props"]["pageProps"]["apolloState"]["ROOT_QUERY"]["__typename"] == "Query"


def test_extracts_env_scripts_by_id():
    env_payload = {
        "args": {"conceptId": "223118"},
        "cache": {"Concept:223118": {"id": "223118", "__typename": "Concept", "name": "Roblox"}},
    }
    html = f"""
    <html>
      <script id="env:abc123" type="application/json">{json.dumps(env_payload)}</script>
    </html>
    """

    state = extract_embedded_state(html)

    assert state.env_scripts["env:abc123"]["args"]["conceptId"] == "223118"
    assert state.env_scripts["env:abc123"]["cache"]["Concept:223118"]["name"] == "Roblox"


def test_missing_next_data_returns_empty_dict():
    state = extract_embedded_state("<html></html>")

    assert state.next_data == {}
    assert state.env_scripts == {}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_next_data.py
```

Expected:

```text
ModuleNotFoundError: No module named 'ps_price_crawler.next_data'
```

- [ ] **Step 3: Implement embedded state extractor**

Create `src/ps_price_crawler/next_data.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class EmbeddedState:
    next_data: JsonObject
    env_scripts: dict[str, JsonObject]


def extract_embedded_state(html: str) -> EmbeddedState:
    soup = BeautifulSoup(html, "html.parser")
    next_data = _load_json_script(soup, "__NEXT_DATA__") or {}
    env_scripts: dict[str, JsonObject] = {}

    for script in soup.find_all("script"):
        script_id = script.get("id")
        if not script_id or not script_id.startswith("env:"):
            continue
        payload = _loads_script_text(script.get_text())
        if payload is not None:
            env_scripts[script_id] = payload

    return EmbeddedState(next_data=next_data, env_scripts=env_scripts)


def _load_json_script(soup: BeautifulSoup, script_id: str) -> JsonObject | None:
    script = soup.find("script", id=script_id)
    if script is None:
        return None
    return _loads_script_text(script.get_text())


def _loads_script_text(raw_text: str) -> JsonObject | None:
    text = raw_text.strip()
    if not text:
        return None
    loaded = json.loads(text)
    if not isinstance(loaded, dict):
        raise ValueError("Expected embedded JSON script to contain an object")
    return loaded
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
pytest tests/test_next_data.py
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit extractor**

Run:

```bash
git add src/ps_price_crawler/next_data.py tests/test_next_data.py
git commit -m "test: parse embedded playstation store json"
```

Expected:

```text
[feat/crawler-spike ...] test: parse embedded playstation store json
```

---

## Task 3: Catalog Page Parser

**Files:**
- Create: `src/ps_price_crawler/models.py`
- Create: `src/ps_price_crawler/catalog.py`
- Create: `tests/test_catalog.py`

- [ ] **Step 1: Write failing catalog parser tests**

Create `tests/test_catalog.py`:

```python
import json

from ps_price_crawler.catalog import parse_catalog_page


def _catalog_html() -> str:
    apollo_state = {
        "CategoryGrid:28c9:zh-hant-tw:0:24": {
            "__typename": "CategoryGrid",
            "id": "28c9",
            "pageInfo": {
                "__typename": "PageInfo",
                "totalCount": 7988,
                "offset": 0,
                "size": 24,
                "isLast": False,
            },
            "concepts": [
                {"__ref": "Concept:223118:zh-hant-tw"},
                {"__ref": "Concept:10005069:zh-hant-tw"},
            ],
        },
        "Concept:223118:zh-hant-tw": {
            "__typename": "Concept",
            "id": "223118",
            "name": "Roblox",
            "price": {
                "__typename": "SkuPrice",
                "basePrice": "免費",
                "discountedPrice": "免費",
                "isFree": True,
                "serviceBranding": ["NONE"],
            },
            "media": [{"role": "MASTER", "url": "https://example.test/roblox.png"}],
            "products": [{"__ref": "Product:UP1821-PPSA10990_00-1887411884729257:zh-hant-tw"}],
        },
        "Concept:10005069:zh-hant-tw": {
            "__typename": "Concept",
            "id": "10005069",
            "name": "《沙羅週期》",
            "price": {
                "__typename": "SkuPrice",
                "basePrice": "NT$1,990",
                "discountedPrice": "NT$1,990",
                "isFree": False,
                "serviceBranding": ["NONE"],
            },
            "media": [],
            "products": [{"__ref": "Product:HP0000-PPSA00000_00-SAROS0000000000:zh-hant-tw"}],
        },
    }
    next_data = {
        "props": {
            "pageProps": {
                "apolloState": apollo_state,
            }
        }
    }
    return f"""
    <html>
      <script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>
    </html>
    """


def test_parse_catalog_page_info():
    page = parse_catalog_page(_catalog_html(), source_url="https://store.playstation.com/zh-hant-tw/category/28c9/1")

    assert page.category_id == "28c9"
    assert page.total_count == 7988
    assert page.offset == 0
    assert page.size == 24
    assert page.is_last is False


def test_parse_catalog_concepts():
    page = parse_catalog_page(_catalog_html(), source_url="https://store.playstation.com/zh-hant-tw/category/28c9/1")

    assert [item.concept_id for item in page.items] == ["223118", "10005069"]
    assert page.items[0].name == "Roblox"
    assert page.items[0].price.discounted_price == "免費"
    assert page.items[0].price.is_free is True
    assert page.items[1].price.base_price == "NT$1,990"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_catalog.py
```

Expected:

```text
ModuleNotFoundError: No module named 'ps_price_crawler.catalog'
```

- [ ] **Step 3: Implement models**

Create `src/ps_price_crawler/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PriceInfo:
    base_price: str | None
    discounted_price: str | None
    discount_text: str | None
    is_free: bool
    is_exclusive: bool
    is_tied_to_subscription: bool
    service_branding: tuple[str, ...] = field(default_factory=tuple)
    upsell_text: str | None = None


@dataclass(frozen=True)
class CatalogItem:
    concept_id: str
    name: str
    product_ids: tuple[str, ...]
    image_url: str | None
    price: PriceInfo | None


@dataclass(frozen=True)
class CatalogPage:
    source_url: str
    category_id: str
    total_count: int
    offset: int
    size: int
    is_last: bool
    items: tuple[CatalogItem, ...]


@dataclass(frozen=True)
class ProductDetail:
    concept_id: str
    concept_name: str
    product_id: str | None
    product_name: str | None
    publisher_name: str | None
    release_date: str | None
    platforms: tuple[str, ...]
    top_category: str | None
    price: PriceInfo | None
```

- [ ] **Step 4: Implement catalog parser**

Create `src/ps_price_crawler/catalog.py`:

```python
from __future__ import annotations

from typing import Any

from ps_price_crawler.models import CatalogItem, CatalogPage, PriceInfo
from ps_price_crawler.next_data import extract_embedded_state


def parse_catalog_page(html: str, source_url: str) -> CatalogPage:
    state = extract_embedded_state(html)
    apollo_state = (
        state.next_data.get("props", {})
        .get("pageProps", {})
        .get("apolloState", {})
    )
    if not isinstance(apollo_state, dict):
        raise ValueError("Missing apolloState in catalog page")

    grid_key, grid = _find_category_grid(apollo_state)
    page_info = grid.get("pageInfo") or {}
    items = tuple(_catalog_item_from_ref(apollo_state, ref) for ref in grid.get("concepts", []))

    return CatalogPage(
        source_url=source_url,
        category_id=str(grid.get("id") or _category_id_from_key(grid_key)),
        total_count=int(page_info.get("totalCount") or 0),
        offset=int(page_info.get("offset") or 0),
        size=int(page_info.get("size") or 0),
        is_last=bool(page_info.get("isLast")),
        items=items,
    )


def _find_category_grid(apollo_state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for key, value in apollo_state.items():
        if key.startswith("CategoryGrid:") and isinstance(value, dict):
            return key, value
    raise ValueError("Catalog page does not contain a CategoryGrid entry")


def _category_id_from_key(key: str) -> str:
    parts = key.split(":")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse CategoryGrid key: {key}")
    return parts[1]


def _catalog_item_from_ref(apollo_state: dict[str, Any], ref: dict[str, str]) -> CatalogItem:
    concept_key = ref["__ref"]
    concept = apollo_state[concept_key]
    product_ids = tuple(_id_from_ref(product_ref["__ref"]) for product_ref in concept.get("products", []))
    return CatalogItem(
        concept_id=str(concept["id"]),
        name=str(concept.get("name") or ""),
        product_ids=product_ids,
        image_url=_master_image_url(concept),
        price=_price_info(concept.get("price")),
    )


def _id_from_ref(ref: str) -> str:
    parts = ref.split(":")
    if len(parts) < 2:
        return ref
    return parts[1]


def _master_image_url(concept: dict[str, Any]) -> str | None:
    media_items = concept.get("media") or concept.get("personalizedMeta", {}).get("media") or []
    for media in media_items:
        if media.get("role") == "MASTER" and media.get("url"):
            return str(media["url"])
    for media in media_items:
        if media.get("url"):
            return str(media["url"])
    return None


def _price_info(raw_price: dict[str, Any] | None) -> PriceInfo | None:
    if not raw_price:
        return None
    return PriceInfo(
        base_price=raw_price.get("basePrice"),
        discounted_price=raw_price.get("discountedPrice"),
        discount_text=raw_price.get("discountText"),
        is_free=bool(raw_price.get("isFree")),
        is_exclusive=bool(raw_price.get("isExclusive")),
        is_tied_to_subscription=bool(raw_price.get("isTiedToSubscription")),
        service_branding=tuple(raw_price.get("serviceBranding") or ()),
        upsell_text=raw_price.get("upsellText"),
    )
```

- [ ] **Step 5: Run catalog tests**

Run:

```bash
pytest tests/test_catalog.py
```

Expected:

```text
2 passed
```

- [ ] **Step 6: Run full unit tests**

Run:

```bash
pytest
```

Expected:

```text
5 passed
```

- [ ] **Step 7: Commit catalog parser**

Run:

```bash
git add src/ps_price_crawler/models.py src/ps_price_crawler/catalog.py tests/test_catalog.py
git commit -m "test: parse playstation catalog pages"
```

Expected:

```text
[feat/crawler-spike ...] test: parse playstation catalog pages
```

---

## Task 4: Concept Detail Parser

**Files:**
- Create: `src/ps_price_crawler/product.py`
- Create: `tests/test_product.py`

- [ ] **Step 1: Write failing product detail tests**

Create `tests/test_product.py`:

```python
import json

from ps_price_crawler.product import parse_product_detail


def _concept_html() -> str:
    env_payload = {
        "args": {"conceptId": "223118"},
        "cache": {
            "Product:UP1821-PPSA10990_00-1887411884729257": {
                "id": "UP1821-PPSA10990_00-1887411884729257",
                "__typename": "Product",
                "name": "Roblox (繁體中文)",
                "platforms": ["PS5"],
                "publisherName": "ROBLOX Corporation",
                "releaseDate": "2026-04-14T22:00:00Z",
                "topCategory": "GAME",
                "price": {
                    "basePrice": "免費",
                    "discountedPrice": "免費",
                    "isFree": True,
                    "serviceBranding": ["NONE"],
                },
            },
            "Concept:223118": {
                "id": "223118",
                "__typename": "Concept",
                "name": "Roblox",
                "publisherName": "ROBLOX Corporation",
                "defaultProduct": {"__ref": "Product:UP1821-PPSA10990_00-1887411884729257"},
                "releaseDate": {"value": "2023-10-10T21:00:00Z"},
            },
        },
    }
    return f"""
    <html>
      <script id="env:detail" type="application/json">{json.dumps(env_payload)}</script>
    </html>
    """


def test_parse_product_detail_from_env_cache():
    detail = parse_product_detail(_concept_html(), concept_id="223118")

    assert detail.concept_id == "223118"
    assert detail.concept_name == "Roblox"
    assert detail.product_id == "UP1821-PPSA10990_00-1887411884729257"
    assert detail.product_name == "Roblox (繁體中文)"
    assert detail.publisher_name == "ROBLOX Corporation"
    assert detail.release_date == "2026-04-14T22:00:00Z"
    assert detail.platforms == ("PS5",)
    assert detail.top_category == "GAME"
    assert detail.price is not None
    assert detail.price.is_free is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_product.py
```

Expected:

```text
ModuleNotFoundError: No module named 'ps_price_crawler.product'
```

- [ ] **Step 3: Implement product detail parser**

Create `src/ps_price_crawler/product.py`:

```python
from __future__ import annotations

from typing import Any

from ps_price_crawler.catalog import _id_from_ref, _price_info
from ps_price_crawler.models import ProductDetail
from ps_price_crawler.next_data import extract_embedded_state


def parse_product_detail(html: str, concept_id: str) -> ProductDetail:
    state = extract_embedded_state(html)
    cache = _combined_cache(state.env_scripts)
    concept = _find_concept(cache, concept_id)
    product = _default_product(cache, concept)

    release_date = product.get("releaseDate") or _concept_release_date(concept)
    price = _price_info(product.get("price") or concept.get("price"))

    return ProductDetail(
        concept_id=str(concept.get("id") or concept_id),
        concept_name=str(concept.get("name") or ""),
        product_id=product.get("id"),
        product_name=product.get("name"),
        publisher_name=product.get("publisherName") or concept.get("publisherName"),
        release_date=release_date,
        platforms=tuple(product.get("platforms") or ()),
        top_category=product.get("topCategory"),
        price=price,
    )


def _combined_cache(env_scripts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    combined: dict[str, Any] = {}
    for payload in env_scripts.values():
        cache = payload.get("cache")
        if isinstance(cache, dict):
            for key, value in cache.items():
                if (
                    key in combined
                    and isinstance(combined[key], dict)
                    and isinstance(value, dict)
                ):
                    combined[key] = {**combined[key], **value}
                else:
                    combined[key] = value
    return combined


def _find_concept(cache: dict[str, Any], concept_id: str) -> dict[str, Any]:
    for key, value in cache.items():
        if key.startswith(f"Concept:{concept_id}") and isinstance(value, dict):
            return value
    raise ValueError(f"Concept {concept_id} not found in embedded env cache")


def _default_product(cache: dict[str, Any], concept: dict[str, Any]) -> dict[str, Any]:
    default_product = concept.get("defaultProduct")
    if isinstance(default_product, dict) and default_product.get("__ref"):
        product_id = _id_from_ref(default_product["__ref"])
        for key, value in cache.items():
            if key.startswith(f"Product:{product_id}") and isinstance(value, dict):
                return value

    for key, value in cache.items():
        if key.startswith("Product:") and isinstance(value, dict):
            return value

    return {}


def _concept_release_date(concept: dict[str, Any]) -> str | None:
    release_date = concept.get("releaseDate")
    if isinstance(release_date, dict):
        value = release_date.get("value")
        return str(value) if value else None
    if isinstance(release_date, str):
        return release_date
    return None
```

- [ ] **Step 4: Run product detail tests**

Run:

```bash
pytest tests/test_product.py
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Run full unit tests**

Run:

```bash
pytest
```

Expected:

```text
6 passed
```

- [ ] **Step 6: Commit product parser**

Run:

```bash
git add src/ps_price_crawler/product.py tests/test_product.py
git commit -m "test: parse playstation concept details"
```

Expected:

```text
[feat/crawler-spike ...] test: parse playstation concept details
```

---

## Task 5: Conservative HTTP Client and CLI

**Files:**
- Create: `src/ps_price_crawler/client.py`
- Create: `src/ps_price_crawler/cli.py`

- [ ] **Step 1: Implement client**

Create `src/ps_price_crawler/client.py`:

```python
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
```

- [ ] **Step 2: Implement CLI**

Create `src/ps_price_crawler/cli.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from ps_price_crawler.catalog import parse_catalog_page
from ps_price_crawler.client import PlayStationStoreClient, save_fixture
from ps_price_crawler.product import parse_product_detail


def main() -> None:
    parser = argparse.ArgumentParser(prog="ps-price-crawler")
    subcommands = parser.add_subparsers(dest="command", required=True)

    catalog_parser = subcommands.add_parser("catalog")
    catalog_parser.add_argument("--pages", type=int, default=1)
    catalog_parser.add_argument("--save-fixtures", type=Path)

    concept_parser = subcommands.add_parser("concept")
    concept_parser.add_argument("concept_id")
    concept_parser.add_argument("--save-fixtures", type=Path)

    args = parser.parse_args()

    if args.command == "catalog":
        run_catalog(args.pages, args.save_fixtures)
        return
    if args.command == "concept":
        run_concept(args.concept_id, args.save_fixtures)
        return
    raise SystemExit(f"Unsupported command: {args.command}")


def run_catalog(pages: int, fixture_dir: Path | None) -> None:
    with PlayStationStoreClient() as client:
        for page_number in range(1, pages + 1):
            url, html = client.fetch_catalog_page(page_number)
            parsed = parse_catalog_page(html, source_url=url)
            if fixture_dir is not None:
                save_fixture(fixture_dir, f"catalog_page_{page_number}.html", html)
            print(
                f"catalog page={page_number} total={parsed.total_count} "
                f"offset={parsed.offset} size={parsed.size} items={len(parsed.items)} "
                f"is_last={parsed.is_last}"
            )
            for item in parsed.items[:5]:
                price = item.price.discounted_price if item.price else "NO_PRICE"
                print(f"  concept={item.concept_id} name={item.name} price={price}")


def run_concept(concept_id: str, fixture_dir: Path | None) -> None:
    with PlayStationStoreClient() as client:
        url, html = client.fetch_concept(concept_id)
    detail = parse_product_detail(html, concept_id=concept_id)
    if fixture_dir is not None:
        save_fixture(fixture_dir, f"concept_{concept_id}.html", html)
    price = detail.price.discounted_price if detail.price else "NO_PRICE"
    print(
        f"concept={detail.concept_id} product={detail.product_id} "
        f"name={detail.product_name or detail.concept_name} "
        f"platforms={','.join(detail.platforms)} category={detail.top_category} price={price}"
    )
```

- [ ] **Step 3: Run full unit tests**

Run:

```bash
pytest
```

Expected:

```text
6 passed
```

- [ ] **Step 4: Run live catalog spike**

Run:

```bash
ps-price-crawler catalog --pages 2 --save-fixtures tests/fixtures/live
```

Expected output must include:

```text
catalog page=1
catalog page=2
items=24
```

The total count may change over time. On 2026-04-27, the observed Taiwan browse page reported about 7,988 items.

- [ ] **Step 5: Run live concept spike**

Run:

```bash
ps-price-crawler concept 223118 --save-fixtures tests/fixtures/live
```

Expected output must include:

```text
concept=223118
name=Roblox
category=GAME
```

- [ ] **Step 6: Commit client and CLI**

Run:

```bash
git add src/ps_price_crawler/client.py src/ps_price_crawler/cli.py
git commit -m "feat: add playstation crawler spike cli"
```

Expected:

```text
[feat/crawler-spike ...] feat: add playstation crawler spike cli
```

---

## Task 6: Spike Evidence Report

**Files:**
- Create: `docs/spikes/ps-store-crawler-spike.md`
- Modify: `README.md`

- [ ] **Step 1: Run live spike commands**

Run:

```bash
ps-price-crawler catalog --pages 2 --save-fixtures tests/fixtures/live
ps-price-crawler concept 223118 --save-fixtures tests/fixtures/live
```

Expected output must include:

```text
catalog page=1
catalog page=2
concept=223118
```

- [ ] **Step 2: Create evidence report**

Create `docs/spikes/ps-store-crawler-spike.md` after the live commands complete. Write the `## Spike Result` section from the actual output produced by Step 1; do not leave instructional text in the committed report.

```markdown
# PS Store Crawler Spike

Date: 2026-04-27

## URLs Tested

- `https://store.playstation.com/zh-hant-tw/category/28c9c2b2-cecc-415c-9a08-482a605cb104/1`
- `https://store.playstation.com/zh-hant-tw/category/28c9c2b2-cecc-415c-9a08-482a605cb104/2`
- `https://store.playstation.com/zh-hant-tw/concept/223118`

## Expected Evidence

- Catalog SSR pages expose `__NEXT_DATA__`.
- Category grid data appears under `apolloState` keys starting with `CategoryGrid:`.
- Catalog pages include `pageInfo.totalCount`, `pageInfo.offset`, `pageInfo.size`, `pageInfo.isLast`.
- Catalog pages include concept refs and concept names.
- Concept detail pages expose `env:*` JSON scripts with MFE cache data.
- Product detail cache includes product IDs, names, platforms, publisher, release date, and `topCategory` for at least one sampled product.

## Spike Result

## Known Gaps After Spike

- Confirm a discounted paid product fixture.
- Confirm a PS Plus price fixture.
- Confirm an unavailable or non-purchasable product fixture.
- Decide whether catalog page price is sufficient for daily price snapshots or whether every concept detail page must be fetched.
```

- [ ] **Step 3: Update README with current spike status**

Append to `README.md`:

```markdown

## Data source notes

The crawler spike starts from PlayStation Store Taiwan SSR pages:

- catalog: `/zh-hant-tw/category/28c9c2b2-cecc-415c-9a08-482a605cb104/{page}`
- concept detail: `/zh-hant-tw/concept/{conceptId}`

The parser reads embedded `__NEXT_DATA__` and `env:*` JSON script payloads. This is a non-public implementation detail of the PlayStation Store website, so parser failures are treated as expected maintenance events.
```

- [ ] **Step 4: Run final verification**

Run:

```bash
pytest
ps-price-crawler catalog --pages 2
ps-price-crawler concept 223118
git status --short
```

Expected:

```text
6 passed
catalog page=1
catalog page=2
concept=223118
```

`git status --short` should show only intentional files for this spike.

- [ ] **Step 5: Commit evidence report**

Run:

```bash
git add README.md docs/spikes/ps-store-crawler-spike.md
git commit -m "docs: record playstation crawler spike findings"
```

Expected:

```text
[feat/crawler-spike ...] docs: record playstation crawler spike findings
```

---

## Self-Review Checklist

- Spec coverage:
  - Crawler source validation: Task 5 and Task 6.
  - Catalog list parsing: Task 3 and Task 5.
  - Concept/product parsing: Task 4 and Task 5.
  - Fixture-based repeatable tests: Task 2 through Task 4.
  - Conservative request behavior: Task 5.
  - Evidence report for follow-up Django planning: Task 6.
- Known exclusions:
  - No Django app.
  - No SQLite models.
  - No Docker Compose.
  - No scheduler.
  - No UI.
  - No full catalog backfill.
- Implementation stop condition:
  - Stop after `docs/spikes/ps-store-crawler-spike.md` records the live results and gaps.
