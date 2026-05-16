from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone
from ps_price_crawler.catalog import normalize_catalog_item_price, parse_catalog_page
from ps_price_crawler.client import PlayStationStoreClient, concept_url
from ps_price_crawler.product import normalize_product_detail_price, parse_product_detail
from ps_price_crawler.source_strategy import choose_snapshot_source
from ps_price_sync.models import SyncError, SyncRun
from ps_price_sync.services.ingestion import (
    finalize_catalog_visibility,
    ingest_catalog_page,
    ingest_catalog_snapshot,
    ingest_product_detail_snapshot,
)


def sync_now() -> datetime:
    return timezone.now()


def run_catalog_sync(
    *,
    sync_run: SyncRun,
    page_limit: int,
    snapshot_date: date,
) -> None:
    if page_limit < 1:
        raise ValueError("page_limit must be >= 1")

    del snapshot_date
    observed_product_ids: set[str] = set()

    with PlayStationStoreClient() as client:
        for page_number in range(1, page_limit + 1):
            source_url, html = client.fetch_catalog_page(page_number)
            parsed = parse_catalog_page(html, source_url=source_url)
            result = ingest_catalog_page(
                sync_run=sync_run,
                page=parsed,
                seen_at=sync_now(),
            )
            if result.persisted_products:
                _increment_success(sync_run=sync_run, delta=result.persisted_products)
            observed_product_ids.update(result.observed_product_ids)

    finalize_catalog_visibility(sync_run=sync_run, observed_product_ids=observed_product_ids)


def run_snapshot_sync(
    *,
    sync_run: SyncRun,
    page_limit: int,
    snapshot_date: date,
) -> None:
    if page_limit < 1:
        raise ValueError("page_limit must be >= 1")

    with PlayStationStoreClient() as client:
        for page_number in range(1, page_limit + 1):
            page_source_url, html = client.fetch_catalog_page(page_number)
            parsed = parse_catalog_page(html, source_url=page_source_url)

            for item in parsed.items:
                _run_snapshot_item(
                    client=client,
                    sync_run=sync_run,
                    item=item,
                    snapshot_date=snapshot_date,
                    fallback_source_url=page_source_url,
                )


def run_catalog_and_snapshot_sync(
    *,
    sync_run: SyncRun,
    page_limit: int,
    snapshot_date: date,
) -> None:
    if page_limit < 1:
        raise ValueError("page_limit must be >= 1")

    observed_product_ids: set[str] = set()

    with PlayStationStoreClient() as client:
        for page_number in range(1, page_limit + 1):
            source_url, html = client.fetch_catalog_page(page_number)
            parsed = parse_catalog_page(html, source_url=source_url)

            catalog_result = ingest_catalog_page(
                sync_run=sync_run,
                page=parsed,
                seen_at=sync_now(),
            )
            if catalog_result.persisted_products:
                _increment_success(sync_run=sync_run, delta=catalog_result.persisted_products)
            observed_product_ids.update(catalog_result.observed_product_ids)

            for item in parsed.items:
                _run_snapshot_item(
                    client=client,
                    sync_run=sync_run,
                    item=item,
                    snapshot_date=snapshot_date,
                    fallback_source_url=source_url,
                )

    finalize_catalog_visibility(sync_run=sync_run, observed_product_ids=observed_product_ids)


def _run_snapshot_item(
    *,
    client: PlayStationStoreClient,
    sync_run: SyncRun,
    item,
    snapshot_date: date,
    fallback_source_url: str,
) -> None:
    source_url = fallback_source_url
    if item.concept_id:
        source_url = concept_url(item.concept_id)

    try:
        normalized_price = normalize_catalog_item_price(item)
        decision = choose_snapshot_source(item, normalized_price)

        if decision.source == "catalog" and item.product_ids:
            snapshot = ingest_catalog_snapshot(
                sync_run=sync_run,
                item=item,
                normalized_price=normalized_price,
                decision=decision,
                snapshot_date=snapshot_date,
                source_url=source_url,
            )
        else:
            concept_source_url, concept_html = client.fetch_concept(item.concept_id)
            source_url = concept_source_url
            detail = parse_product_detail(
                concept_html,
                concept_id=item.concept_id,
                catalog_price=item.price,
            )
            detail_normalized_price = normalize_product_detail_price(
                detail,
                source="concept_detail",
            )
            snapshot = ingest_product_detail_snapshot(
                sync_run=sync_run,
                detail=detail,
                normalized_price=detail_normalized_price,
                decision=decision,
                snapshot_date=snapshot_date,
                source_url=source_url,
            )

        if snapshot is not None:
            _increment_success(sync_run=sync_run, delta=1)
        return
    except Exception as exc:
        SyncError.objects.create(
            sync_run=sync_run,
            stage="snapshot_ingestion",
            product_id=_first_product_id(item),
            concept_id=item.concept_id,
            source_url=source_url,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        sync_run.error_count += 1
        sync_run.save(update_fields=["error_count", "updated_at"])


def _first_product_id(item) -> str | None:
    return item.product_ids[0] if item.product_ids else None


def _increment_success(*, sync_run: SyncRun, delta: int) -> None:
    sync_run.success_count += delta
    sync_run.save(update_fields=["success_count", "updated_at"])
