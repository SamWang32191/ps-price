from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json

from django.utils import timezone

from ps_price_crawler.models import CatalogItem, CatalogPage, ProductDetail
from ps_price_crawler.price_contract import NormalizedPrice
from ps_price_crawler.source_strategy import SnapshotSourceDecision
from ps_price_sync.models import PriceSnapshot, StoreProduct, SyncError, SyncRun


@dataclass(frozen=True)
class CatalogIngestionResult:
    observed_items: int
    persisted_products: int
    skipped_missing_product_id: int
    observed_product_ids: set[str]


def _first_product_id(item: CatalogItem) -> str | None:
    return item.product_ids[0] if item.product_ids else None


def _build_summary(observed_items: int, persisted_products: int, skipped_missing_product_id: int) -> str:
    return json.dumps(
        {
            "observed_items": observed_items,
            "persisted_products": persisted_products,
            "skipped_missing_product_id": skipped_missing_product_id,
        }
    )


def _load_summary(summary_text: str | None) -> dict[str, int]:
    if not summary_text:
        return {
            "observed_items": 0,
            "persisted_products": 0,
            "skipped_missing_product_id": 0,
        }
    try:
        parsed = json.loads(summary_text)
    except json.JSONDecodeError:
        return {
            "observed_items": 0,
            "persisted_products": 0,
            "skipped_missing_product_id": 0,
        }
    if not isinstance(parsed, dict):
        return {
            "observed_items": 0,
            "persisted_products": 0,
            "skipped_missing_product_id": 0,
        }

    def _as_int(value: object) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    return {
        "observed_items": _as_int(parsed.get("observed_items")),
        "persisted_products": _as_int(parsed.get("persisted_products")),
        "skipped_missing_product_id": _as_int(parsed.get("skipped_missing_product_id")),
    }


def _upsert_snapshot(
    *,
    store_product: StoreProduct,
    snapshot_date,
    normalized_price: NormalizedPrice,
    decision: SnapshotSourceDecision,
) -> None:
    PriceSnapshot.objects.update_or_create(
        store_product=store_product,
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
            "service_branding_raw": json.dumps(list(normalized_price.service_branding)),
            "upsell_text": normalized_price.upsell_text,
            "source_strategy_source": decision.source,
            "source_strategy_reason": decision.reason,
            "source_strategy_reason_codes_raw": json.dumps(list(decision.reason_codes)),
        },
    )


def ingest_catalog_snapshot(
    sync_run: SyncRun,
    item: CatalogItem,
    normalized_price: NormalizedPrice,
    decision: SnapshotSourceDecision,
    snapshot_date,
    source_url: str,
) -> None:
    _ = sync_run
    product_id = _first_product_id(item)
    if not product_id:
        return

    product, created = StoreProduct.objects.get_or_create(
        product_id=product_id,
        defaults={
            "concept_id": item.concept_id,
            "product_name": item.name,
            "concept_name": item.name,
            "image_url": item.image_url,
            "source_url": source_url,
            "platforms_raw": json.dumps([]),
            "is_visible": None,
            "missing_count": None,
        },
    )

    product.concept_id = item.concept_id
    if not product.product_name:
        product.product_name = item.name
    if not product.concept_name:
        product.concept_name = item.name
    if item.image_url:
        product.image_url = item.image_url
    if source_url:
        product.source_url = source_url
    update_fields = (
        "concept_id",
        "product_name",
        "concept_name",
        "image_url",
        "source_url",
        "updated_at",
    )
    if created:
        update_fields = (
            *update_fields,
            "is_visible",
            "missing_count",
        )
    product.save(
        update_fields=update_fields
    )

    _upsert_snapshot(
        store_product=product,
        snapshot_date=snapshot_date,
        normalized_price=normalized_price,
        decision=decision,
    )


def ingest_product_detail_snapshot(
    sync_run: SyncRun,
    detail: ProductDetail,
    normalized_price: NormalizedPrice,
    decision: SnapshotSourceDecision,
    snapshot_date,
    source_url: str,
) -> None:
    _ = sync_run
    product_id = detail.product_id
    if not product_id:
        return

    product_name = detail.product_name or detail.concept_name or detail.concept_id
    if not product_name:
        return

    product, created = StoreProduct.objects.get_or_create(
        product_id=product_id,
        defaults={
            "concept_id": detail.concept_id,
            "product_name": product_name,
            "concept_name": detail.concept_name,
            "publisher_name": detail.publisher_name,
            "release_date_raw": detail.release_date,
            "top_category": detail.top_category,
            "platforms_raw": json.dumps(list(detail.platforms)),
            "source_url": source_url,
            "is_visible": None,
            "missing_count": None,
        },
    )

    product.concept_id = detail.concept_id
    if detail.concept_name:
        product.concept_name = detail.concept_name
    if detail.product_name:
        product.product_name = detail.product_name
    if detail.publisher_name:
        product.publisher_name = detail.publisher_name
    if detail.release_date:
        product.release_date_raw = detail.release_date
    if detail.top_category:
        product.top_category = detail.top_category
    if source_url:
        product.source_url = source_url
    update_fields = (
        "concept_id",
        "product_name",
        "concept_name",
        "publisher_name",
        "release_date_raw",
        "top_category",
        "source_url",
        "updated_at",
    )
    if detail.platforms:
        product.platforms_raw = json.dumps(list(detail.platforms))
        update_fields = (*update_fields, "platforms_raw")
    if created:
        update_fields = (
            *update_fields,
            "is_visible",
            "missing_count",
        )

    product.save(update_fields=update_fields)

    _upsert_snapshot(
        store_product=product,
        snapshot_date=snapshot_date,
        normalized_price=normalized_price,
        decision=decision,
    )


def ingest_catalog_page(
    sync_run: SyncRun,
    page: CatalogPage,
    seen_at: datetime,
) -> CatalogIngestionResult:
    observed_product_ids: set[str] = set()
    persisted_products = 0
    skipped_missing_product_id = 0

    for item in page.items:
        product_id = _first_product_id(item)
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
            continue

        observed_product_ids.add(product_id)

        product, _ = StoreProduct.objects.get_or_create(
            product_id=product_id,
            defaults={
                "concept_id": item.concept_id,
                "product_name": item.name,
                "concept_name": item.name,
                "image_url": item.image_url,
                "is_visible": True,
                "missing_count": 0,
                "last_seen_at": seen_at,
            },
        )
        product.concept_id = item.concept_id
        if not product.product_name:
            product.product_name = item.name
        if not product.concept_name:
            product.concept_name = item.name
        if item.image_url:
            product.image_url = item.image_url
        product.is_visible = True
        product.missing_count = 0
        product.last_seen_at = seen_at
        product.save(
            update_fields=(
                "concept_id",
                "product_name",
                "concept_name",
                "image_url",
                "is_visible",
                "missing_count",
                "last_seen_at",
                "updated_at",
            )
        )
        persisted_products += 1

    previous_summary = _load_summary(sync_run.summary)
    sync_run.error_count += skipped_missing_product_id
    sync_run.summary = _build_summary(
        observed_items=previous_summary["observed_items"] + len(page.items),
        persisted_products=previous_summary["persisted_products"] + persisted_products,
        skipped_missing_product_id=previous_summary["skipped_missing_product_id"]
        + skipped_missing_product_id,
    )
    sync_run.updated_at = timezone.now()
    sync_run.save(update_fields=["error_count", "summary", "updated_at"])

    return CatalogIngestionResult(
        observed_items=len(page.items),
        persisted_products=persisted_products,
        skipped_missing_product_id=skipped_missing_product_id,
        observed_product_ids=observed_product_ids,
    )


def finalize_catalog_visibility(sync_run: SyncRun, observed_product_ids: set[str]) -> int:
    unseen = StoreProduct.objects.exclude(product_id__in=observed_product_ids)
    unseen_count = unseen.count()

    for product in unseen:
        product.is_visible = False
        missing_count = product.missing_count or 0
        product.missing_count = missing_count + 1
        product.save(update_fields=("is_visible", "missing_count", "updated_at"))

    sync_run.updated_at = timezone.now()
    sync_run.save(update_fields=["updated_at"])

    return unseen_count
