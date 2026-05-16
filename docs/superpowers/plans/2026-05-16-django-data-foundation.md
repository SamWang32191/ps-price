# Django Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal Django + SQLite data foundation that persists products, daily price snapshots, sync runs, and sync errors from the existing crawler contract.

**Architecture:** Keep the existing `ps_price_crawler` package as the only HTML-fetching and parsing adapter. Add one Django project package plus one Django app for ORM models, ingestion services, and a management command. `catalog-only` updates product visibility and metadata, `snapshot-only` still reads catalog pages to obey source strategy but only writes snapshots, and `catalog-and-snapshot` reuses the same catalog fetch for both paths.

**Tech Stack:** Python 3.12, Django 5.x, SQLite, pytest, pytest-django, existing `ps_price_crawler` adapter modules

---

## File Map

- Modify: `pyproject.toml`
  - Add Django runtime dependency, pytest-django, and pytest Django settings wiring.
- Modify: `README.md`
  - Document Django setup, migrate command, and manual sync command.
- Create: `manage.py`
  - Django management entrypoint.
- Create: `src/ps_price_site/__init__.py`
  - Django project package marker.
- Create: `src/ps_price_site/settings.py`
  - Minimal Django settings for SQLite and timezone.
- Create: `src/ps_price_site/urls.py`
  - Minimal URLConf.
- Create: `src/ps_price_site/asgi.py`
  - Django ASGI entrypoint.
- Create: `src/ps_price_site/wsgi.py`
  - Django WSGI entrypoint.
- Create: `src/ps_price_sync/__init__.py`
  - Django app package marker.
- Create: `src/ps_price_sync/apps.py`
  - App config.
- Create: `src/ps_price_sync/models.py`
  - `StoreProduct`, `PriceSnapshot`, `SyncRun`, `SyncError`.
- Create: `src/ps_price_sync/services/__init__.py`
  - Services package marker.
- Create: `src/ps_price_sync/services/ingestion.py`
  - ORM upsert logic for catalog products and snapshots.
- Create: `src/ps_price_sync/services/sync_runner.py`
  - Adapter-facing orchestration helpers used by the management command.
- Create: `src/ps_price_sync/management/__init__.py`
  - Django management package marker.
- Create: `src/ps_price_sync/management/commands/__init__.py`
  - Django commands package marker.
- Create: `src/ps_price_sync/management/commands/sync_ps_store.py`
  - Manual sync command.
- Create: `src/ps_price_sync/migrations/0001_initial.py`
  - Initial schema migration.
- Create: `tests/test_django_setup.py`
  - Project bootstrap smoke test.
- Create: `tests/test_sync_models.py`
  - Model constraint and field semantics tests.
- Create: `tests/test_ingestion_service.py`
  - Catalog ingestion, catalog snapshot ingestion, and detail snapshot ingestion tests.
- Create: `tests/test_sync_command.py`
  - Command mode and `SyncRun` lifecycle tests.

## Task 1: Add Django Dependencies And Project Skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `manage.py`
- Create: `src/ps_price_site/__init__.py`
- Create: `src/ps_price_site/settings.py`
- Create: `src/ps_price_site/urls.py`
- Create: `src/ps_price_site/asgi.py`
- Create: `src/ps_price_site/wsgi.py`
- Create: `src/ps_price_sync/__init__.py`
- Create: `src/ps_price_sync/apps.py`
- Test: `tests/test_django_setup.py`

- [ ] **Step 1: Write the failing bootstrap test**

```python
from pathlib import Path


def test_manage_py_exists():
    assert Path("manage.py").exists()


def test_django_settings_module_is_configured():
    settings_file = Path("src/ps_price_site/settings.py")
    assert settings_file.exists()
    assert "TIME_ZONE = \"Asia/Taipei\"" in settings_file.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run the bootstrap test to verify it fails**

Run: `uv run pytest tests/test_django_setup.py -v`

Expected:

```text
FAILED tests/test_django_setup.py::test_manage_py_exists
FAILED tests/test_django_setup.py::test_django_settings_module_is_configured
```

- [ ] **Step 3: Add Django dependencies and pytest-django wiring**

Update `pyproject.toml`:

```toml
[project]
dependencies = [
  "beautifulsoup4>=4.12.3",
  "django>=5.2,<6",
  "httpx>=0.27.2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.3",
  "pytest-django>=4.11.1",
  "pytest-httpx>=0.30.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-q"
DJANGO_SETTINGS_MODULE = "ps_price_site.settings"
```

- [ ] **Step 4: Create the minimal Django project and app skeleton**

Create `manage.py`:

```python
#!/usr/bin/env python
from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ps_price_site.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

Create `src/ps_price_site/settings.py`:

```python
from __future__ import annotations

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
]
MIDDLEWARE: list[str] = []
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```

Create `src/ps_price_sync/apps.py`:

```python
from django.apps import AppConfig


class PsPriceSyncConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ps_price_sync"
```

- [ ] **Step 5: Sync dependencies and rerun the bootstrap test**

Run: `uv sync --extra dev`

Expected:

```text
Resolved ...
Prepared ...
Installed ...
```

Run: `uv run pytest tests/test_django_setup.py -v`

Expected:

```text
PASSED tests/test_django_setup.py::test_manage_py_exists
PASSED tests/test_django_setup.py::test_django_settings_module_is_configured
```

- [ ] **Step 6: Commit the skeleton**

```bash
git add pyproject.toml manage.py src/ps_price_site src/ps_price_sync tests/test_django_setup.py
git commit -m "chore: add django project skeleton"
```

## Task 2: Add Failing Model Tests And Implement The Initial Schema

**Files:**
- Create: `tests/test_sync_models.py`
- Modify: `src/ps_price_sync/models.py`
- Create: `src/ps_price_sync/migrations/0001_initial.py`

- [ ] **Step 1: Write failing model constraint tests**

Create `tests/test_sync_models.py`:

```python
import json
from datetime import date

import pytest
from django.db import IntegrityError

from ps_price_sync.models import PriceSnapshot, StoreProduct, SyncError, SyncRun


@pytest.mark.django_db
def test_product_id_is_unique():
    StoreProduct.objects.create(product_id="P1", product_name="A")

    with pytest.raises(IntegrityError):
        StoreProduct.objects.create(product_id="P1", product_name="B")


@pytest.mark.django_db
def test_price_snapshot_is_unique_per_product_and_date():
    product = StoreProduct.objects.create(product_id="P1", product_name="A")
    PriceSnapshot.objects.create(store_product=product, snapshot_date=date(2026, 5, 16))

    with pytest.raises(IntegrityError):
        PriceSnapshot.objects.create(store_product=product, snapshot_date=date(2026, 5, 16))


@pytest.mark.django_db
def test_sync_run_summary_defaults_to_json_text():
    run = SyncRun.objects.create(sync_type="catalog_only", status="running")
    assert json.loads(run.summary) == {}


@pytest.mark.django_db
def test_sync_error_allows_repeated_product_id_across_runs():
    run_one = SyncRun.objects.create(sync_type="catalog_only", status="failed")
    run_two = SyncRun.objects.create(sync_type="catalog_only", status="failed")
    SyncError.objects.create(sync_run=run_one, stage="catalog_ingestion", product_id="P1", error_type="MissingProductId", error_message="first")
    SyncError.objects.create(sync_run=run_two, stage="catalog_ingestion", product_id="P1", error_type="MissingProductId", error_message="second")

    assert SyncError.objects.count() == 2
```

- [ ] **Step 2: Run the model test file to verify it fails**

Run: `uv run pytest tests/test_sync_models.py -v`

Expected:

```text
FAILED ... ImportError: cannot import name 'PriceSnapshot' from 'ps_price_sync.models'
```

- [ ] **Step 3: Implement the schema in `src/ps_price_sync/models.py`**

```python
from __future__ import annotations

from django.db import models


class StoreProduct(models.Model):
    product_id = models.CharField(max_length=128, unique=True)
    concept_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    product_name = models.TextField()
    concept_name = models.TextField(blank=True, default="")
    publisher_name = models.TextField(null=True, blank=True)
    release_date_raw = models.TextField(null=True, blank=True)
    top_category = models.TextField(null=True, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)
    source_url = models.URLField(max_length=500, null=True, blank=True)
    platforms_raw = models.TextField(default="[]")
    is_visible = models.BooleanField(null=True, blank=True)
    missing_count = models.PositiveIntegerField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PriceSnapshot(models.Model):
    store_product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name="snapshots")
    snapshot_date = models.DateField()
    normalized_state = models.CharField(max_length=32)
    currency = models.CharField(max_length=16, null=True, blank=True)
    base_amount_cents = models.IntegerField(null=True, blank=True)
    discounted_amount_cents = models.IntegerField(null=True, blank=True)
    plus_amount_cents = models.IntegerField(null=True, blank=True)
    base_display = models.TextField(null=True, blank=True)
    discounted_display = models.TextField(null=True, blank=True)
    discount_text = models.TextField(null=True, blank=True)
    service_branding_raw = models.TextField(default="[]")
    upsell_text = models.TextField(null=True, blank=True)
    source_strategy_source = models.CharField(max_length=32)
    source_strategy_reason = models.CharField(max_length=64)
    source_strategy_reason_codes_raw = models.TextField(default="[]")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("store_product", "snapshot_date"),
                name="unique_snapshot_per_product_per_day",
            )
        ]


class SyncRun(models.Model):
    sync_type = models.CharField(max_length=32)
    status = models.CharField(max_length=32)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    summary = models.TextField(default="{}")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SyncError(models.Model):
    sync_run = models.ForeignKey(SyncRun, on_delete=models.CASCADE, related_name="errors")
    stage = models.CharField(max_length=32)
    product_id = models.CharField(max_length=128, null=True, blank=True)
    concept_id = models.CharField(max_length=64, null=True, blank=True)
    source_url = models.URLField(max_length=500, null=True, blank=True)
    error_type = models.CharField(max_length=128)
    error_message = models.TextField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

- [ ] **Step 4: Generate and inspect the initial migration**

Run: `uv run python manage.py makemigrations ps_price_sync`

Expected:

```text
Migrations for 'ps_price_sync':
  src/ps_price_sync/migrations/0001_initial.py
```

Open the migration and make sure it contains:

```python
migrations.CreateModel(
    name="StoreProduct",
    fields=[...],
)
...
migrations.AddConstraint(
    model_name="pricesnapshot",
    constraint=models.UniqueConstraint(
        fields=("store_product", "snapshot_date"),
        name="unique_snapshot_per_product_per_day",
    ),
)
```

- [ ] **Step 5: Apply migrations and rerun the model test file**

Run: `uv run python manage.py migrate`

Expected:

```text
Applying ps_price_sync.0001_initial... OK
```

Run: `uv run pytest tests/test_sync_models.py -v`

Expected:

```text
PASSED tests/test_sync_models.py::test_product_id_is_unique
PASSED tests/test_sync_models.py::test_price_snapshot_is_unique_per_product_and_date
PASSED tests/test_sync_models.py::test_sync_run_summary_defaults_to_json_text
PASSED tests/test_sync_models.py::test_sync_error_allows_repeated_product_id_across_runs
```

- [ ] **Step 6: Commit the schema**

```bash
git add src/ps_price_sync/models.py src/ps_price_sync/migrations/0001_initial.py tests/test_sync_models.py
git commit -m "feat: add sync persistence schema"
```

## Task 3: Add Failing Catalog Ingestion Tests And Implement Catalog Product Persistence

**Files:**
- Create: `src/ps_price_sync/services/__init__.py`
- Modify: `src/ps_price_sync/services/ingestion.py`
- Create: `tests/test_ingestion_service.py`

- [ ] **Step 1: Write failing catalog ingestion tests**

Create the first half of `tests/test_ingestion_service.py`:

```python
from __future__ import annotations

import json
from datetime import datetime

import pytest
from django.utils import timezone

from ps_price_crawler.models import CatalogItem, CatalogPage, PriceInfo
from ps_price_sync.models import StoreProduct, SyncError, SyncRun
from ps_price_sync.services.ingestion import finalize_catalog_visibility, ingest_catalog_page


def _catalog_item(*, concept_id: str = "10002075", product_ids: tuple[str, ...] = ("EP0001-PRODUCT",), name: str = "Game A") -> CatalogItem:
    return CatalogItem(
        concept_id=concept_id,
        name=name,
        product_ids=product_ids,
        image_url="https://example.com/game.jpg",
        price=PriceInfo(
            base_price="NT$1,990",
            discounted_price="NT$1,990",
            discount_text=None,
            is_free=False,
            is_exclusive=False,
            is_tied_to_subscription=False,
            service_branding=(),
            upsell_text=None,
        ),
    )


def _catalog_page(*items: CatalogItem) -> CatalogPage:
    return CatalogPage(
        source_url="https://store.playstation.com/zh-hant-tw/category/test/1",
        category_id="test",
        total_count=len(items),
        offset=0,
        size=len(items),
        is_last=True,
        items=items,
    )


@pytest.mark.django_db
def test_ingest_catalog_page_upserts_product_and_marks_visible():
    run = SyncRun.objects.create(sync_type="catalog_only", status="running", summary="{}")
    result = ingest_catalog_page(
        sync_run=run,
        page=_catalog_page(_catalog_item()),
        seen_at=timezone.make_aware(datetime(2026, 5, 16, 8, 0)),
    )

    product = StoreProduct.objects.get(product_id="EP0001-PRODUCT")
    assert product.concept_id == "10002075"
    assert product.is_visible is True
    assert product.missing_count == 0
    assert result.persisted_products == 1


@pytest.mark.django_db
def test_ingest_catalog_page_records_missing_product_id_as_sync_error():
    run = SyncRun.objects.create(sync_type="catalog_only", status="running", summary="{}")
    result = ingest_catalog_page(
        sync_run=run,
        page=_catalog_page(_catalog_item(product_ids=())),
        seen_at=timezone.make_aware(datetime(2026, 5, 16, 8, 0)),
    )

    assert StoreProduct.objects.count() == 0
    assert SyncError.objects.filter(sync_run=run, stage="catalog_ingestion").count() == 1
    assert result.skipped_missing_product_id == 1


@pytest.mark.django_db
def test_finalize_catalog_visibility_marks_unseen_products_missing():
    existing = StoreProduct.objects.create(
        product_id="EP0001-OLD",
        product_name="Old",
        is_visible=True,
        missing_count=2,
    )
    run = SyncRun.objects.create(sync_type="catalog_only", status="running", summary="{}")
    result = ingest_catalog_page(
        sync_run=run,
        page=_catalog_page(_catalog_item(product_ids=("EP0001-NEW",))),
        seen_at=timezone.make_aware(datetime(2026, 5, 16, 8, 0)),
    )
    finalize_catalog_visibility(sync_run=run, observed_product_ids=result.observed_product_ids)

    existing.refresh_from_db()
    assert existing.is_visible is False
    assert existing.missing_count == 3
```

- [ ] **Step 2: Run the catalog ingestion tests to verify they fail**

Run: `uv run pytest tests/test_ingestion_service.py -k catalog -v`

Expected:

```text
FAILED ... ImportError: cannot import name 'ingest_catalog_page'
```

- [ ] **Step 3: Implement `ingest_catalog_page` with a small result object**

Create `src/ps_price_sync/services/ingestion.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from ps_price_crawler.models import CatalogItem, CatalogPage

from ps_price_sync.models import StoreProduct, SyncError, SyncRun


@dataclass(frozen=True)
class CatalogIngestionResult:
    observed_items: int
    persisted_products: int
    skipped_missing_product_id: int
    observed_product_ids: set[str]


def ingest_catalog_page(
    *,
    sync_run: SyncRun,
    page: CatalogPage,
    seen_at: datetime,
) -> CatalogIngestionResult:
    persisted_products = 0
    skipped_missing_product_id = 0
    observed_product_ids: set[str] = set()

    for item in page.items:
        product_id = item.product_ids[0] if item.product_ids else None
        if not product_id:
            SyncError.objects.create(
                sync_run=sync_run,
                stage="catalog_ingestion",
                concept_id=item.concept_id,
                source_url=page.source_url,
                error_type="MissingProductId",
                error_message="Catalog item has no product_id",
            )
            skipped_missing_product_id += 1
            sync_run.error_count += 1
            continue

        product, _ = StoreProduct.objects.get_or_create(
            product_id=product_id,
            defaults={"product_name": item.name},
        )
        observed_product_ids.add(product_id)
        product.concept_id = item.concept_id
        product.product_name = item.name
        product.concept_name = item.name if not product.concept_name else product.concept_name
        product.image_url = item.image_url or product.image_url
        product.is_visible = True
        product.missing_count = 0
        product.last_seen_at = seen_at
        product.save()
        persisted_products += 1

    sync_run.summary = json.dumps(
        {
            "observed_items": len(page.items),
            "persisted_products": persisted_products,
            "skipped_missing_product_id": skipped_missing_product_id,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    sync_run.save(update_fields=["error_count", "summary", "updated_at"])
    return CatalogIngestionResult(len(page.items), persisted_products, skipped_missing_product_id, observed_product_ids)


def finalize_catalog_visibility(*, sync_run: SyncRun, observed_product_ids: set[str]) -> int:
    del sync_run
    unseen = 0
    for product in StoreProduct.objects.exclude(product_id__in=observed_product_ids):
        product.is_visible = False
        product.missing_count = (product.missing_count or 0) + 1
        product.save(update_fields=["is_visible", "missing_count", "updated_at"])
        unseen += 1
    return unseen
```

- [ ] **Step 4: Rerun the catalog ingestion tests**

Run: `uv run pytest tests/test_ingestion_service.py -k catalog -v`

Expected:

```text
PASSED tests/test_ingestion_service.py::test_ingest_catalog_page_upserts_product_and_marks_visible
PASSED tests/test_ingestion_service.py::test_ingest_catalog_page_records_missing_product_id_as_sync_error
PASSED tests/test_ingestion_service.py::test_finalize_catalog_visibility_marks_unseen_products_missing
```

- [ ] **Step 5: Commit the catalog ingestion service**

```bash
git add src/ps_price_sync/services/__init__.py src/ps_price_sync/services/ingestion.py tests/test_ingestion_service.py
git commit -m "feat: persist catalog sync products"
```

## Task 4: Add Failing Snapshot Ingestion Tests And Implement Catalog/Detail Snapshot Writes

**Files:**
- Modify: `tests/test_ingestion_service.py`
- Modify: `src/ps_price_sync/services/ingestion.py`

- [ ] **Step 1: Extend the ingestion tests with snapshot cases**

Append to `tests/test_ingestion_service.py`:

```python
from datetime import date

from ps_price_crawler.models import ProductDetail
from ps_price_crawler.price_contract import NormalizedPrice, PriceState
from ps_price_crawler.source_strategy import SnapshotSourceDecision
from ps_price_sync.models import PriceSnapshot
from ps_price_sync.services.ingestion import ingest_catalog_snapshot, ingest_product_detail_snapshot


def _normalized_price(*, state: PriceState = PriceState.PAID) -> NormalizedPrice:
    return NormalizedPrice(
        state=state,
        currency="TWD",
        base_amount_cents=199000,
        discounted_amount_cents=199000,
        plus_amount_cents=None,
        base_display="NT$1,990",
        discounted_display="NT$1,990",
        discount_text=None,
        service_branding=(),
        upsell_text=None,
        source="catalog",
        raw_missing_reason=None,
    )


def _decision(*, source: str = "catalog") -> SnapshotSourceDecision:
    return SnapshotSourceDecision(
        source=source,
        reason="catalog_price_snapshot" if source == "catalog" else "price_state_unknown",
        reason_codes=("clear_catalog_price",) if source == "catalog" else ("price_state_unknown",),
        normalized_state=PriceState.PAID if source == "catalog" else PriceState.UNKNOWN,
        product_ids=("EP0001-PRODUCT",),
        missing_metadata_fields=(),
    )


@pytest.mark.django_db
def test_ingest_catalog_snapshot_writes_snapshot_without_detail():
    run = SyncRun.objects.create(sync_type="snapshot_only", status="running", summary="{}")
    ingest_catalog_snapshot(
        sync_run=run,
        item=_catalog_item(),
        normalized_price=_normalized_price(),
        decision=_decision(source="catalog"),
        snapshot_date=date(2026, 5, 16),
        source_url="https://store.playstation.com/zh-hant-tw/concept/10002075",
    )

    snapshot = PriceSnapshot.objects.get()
    assert snapshot.source_strategy_source == "catalog"
    assert snapshot.normalized_state == "PAID"


@pytest.mark.django_db
def test_ingest_product_detail_snapshot_can_create_product_before_catalog():
    run = SyncRun.objects.create(sync_type="snapshot_only", status="running", summary="{}")
    detail = ProductDetail(
        concept_id="10002075",
        concept_name="Game A",
        product_id="EP0001-PRODUCT",
        product_name="Game A Standard Edition",
        publisher_name="Sony",
        release_date="2026-01-01",
        platforms=("PS5",),
        top_category="GAME",
        price=_catalog_item().price,
    )

    ingest_product_detail_snapshot(
        sync_run=run,
        detail=detail,
        normalized_price=_normalized_price(),
        decision=_decision(source="concept_detail"),
        snapshot_date=date(2026, 5, 16),
        source_url="https://store.playstation.com/zh-hant-tw/concept/10002075",
    )

    product = StoreProduct.objects.get(product_id="EP0001-PRODUCT")
    assert product.is_visible is None
    assert product.missing_count is None


@pytest.mark.django_db
def test_ingest_snapshot_upserts_same_day_record():
    run = SyncRun.objects.create(sync_type="snapshot_only", status="running", summary="{}")
    product = StoreProduct.objects.create(product_id="EP0001-PRODUCT", product_name="Game A")

    ingest_catalog_snapshot(
        sync_run=run,
        item=_catalog_item(),
        normalized_price=_normalized_price(),
        decision=_decision(source="catalog"),
        snapshot_date=date(2026, 5, 16),
        source_url="https://store.playstation.com/zh-hant-tw/concept/10002075",
    )
    ingest_catalog_snapshot(
        sync_run=run,
        item=_catalog_item(),
        normalized_price=_normalized_price(state=PriceState.DISCOUNTED),
        decision=SnapshotSourceDecision(
            source="catalog",
            reason="catalog_price_snapshot",
            reason_codes=("clear_catalog_price",),
            normalized_state=PriceState.DISCOUNTED,
            product_ids=("EP0001-PRODUCT",),
            missing_metadata_fields=(),
        ),
        snapshot_date=date(2026, 5, 16),
        source_url="https://store.playstation.com/zh-hant-tw/concept/10002075",
    )

    assert PriceSnapshot.objects.count() == 1
    assert PriceSnapshot.objects.get().normalized_state == "DISCOUNTED"
```

- [ ] **Step 2: Run the snapshot-focused tests to verify they fail**

Run: `uv run pytest tests/test_ingestion_service.py -k snapshot -v`

Expected:

```text
FAILED ... ImportError: cannot import name 'ingest_catalog_snapshot'
```

- [ ] **Step 3: Implement catalog and detail snapshot ingestion**

Extend `src/ps_price_sync/services/ingestion.py`:

```python
import json
from dataclasses import asdict
from datetime import date

from ps_price_crawler.models import CatalogItem, ProductDetail
from ps_price_crawler.price_contract import NormalizedPrice
from ps_price_crawler.source_strategy import SnapshotSourceDecision

from ps_price_sync.models import PriceSnapshot, StoreProduct, SyncRun


def ingest_catalog_snapshot(
    *,
    sync_run: SyncRun,
    item: CatalogItem,
    normalized_price: NormalizedPrice,
    decision: SnapshotSourceDecision,
    snapshot_date: date,
    source_url: str,
) -> PriceSnapshot:
    product_id = item.product_ids[0]
    product, _ = StoreProduct.objects.get_or_create(
        product_id=product_id,
        defaults={"product_name": item.name},
    )
    product.concept_id = item.concept_id
    product.product_name = item.name
    product.concept_name = product.concept_name or item.name
    product.image_url = item.image_url or product.image_url
    product.source_url = source_url or product.source_url
    product.save()
    return _upsert_snapshot(product, normalized_price, decision, snapshot_date)


def ingest_product_detail_snapshot(
    *,
    sync_run: SyncRun,
    detail: ProductDetail,
    normalized_price: NormalizedPrice,
    decision: SnapshotSourceDecision,
    snapshot_date: date,
    source_url: str,
) -> PriceSnapshot:
    product, created = StoreProduct.objects.get_or_create(
        product_id=detail.product_id,
        defaults={
            "product_name": detail.product_name or detail.concept_name,
            "is_visible": None,
            "missing_count": None,
        },
    )
    product.concept_id = detail.concept_id
    product.product_name = detail.product_name or product.product_name
    product.concept_name = detail.concept_name
    product.publisher_name = detail.publisher_name or product.publisher_name
    product.release_date_raw = detail.release_date or product.release_date_raw
    product.top_category = detail.top_category or product.top_category
    product.platforms_raw = json.dumps(list(detail.platforms), ensure_ascii=False)
    product.source_url = source_url or product.source_url
    product.save()
    return _upsert_snapshot(product, normalized_price, decision, snapshot_date)


def _upsert_snapshot(
    product: StoreProduct,
    normalized_price: NormalizedPrice,
    decision: SnapshotSourceDecision,
    snapshot_date: date,
) -> PriceSnapshot:
    snapshot, _ = PriceSnapshot.objects.update_or_create(
        store_product=product,
        snapshot_date=snapshot_date,
        defaults={
            "normalized_state": normalized_price.state.value,
            "currency": normalized_price.currency,
            "base_amount_cents": normalized_price.base_amount_cents,
            "discounted_amount_cents": normalized_price.discounted_amount_cents,
            "plus_amount_cents": normalized_price.plus_amount_cents,
            "base_display": normalized_price.base_display,
            "discounted_display": normalized_price.discounted_display,
            "discount_text": normalized_price.discount_text,
            "service_branding_raw": json.dumps(list(normalized_price.service_branding), ensure_ascii=False),
            "upsell_text": normalized_price.upsell_text,
            "source_strategy_source": decision.source,
            "source_strategy_reason": decision.reason,
            "source_strategy_reason_codes_raw": json.dumps(list(decision.reason_codes), ensure_ascii=False),
        },
    )
    return snapshot
```

- [ ] **Step 4: Rerun the full ingestion service test file**

Run: `uv run pytest tests/test_ingestion_service.py -v`

Expected:

```text
PASSED tests/test_ingestion_service.py::test_ingest_catalog_page_upserts_product_and_marks_visible
PASSED tests/test_ingestion_service.py::test_ingest_catalog_snapshot_writes_snapshot_without_detail
PASSED tests/test_ingestion_service.py::test_ingest_product_detail_snapshot_can_create_product_before_catalog
PASSED tests/test_ingestion_service.py::test_ingest_snapshot_upserts_same_day_record
```

- [ ] **Step 5: Commit the snapshot ingestion work**

```bash
git add src/ps_price_sync/services/ingestion.py tests/test_ingestion_service.py
git commit -m "feat: add snapshot ingestion services"
```

## Task 5: Add Failing Command Tests And Implement `sync_ps_store`

**Files:**
- Create: `src/ps_price_sync/services/sync_runner.py`
- Create: `src/ps_price_sync/management/__init__.py`
- Create: `src/ps_price_sync/management/commands/__init__.py`
- Create: `src/ps_price_sync/management/commands/sync_ps_store.py`
- Create: `tests/test_sync_command.py`

- [ ] **Step 1: Write failing command tests**

Create `tests/test_sync_command.py`:

```python
from __future__ import annotations

import json
from datetime import date

import pytest
from django.core.management import call_command

from ps_price_sync.models import SyncRun


@pytest.mark.django_db
def test_catalog_only_command_creates_succeeded_run(monkeypatch):
    from ps_price_sync.services import sync_runner

    def fake_catalog_sync(*, sync_run, page_limit, snapshot_date):
        sync_run.success_count = 3
        sync_run.summary = json.dumps(
            {"observed_items": 4, "persisted_products": 3, "skipped_missing_product_id": 1},
            ensure_ascii=False,
        )
        sync_run.save(update_fields=["success_count", "summary", "updated_at"])

    monkeypatch.setattr(sync_runner, "run_catalog_sync", fake_catalog_sync)

    call_command("sync_ps_store", "--mode", "catalog-only", "--pages", "2", "--snapshot-date", "2026-05-16")

    run = SyncRun.objects.get()
    assert run.sync_type == "catalog_only"
    assert run.status == "succeeded"
    assert run.success_count == 3


@pytest.mark.django_db
def test_partial_failures_mark_run_partial(monkeypatch):
    from ps_price_sync.services import sync_runner

    def fake_snapshot_sync(*, sync_run, page_limit, snapshot_date):
        sync_run.success_count = 2
        sync_run.error_count = 1
        sync_run.summary = json.dumps({"observed_items": 3, "persisted_products": 2, "skipped_missing_product_id": 1}, ensure_ascii=False)
        sync_run.save(update_fields=["success_count", "error_count", "summary", "updated_at"])

    monkeypatch.setattr(sync_runner, "run_snapshot_sync", fake_snapshot_sync)

    call_command("sync_ps_store", "--mode", "snapshot-only", "--pages", "1", "--snapshot-date", "2026-05-16")

    run = SyncRun.objects.get()
    assert run.sync_type == "snapshot_only"
    assert run.status == "partial"
```

- [ ] **Step 2: Run the command tests to verify they fail**

Run: `uv run pytest tests/test_sync_command.py -v`

Expected:

```text
FAILED ... django.core.management.base.CommandError: Unknown command: 'sync_ps_store'
```

- [ ] **Step 3: Create package markers and the management command shell**

Create the package markers:

```python
# src/ps_price_sync/management/__init__.py

# src/ps_price_sync/management/commands/__init__.py
```

Create `src/ps_price_sync/management/commands/sync_ps_store.py`:

```python
from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from ps_price_sync.models import SyncRun
from ps_price_sync.services import sync_runner


class Command(BaseCommand):
    help = "Run catalog and/or snapshot persistence using the existing crawler adapter"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--mode", choices=("catalog-only", "snapshot-only", "catalog-and-snapshot"), required=True)
        parser.add_argument("--pages", type=int, default=1)
        parser.add_argument("--snapshot-date", required=True)

    def handle(self, *args, **options):
        mode = options["mode"]
        run = SyncRun.objects.create(
            sync_type=mode.replace("-", "_"),
            status="running",
            started_at=sync_runner.sync_now(),
            summary="{}",
        )

        try:
            snapshot_date = date.fromisoformat(options["snapshot_date"])
            if mode == "catalog-only":
                sync_runner.run_catalog_sync(sync_run=run, page_limit=options["pages"], snapshot_date=snapshot_date)
            elif mode == "snapshot-only":
                sync_runner.run_snapshot_sync(sync_run=run, page_limit=options["pages"], snapshot_date=snapshot_date)
            else:
                sync_runner.run_catalog_sync(sync_run=run, page_limit=options["pages"], snapshot_date=snapshot_date)
                sync_runner.run_snapshot_sync(sync_run=run, page_limit=options["pages"], snapshot_date=snapshot_date)

            run.refresh_from_db()
            if run.error_count and run.success_count:
                run.status = "partial"
            elif run.error_count:
                run.status = "failed"
            else:
                run.status = "succeeded"
        except Exception:
            run.status = "failed"
            raise
        finally:
            run.finished_at = sync_runner.sync_now()
            run.save(update_fields=["status", "finished_at", "updated_at"])
```

- [ ] **Step 4: Implement the real adapter orchestration helpers**

Implement these behaviors in `src/ps_price_sync/services/sync_runner.py`:

```python
from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone

from ps_price_crawler.catalog import normalize_catalog_item_price, parse_catalog_page
from ps_price_crawler.client import PlayStationStoreClient, concept_url
from ps_price_crawler.product import normalize_product_detail_price, parse_product_detail
from ps_price_crawler.source_strategy import choose_snapshot_source
from ps_price_sync.services.ingestion import (
    finalize_catalog_visibility,
    ingest_catalog_page,
    ingest_catalog_snapshot,
    ingest_product_detail_snapshot,
)


def sync_now() -> datetime:
    return timezone.now()


def run_catalog_sync(*, sync_run, page_limit: int, snapshot_date: date) -> None:
    del snapshot_date
    with PlayStationStoreClient() as client:
        observed_product_ids: set[str] = set()
        for page_number in range(1, page_limit + 1):
            source_url, html = client.fetch_catalog_page(page_number)
            page = parse_catalog_page(html, source_url=source_url)
            result = ingest_catalog_page(
                sync_run=sync_run,
                page=page,
                seen_at=sync_now(),
            )
            observed_product_ids.update(result.observed_product_ids)
            sync_run.success_count += result.persisted_products
            sync_run.save(update_fields=["success_count", "updated_at"])
        finalize_catalog_visibility(sync_run=sync_run, observed_product_ids=observed_product_ids)


def run_snapshot_sync(*, sync_run, page_limit: int, snapshot_date: date) -> None:
    with PlayStationStoreClient() as client:
        for page_number in range(1, page_limit + 1):
            source_url, html = client.fetch_catalog_page(page_number)
            page = parse_catalog_page(html, source_url=source_url)
            for item in page.items:
                normalized_price = normalize_catalog_item_price(item)
                decision = choose_snapshot_source(item, normalized_price)
                if decision.source == "catalog" and item.product_ids:
                    ingest_catalog_snapshot(
                        sync_run=sync_run,
                        item=item,
                        normalized_price=normalized_price,
                        decision=decision,
                        snapshot_date=snapshot_date,
                        source_url=concept_url(item.concept_id),
                    )
                    sync_run.success_count += 1
                    sync_run.save(update_fields=["success_count", "updated_at"])
                    continue

                detail_url, detail_html = client.fetch_concept(item.concept_id)
                detail = parse_product_detail(detail_html, concept_id=item.concept_id, catalog_price=item.price)
                detail_price = normalize_product_detail_price(detail)
                ingest_product_detail_snapshot(
                    sync_run=sync_run,
                    detail=detail,
                    normalized_price=detail_price,
                    decision=decision,
                    snapshot_date=snapshot_date,
                    source_url=detail_url,
                )
                sync_run.success_count += 1
                sync_run.save(update_fields=["success_count", "updated_at"])
```

- [ ] **Step 5: Rerun the command test file**

Run: `uv run pytest tests/test_sync_command.py -v`

Expected:

```text
PASSED tests/test_sync_command.py::test_catalog_only_command_creates_succeeded_run
PASSED tests/test_sync_command.py::test_partial_failures_mark_run_partial
```

- [ ] **Step 6: Commit the command layer**

```bash
git add src/ps_price_sync/services/sync_runner.py src/ps_price_sync/management tests/test_sync_command.py
git commit -m "feat: add manual sync command"
```

## Task 6: Update Documentation And Run End-To-End Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing documentation assertion as a smoke check**

Temporarily add this test at the end of `tests/test_django_setup.py`:

```python
def test_readme_mentions_django_sync_commands():
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "uv run python manage.py migrate" in readme
    assert "uv run python manage.py sync_ps_store --mode catalog-and-snapshot" in readme
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run: `uv run pytest tests/test_django_setup.py::test_readme_mentions_django_sync_commands -v`

Expected:

```text
FAILED ... AssertionError
```

- [ ] **Step 3: Update the README with Django setup and sync usage**

Append this section to `README.md` after the current verification section:

````markdown
## Django data foundation setup

```bash
uv sync --extra dev
uv run python manage.py migrate
```

## Manual persistence commands

Catalog metadata only:

```bash
uv run python manage.py sync_ps_store --mode catalog-only --pages 5 --snapshot-date 2026-05-16
```

Daily snapshots using source strategy:

```bash
uv run python manage.py sync_ps_store --mode snapshot-only --pages 5 --snapshot-date 2026-05-16
```

Run both catalog persistence and snapshot persistence:

```bash
uv run python manage.py sync_ps_store --mode catalog-and-snapshot --pages 5 --snapshot-date 2026-05-16
```
````

- [ ] **Step 4: Run focused verification, then the full test suite**

Run:

```bash
uv run pytest tests/test_django_setup.py -v
uv run pytest tests/test_sync_models.py tests/test_ingestion_service.py tests/test_sync_command.py -v
uv run pytest -v
```

Expected:

```text
PASSED tests/test_django_setup.py ...
PASSED tests/test_sync_models.py ...
PASSED tests/test_ingestion_service.py ...
PASSED tests/test_sync_command.py ...
... full suite green ...
```

- [ ] **Step 5: Commit docs and verification**

```bash
git add README.md tests/test_django_setup.py
git commit -m "docs: add django data foundation usage"
```

## Self-Review

- Spec coverage:
  - Django skeleton: Task 1
  - models and migrations: Task 2
  - catalog ingestion: Task 3
  - catalog snapshot and detail snapshot writes: Task 4
  - manual command and sync run lifecycle: Task 5
  - README and verification: Task 6
- Placeholder scan:
  - No `TODO`, `TBD`, or "implement later" markers remain in tasks.
- Type consistency:
  - `StoreProduct`, `PriceSnapshot`, `SyncRun`, `SyncError`
  - `ingest_catalog_page`, `ingest_catalog_snapshot`, `ingest_product_detail_snapshot`
  - `catalog-only`, `snapshot-only`, `catalog-and-snapshot`
