from __future__ import annotations

from datetime import date
import json

import pytest
from django.db.utils import IntegrityError

from ps_price_sync.models import PriceSnapshot, StoreProduct, SyncError, SyncRun


@pytest.mark.django_db
def test_product_id_is_unique() -> None:
    StoreProduct.objects.create(product_id="P-100", product_name="Product 100")

    with pytest.raises(IntegrityError):
        StoreProduct.objects.create(product_id="P-100", product_name="Product 100 duplicate")


@pytest.mark.django_db
def test_price_snapshot_is_unique_per_product_and_date() -> None:
    product = StoreProduct.objects.create(product_id="P-200", product_name="Product 200")

    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 16),
        normalized_state="active",
        source_strategy_source="http",
        source_strategy_reason="default",
    )

    with pytest.raises(IntegrityError):
        PriceSnapshot.objects.create(
            store_product=product,
            snapshot_date=date(2026, 5, 16),
            normalized_state="active",
            source_strategy_source="http",
            source_strategy_reason="default",
        )


@pytest.mark.django_db
def test_sync_run_summary_defaults_to_json_text() -> None:
    run = SyncRun.objects.create(sync_type="catalog_only", status="running")

    assert json.loads(run.summary) == {}


@pytest.mark.django_db
def test_sync_error_allows_repeated_product_id_across_runs() -> None:
    run_one = SyncRun.objects.create(sync_type="catalog_only", status="failed")
    run_two = SyncRun.objects.create(sync_type="catalog_only", status="failed")

    SyncError.objects.create(
        sync_run=run_one,
        stage="catalog_ingestion",
        product_id="P-300",
        error_type="MissingProductId",
        error_message="first failure",
    )
    SyncError.objects.create(
        sync_run=run_two,
        stage="catalog_ingestion",
        product_id="P-300",
        error_type="MissingProductId",
        error_message="second failure",
    )

    assert SyncError.objects.filter(product_id="P-300").count() == 2
