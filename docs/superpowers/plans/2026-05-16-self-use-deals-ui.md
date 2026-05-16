# Self-Use Deals UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first server-rendered self-use deals UI with `/deals/` and `/products/<product_id>/`.

**Architecture:** Add a new read-only `ps_price_web` Django app for page routing, query helpers, formatting helpers, views, and templates. Keep crawler, ingestion, scheduler, and ORM writes inside existing boundaries; the web app only reads `StoreProduct` and `PriceSnapshot`.

**Tech Stack:** Python 3.12+, Django 5.2, SQLite, pytest, pytest-django, Django templates.

---

## File Structure

- Create: `src/ps_price_web/__init__.py`
  - Package marker for the web app.
- Create: `src/ps_price_web/apps.py`
  - Django app config.
- Create: `src/ps_price_web/formatting.py`
  - Small display helpers for money and raw JSON text.
- Create: `src/ps_price_web/queries.py`
  - Read-only query helpers for latest deals, latest snapshot, and regular historical low.
- Create: `src/ps_price_web/views.py`
  - `deals_view` and `product_detail_view`.
- Create: `src/ps_price_web/urls.py`
  - App-level routes for `/deals/` and `/products/<product_id>/`.
- Create: `src/ps_price_web/templates/ps_price_web/base.html`
  - Minimal shared HTML shell.
- Create: `src/ps_price_web/templates/ps_price_web/deals.html`
  - Deals list template.
- Create: `src/ps_price_web/templates/ps_price_web/product_detail.html`
  - Product detail template.
- Modify: `src/ps_price_site/settings.py`
  - Add `ps_price_web` to `INSTALLED_APPS`.
  - Add `TEMPLATES` with `APP_DIRS = True`.
- Modify: `src/ps_price_site/urls.py`
  - Include `ps_price_web.urls`.
- Modify: `pyproject.toml`
  - Add `src/ps_price_web` to hatch wheel packages.
- Modify: `tests/test_django_setup.py`
  - Update installed apps expectation and assert template config exists.
- Create: `tests/test_web_queries.py`
  - Focused query helper tests.
- Create: `tests/test_web_views.py`
  - HTTP view tests using Django test client.

## Task 1: Register `ps_price_web` App And URL Boundary

**Files:**
- Create: `src/ps_price_web/__init__.py`
- Create: `src/ps_price_web/apps.py`
- Create: `src/ps_price_web/urls.py`
- Modify: `src/ps_price_site/settings.py`
- Modify: `src/ps_price_site/urls.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_django_setup.py`

- [ ] **Step 1: Write failing Django setup tests**

Update `tests/test_django_setup.py` so `test_django_settings_module_is_configured` expects the new app and template config:

```python
from pathlib import Path
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.urls import resolve, reverse


def test_manage_py_exists() -> None:
    assert Path("manage.py").exists()


def test_django_settings_module_is_configured() -> None:
    settings_path = Path("src/ps_price_site/settings.py")
    assert settings_path.exists()
    assert 'TIME_ZONE = "Asia/Taipei"' in settings_path.read_text()

    assert settings.configured
    assert settings.TIME_ZONE == "Asia/Taipei"
    assert settings.USE_TZ
    assert settings.INSTALLED_APPS == [
        "django.contrib.contenttypes",
        "ps_price_sync",
        "ps_price_web",
    ]
    assert settings.TEMPLATES[0]["APP_DIRS"] is True
    assert apps.get_app_config("ps_price_sync").name == "ps_price_sync"
    assert apps.get_app_config("ps_price_web").name == "ps_price_web"
    assert import_module(settings.ROOT_URLCONF).__name__ == "ps_price_site.urls"


def test_web_routes_are_registered() -> None:
    assert reverse("ps_price_web:deals") == "/deals/"
    assert reverse("ps_price_web:product_detail", kwargs={"product_id": "P-100"}) == "/products/P-100/"
    assert resolve("/deals/").view_name == "ps_price_web:deals"
    assert resolve("/products/P-100/").view_name == "ps_price_web:product_detail"


def test_readme_mentions_django_sync_commands() -> None:
    readme_content = Path("README.md").read_text()
    assert "uv run python manage.py migrate" in readme_content
    assert "uv run python manage.py sync_ps_store --mode catalog-and-snapshot" in readme_content
```

- [ ] **Step 2: Run setup tests to verify they fail**

Run:

```bash
uv run pytest tests/test_django_setup.py -q
```

Expected: fail because `ps_price_web` is not installed and routes do not exist.

- [ ] **Step 3: Create the web app skeleton**

Create `src/ps_price_web/__init__.py`:

```python
from __future__ import annotations
```

Create `src/ps_price_web/apps.py`:

```python
from __future__ import annotations

from django.apps import AppConfig


class PsPriceWebConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ps_price_web"
```

Create `src/ps_price_web/urls.py`:

```python
from __future__ import annotations

from django.urls import path

from ps_price_web import views

app_name = "ps_price_web"

urlpatterns = [
    path("deals/", views.deals_view, name="deals"),
    path("products/<str:product_id>/", views.product_detail_view, name="product_detail"),
]
```

Create a temporary minimal `src/ps_price_web/views.py` so URL importing works:

```python
from __future__ import annotations

from django.http import HttpRequest, HttpResponse


def deals_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("deals")


def product_detail_view(request: HttpRequest, product_id: str) -> HttpResponse:
    return HttpResponse(product_id)
```

- [ ] **Step 4: Register app, templates, URL include, and package**

Modify `src/ps_price_site/settings.py`:

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = "dev-only-ps-price"

DEBUG = True

ALLOWED_HOSTS: list[str] = []

USE_TZ = True
TIME_ZONE = "Asia/Taipei"

ROOT_URLCONF = "ps_price_site.urls"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "ps_price_sync",
    "ps_price_web",
]

MIDDLEWARE: list[str] = []

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [],
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

Modify `src/ps_price_site/urls.py`:

```python
from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("", include("ps_price_web.urls")),
]
```

Modify the hatch packages block in `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/ps_price_crawler", "src/ps_price_site", "src/ps_price_sync", "src/ps_price_web"]
```

- [ ] **Step 5: Run setup tests to verify they pass**

Run:

```bash
uv run pytest tests/test_django_setup.py -q
```

Expected: pass.

- [ ] **Step 6: Commit app boundary**

Run:

```bash
git add pyproject.toml src/ps_price_site/settings.py src/ps_price_site/urls.py src/ps_price_web tests/test_django_setup.py
git commit -m "feat: add price web app boundary"
```

## Task 2: Add Formatting Helpers

**Files:**
- Create: `src/ps_price_web/formatting.py`
- Test: `tests/test_web_queries.py`

- [ ] **Step 1: Write failing formatting tests**

Create `tests/test_web_queries.py` with these initial tests:

```python
from __future__ import annotations

from ps_price_web.formatting import format_money_twd, format_raw_json_list


def test_format_money_twd_formats_integer_cents() -> None:
    assert format_money_twd(59000, "NT$590") == "NT$590"
    assert format_money_twd(0, "Free") == "NT$0"


def test_format_money_twd_falls_back_to_display_text() -> None:
    assert format_money_twd(None, "NT$1,490") == "NT$1,490"
    assert format_money_twd(None, None) == "-"


def test_format_raw_json_list_formats_json_arrays() -> None:
    assert format_raw_json_list('["PS5", "PS4"]') == "PS5, PS4"
    assert format_raw_json_list("[]") == "-"


def test_format_raw_json_list_falls_back_to_raw_text() -> None:
    assert format_raw_json_list("not-json") == "not-json"
    assert format_raw_json_list("") == "-"
```

- [ ] **Step 2: Run formatting tests to verify they fail**

Run:

```bash
uv run pytest tests/test_web_queries.py -q
```

Expected: fail because `ps_price_web.formatting` does not exist.

- [ ] **Step 3: Implement formatting helpers**

Create `src/ps_price_web/formatting.py`:

```python
from __future__ import annotations

import json
from typing import Any


def format_money_twd(amount_cents: int | None, display_text: str | None = None) -> str:
    if amount_cents is not None:
        return f"NT${amount_cents // 100:,}"
    if display_text:
        return display_text
    return "-"


def format_raw_json_list(raw_value: str | None) -> str:
    if not raw_value:
        return "-"
    try:
        parsed: Any = json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value
    if not isinstance(parsed, list):
        return raw_value
    values = [str(item) for item in parsed if item is not None and str(item)]
    if not values:
        return "-"
    return ", ".join(values)
```

- [ ] **Step 4: Run formatting tests to verify they pass**

Run:

```bash
uv run pytest tests/test_web_queries.py -q
```

Expected: pass.

- [ ] **Step 5: Commit formatting helpers**

Run:

```bash
git add src/ps_price_web/formatting.py tests/test_web_queries.py
git commit -m "feat: add web formatting helpers"
```

## Task 3: Add Read-Only Deal Query Helpers

**Files:**
- Create: `src/ps_price_web/queries.py`
- Modify: `tests/test_web_queries.py`

- [ ] **Step 1: Add failing query tests for deals**

Append to `tests/test_web_queries.py`:

```python
from datetime import date

import pytest

from ps_price_sync.models import PriceSnapshot, StoreProduct
from ps_price_web.queries import get_latest_deals


def create_product(product_id: str, name: str, *, concept_name: str = "", is_visible: bool | None = True) -> StoreProduct:
    return StoreProduct.objects.create(
        product_id=product_id,
        product_name=name,
        concept_name=concept_name,
        is_visible=is_visible,
    )


def create_snapshot(
    product: StoreProduct,
    snapshot_date: date,
    state: str,
    *,
    base: int | None = None,
    discounted: int | None = None,
) -> PriceSnapshot:
    return PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=snapshot_date,
        normalized_state=state,
        base_amount_cents=base,
        discounted_amount_cents=discounted,
        source_strategy_source="catalog",
        source_strategy_reason="catalog_price",
    )


@pytest.mark.django_db
def test_get_latest_deals_only_returns_discounted_latest_snapshots() -> None:
    discounted = create_product("P-DISCOUNT", "Discounted")
    paid = create_product("P-PAID", "Paid")
    plus = create_product("P-PLUS", "Plus")
    hidden = create_product("P-HIDDEN", "Hidden", is_visible=False)

    create_snapshot(discounted, date(2026, 5, 15), "PAID", base=100000)
    create_snapshot(discounted, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=50000)
    create_snapshot(paid, date(2026, 5, 16), "PAID", base=90000)
    create_snapshot(plus, date(2026, 5, 16), "PS_PLUS", base=90000, discounted=60000)
    create_snapshot(hidden, date(2026, 5, 16), "DISCOUNTED", base=90000, discounted=30000)

    deals = get_latest_deals()

    assert [deal.product.product_id for deal in deals] == ["P-DISCOUNT"]
    assert deals[0].snapshot.normalized_state == "DISCOUNTED"
    assert deals[0].discount_percent == 50


@pytest.mark.django_db
def test_get_latest_deals_sorts_by_discount_percent_descending() -> None:
    lower = create_product("P-LOWER", "Lower")
    higher = create_product("P-HIGHER", "Higher")

    create_snapshot(lower, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=75000)
    create_snapshot(higher, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=40000)

    deals = get_latest_deals()

    assert [deal.product.product_id for deal in deals] == ["P-HIGHER", "P-LOWER"]
    assert [deal.discount_percent for deal in deals] == [60, 25]


@pytest.mark.django_db
def test_get_latest_deals_searches_product_and_concept_name() -> None:
    product_match = create_product("P-PRODUCT", "Final Fantasy")
    concept_match = create_product("P-CONCEPT", "Some Edition", concept_name="Monster Hunter")
    miss = create_product("P-MISS", "Gran Turismo")

    create_snapshot(product_match, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=60000)
    create_snapshot(concept_match, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=50000)
    create_snapshot(miss, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=40000)

    assert [deal.product.product_id for deal in get_latest_deals(query="fantasy")] == ["P-PRODUCT"]
    assert [deal.product.product_id for deal in get_latest_deals(query="hunter")] == ["P-CONCEPT"]
```

- [ ] **Step 2: Run query tests to verify they fail**

Run:

```bash
uv run pytest tests/test_web_queries.py -q
```

Expected: fail because `ps_price_web.queries` does not exist.

- [ ] **Step 3: Implement deal query helper**

Create `src/ps_price_web/queries.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Max, Q

from ps_price_sync.models import PriceSnapshot, StoreProduct


@dataclass(frozen=True)
class DealRow:
    product: StoreProduct
    snapshot: PriceSnapshot
    discount_percent: int


def _discount_percent(base_amount_cents: int, discounted_amount_cents: int) -> int:
    discount = Decimal(base_amount_cents - discounted_amount_cents) / Decimal(base_amount_cents)
    return int((discount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def get_latest_deals(query: str = "") -> list[DealRow]:
    products = StoreProduct.objects.exclude(is_visible=False)
    search = query.strip()
    if search:
        products = products.filter(Q(product_name__icontains=search) | Q(concept_name__icontains=search))

    latest_dates = (
        PriceSnapshot.objects.filter(store_product__in=products)
        .values("store_product_id")
        .annotate(latest_date=Max("snapshot_date"))
    )
    latest_lookup = {row["store_product_id"]: row["latest_date"] for row in latest_dates}

    snapshots = (
        PriceSnapshot.objects.select_related("store_product")
        .filter(
            store_product_id__in=latest_lookup.keys(),
            normalized_state="DISCOUNTED",
            base_amount_cents__isnull=False,
            discounted_amount_cents__isnull=False,
        )
        .order_by("store_product__product_name", "store_product__product_id")
    )

    deals: list[DealRow] = []
    for snapshot in snapshots:
        if latest_lookup.get(snapshot.store_product_id) != snapshot.snapshot_date:
            continue
        base = snapshot.base_amount_cents
        discounted = snapshot.discounted_amount_cents
        if base is None or discounted is None or base <= 0 or discounted >= base:
            continue
        deals.append(
            DealRow(
                product=snapshot.store_product,
                snapshot=snapshot,
                discount_percent=_discount_percent(base, discounted),
            )
        )

    return sorted(deals, key=lambda deal: (-deal.discount_percent, deal.product.product_name, deal.product.product_id))
```

- [ ] **Step 4: Run query tests to verify they pass**

Run:

```bash
uv run pytest tests/test_web_queries.py -q
```

Expected: pass.

- [ ] **Step 5: Commit deal query helper**

Run:

```bash
git add src/ps_price_web/queries.py tests/test_web_queries.py
git commit -m "feat: add latest deals query"
```

## Task 4: Add Product Detail Query Helpers

**Files:**
- Modify: `src/ps_price_web/queries.py`
- Modify: `tests/test_web_queries.py`

- [ ] **Step 1: Add failing detail query tests**

Append to `tests/test_web_queries.py`:

```python
from ps_price_web.queries import get_product_detail


@pytest.mark.django_db
def test_get_product_detail_returns_latest_snapshot_and_regular_historical_low() -> None:
    product = create_product("P-DETAIL", "Detail Product")

    create_snapshot(product, date(2026, 5, 14), "PAID", base=120000)
    create_snapshot(product, date(2026, 5, 15), "PS_PLUS", base=120000, discounted=20000)
    create_snapshot(product, date(2026, 5, 16), "DISCOUNTED", base=120000, discounted=70000)

    detail = get_product_detail("P-DETAIL")

    assert detail.product.product_id == "P-DETAIL"
    assert detail.latest_snapshot is not None
    assert detail.latest_snapshot.snapshot_date == date(2026, 5, 16)
    assert detail.current_price_amount_cents == 70000
    assert detail.current_price_display is None
    assert detail.regular_low_amount_cents == 70000
    assert detail.regular_low_date == date(2026, 5, 16)
    assert [snapshot.snapshot_date for snapshot in detail.snapshots] == [
        date(2026, 5, 16),
        date(2026, 5, 15),
        date(2026, 5, 14),
    ]


@pytest.mark.django_db
def test_get_product_detail_regular_low_ignores_free_and_unavailable_states() -> None:
    product = create_product("P-STATES", "State Product")

    create_snapshot(product, date(2026, 5, 14), "FREE", base=0)
    create_snapshot(product, date(2026, 5, 15), "UNKNOWN")
    create_snapshot(product, date(2026, 5, 16), "PAID", base=90000)

    detail = get_product_detail("P-STATES")

    assert detail.regular_low_amount_cents == 90000
    assert detail.regular_low_date == date(2026, 5, 16)


@pytest.mark.django_db
def test_get_product_detail_handles_product_without_snapshots() -> None:
    create_product("P-NO-SNAPSHOTS", "No Snapshots")

    detail = get_product_detail("P-NO-SNAPSHOTS")

    assert detail.latest_snapshot is None
    assert detail.regular_low_amount_cents is None
    assert detail.regular_low_date is None
    assert detail.snapshots == []
```

- [ ] **Step 2: Run detail query tests to verify they fail**

Run:

```bash
uv run pytest tests/test_web_queries.py -q
```

Expected: fail because `get_product_detail` does not exist.

- [ ] **Step 3: Implement detail query helper**

Add `from datetime import date` to the import section in `src/ps_price_web/queries.py`, then append the detail helper code below the existing deal query code:

```python
@dataclass(frozen=True)
class ProductDetail:
    product: StoreProduct
    latest_snapshot: PriceSnapshot | None
    snapshots: list[PriceSnapshot]
    current_price_amount_cents: int | None
    current_price_display: str | None
    regular_low_amount_cents: int | None
    regular_low_date: date | None


def _regular_snapshot_price(snapshot: PriceSnapshot) -> int | None:
    if snapshot.normalized_state == "DISCOUNTED":
        return snapshot.discounted_amount_cents
    if snapshot.normalized_state == "PAID":
        return snapshot.base_amount_cents
    return None


def _current_snapshot_price(snapshot: PriceSnapshot | None) -> tuple[int | None, str | None]:
    if snapshot is None:
        return None, None
    if snapshot.normalized_state == "DISCOUNTED":
        return snapshot.discounted_amount_cents, snapshot.discounted_display
    if snapshot.normalized_state == "PS_PLUS":
        return snapshot.plus_amount_cents, None
    return snapshot.base_amount_cents, snapshot.base_display


def get_product_detail(product_id: str) -> ProductDetail:
    product = StoreProduct.objects.get(product_id=product_id)
    snapshots = list(product.snapshots.order_by("-snapshot_date", "-id"))
    latest_snapshot = snapshots[0] if snapshots else None
    current_amount, current_display = _current_snapshot_price(latest_snapshot)

    low_amount: int | None = None
    low_date: date | None = None
    for snapshot in snapshots:
        price = _regular_snapshot_price(snapshot)
        if price is None:
            continue
        if low_amount is None or price < low_amount:
            low_amount = price
            low_date = snapshot.snapshot_date

    return ProductDetail(
        product=product,
        latest_snapshot=latest_snapshot,
        snapshots=snapshots,
        current_price_amount_cents=current_amount,
        current_price_display=current_display,
        regular_low_amount_cents=low_amount,
        regular_low_date=low_date,
    )
```

- [ ] **Step 4: Run detail query tests to verify they pass**

Run:

```bash
uv run pytest tests/test_web_queries.py -q
```

Expected: pass.

- [ ] **Step 5: Commit detail query helper**

Run:

```bash
git add src/ps_price_web/queries.py tests/test_web_queries.py
git commit -m "feat: add product detail query"
```

## Task 5: Render Deals Page

**Files:**
- Modify: `src/ps_price_web/views.py`
- Create: `src/ps_price_web/templates/ps_price_web/base.html`
- Create: `src/ps_price_web/templates/ps_price_web/deals.html`
- Create: `tests/test_web_views.py`

- [ ] **Step 1: Write failing deals view tests**

Create `tests/test_web_views.py`:

```python
from __future__ import annotations

from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from ps_price_sync.models import PriceSnapshot, StoreProduct


def create_product(product_id: str, name: str, *, concept_name: str = "", is_visible: bool | None = True) -> StoreProduct:
    return StoreProduct.objects.create(
        product_id=product_id,
        product_name=name,
        concept_name=concept_name,
        platforms_raw='["PS5"]',
        image_url="https://example.test/cover.jpg",
        source_url="https://store.playstation.test/product",
        is_visible=is_visible,
    )


def create_snapshot(
    product: StoreProduct,
    snapshot_date: date,
    state: str,
    *,
    base: int | None = None,
    discounted: int | None = None,
) -> PriceSnapshot:
    return PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=snapshot_date,
        normalized_state=state,
        base_amount_cents=base,
        discounted_amount_cents=discounted,
        base_display="NT$1,000" if base is not None else None,
        discounted_display="NT$500" if discounted is not None else None,
        source_strategy_source="catalog",
        source_strategy_reason="catalog_price",
    )


@pytest.mark.django_db
def test_deals_page_renders_discounted_products() -> None:
    client = Client()
    discounted = create_product("P-DISCOUNT", "Discounted Product")
    plus = create_product("P-PLUS", "Plus Product")
    create_snapshot(discounted, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=50000)
    create_snapshot(plus, date(2026, 5, 16), "PS_PLUS", base=100000, discounted=30000)

    response = client.get(reverse("ps_price_web:deals"))

    assert response.status_code == 200
    assert "Discounted Product" in response.content.decode()
    assert "Plus Product" not in response.content.decode()
    assert "50%" in response.content.decode()
    assert "/products/P-DISCOUNT/" in response.content.decode()


@pytest.mark.django_db
def test_deals_page_applies_search_query() -> None:
    client = Client()
    match = create_product("P-MATCH", "Final Fantasy")
    miss = create_product("P-MISS", "Gran Turismo")
    create_snapshot(match, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=50000)
    create_snapshot(miss, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=40000)

    response = client.get(reverse("ps_price_web:deals"), {"q": "fantasy"})

    assert response.status_code == 200
    assert "Final Fantasy" in response.content.decode()
    assert "Gran Turismo" not in response.content.decode()


@pytest.mark.django_db
def test_deals_page_empty_state() -> None:
    client = Client()

    response = client.get(reverse("ps_price_web:deals"))

    assert response.status_code == 200
    assert "目前沒有一般折扣商品" in response.content.decode()
```

- [ ] **Step 2: Run deals view tests to verify they fail**

Run:

```bash
uv run pytest tests/test_web_views.py -q
```

Expected: fail because views still return temporary plain responses or templates do not exist.

- [ ] **Step 3: Implement deals view**

Replace `src/ps_price_web/views.py` with:

```python
from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from ps_price_web.queries import get_latest_deals


def deals_view(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "")
    return render(
        request,
        "ps_price_web/deals.html",
        {
            "deals": get_latest_deals(query=query),
            "query": query,
        },
    )


def product_detail_view(request: HttpRequest, product_id: str) -> HttpResponse:
    return HttpResponse(product_id)
```

- [ ] **Step 4: Add base template and deals template**

Create `src/ps_price_web/templates/ps_price_web/base.html`:

```html
<!doctype html>
<html lang="zh-Hant-TW">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}PS Price{% endblock %}</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #18181b; background: #f7f7f8; }
    header { background: #111827; color: white; padding: 16px 24px; }
    header a { color: white; text-decoration: none; }
    main { max-width: 1120px; margin: 0 auto; padding: 24px; }
    table { width: 100%; border-collapse: collapse; background: white; }
    th, td { padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: middle; }
    th { font-size: 14px; color: #4b5563; background: #f9fafb; }
    img.cover { width: 56px; height: 56px; object-fit: cover; background: #e5e7eb; }
    .toolbar { display: flex; gap: 8px; margin: 16px 0; }
    .toolbar input { flex: 1; padding: 8px 10px; }
    .toolbar button { padding: 8px 12px; }
    .empty { background: white; padding: 24px; border: 1px solid #e5e7eb; }
    .muted { color: #6b7280; }
  </style>
</head>
<body>
  <header><a href="{% url 'ps_price_web:deals' %}">PS Price</a></header>
  <main>{% block content %}{% endblock %}</main>
</body>
</html>
```

Create `src/ps_price_web/templates/ps_price_web/deals.html`:

```html
{% extends "ps_price_web/base.html" %}
{% load ps_price_web_extras %}

{% block title %}特價清單 - PS Price{% endblock %}

{% block content %}
  <h1>特價清單</h1>
  <form class="toolbar" method="get" action="{% url 'ps_price_web:deals' %}">
    <input type="search" name="q" value="{{ query }}" placeholder="搜尋商品或 Concept">
    <button type="submit">搜尋</button>
  </form>

  {% if deals %}
    <table>
      <thead>
        <tr>
          <th>封面</th>
          <th>商品</th>
          <th>平台</th>
          <th>原價</th>
          <th>折扣價</th>
          <th>折扣</th>
          <th>日期</th>
          <th>連結</th>
        </tr>
      </thead>
      <tbody>
        {% for deal in deals %}
          <tr>
            <td>
              {% if deal.product.image_url %}
                <img class="cover" src="{{ deal.product.image_url }}" alt="">
              {% else %}
                <span class="muted">無圖片</span>
              {% endif %}
            </td>
            <td><a href="{% url 'ps_price_web:product_detail' deal.product.product_id %}">{{ deal.product.product_name }}</a></td>
            <td>{{ deal.product.platforms_raw|raw_json_list }}</td>
            <td>{{ deal.snapshot.base_amount_cents|money_twd:deal.snapshot.base_display }}</td>
            <td>{{ deal.snapshot.discounted_amount_cents|money_twd:deal.snapshot.discounted_display }}</td>
            <td>{{ deal.discount_percent }}%</td>
            <td>{{ deal.snapshot.snapshot_date }}</td>
            <td>
              {% if deal.product.source_url %}
                <a href="{{ deal.product.source_url }}">PS Store</a>
              {% else %}
                <span class="muted">-</span>
              {% endif %}
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% else %}
    <div class="empty">目前沒有一般折扣商品</div>
  {% endif %}
{% endblock %}
```

- [ ] **Step 5: Add template filters**

Create `src/ps_price_web/templatetags/__init__.py`:

```python
from __future__ import annotations
```

Create `src/ps_price_web/templatetags/ps_price_web_extras.py`:

```python
from __future__ import annotations

from django import template

from ps_price_web.formatting import format_money_twd, format_raw_json_list

register = template.Library()


@register.filter
def money_twd(amount_cents: int | None, display_text: str | None = None) -> str:
    return format_money_twd(amount_cents, display_text)


@register.filter
def raw_json_list(raw_value: str | None) -> str:
    return format_raw_json_list(raw_value)
```

- [ ] **Step 6: Run deals view tests to verify they pass**

Run:

```bash
uv run pytest tests/test_web_views.py -q
```

Expected: pass.

- [ ] **Step 7: Commit deals page**

Run:

```bash
git add src/ps_price_web tests/test_web_views.py
git commit -m "feat: render deals page"
```

## Task 6: Render Product Detail Page

**Files:**
- Modify: `src/ps_price_web/views.py`
- Create: `src/ps_price_web/templates/ps_price_web/product_detail.html`
- Modify: `tests/test_web_views.py`

- [ ] **Step 1: Add failing product detail view tests**

Append to `tests/test_web_views.py`:

```python
@pytest.mark.django_db
def test_product_detail_page_renders_latest_price_and_regular_low() -> None:
    client = Client()
    product = create_product("P-DETAIL", "Detail Product", concept_name="Detail Concept")
    product.publisher_name = "Publisher"
    product.save()
    create_snapshot(product, date(2026, 5, 14), "PAID", base=120000)
    create_snapshot(product, date(2026, 5, 15), "PS_PLUS", base=120000, discounted=20000)
    create_snapshot(product, date(2026, 5, 16), "DISCOUNTED", base=120000, discounted=70000)

    response = client.get(reverse("ps_price_web:product_detail", kwargs={"product_id": "P-DETAIL"}))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Detail Product" in html
    assert "Detail Concept" in html
    assert "Publisher" in html
    assert "一般歷史最低價" in html
    assert "NT$700" in html
    assert "PS_PLUS" in html
    assert html.index("2026-05-16") < html.index("2026-05-15")


@pytest.mark.django_db
def test_product_detail_page_404_for_missing_product() -> None:
    client = Client()

    response = client.get(reverse("ps_price_web:product_detail", kwargs={"product_id": "NOPE"}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_product_detail_page_renders_product_without_snapshots() -> None:
    client = Client()
    create_product("P-NO-SNAPSHOTS", "No Snapshots")

    response = client.get(reverse("ps_price_web:product_detail", kwargs={"product_id": "P-NO-SNAPSHOTS"}))
    html = response.content.decode()

    assert response.status_code == 200
    assert "No Snapshots" in html
    assert "尚無價格快照" in html
```

- [ ] **Step 2: Run product detail tests to verify they fail**

Run:

```bash
uv run pytest tests/test_web_views.py -q
```

Expected: fail because `product_detail_view` still returns a temporary plain response or template does not exist.

- [ ] **Step 3: Implement product detail view**

Modify `src/ps_price_web/views.py`:

```python
from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from ps_price_sync.models import StoreProduct
from ps_price_web.queries import get_latest_deals, get_product_detail


def deals_view(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "")
    return render(
        request,
        "ps_price_web/deals.html",
        {
            "deals": get_latest_deals(query=query),
            "query": query,
        },
    )


def product_detail_view(request: HttpRequest, product_id: str) -> HttpResponse:
    get_object_or_404(StoreProduct, product_id=product_id)
    return render(
        request,
        "ps_price_web/product_detail.html",
        {
            "detail": get_product_detail(product_id),
        },
    )
```

- [ ] **Step 4: Add product detail template**

Create `src/ps_price_web/templates/ps_price_web/product_detail.html`:

```html
{% extends "ps_price_web/base.html" %}
{% load ps_price_web_extras %}

{% block title %}{{ detail.product.product_name }} - PS Price{% endblock %}

{% block content %}
  <p><a href="{% url 'ps_price_web:deals' %}">回特價清單</a></p>
  <h1>{{ detail.product.product_name }}</h1>

  <section>
    {% if detail.product.image_url %}
      <img class="cover" src="{{ detail.product.image_url }}" alt="">
    {% endif %}
    <dl>
      <dt>Concept</dt>
      <dd>{{ detail.product.concept_name|default:"-" }}</dd>
      <dt>Publisher</dt>
      <dd>{{ detail.product.publisher_name|default:"-" }}</dd>
      <dt>平台</dt>
      <dd>{{ detail.product.platforms_raw|raw_json_list }}</dd>
      <dt>PS Store</dt>
      <dd>
        {% if detail.product.source_url %}
          <a href="{{ detail.product.source_url }}">{{ detail.product.source_url }}</a>
        {% else %}
          -
        {% endif %}
      </dd>
    </dl>
  </section>

  <section>
    <h2>價格摘要</h2>
    {% if detail.latest_snapshot %}
      <p>最新狀態：{{ detail.latest_snapshot.normalized_state }}（{{ detail.latest_snapshot.snapshot_date }}）</p>
      <p>目前價格：{{ detail.current_price_amount_cents|money_twd:detail.current_price_display }}</p>
    {% else %}
      <p>尚無價格快照</p>
    {% endif %}

    {% if detail.regular_low_amount_cents %}
      <p>一般歷史最低價：{{ detail.regular_low_amount_cents|money_twd }}（{{ detail.regular_low_date }}）</p>
    {% else %}
      <p>一般歷史最低價：-</p>
    {% endif %}
  </section>

  <section>
    <h2>每日快照</h2>
    {% if detail.snapshots %}
      <table>
        <thead>
          <tr>
            <th>日期</th>
            <th>狀態</th>
            <th>原價</th>
            <th>折扣價</th>
            <th>PS Plus 價</th>
            <th>折扣文字</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {% for snapshot in detail.snapshots %}
            <tr>
              <td>{{ snapshot.snapshot_date }}</td>
              <td>{{ snapshot.normalized_state }}</td>
              <td>{{ snapshot.base_amount_cents|money_twd:snapshot.base_display }}</td>
              <td>{{ snapshot.discounted_amount_cents|money_twd:snapshot.discounted_display }}</td>
              <td>{{ snapshot.plus_amount_cents|money_twd }}</td>
              <td>{{ snapshot.discount_text|default:"-" }}</td>
              <td>{{ snapshot.source_strategy_source }} / {{ snapshot.source_strategy_reason }}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% else %}
      <div class="empty">尚無價格快照</div>
    {% endif %}
  </section>
{% endblock %}
```

- [ ] **Step 5: Run product detail tests to verify they pass**

Run:

```bash
uv run pytest tests/test_web_views.py -q
```

Expected: pass.

- [ ] **Step 6: Commit product detail page**

Run:

```bash
git add src/ps_price_web tests/test_web_views.py
git commit -m "feat: render product detail page"
```

## Task 7: Final Verification And README Note

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a short README usage note**

Add this section after "Django setup and sync usage" in `README.md`:

````markdown
## Self-use deals UI

After migrating and syncing data, run the Django dev server:

```bash
uv run python manage.py runserver
```

Open:

- `http://127.0.0.1:8000/deals/`
- `http://127.0.0.1:8000/products/<product_id>/`

The first UI milestone is read-only. It shows general discounted products and a thin product detail page; PS Plus prices are not mixed into regular discounts or regular historical lows.
````

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/test_django_setup.py tests/test_web_queries.py tests/test_web_views.py -q
```

Expected: pass.

- [ ] **Step 3: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: pass.

- [ ] **Step 4: Run Django system check**

Run:

```bash
uv run python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 5: Commit final docs and verification cleanups**

Run:

```bash
git add README.md
git commit -m "docs: add self-use deals UI usage"
```

If no README changes are needed because the user declines documentation, skip this commit and state that in the final verification report.
