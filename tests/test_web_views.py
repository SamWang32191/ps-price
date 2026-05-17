from __future__ import annotations

from datetime import date
import re

import pytest
from django.urls import reverse

from ps_price_sync.models import PriceSnapshot, StoreProduct, SyncError, SyncRun
from ps_price_web.models import WatchedProduct


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
def test_product_detail_page_404_for_missing_product(client) -> None:
    response = client.get(reverse("ps_price_web:product_detail", kwargs={"product_id": "NOPE"}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_product_detail_page_renders_latest_price_and_regular_low(client) -> None:
    product = _web_product("P-DETAIL", "Detail Product")
    product.concept_name = "Detail Concept"
    product.publisher_name = "Publisher"
    product.save(update_fields=["concept_name", "publisher_name"])
    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 14),
        normalized_state="PAID",
        currency="TWD",
        base_amount_cents=120000,
        discounted_amount_cents=120000,
        base_display="NT$1,200",
        discounted_display="NT$1,200",
        source_strategy_source="catalog",
        source_strategy_reason="test",
    )
    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 15),
        normalized_state="PS_PLUS",
        currency="TWD",
        base_amount_cents=120000,
        discounted_amount_cents=20000,
        base_display="NT$1,200",
        discounted_display="NT$200",
        source_strategy_source="catalog",
        source_strategy_reason="test",
    )
    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 16),
        normalized_state="DISCOUNTED",
        currency="TWD",
        base_amount_cents=120000,
        discounted_amount_cents=70000,
        base_display="NT$1,200",
        discounted_display="NT$700",
        source_strategy_source="catalog",
        source_strategy_reason="test",
    )

    response = client.get(reverse("ps_price_web:product_detail", kwargs={"product_id": "P-DETAIL"}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Detail Product" in content
    assert "Detail Concept" in content
    assert "Publisher" in content
    assert "一般歷史最低價" in content
    assert "NT$700" in content
    assert "PS_PLUS" in content
    assert content.index("2026-05-16") < content.index("2026-05-15")


@pytest.mark.django_db
def test_product_detail_page_renders_product_without_snapshots(client) -> None:
    product = _web_product("P-NO-SNAPSHOTS", "No Snapshots")

    response = client.get(reverse("ps_price_web:product_detail", kwargs={"product_id": "P-NO-SNAPSHOTS"}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "No Snapshots" in content
    assert "尚無價格快照" in content


@pytest.mark.django_db
def test_product_detail_page_renders_zero_regular_low(client) -> None:
    product = _web_product("P-FREE-DEAL", "Free Deal")
    PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=date(2026, 5, 16),
        normalized_state="DISCOUNTED",
        currency="TWD",
        base_amount_cents=120000,
        discounted_amount_cents=0,
        base_display="NT$1,200",
        discounted_display="NT$0",
        source_strategy_source="catalog",
        source_strategy_reason="test",
    )

    response = client.get(reverse("ps_price_web:product_detail", kwargs={"product_id": "P-FREE-DEAL"}))
    content = response.content.decode()

    assert response.status_code == 200
    assert "一般歷史最低價：NT$0" in content


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
    WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    response = client.post(
        reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id}),
        {"action": "save_watch", "target_price": ""},
    )

    assert response.status_code == 302
    watched = WatchedProduct.objects.get(store_product=product)
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
@pytest.mark.parametrize("target_price", ["590.5", "0", "-1"])
def test_product_detail_post_rejects_invalid_target_price_without_redirect(client, target_price: str) -> None:
    product = _web_product("P-WATCH-INVALID", "Watch Invalid")

    response = client.post(
        reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id}),
        {"action": "save_watch", "target_price": target_price},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "target price 必須是正整數台幣元" in content
    assert not WatchedProduct.objects.filter(store_product=product).exists()


@pytest.mark.django_db
def test_product_detail_post_creates_empty_target_watch_when_none_exists(client) -> None:
    product = _web_product("P-WATCH-CREATE-EMPTY", "Watch Create Empty")

    response = client.post(
        reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id}),
        {"action": "save_watch", "target_price": ""},
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id})
    watched = WatchedProduct.objects.get(store_product=product)
    assert watched.target_price_cents is None


@pytest.mark.parametrize("target_price", ["590.5", "0", "-1"])
@pytest.mark.django_db
def test_product_detail_post_invalid_target_price_does_not_overwrite_existing_watch(
    client,
    target_price: str,
) -> None:
    product = _web_product("P-WATCH-INVALID-UPDATE", "Watch Invalid Update")
    WatchedProduct.objects.create(store_product=product, target_price_cents=59000)

    response = client.post(
        reverse("ps_price_web:product_detail", kwargs={"product_id": product.product_id}),
        {"action": "save_watch", "target_price": target_price},
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "target price 必須是正整數台幣元" in content
    watched = WatchedProduct.objects.get(store_product=product)
    assert watched.target_price_cents == 59000


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


@pytest.mark.django_db
def test_deals_page_renders_discounted_products(client) -> None:
    discounted = _web_product("P-DISCOUNT", "Discounted Product")
    plus = _web_product("P-PLUS", "Plus Product")
    _web_snapshot(discounted, state="DISCOUNTED", base_amount_cents=100000, discounted_amount_cents=50000)
    _web_snapshot(plus, state="PS_PLUS", base_amount_cents=100000, discounted_amount_cents=30000)

    response = client.get(reverse("ps_price_web:deals"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Discounted Product" in content
    assert "Plus Product" not in content
    assert "50%" in content
    assert "/products/P-DISCOUNT/" in content


@pytest.mark.django_db
def test_deals_page_applies_search_query(client) -> None:
    fantasy = _web_product("P-DEAL-1", "Final Fantasy")
    gran_turismo = _web_product("P-DEAL-2", "Gran Turismo")
    _web_snapshot(fantasy, state="DISCOUNTED")
    _web_snapshot(gran_turismo, state="DISCOUNTED")

    response = client.get(reverse("ps_price_web:deals"), {"q": "fantasy"})
    content = response.content.decode()

    assert response.status_code == 200
    assert "Final Fantasy" in content
    assert "Gran Turismo" not in content


@pytest.mark.django_db
def test_deals_page_empty_state(client) -> None:
    response = client.get(reverse("ps_price_web:deals"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "目前沒有一般折扣商品" in content


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
