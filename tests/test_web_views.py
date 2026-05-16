from __future__ import annotations

from datetime import date

import pytest
from django.urls import reverse

from ps_price_sync.models import PriceSnapshot, StoreProduct, SyncError, SyncRun


def _web_product(product_id: str = "P-web-1", name: str = "Web Game") -> StoreProduct:
    return StoreProduct.objects.create(product_id=product_id, product_name=name, is_visible=True, missing_count=0)


def _web_snapshot(product: StoreProduct, *, state: str = "DISCOUNTED") -> PriceSnapshot:
    return PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 16),
        normalized_state=state,
        currency="TWD",
        base_amount_cents=200000,
        discounted_amount_cents=120000,
        base_display="NT$2,000",
        discounted_display="NT$1,200",
        source_strategy_source="catalog",
        source_strategy_reason="test",
    )


@pytest.mark.django_db
def test_dashboard_route_renders_empty_state(client) -> None:
    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert "PS Price" in response.content.decode()
    assert "尚無同步紀錄" in response.content.decode()


@pytest.mark.django_db
def test_dashboard_renders_sync_and_price_summary(client) -> None:
    product = _web_product()
    _web_snapshot(product)
    run = SyncRun.objects.create(
        sync_type="catalog_and_snapshot",
        status="partial",
        success_count=10,
        error_count=1,
        summary='{"pages_fetched": 3, "last_page_reached": true, "catalog_total_count": 72}',
    )
    SyncError.objects.create(
        sync_run=run,
        stage="snapshot_ingestion",
        product_id="P-web-error",
        error_type="ParserError",
        error_message="bad source",
    )

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "商品總數" in content
    assert "目前特價" in content
    assert "2026-05-16" in content
    assert "catalog_and_snapshot" in content
    assert "ParserError" in content
    assert "3" in content


@pytest.mark.django_db
def test_product_list_route_renders_empty_state(client) -> None:
    response = client.get(reverse("product-list"))

    assert response.status_code == 200
    assert "商品查詢" in response.content.decode()
    assert "目前沒有符合條件的商品" in response.content.decode()


@pytest.mark.django_db
def test_product_detail_returns_404_for_unknown_product(client) -> None:
    response = client.get(reverse("product-detail", kwargs={"product_id": "missing-product"}))

    assert response.status_code == 404
