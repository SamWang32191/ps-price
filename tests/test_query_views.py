from __future__ import annotations

from datetime import date

import pytest

from ps_price_sync.models import PriceSnapshot, StoreProduct, SyncError, SyncRun


def _product(product_id: str = "P-100", name: str = "Game 100") -> StoreProduct:
    return StoreProduct.objects.create(product_id=product_id, product_name=name, is_visible=True, missing_count=0)


def _snapshot(
    product: StoreProduct,
    *,
    snapshot_date: date,
    state: str,
    base: int | None = None,
    discounted: int | None = None,
    plus: int | None = None,
) -> PriceSnapshot:
    return PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=snapshot_date,
        normalized_state=state,
        currency="TWD",
        base_amount_cents=base,
        discounted_amount_cents=discounted,
        plus_amount_cents=plus,
        base_display=f"NT${base // 100:,}" if base is not None else None,
        discounted_display=f"NT${discounted // 100:,}" if discounted is not None else None,
        source_strategy_source="catalog",
        source_strategy_reason="test",
    )


@pytest.mark.django_db
def test_get_current_snapshot_prefers_latest_snapshot_date() -> None:
    product = _product()
    older = _snapshot(product, snapshot_date=date(2026, 5, 15), state="PAID", base=200000, discounted=200000)
    newer = _snapshot(product, snapshot_date=date(2026, 5, 16), state="DISCOUNTED", base=200000, discounted=150000)

    from ps_price_sync.services.query_views import get_current_snapshot

    assert get_current_snapshot(product).id == newer.id
    assert get_current_snapshot(StoreProduct.objects.create(product_id="P-empty", product_name="Empty")) is None
    assert older.id != newer.id


@pytest.mark.django_db
def test_calculate_price_summary_separates_general_and_plus_lows() -> None:
    product = _product()
    _snapshot(product, snapshot_date=date(2026, 5, 14), state="PAID", base=200000, discounted=200000)
    _snapshot(product, snapshot_date=date(2026, 5, 15), state="DISCOUNTED", base=200000, discounted=120000)
    _snapshot(product, snapshot_date=date(2026, 5, 16), state="FREE", base=0, discounted=0)
    _snapshot(product, snapshot_date=date(2026, 5, 17), state="PS_PLUS", base=200000, discounted=90000, plus=90000)

    from ps_price_sync.services.query_views import calculate_price_summary

    summary = calculate_price_summary(product)

    assert summary.current_snapshot.snapshot_date == date(2026, 5, 17)
    assert summary.general_low_amount_cents == 120000
    assert summary.general_low_date == date(2026, 5, 15)
    assert summary.plus_low_amount_cents == 90000
    assert summary.plus_low_date == date(2026, 5, 17)
    assert summary.is_current_discounted is False


@pytest.mark.django_db
def test_list_products_applies_search_state_discount_visibility_and_category_filters() -> None:
    visible_discount = _product("P-1", "Discount Game")
    visible_discount.top_category = "GAME"
    visible_discount.save(update_fields=["top_category"])
    hidden_paid = StoreProduct.objects.create(product_id="P-2", product_name="Hidden Game", is_visible=False, top_category="GAME")
    visible_plus = StoreProduct.objects.create(product_id="P-3", product_name="Plus Pack", is_visible=True, top_category="ADD_ON")
    _snapshot(visible_discount, snapshot_date=date(2026, 5, 16), state="DISCOUNTED", base=200000, discounted=120000)
    _snapshot(hidden_paid, snapshot_date=date(2026, 5, 16), state="PAID", base=300000, discounted=300000)
    _snapshot(visible_plus, snapshot_date=date(2026, 5, 16), state="PS_PLUS", base=300000, discounted=200000, plus=200000)

    from ps_price_sync.services.query_views import ProductListFilters, list_products

    result = list_products(
        ProductListFilters(
            query="discount",
            state="DISCOUNTED",
            sale_only=True,
            visibility="visible",
            top_category="GAME",
            page=1,
            page_size=50,
        )
    )

    assert result.total_count == 1
    assert [row.product.product_id for row in result.products] == ["P-1"]
    assert result.products[0].price_summary.is_current_discounted is True


@pytest.mark.django_db
def test_get_dashboard_summary_reads_latest_sync_run_and_counts() -> None:
    product = _product("P-1", "Discount Game")
    _snapshot(product, snapshot_date=date(2026, 5, 16), state="DISCOUNTED", base=200000, discounted=120000)
    sync_run = SyncRun.objects.create(
        sync_type="catalog_and_snapshot",
        status="partial",
        success_count=10,
        error_count=1,
        summary='{"pages_fetched": 3, "last_page_reached": true, "catalog_total_count": 72}',
    )
    SyncError.objects.create(
        sync_run=sync_run,
        stage="snapshot_ingestion",
        product_id="P-err",
        error_type="ParserError",
        error_message="bad source",
    )

    from ps_price_sync.services.query_views import get_dashboard_summary

    summary = get_dashboard_summary()

    assert summary.total_products == 1
    assert summary.visible_products == 1
    assert summary.current_discounted_products == 1
    assert summary.latest_snapshot_date == date(2026, 5, 16)
    assert summary.latest_sync_run.id == sync_run.id
    assert summary.latest_sync_summary["pages_fetched"] == 3
    assert summary.recent_errors[0].error_type == "ParserError"


def test_normalize_filters_parses_page_and_page_size() -> None:
    from ps_price_sync.services.query_views import ProductListFilters, normalize_filters

    filters = normalize_filters(
        {
            "q": "game",
            "state": "PAID",
            "sale": "1",
            "visibility": "visible",
            "top_category": "GAME",
            "page": "3",
            "page_size": "25",
        }
    )

    assert filters == ProductListFilters(
        query="game",
        state="PAID",
        sale_only=True,
        visibility="visible",
        top_category="GAME",
        page=3,
        page_size=25,
    )


def test_normalize_filters_clamps_invalid_pagination_values() -> None:
    from ps_price_sync.services.query_views import ProductListFilters, normalize_filters

    filters = normalize_filters(
        {
            "page": "0",
            "page_size": "0",
        }
    )
    assert filters == ProductListFilters(page=1, page_size=1)

    filters = normalize_filters(
        {
            "page": "-5",
            "page_size": "abc",
        }
    )
    assert filters == ProductListFilters(page=1, page_size=50)

    filters = normalize_filters(
        {
            "page": "2",
            "page_size": "200",
        }
    )
    assert filters == ProductListFilters(page=2, page_size=100)


@pytest.mark.django_db
def test_list_products_state_options_only_include_current_states() -> None:
    _product("P-1", "Game 1")
    _product("P-2", "Game 2")
    _product("P-3", "Game 3")

    from ps_price_sync.services.query_views import ProductListFilters, list_products

    p1 = StoreProduct.objects.get(product_id="P-1")
    p2 = StoreProduct.objects.get(product_id="P-2")
    p3 = StoreProduct.objects.get(product_id="P-3")

    _snapshot(p1, snapshot_date=date(2026, 5, 14), state="PAID", base=200000, discounted=200000)
    _snapshot(p1, snapshot_date=date(2026, 5, 15), state="DISCOUNTED", base=200000, discounted=150000)
    _snapshot(p2, snapshot_date=date(2026, 5, 16), state="PAID", base=200000, discounted=130000)
    _snapshot(p3, snapshot_date=date(2026, 5, 14), state="FREE", base=300000, discounted=300000)
    _snapshot(p3, snapshot_date=date(2026, 5, 16), state="PAID", base=220000, discounted=220000)

    result = list_products(ProductListFilters())

    assert "FREE" not in result.state_options
    assert set(result.state_options) == {"DISCOUNTED", "PAID"}


@pytest.mark.django_db
def test_list_products_does_not_n_plus_one(django_assert_num_queries) -> None:
    for index in range(1, 4):
        product = _product(f"P-{index}", f"Game {index}")
        _snapshot(product, snapshot_date=date(2026, 5, 16), state="PAID", base=200000, discounted=150000)
        _snapshot(product, snapshot_date=date(2026, 5, 17), state="DISCOUNTED", base=180000, discounted=120000)

    from ps_price_sync.services.query_views import ProductListFilters, list_products

    with django_assert_num_queries(4):
        result = list_products(ProductListFilters(page=1, page_size=50))

    assert result.total_count == 3


@pytest.mark.django_db
def test_build_chart_points_uses_only_general_numeric_prices() -> None:
    product = _product()
    paid = _snapshot(product, snapshot_date=date(2026, 5, 14), state="PAID", base=200000, discounted=200000)
    discounted = _snapshot(product, snapshot_date=date(2026, 5, 15), state="DISCOUNTED", base=200000, discounted=100000)
    _snapshot(product, snapshot_date=date(2026, 5, 16), state="PS_PLUS", base=200000, discounted=90000, plus=90000)

    from ps_price_sync.services.query_views import build_chart_points

    points = build_chart_points([paid, discounted])

    assert len(points) == 2
    assert points[0].snapshot_date == date(2026, 5, 14)
    assert points[0].amount_cents == 200000
    assert points[1].snapshot_date == date(2026, 5, 15)
    assert points[1].amount_cents == 100000
