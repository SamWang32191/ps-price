# Watchlist + Target Price Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a database-backed Watchlist + target price MVP for self-use Product price tracking.

**Architecture:** `ps_price_web` owns the self-use preference model `WatchedProduct`, routes, forms, templates, and query helpers. `WatchedProduct` points to `ps_price_sync.StoreProduct`; crawler, ingestion, scheduler, and `PriceSnapshot` writes remain unchanged. **Implementation work must read `CONTEXT.md` first** and use canonical terms, especially **Watched Product** and **General Purchase Price**.

**Tech Stack:** Python 3.12+, Django 5.2, SQLite, pytest, pytest-django, Django templates.

---

## File Structure

- Read first: `CONTEXT.md`
  - Canonical glossary for **Product**, **Watched Product**, **General Purchase Price**, **Catalog Visibility**, and **PriceSnapshot**.
- Read first: `docs/superpowers/specs/2026-05-17-watchlist-target-price-design.md`
  - Source of truth for behavior and explicit non-goals.
- Create: `src/ps_price_web/models.py`
  - Defines `WatchedProduct`.
- Create: `src/ps_price_web/migrations/__init__.py`
  - Enables migrations for the web app.
- Create: `src/ps_price_web/migrations/0001_watched_product.py`
  - Migration for `WatchedProduct`.
- Modify: `src/ps_price_web/queries.py`
  - Adds **General Purchase Price** helpers, watch status dataclasses, list query, and product detail watch context.
- Modify: `src/ps_price_web/views.py`
  - Adds `/watchlist/` view and Product detail POST handling.
- Modify: `src/ps_price_web/urls.py`
  - Adds `watchlist/` route.
- Modify: `src/ps_price_web/templates/ps_price_web/base.html`
  - Adds Watchlist navigation.
- Modify: `src/ps_price_web/templates/ps_price_web/product_detail.html`
  - Adds Watchlist form, status, and validation error display.
- Create: `src/ps_price_web/templates/ps_price_web/watchlist.html`
  - Lists **Watched Product** rows.
- Modify: `README.md`
  - Documents `/watchlist/` and single-user write UI boundary.
- Modify: `tests/test_django_setup.py`
  - Asserts watchlist route registration.
- Modify: `tests/test_web_queries.py`
  - Adds query/status tests for **General Purchase Price** and **Watched Product** ordering.
- Modify: `tests/test_web_views.py`
  - Adds HTTP tests for `/watchlist/` and Product detail POST behavior.
- Create: `tests/test_web_models.py`
  - Tests one-to-one and cascade behavior.

## Task 1: Add `WatchedProduct` Model And Migration

**Files:**
- Read: `CONTEXT.md`
- Read: `docs/superpowers/specs/2026-05-17-watchlist-target-price-design.md`
- Create: `src/ps_price_web/models.py`
- Create: `src/ps_price_web/migrations/__init__.py`
- Create: `src/ps_price_web/migrations/0001_watched_product.py`
- Create: `tests/test_web_models.py`

- [ ] **Step 1: Read the domain context**

Run:

```bash
sed -n '1,140p' CONTEXT.md
sed -n '1,240p' docs/superpowers/specs/2026-05-17-watchlist-target-price-design.md
```

Expected: both files define **Watched Product** as one tracked **Product** and **General Purchase Price** as latest `DISCOUNTED`/`PAID` price only.

- [ ] **Step 2: Write failing model tests**

Create `tests/test_web_models.py`:

```python
from __future__ import annotations

import pytest
from django.db import IntegrityError

from ps_price_sync.models import StoreProduct
from ps_price_web.models import WatchedProduct


def _product(product_id: str = "P-WATCHED", name: str = "Watched Product") -> StoreProduct:
    return StoreProduct.objects.create(product_id=product_id, product_name=name, is_visible=True, missing_count=0)


@pytest.mark.django_db
def test_watched_product_belongs_to_one_product() -> None:
    product = _product()

    watched = WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    assert watched.store_product == product
    assert product.watch == watched
    assert watched.target_price_cents == 59000


@pytest.mark.django_db
def test_watched_product_is_one_to_one_per_product() -> None:
    product = _product()
    WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    with pytest.raises(IntegrityError):
        WatchedProduct.objects.create(store_product=product, target_price_cents=49000)


@pytest.mark.django_db
def test_watched_product_allows_empty_target_price() -> None:
    product = _product()

    watched = WatchedProduct.objects.create(store_product=product, target_price_cents=None)

    assert watched.target_price_cents is None


@pytest.mark.django_db
def test_watched_product_is_deleted_when_product_is_deleted() -> None:
    product = _product()
    watched = WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    product.delete()

    assert not WatchedProduct.objects.filter(id=watched.id).exists()
```

- [ ] **Step 3: Run model tests to verify they fail**

Run:

```bash
uv run pytest tests/test_web_models.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'ps_price_web.models'` or missing `WatchedProduct`.

- [ ] **Step 4: Add `WatchedProduct` model**

Create `src/ps_price_web/models.py`:

```python
from __future__ import annotations

from django.db import models

from ps_price_sync.models import StoreProduct


class WatchedProduct(models.Model):
    store_product = models.OneToOneField(StoreProduct, on_delete=models.CASCADE, related_name="watch")
    target_price_cents = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["store_product__product_name", "store_product__product_id"]
```

Create `src/ps_price_web/migrations/__init__.py`:

```python
from __future__ import annotations
```

- [ ] **Step 5: Generate migration**

Run:

```bash
uv run python manage.py makemigrations ps_price_web --name watched_product
```

Expected: creates `src/ps_price_web/migrations/0001_watched_product.py`.

- [ ] **Step 6: Run model tests to verify they pass**

Run:

```bash
uv run pytest tests/test_web_models.py -q
```

Expected: pass.

- [ ] **Step 7: Commit model and migration**

Run:

```bash
git add src/ps_price_web/models.py src/ps_price_web/migrations tests/test_web_models.py
git commit -m "feat: add watched product model"
```

## Task 2: Add Watchlist Query And Status Logic

**Files:**
- Modify: `src/ps_price_web/queries.py`
- Modify: `tests/test_web_queries.py`

- [ ] **Step 1: Add failing query tests**

Append to `tests/test_web_queries.py`:

```python
from ps_price_web.models import WatchedProduct
from ps_price_web.queries import WatchStatus, get_watchlist_rows


def watch(product: StoreProduct, target: int | None) -> WatchedProduct:
    return WatchedProduct.objects.create(store_product=product, target_price_cents=target)


@pytest.mark.django_db
def test_get_watchlist_rows_marks_discounted_product_as_reached() -> None:
    product = create_product("P-WATCH-REACHED", "Reached")
    create_snapshot(product, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=50000)
    watch(product, 59000)

    rows = get_watchlist_rows()

    assert [(row.product.product_id, row.status) for row in rows] == [("P-WATCH-REACHED", WatchStatus.REACHED)]
    assert rows[0].general_purchase_price_cents == 50000


@pytest.mark.django_db
def test_get_watchlist_rows_marks_paid_product_as_not_reached() -> None:
    product = create_product("P-WATCH-NOT-REACHED", "Not Reached")
    create_snapshot(product, date(2026, 5, 16), "PAID", base=90000)
    watch(product, 59000)

    rows = get_watchlist_rows()

    assert rows[0].status == WatchStatus.NOT_REACHED
    assert rows[0].general_purchase_price_cents == 90000


@pytest.mark.django_db
def test_get_watchlist_rows_excludes_ps_plus_and_free_from_general_purchase_price() -> None:
    plus = create_product("P-WATCH-PLUS", "Plus")
    free = create_product("P-WATCH-FREE", "Free")
    create_snapshot(plus, date(2026, 5, 16), "PS_PLUS", base=90000, discounted=10000)
    create_snapshot(free, date(2026, 5, 16), "FREE", base=0, discounted=0)
    watch(plus, 59000)
    watch(free, 59000)

    rows = get_watchlist_rows()

    assert [(row.product.product_id, row.status, row.general_purchase_price_cents) for row in rows] == [
        ("P-WATCH-FREE", WatchStatus.NO_GENERAL_PURCHASE_PRICE, None),
        ("P-WATCH-PLUS", WatchStatus.NO_GENERAL_PURCHASE_PRICE, None),
    ]


@pytest.mark.django_db
def test_get_watchlist_rows_keeps_hidden_products_and_sorts_by_status_then_name() -> None:
    reached = create_product("P-SORT-REACHED", "B Reached", is_visible=False)
    not_reached = create_product("P-SORT-NOT", "A Not Reached")
    no_target = create_product("P-SORT-NO-TARGET", "A No Target")
    no_price = create_product("P-SORT-NO-PRICE", "A No Price")
    create_snapshot(reached, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=50000)
    create_snapshot(not_reached, date(2026, 5, 16), "PAID", base=90000)
    create_snapshot(no_target, date(2026, 5, 16), "PAID", base=90000)
    create_snapshot(no_price, date(2026, 5, 16), "UNKNOWN", base=None)
    watch(reached, 59000)
    watch(not_reached, 59000)
    watch(no_target, None)
    watch(no_price, 59000)

    rows = get_watchlist_rows()

    assert [(row.product.product_id, row.status) for row in rows] == [
        ("P-SORT-REACHED", WatchStatus.REACHED),
        ("P-SORT-NOT", WatchStatus.NOT_REACHED),
        ("P-SORT-NO-TARGET", WatchStatus.NO_TARGET_PRICE),
        ("P-SORT-NO-PRICE", WatchStatus.NO_GENERAL_PURCHASE_PRICE),
    ]
```

- [ ] **Step 2: Run query tests to verify they fail**

Run:

```bash
uv run pytest tests/test_web_queries.py -q
```

Expected: fail because `WatchStatus` and `get_watchlist_rows` do not exist.

- [ ] **Step 3: Implement query dataclasses and helpers**

Modify `src/ps_price_web/queries.py` by adding imports and dataclasses:

```python
from enum import StrEnum

from ps_price_web.models import WatchedProduct


class WatchStatus(StrEnum):
    REACHED = "達標"
    NOT_REACHED = "未達標"
    NO_TARGET_PRICE = "未設定目標價"
    NO_GENERAL_PURCHASE_PRICE = "無 General Purchase Price"


@dataclass(frozen=True)
class WatchlistRow:
    watched_product: WatchedProduct
    product: StoreProduct
    latest_snapshot: PriceSnapshot | None
    general_purchase_price_cents: int | None
    target_price_cents: int | None
    status: WatchStatus
```

Add helpers near `_regular_snapshot_price`:

```python
def get_general_purchase_price(snapshot: PriceSnapshot | None) -> int | None:
    if snapshot is None:
        return None
    if snapshot.normalized_state == "DISCOUNTED":
        return snapshot.discounted_amount_cents
    if snapshot.normalized_state == "PAID":
        return snapshot.base_amount_cents
    return None


def get_watch_status(*, target_price_cents: int | None, general_purchase_price_cents: int | None) -> WatchStatus:
    if target_price_cents is None:
        return WatchStatus.NO_TARGET_PRICE
    if general_purchase_price_cents is None:
        return WatchStatus.NO_GENERAL_PURCHASE_PRICE
    if general_purchase_price_cents <= target_price_cents:
        return WatchStatus.REACHED
    return WatchStatus.NOT_REACHED
```

Add list query:

```python
def get_watchlist_rows() -> list[WatchlistRow]:
    watched_products = list(WatchedProduct.objects.select_related("store_product").order_by("store_product__product_name"))
    latest_dates = (
        PriceSnapshot.objects.filter(store_product__in=[watched.store_product for watched in watched_products])
        .values("store_product_id")
        .annotate(latest_date=Max("snapshot_date"))
    )
    latest_lookup = {row["store_product_id"]: row["latest_date"] for row in latest_dates}
    snapshots = PriceSnapshot.objects.filter(
        store_product_id__in=latest_lookup.keys(),
        snapshot_date__in=latest_lookup.values(),
    ).order_by("store_product_id", "-id")
    snapshot_lookup: dict[int, PriceSnapshot] = {}
    for snapshot in snapshots:
        snapshot_lookup.setdefault(snapshot.store_product_id, snapshot)

    rows: list[WatchlistRow] = []
    for watched in watched_products:
        snapshot = snapshot_lookup.get(watched.store_product_id)
        general_price = get_general_purchase_price(snapshot)
        rows.append(
            WatchlistRow(
                watched_product=watched,
                product=watched.store_product,
                latest_snapshot=snapshot,
                general_purchase_price_cents=general_price,
                target_price_cents=watched.target_price_cents,
                status=get_watch_status(
                    target_price_cents=watched.target_price_cents,
                    general_purchase_price_cents=general_price,
                ),
            )
        )

    status_order = {
        WatchStatus.REACHED: 0,
        WatchStatus.NOT_REACHED: 1,
        WatchStatus.NO_TARGET_PRICE: 2,
        WatchStatus.NO_GENERAL_PURCHASE_PRICE: 3,
    }
    return sorted(rows, key=lambda row: (status_order[row.status], row.product.product_name, row.product.product_id))
```

- [ ] **Step 4: Run query tests to verify they pass**

Run:

```bash
uv run pytest tests/test_web_queries.py -q
```

Expected: pass.

- [ ] **Step 5: Commit query logic**

Run:

```bash
git add src/ps_price_web/queries.py tests/test_web_queries.py
git commit -m "feat: add watchlist query status"
```

## Task 3: Add `/watchlist/` Page

**Files:**
- Modify: `src/ps_price_web/urls.py`
- Modify: `src/ps_price_web/views.py`
- Modify: `src/ps_price_web/templates/ps_price_web/base.html`
- Create: `src/ps_price_web/templates/ps_price_web/watchlist.html`
- Modify: `tests/test_django_setup.py`
- Modify: `tests/test_web_views.py`

- [ ] **Step 1: Add failing route and page tests**

Append to `tests/test_django_setup.py`:

```python
def test_watchlist_route_is_registered() -> None:
    assert reverse("ps_price_web:watchlist") == "/watchlist/"
    assert resolve("/watchlist/").view_name == "ps_price_web:watchlist"
```

Append to `tests/test_web_views.py`:

```python
from ps_price_web.models import WatchedProduct


@pytest.mark.django_db
def test_watchlist_page_renders_empty_state(client) -> None:
    response = client.get(reverse("ps_price_web:watchlist"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Watchlist" in content
    assert "目前沒有 Watched Product" in content


@pytest.mark.django_db
def test_watchlist_page_renders_rows_and_keeps_hidden_products(client) -> None:
    product = _web_product("P-WATCHLIST", "Watchlist Product")
    product.is_visible = False
    product.save(update_fields=["is_visible"])
    _web_snapshot(product, state="DISCOUNTED", base_amount_cents=100000, discounted_amount_cents=50000)
    WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    response = client.get(reverse("ps_price_web:watchlist"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Watchlist Product" in content
    assert "達標" in content
    assert "NT$500" in content
    assert "NT$590" in content
    assert reverse("ps_price_web:product_detail", kwargs={"product_id": "P-WATCHLIST"}) in content
```

- [ ] **Step 2: Run route and page tests to verify they fail**

Run:

```bash
uv run pytest tests/test_django_setup.py tests/test_web_views.py -q
```

Expected: fail because route, view, and template do not exist.

- [ ] **Step 3: Add route and view**

Modify `src/ps_price_web/urls.py`:

```python
urlpatterns = [
    path("deals/", views.deals_view, name="deals"),
    path("watchlist/", views.watchlist_view, name="watchlist"),
    path("products/<str:product_id>/", views.product_detail_view, name="product_detail"),
]
```

Modify imports and add view in `src/ps_price_web/views.py`:

```python
from ps_price_web.queries import get_latest_deals, get_product_detail, get_watchlist_rows


def watchlist_view(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "ps_price_web/watchlist.html",
        {"rows": get_watchlist_rows()},
    )
```

- [ ] **Step 4: Add navigation and template**

Modify `src/ps_price_web/templates/ps_price_web/base.html` nav:

```html
<nav class="top-nav">
  <a href="{% url 'ps_price_web:deals' %}">特價清單</a>
  <a href="{% url 'ps_price_web:watchlist' %}">Watchlist</a>
</nav>
```

Create `src/ps_price_web/templates/ps_price_web/watchlist.html`:

```html
{% extends "ps_price_web/base.html" %}
{% load ps_price_web_extras %}

{% block title %}Watchlist - PS Price{% endblock %}

{% block content %}
  <h1>Watchlist</h1>

  {% if rows %}
    <table>
      <thead>
        <tr>
          <th>Product</th>
          <th>General Purchase Price</th>
          <th>Target Price</th>
          <th>Status</th>
          <th>Snapshot Date</th>
        </tr>
      </thead>
      <tbody>
        {% for row in rows %}
          <tr>
            <td>
              <a href="{% url 'ps_price_web:product_detail' row.product.product_id %}">
                {{ row.product.product_name }}
              </a>
            </td>
            <td>{{ row.general_purchase_price_cents|money_twd }}</td>
            <td>{{ row.target_price_cents|money_twd }}</td>
            <td>{{ row.status }}</td>
            <td>
              {% if row.latest_snapshot %}
                {{ row.latest_snapshot.snapshot_date|date:"Y-m-d" }}
              {% else %}
                -
              {% endif %}
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% else %}
    <p class="empty">目前沒有 Watched Product</p>
  {% endif %}
{% endblock %}
```

- [ ] **Step 5: Run route and page tests to verify they pass**

Run:

```bash
uv run pytest tests/test_django_setup.py tests/test_web_views.py -q
```

Expected: pass.

- [ ] **Step 6: Commit watchlist page**

Run:

```bash
git add src/ps_price_web/urls.py src/ps_price_web/views.py src/ps_price_web/templates/ps_price_web/base.html src/ps_price_web/templates/ps_price_web/watchlist.html tests/test_django_setup.py tests/test_web_views.py
git commit -m "feat: add watchlist page"
```

## Task 4: Add Product Detail Watchlist Form And POST Handling

**Files:**
- Modify: `src/ps_price_web/queries.py`
- Modify: `src/ps_price_web/views.py`
- Modify: `src/ps_price_web/templates/ps_price_web/product_detail.html`
- Modify: `tests/test_web_views.py`

- [ ] **Step 1: Add failing Product detail watch tests**

Append to `tests/test_web_views.py`:

```python
@pytest.mark.django_db
def test_product_detail_page_renders_watchlist_form(client) -> None:
    product = _web_product("P-WATCH-FORM", "Watch Form")

    response = client.get(reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Watchlist" in content
    assert 'name="target_price"' in content
    assert 'name="action" value="save_watch"' in content


@pytest.mark.django_db
def test_product_detail_post_creates_watched_product_and_redirects(client) -> None:
    product = _web_product("P-WATCH-CREATE", "Watch Create")

    response = client.post(
        reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id}),
        {"action": "save_watch", "target_price": "590"},
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id})
    watched = WatchedProduct.objects.get(store_product=product)
    assert watched.target_price_cents == 59000


@pytest.mark.django_db
def test_product_detail_post_updates_and_clears_target_price(client) -> None:
    product = _web_product("P-WATCH-UPDATE", "Watch Update")
    watched = WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    response = client.post(
        reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id}),
        {"action": "save_watch", "target_price": ""},
    )

    assert response.status_code == 302
    watched.refresh_from_db()
    assert watched.target_price_cents is None


@pytest.mark.django_db
def test_product_detail_post_removes_watched_product_idempotently(client) -> None:
    product = _web_product("P-WATCH-REMOVE", "Watch Remove")
    WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    first = client.post(
        reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id}),
        {"action": "remove_watch"},
    )
    second = client.post(
        reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id}),
        {"action": "remove_watch"},
    )

    assert first.status_code == 302
    assert second.status_code == 302
    assert not WatchedProduct.objects.filter(store_product=product).exists()


@pytest.mark.django_db
def test_product_detail_post_rejects_invalid_target_price_without_redirect(client) -> None:
    product = _web_product("P-WATCH-INVALID", "Watch Invalid")

    response = client.post(
        reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id}),
        {"action": "save_watch", "target_price": "590.5"},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "target price 必須是正整數台幣元" in content
    assert not WatchedProduct.objects.filter(store_product=product).exists()
```

- [ ] **Step 2: Run Product detail watch tests to verify they fail**

Run:

```bash
uv run pytest tests/test_web_views.py -q
```

Expected: fail because the Product detail template has no form and the view does not handle POST.

- [ ] **Step 3: Add watch context to product detail query**

Modify `ProductDetail` in `src/ps_price_web/queries.py`:

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
    watched_product: WatchedProduct | None
    watch_status: WatchStatus | None
    general_purchase_price_cents: int | None
```

Modify the end of `get_product_detail`:

```python
    watched_product = WatchedProduct.objects.filter(store_product=product).first()
    general_purchase_price_cents = get_general_purchase_price(latest_snapshot)
    watch_status = None
    if watched_product is not None:
        watch_status = get_watch_status(
            target_price_cents=watched_product.target_price_cents,
            general_purchase_price_cents=general_purchase_price_cents,
        )

    return ProductDetail(
        product=product,
        latest_snapshot=latest_snapshot,
        snapshots=snapshots,
        current_price_amount_cents=current_price_amount_cents,
        current_price_display=current_price_display,
        regular_low_amount_cents=regular_low_amount_cents,
        regular_low_date=regular_low_date,
        watched_product=watched_product,
        watch_status=watch_status,
        general_purchase_price_cents=general_purchase_price_cents,
    )
```

- [ ] **Step 4: Add target price parsing and POST handling**

Modify `src/ps_price_web/views.py`:

```python
from django.shortcuts import get_object_or_404, redirect, render

from ps_price_web.models import WatchedProduct


def _parse_target_price(raw_value: str) -> tuple[int | None, str | None]:
    value = raw_value.strip()
    if value == "":
        return None, None
    if not value.isdecimal():
        return None, "target price 必須是正整數台幣元"
    amount = int(value)
    if amount <= 0:
        return None, "target price 必須是正整數台幣元"
    return amount * 100, None
```

Add a small display helper and replace `product_detail_view`:

```python
def _target_price_value(detail) -> str:
    watched_product = detail.watched_product
    if watched_product is None or watched_product.target_price_cents is None:
        return ""
    return str(watched_product.target_price_cents // 100)


def product_detail_view(request: HttpRequest, product_id: str) -> HttpResponse:
    product = get_object_or_404(StoreProduct, product_id=product_id)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "remove_watch":
            WatchedProduct.objects.filter(store_product=product).delete()
            return redirect("ps_price_web:product_detail", product_id=product.product_id)
        if action == "save_watch":
            target_price_cents, error = _parse_target_price(request.POST.get("target_price", ""))
            if error is not None:
                return render(
                    request,
                    "ps_price_web/product_detail.html",
                    {
                        "detail": get_product_detail(product_id),
                        "watch_error": error,
                        "target_price_value": request.POST.get("target_price", ""),
                    },
                )
            WatchedProduct.objects.update_or_create(
                store_product=product,
                defaults={"target_price_cents": target_price_cents},
            )
            return redirect("ps_price_web:product_detail", product_id=product.product_id)

    detail = get_product_detail(product_id)
    return render(
        request,
        "ps_price_web/product_detail.html",
        {"detail": detail, "target_price_value": _target_price_value(detail)},
    )
```

- [ ] **Step 5: Add Product detail form**

Add this section to `src/ps_price_web/templates/ps_price_web/product_detail.html` after the product metadata and before `價格摘要`:

```html
<section>
  <h2>Watchlist</h2>
  {% if detail.watched_product %}
    <p>狀態：{{ detail.watch_status }}</p>
    <p>目標價：{{ detail.watched_product.target_price_cents|money_twd }}</p>
  {% else %}
    <p>尚未建立 Watched Product</p>
  {% endif %}

  {% if watch_error %}
    <p class="error">{{ watch_error }}</p>
  {% endif %}

  <form method="post" action="{% url 'ps_price_web:product_detail' detail.product.product_id %}">
    <input type="hidden" name="action" value="save_watch">
    <label>
      Target price（TWD）：
      <input
        type="text"
        name="target_price"
        value="{{ target_price_value }}"
        placeholder="例如 590"
      >
    </label>
    <button type="submit">儲存 Watched Product</button>
  </form>

  {% if detail.watched_product %}
    <form method="post" action="{% url 'ps_price_web:product_detail' detail.product.product_id %}">
      <input type="hidden" name="action" value="remove_watch">
      <button type="submit">移除 Watched Product</button>
    </form>
  {% endif %}
</section>
```

- [ ] **Step 6: Run Product detail watch tests to verify they pass**

Run:

```bash
uv run pytest tests/test_web_views.py -q
```

Expected: pass.

- [ ] **Step 7: Commit Product detail write UI**

Run:

```bash
git add src/ps_price_web/queries.py src/ps_price_web/views.py src/ps_price_web/templates/ps_price_web/product_detail.html tests/test_web_views.py
git commit -m "feat: manage watched products from detail page"
```

## Task 5: Documentation And Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-05-17-watchlist-target-price.md`

- [ ] **Step 1: Add README coverage test**

Append to `tests/test_django_setup.py`:

```python
def test_readme_mentions_watchlist_ui() -> None:
    readme_content = Path("README.md").read_text()

    assert "http://127.0.0.1:8000/watchlist/" in readme_content
    assert "Watched Product" in readme_content
    assert "single-user" in readme_content
```

- [ ] **Step 2: Run README test to verify it fails**

Run:

```bash
uv run pytest tests/test_django_setup.py::test_readme_mentions_watchlist_ui -q
```

Expected: fail because README has no Watchlist section yet.

- [ ] **Step 3: Update README**

Add this subsection under the web UI usage section in `README.md`:

```markdown
### Watchlist + target price

After syncing data and starting the Django dev server, open:

- `http://127.0.0.1:8000/watchlist/`
- `http://127.0.0.1:8000/products/<product_id>/`

Product detail pages can create, update, clear, and remove a **Watched Product**. Target price input uses integer TWD, for example `590`, and the app stores cents internally.

Target price status uses **General Purchase Price** only: latest `DISCOUNTED` uses the discounted amount, latest `PAID` uses the base amount, and `PS_PLUS` or `FREE` does not count as reached.

This is a single-user self-hosted write UI. It does not add authentication, authorization, sessions, or CSRF protection; do not expose the write UI as a public service without adding those protections first.
```

- [ ] **Step 4: Run README test to verify it passes**

Run:

```bash
uv run pytest tests/test_django_setup.py::test_readme_mentions_watchlist_ui -q
```

Expected: pass.

- [ ] **Step 5: Run targeted test suite**

Run:

```bash
uv run pytest tests/test_web_models.py tests/test_web_queries.py tests/test_web_views.py tests/test_django_setup.py -q
```

Expected: pass.

- [ ] **Step 6: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: pass.

- [ ] **Step 7: Commit docs and final verification**

Run:

```bash
git add README.md tests/test_django_setup.py
git commit -m "docs: document watchlist usage"
```

## Self-Review Checklist

- Spec coverage: tasks cover `WatchedProduct`, **General Purchase Price**, target status ordering, hidden Product visibility, Product detail POST behavior, invalid input behavior, idempotent remove, README usage, and full test verification.
- Non-goals preserved: no auth/session/CSRF, no notifications, no dashboard summary, no `/watchlist/` search/filter, no crawler/sync/scheduler changes.
- Type consistency: model name is `WatchedProduct`; route name is `ps_price_web:watchlist`; status enum is `WatchStatus`; list row type is `WatchlistRow`.
- Context usage: Task 1 starts by reading `CONTEXT.md`; plan terminology uses **Product**, **Watched Product**, and **General Purchase Price**.
