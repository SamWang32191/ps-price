from __future__ import annotations

from datetime import datetime
from datetime import timezone
import json

import pytest
from django.utils import timezone as django_timezone

from ps_price_crawler.models import CatalogItem, CatalogPage
from ps_price_sync.models import StoreProduct, SyncError, SyncRun


def _catalog_item(*, concept_id: str, product_ids: tuple[str, ...]) -> CatalogItem:
    return CatalogItem(
        concept_id=concept_id,
        name=f"Game {concept_id}",
        product_ids=product_ids,
        image_url="https://example.test/image.jpg",
        price=None,
    )


def _catalog_page(items: tuple[CatalogItem, ...]) -> CatalogPage:
    return CatalogPage(
        source_url="https://store.playstation.com/zh-hant-tw/category/test/1",
        category_id="test",
        total_count=len(items),
        offset=0,
        size=24,
        is_last=True,
        items=items,
    )


@pytest.mark.django_db
def test_ingest_catalog_page_upserts_product_and_marks_visible() -> None:
    sync_run = SyncRun.objects.create(sync_type="catalog_only", status="running")
    seen_at = django_timezone.now()
    first_product = StoreProduct.objects.create(
        product_id="UP1821-PPSA10990_00-1887411884729257",
        concept_id="old",
        product_name="old name",
        concept_name="old concept",
        is_visible=False,
        missing_count=2,
        last_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    page = _catalog_page((_catalog_item(concept_id="223118", product_ids=("UP1821-PPSA10990_00-1887411884729257",)),))

    from ps_price_sync.services.ingestion import CatalogIngestionResult

    from ps_price_sync.services.ingestion import ingest_catalog_page

    result = ingest_catalog_page(sync_run=sync_run, page=page, seen_at=seen_at)

    refreshed_product = StoreProduct.objects.get(product_id="UP1821-PPSA10990_00-1887411884729257")

    assert result == CatalogIngestionResult(
        observed_items=1,
        persisted_products=1,
        skipped_missing_product_id=0,
        observed_product_ids={"UP1821-PPSA10990_00-1887411884729257"},
    )
    assert StoreProduct.objects.filter(product_id="UP1821-PPSA10990_00-1887411884729257").count() == 1
    assert refreshed_product.id == first_product.id
    assert refreshed_product.concept_id == "223118"
    assert refreshed_product.product_name == "Game 223118"
    assert refreshed_product.concept_name == "Game 223118"
    assert refreshed_product.image_url == "https://example.test/image.jpg"
    assert refreshed_product.is_visible is True
    assert refreshed_product.missing_count == 0
    assert refreshed_product.last_seen_at == seen_at

    sync_run.refresh_from_db()
    assert json.loads(sync_run.summary) == {
        "observed_items": 1,
        "persisted_products": 1,
        "skipped_missing_product_id": 0,
    }
    assert sync_run.error_count == 0


@pytest.mark.django_db
def test_ingest_catalog_page_records_missing_product_id_as_sync_error() -> None:
    sync_run = SyncRun.objects.create(sync_type="catalog_only", status="running")

    page = _catalog_page((_catalog_item(concept_id="334455", product_ids=()),))

    from ps_price_sync.services.ingestion import ingest_catalog_page

    result = ingest_catalog_page(sync_run=sync_run, page=page, seen_at=django_timezone.now())

    assert result.persisted_products == 0
    assert result.skipped_missing_product_id == 1

    sync_run.refresh_from_db()
    assert json.loads(sync_run.summary) == {
        "observed_items": 1,
        "persisted_products": 0,
        "skipped_missing_product_id": 1,
    }
    assert sync_run.error_count == 1
    assert StoreProduct.objects.count() == 0

    error = SyncError.objects.get(sync_run=sync_run)
    assert error.stage == "catalog_ingestion"
    assert error.concept_id == "334455"
    assert error.source_url == page.source_url
    assert error.error_type == "MissingProductId"
    assert error.error_message == "Catalog item has no product_id"


@pytest.mark.django_db
def test_finalize_catalog_visibility_marks_unseen_products_missing() -> None:
    from ps_price_sync.services.ingestion import finalize_catalog_visibility

    sync_run = SyncRun.objects.create(sync_type="catalog_only", status="running")
    StoreProduct.objects.create(
        product_id="UP1821-PPSA10990_00-1887411884729257",
        concept_id="223118",
        product_name="Game 223118",
        concept_name="",
        is_visible=True,
        missing_count=0,
    )
    missing_product = StoreProduct.objects.create(
        product_id="HP0000-PSAB00000_00-EXAMPLE",
        concept_id="100050",
        product_name="Game 100050",
        concept_name="",
        is_visible=True,
        missing_count=2,
    )

    unseen_count = finalize_catalog_visibility(
        sync_run,
        observed_product_ids={"UP1821-PPSA10990_00-1887411884729257"},
    )

    missing_product.refresh_from_db()
    assert unseen_count == 1
    assert StoreProduct.objects.get(product_id="UP1821-PPSA10990_00-1887411884729257").is_visible is True
    assert missing_product.is_visible is False
    assert missing_product.missing_count == 3


@pytest.mark.django_db
def test_finalize_catalog_visibility_increments_missing_count_for_already_invisible_products() -> None:
    from ps_price_sync.services.ingestion import finalize_catalog_visibility

    sync_run = SyncRun.objects.create(sync_type="catalog_only", status="running")
    StoreProduct.objects.create(
        product_id="UP1821-PPSA10990_00-1887411884729257",
        concept_id="223118",
        product_name="Game 223118",
        concept_name="",
        is_visible=True,
        missing_count=0,
    )
    hidden_product = StoreProduct.objects.create(
        product_id="HP0000-PSAB00000_00-HIDDEN",
        concept_id="100051",
        product_name="Game 100051",
        concept_name="",
        is_visible=False,
        missing_count=2,
    )

    unseen_count = finalize_catalog_visibility(
        sync_run,
        observed_product_ids={"UP1821-PPSA10990_00-1887411884729257"},
    )

    hidden_product.refresh_from_db()
    assert unseen_count == 1
    assert hidden_product.is_visible is False
    assert hidden_product.missing_count == 3
