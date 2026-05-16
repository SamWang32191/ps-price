from __future__ import annotations

from datetime import date
import re

import pytest
from django.urls import reverse

from ps_price_sync.models import PriceSnapshot, StoreProduct, SyncError, SyncRun


def _web_product(product_id: str = "P-web-1", name: str = "Web Game") -> StoreProduct:
    return StoreProduct.objects.create(product_id=product_id, product_name=name, is_visible=True, missing_count=0)


def _web_snapshot(
    product: StoreProduct,
    *,
    state: str = "DISCOUNTED",
    base_amount_cents: int = 200000,
    discounted_amount_cents: int | None = None,
    base_display: str | None = None,
    discounted_display: str | None = None,
) -> PriceSnapshot:
    if state == "PAID":
        if discounted_amount_cents is None:
            discounted_amount_cents = base_amount_cents
        if base_display is None:
            base_display = f"NT${base_amount_cents // 100:,}"
        if discounted_display is None:
            discounted_display = f"NT${discounted_amount_cents // 100:,}"
    elif state == "FREE":
        if base_display is None:
            base_display = "免費"
        if discounted_display is None:
            discounted_display = "免費"
        if discounted_amount_cents is None:
            discounted_amount_cents = 0
        base_amount_cents = 0
    else:
        if base_display is None:
            base_display = "NT$2,000"
        if discounted_display is None:
            discounted_display = "NT$1,200"
        if discounted_amount_cents is None:
            discounted_amount_cents = 120000

    if discounted_amount_cents is None:
        discounted_amount_cents = base_amount_cents

    return PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 16),
        normalized_state=state,
        currency="TWD",
        base_amount_cents=base_amount_cents,
        discounted_amount_cents=discounted_amount_cents,
        base_display=base_display,
        discounted_display=discounted_display,
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
def test_dashboard_shows_zero_counts_but_unknown_last_page_mark(client) -> None:
    product = _web_product(product_id="P-web-2", name="Zero Summary Game")
    _web_snapshot(product)
    run = SyncRun.objects.create(
        sync_type="catalog_and_snapshot",
        status="partial",
        success_count=5,
        error_count=0,
        summary='{"pages_fetched": 0, "catalog_total_count": 0}',
    )
    SyncError.objects.create(
        sync_run=run,
        stage="catalog_fetch",
        product_id=None,
        error_type="TransientError",
        error_message="temporary issue",
    )

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert re.search(r"抓取頁數</div>\s*<div>\s*0\s*</div>", content) is not None
    assert re.search(r"Catalog 總數</div>\s*<div>\s*0\s*</div>", content) is not None
    assert "catalog_and_snapshot" in content
    assert re.search(r"已到達最後頁</div>\s*<div>\s*-\s*</div>", content) is not None


@pytest.mark.django_db
def test_product_list_route_renders_empty_state(client) -> None:
    response = client.get(reverse("product-list"))

    assert response.status_code == 200
    assert "商品查詢" in response.content.decode()
    assert "目前沒有符合條件的商品" in response.content.decode()


@pytest.mark.django_db
def test_product_list_renders_products_and_filter_form(client) -> None:
    product = _web_product("P-list-1", "List Game")
    _web_snapshot(product, state="DISCOUNTED")

    response = client.get(reverse("product-list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "List Game" in content
    assert "NT$1,200" in content
    assert "DISCOUNTED" in content
    assert 'name="q"' in content
    assert 'name="sale"' in content
    assert reverse("product-detail", kwargs={"product_id": "P-list-1"}) in content


@pytest.mark.django_db
def test_product_list_applies_query_and_sale_filter(client) -> None:
    discounted = _web_product("P-list-2", "Discount Match")
    paid = _web_product("P-list-3", "Full Price Match")
    _web_snapshot(discounted, state="DISCOUNTED")
    _web_snapshot(paid, state="PAID")

    response = client.get(reverse("product-list"), {"q": "Match", "sale": "1"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "Discount Match" in content
    assert "Full Price Match" not in content
    assert 'value="Match"' in content
    assert 'name="sale" value="1" checked' in content


@pytest.mark.django_db
def test_product_list_renders_visibility_and_category_filters(client) -> None:
    product = _web_product("P-list-4", "Category Game")
    product.top_category = "RPG"
    product.save(update_fields=["top_category"])
    _web_snapshot(product)

    response = client.get(reverse("product-list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'name="visibility"' in content
    assert 'name="top_category"' in content
    assert 'value="RPG"' in content


@pytest.mark.django_db
def test_product_list_renders_zero_price(client) -> None:
    product = _web_product("P-list-5", "Zero Price")
    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 16),
        normalized_state="DISCOUNTED",
        currency="TWD",
        base_amount_cents=0,
        discounted_amount_cents=None,
        plus_amount_cents=None,
        base_display=None,
        discounted_display=None,
        source_strategy_source="catalog",
        source_strategy_reason="test",
    )

    response = client.get(reverse("product-list"), {"q": "Zero"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "NT$0" in content


@pytest.mark.django_db
def test_product_detail_returns_404_for_unknown_product(client) -> None:
    response = client.get(reverse("product-detail", kwargs={"product_id": "missing-product"}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_product_detail_renders_current_price_lows_chart_and_snapshot_table(client) -> None:
    product = _web_product("P-detail-1", "Detail Game")
    product.concept_id = "C-detail-1"
    product.publisher_name = "Detail Studio"
    product.release_date_raw = "2026-01-01"
    product.top_category = "RPG"
    product.source_url = "https://example.com/detail-game"
    product.save(
        update_fields=[
            "concept_id",
            "publisher_name",
            "release_date_raw",
            "top_category",
            "source_url",
        ]
    )
    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 14),
        normalized_state="PAID",
        currency="TWD",
        base_amount_cents=200000,
        discounted_amount_cents=200000,
        base_display="NT$2,000",
        discounted_display="NT$2,000",
        source_strategy_source="catalog",
        source_strategy_reason="test",
    )
    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 13),
        normalized_state="FREE",
        currency="TWD",
        base_amount_cents=0,
        discounted_amount_cents=0,
        base_display="NT$0",
        discounted_display="NT$0",
        source_strategy_source="catalog",
        source_strategy_reason="test",
    )
    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 15),
        normalized_state="DISCOUNTED",
        currency="TWD",
        base_amount_cents=200000,
        discounted_amount_cents=120000,
        base_display="NT$2,000",
        discounted_display="NT$1,200",
        discount_text="限時優惠",
        source_strategy_source="catalog",
        source_strategy_reason="test",
    )
    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 16),
        normalized_state="PS_PLUS",
        currency="TWD",
        base_amount_cents=200000,
        discounted_amount_cents=90000,
        plus_amount_cents=90000,
        base_display="NT$2,000",
        discounted_display="NT$900",
        source_strategy_source="concept_detail",
        source_strategy_reason="price_state_ps_plus",
    )

    response = client.get(reverse("product-detail", kwargs={"product_id": "P-detail-1"}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Detail Game" in content
    assert "P-detail-1" in content
    assert "C-detail-1" in content
    assert "Detail Studio" in content
    assert "RPG" in content
    assert "2026-01-01" in content
    assert 'https://example.com/detail-game' in content
    assert "一般歷史低價" in content
    assert "NT$1,200" in content
    assert "PS Plus 歷史低價" in content
    assert "NT$900" in content
    assert "<svg" in content
    assert "每日價格紀錄" in content
    assert "限時優惠" in content
    assert "NT$0" in content


def test_twd_cents_template_filter_formats_integer_cents() -> None:
    from ps_price_sync.templatetags.price_format import twd_cents

    assert twd_cents(120000) == "NT$1,200"
    assert twd_cents(0) == "NT$0"
    assert twd_cents(None) == "-"


def test_snapshot_price_display_prefers_display_text_over_cents() -> None:
    from ps_price_sync.templatetags.price_format import snapshot_price_display
    from ps_price_sync.models import PriceSnapshot

    snapshot = PriceSnapshot(
        base_amount_cents=0,
        discounted_amount_cents=120000,
        base_display="免費",
        discounted_display="NT$999",
    )

    assert snapshot_price_display(snapshot) == "NT$999"
