from __future__ import annotations

from datetime import date
from datetime import datetime
from datetime import timezone
import json

import pytest
from django.utils import timezone as django_timezone
from ps_price_crawler.price_contract import NormalizedPrice, PriceState
from ps_price_crawler.source_strategy import SnapshotSource, SnapshotSourceDecision

from ps_price_crawler.models import CatalogItem, CatalogPage, ProductDetail
from ps_price_sync.models import PriceSnapshot, StoreProduct, SyncError, SyncRun


def _catalog_item(*, concept_id: str, product_ids: tuple[str, ...]) -> CatalogItem:
    return CatalogItem(
        concept_id=concept_id,
        name=f"Game {concept_id}",
        product_ids=product_ids,
        image_url="https://example.test/image.jpg",
        price=None,
    )


def _catalog_item_with_image(*, concept_id: str, product_ids: tuple[str, ...], image_url: str | None) -> CatalogItem:
    return CatalogItem(
        concept_id=concept_id,
        name=f"Game {concept_id}",
        product_ids=product_ids,
        image_url=image_url,
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


def _normalized_price(*, state: PriceState = PriceState.PAID) -> NormalizedPrice:
    return NormalizedPrice(
        state=state,
        currency="TWD",
        base_amount_cents=169000,
        discounted_amount_cents=139000,
        plus_amount_cents=None,
        base_display="NT$1,690",
        discounted_display="NT$1,390",
        discount_text="限時優惠",
        service_branding=("PS Plus",),
        upsell_text="訂閱享好禮",
        source="catalog",
        raw_missing_reason=None,
    )


def _decision(*, source: SnapshotSource = "catalog") -> SnapshotSourceDecision:
    return SnapshotSourceDecision(
        source=source,
        reason="test_reason",
        reason_codes=("test_reason",),
        normalized_state=PriceState.PAID,
        product_ids=("UP1821-PPSA10990_00-1887411884729257",),
        missing_metadata_fields=(),
    )


@pytest.mark.django_db
def test_ingest_catalog_page_upserts_product_and_marks_visible() -> None:
    sync_run = SyncRun.objects.create(sync_type="catalog_only", status="running")
    seen_at = django_timezone.now()
    first_product = StoreProduct.objects.create(
        product_id="UP1821-PPSA10990_00-1887411884729257",
        concept_id="old",
        product_name="",
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
    assert refreshed_product.concept_name == "old concept"
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


@pytest.mark.django_db
def test_ingest_catalog_page_accumulates_summary_across_pages() -> None:
    from ps_price_sync.services.ingestion import ingest_catalog_page

    sync_run = SyncRun.objects.create(sync_type="catalog_only", status="running")
    first_page = _catalog_page((_catalog_item(concept_id="223118", product_ids=("UP1821-PPSA10990_00-1887411884729257",)),))
    second_page = _catalog_page((_catalog_item(concept_id="334455", product_ids=()),))

    ingest_catalog_page(sync_run=sync_run, page=first_page, seen_at=django_timezone.now())
    ingest_catalog_page(sync_run=sync_run, page=second_page, seen_at=django_timezone.now())

    sync_run.refresh_from_db()
    assert json.loads(sync_run.summary) == {
        "observed_items": 2,
        "persisted_products": 1,
        "skipped_missing_product_id": 1,
    }
    assert sync_run.error_count == 1


@pytest.mark.django_db
def test_ingest_catalog_page_keeps_existing_image_url_when_catalog_missing_it() -> None:
    from ps_price_sync.services.ingestion import ingest_catalog_page

    sync_run = SyncRun.objects.create(sync_type="catalog_only", status="running")
    StoreProduct.objects.create(
        product_id="UP1821-PPSA10990_00-1887411884729257",
        concept_id="223118",
        product_name="Game 223118",
        concept_name="",
        image_url="https://example.test/old-image.jpg",
        is_visible=False,
        missing_count=2,
    )
    page = _catalog_page(
        (_catalog_item_with_image(
            concept_id="223118",
            product_ids=("UP1821-PPSA10990_00-1887411884729257",),
            image_url=None,
        ),),
    )

    ingest_catalog_page(sync_run=sync_run, page=page, seen_at=django_timezone.now())

    product = StoreProduct.objects.get(product_id="UP1821-PPSA10990_00-1887411884729257")
    assert product.image_url == "https://example.test/old-image.jpg"


@pytest.mark.django_db
def test_ingest_catalog_page_keeps_existing_non_empty_concept_name() -> None:
    from ps_price_sync.services.ingestion import ingest_catalog_page

    sync_run = SyncRun.objects.create(sync_type="catalog_only", status="running")
    StoreProduct.objects.create(
        product_id="UP1821-PPSA10990_00-1887411884729257",
        concept_id="223118",
        product_name="Game 223118",
        concept_name="Detail concept",
        is_visible=False,
        missing_count=2,
    )
    page = _catalog_page(
        (_catalog_item(
            concept_id="223118",
            product_ids=("UP1821-PPSA10990_00-1887411884729257",),
        ),),
    )

    ingest_catalog_page(sync_run=sync_run, page=page, seen_at=django_timezone.now())

    product = StoreProduct.objects.get(product_id="UP1821-PPSA10990_00-1887411884729257")
    assert product.concept_name == "Detail concept"


@pytest.mark.django_db
def test_ingest_catalog_page_keeps_existing_product_name_from_detail_data() -> None:
    from ps_price_sync.services.ingestion import ingest_catalog_page

    sync_run = SyncRun.objects.create(sync_type="catalog_only", status="running")
    StoreProduct.objects.create(
        product_id="UP1821-PPSA10990_00-1887411884729257",
        concept_id="223118",
        product_name="Detail product name",
        concept_name="Detail concept",
        is_visible=False,
        missing_count=2,
    )
    page = _catalog_page(
        (_catalog_item(
            concept_id="223118",
            product_ids=("UP1821-PPSA10990_00-1887411884729257",),
        ),),
    )

    ingest_catalog_page(sync_run=sync_run, page=page, seen_at=django_timezone.now())

    product = StoreProduct.objects.get(product_id="UP1821-PPSA10990_00-1887411884729257")
    assert product.product_name == "Detail product name"
    assert product.concept_name == "Detail concept"
    assert product.is_visible is True
    assert product.missing_count == 0


@pytest.mark.django_db
def test_ingest_catalog_snapshot_writes_snapshot_without_detail() -> None:
    sync_run = SyncRun.objects.create(sync_type="catalog_snapshot", status="running")
    item = _catalog_item(
        concept_id="223118",
        product_ids=("UP1821-PPSA10990_00-1887411884729257",),
    )
    normalized_price = _normalized_price(state=PriceState.PAID)
    decision = _decision(source="catalog")

    from ps_price_sync.services.ingestion import ingest_catalog_snapshot

    ingest_catalog_snapshot(
        sync_run=sync_run,
        item=item,
        normalized_price=normalized_price,
        decision=decision,
        snapshot_date=date(2026, 5, 16),
        source_url="https://store.playstation.com/zh-hant-tw/catalog/223118",
    )

    product = StoreProduct.objects.get(product_id="UP1821-PPSA10990_00-1887411884729257")
    snapshot = PriceSnapshot.objects.get(store_product=product, snapshot_date=date(2026, 5, 16))

    assert product.concept_id == "223118"
    assert product.product_name == "Game 223118"
    assert product.source_url == "https://store.playstation.com/zh-hant-tw/catalog/223118"
    assert product.is_visible is None
    assert product.missing_count is None
    assert snapshot.normalized_state == PriceState.PAID.value
    assert snapshot.currency == "TWD"
    assert snapshot.base_amount_cents == 169000
    assert snapshot.discounted_amount_cents == 139000
    assert snapshot.base_display == "NT$1,690"
    assert snapshot.discounted_display == "NT$1,390"
    assert snapshot.discount_text == "限時優惠"
    assert snapshot.service_branding_raw == json.dumps(["PS Plus"])
    assert snapshot.upsell_text == "訂閱享好禮"
    assert snapshot.source_strategy_source == "catalog"
    assert snapshot.source_strategy_reason == "test_reason"
    assert snapshot.source_strategy_reason_codes_raw == json.dumps(["test_reason"])


@pytest.mark.django_db
def test_ingest_product_detail_snapshot_can_create_product_before_catalog() -> None:
    sync_run = SyncRun.objects.create(sync_type="snapshot", status="running")
    detail = ProductDetail(
        concept_id="223118",
        concept_name="PRAGMATA",
        product_id="UP1821-PPSA10990_00-1887411884729257",
        product_name="PRAGMATA Game",
        publisher_name="Capcom",
        release_date="2026-05-16",
        platforms=("PS5", "PS4"),
        top_category="GAME",
        price=None,
    )
    normalized_price = _normalized_price(state=PriceState.PAID)
    decision = _decision(source="concept_detail")

    from ps_price_sync.services.ingestion import ingest_product_detail_snapshot

    ingest_product_detail_snapshot(
        sync_run=sync_run,
        detail=detail,
        normalized_price=normalized_price,
        decision=decision,
        snapshot_date=date(2026, 5, 16),
        source_url="https://store.playstation.com/zh-hant-tw/concept/223118",
    )

    product = StoreProduct.objects.get(product_id="UP1821-PPSA10990_00-1887411884729257")
    snapshot = PriceSnapshot.objects.get(store_product=product, snapshot_date=date(2026, 5, 16))

    assert product.concept_id == "223118"
    assert product.concept_name == "PRAGMATA"
    assert product.product_name == "PRAGMATA Game"
    assert product.publisher_name == "Capcom"
    assert product.release_date_raw == "2026-05-16"
    assert product.top_category == "GAME"
    assert product.platforms_raw == json.dumps(["PS5", "PS4"])
    assert product.source_url == "https://store.playstation.com/zh-hant-tw/concept/223118"
    assert product.is_visible is None
    assert product.missing_count is None
    assert snapshot.source_strategy_source == "concept_detail"


@pytest.mark.django_db
def test_ingest_snapshot_upserts_same_day_record() -> None:
    sync_run = SyncRun.objects.create(sync_type="catalog_snapshot", status="running")
    product = StoreProduct.objects.create(
        product_id="UP1821-PPSA10990_00-1887411884729257",
        concept_id="223118",
        product_name="PRAGMATA",
        concept_name="PRAGMATA",
        is_visible=True,
        missing_count=0,
    )
    snapshot_date = date(2026, 5, 16)
    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=snapshot_date,
        normalized_state=PriceState.PAID.value,
        source_strategy_source="catalog",
        source_strategy_reason="first",
        source_strategy_reason_codes_raw=json.dumps(["first"]),
        currency="TWD",
        base_amount_cents=100,
        discounted_amount_cents=100,
        base_display="NT$100",
        discounted_display="NT$100",
    )

    item = _catalog_item(
        concept_id="223118",
        product_ids=(product.product_id,),
    )
    normalized_price = _normalized_price(state=PriceState.DISCOUNTED)
    decision = _decision(source="catalog")

    from ps_price_sync.services.ingestion import ingest_catalog_snapshot

    ingest_catalog_snapshot(
        sync_run=sync_run,
        item=item,
        normalized_price=normalized_price,
        decision=decision,
        snapshot_date=snapshot_date,
        source_url="https://store.playstation.com/zh-hant-tw/catalog/223118",
    )

    assert PriceSnapshot.objects.filter(store_product=product, snapshot_date=snapshot_date).count() == 1
    snapshot = PriceSnapshot.objects.get(store_product=product, snapshot_date=snapshot_date)
    assert snapshot.normalized_state == PriceState.DISCOUNTED.value
    assert snapshot.discounted_amount_cents == 139000
