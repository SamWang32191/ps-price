from __future__ import annotations

from datetime import date

from ps_price_web.formatting import format_money_twd, format_raw_json_list
import pytest

from ps_price_sync.models import PriceSnapshot, StoreProduct
from ps_price_web.models import WatchedProduct
from ps_price_web.queries import WatchStatus, get_latest_deals, get_product_detail, get_watchlist_rows


def create_product(
    product_id: str, name: str, *, concept_name: str = "", is_visible: bool | None = True
) -> StoreProduct:
    return StoreProduct.objects.create(
        product_id=product_id,
        product_name=name,
        concept_name=concept_name,
        is_visible=is_visible,
    )


def create_snapshot(
    product: StoreProduct,
    snapshot_date: date,
    state: str,
    *,
    base: int | None = None,
    discounted: int | None = None,
) -> PriceSnapshot:
    return PriceSnapshot.objects.create(
        store_product=product,
        snapshot_date=snapshot_date,
        normalized_state=state,
        base_amount_cents=base,
        discounted_amount_cents=discounted,
        source_strategy_source="catalog",
        source_strategy_reason="catalog_price",
    )


def watch(product: StoreProduct, target: int | None) -> WatchedProduct:
    return WatchedProduct.objects.create(store_product=product, target_price_cents=target)


def test_format_money_twd_formats_integer_cents() -> None:
    assert format_money_twd(59000, "NT$590") == "NT$590"
    assert format_money_twd(0, "Free") == "NT$0"


def test_format_money_twd_falls_back_to_display_text() -> None:
    assert format_money_twd(None, "NT$1,490") == "NT$1,490"
    assert format_money_twd(None, None) == "-"


def test_format_raw_json_list_formats_json_arrays() -> None:
    assert format_raw_json_list("[\"PS5\", \"PS4\"]") == "PS5, PS4"
    assert format_raw_json_list("[]") == "-"


def test_format_raw_json_list_falls_back_to_raw_text() -> None:
    assert format_raw_json_list("not-json") == "not-json"
    assert format_raw_json_list("") == "-"


@pytest.mark.django_db
def test_get_latest_deals_only_returns_discounted_latest_snapshots() -> None:
    discounted = create_product("P-DISCOUNT", "Discounted")
    paid = create_product("P-PAID", "Paid")
    plus = create_product("P-PLUS", "Plus")
    hidden = create_product("P-HIDDEN", "Hidden", is_visible=False)

    create_snapshot(discounted, date(2026, 5, 15), "PAID", base=100000)
    create_snapshot(discounted, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=50000)
    create_snapshot(paid, date(2026, 5, 16), "PAID", base=90000)
    create_snapshot(plus, date(2026, 5, 16), "PS_PLUS", base=90000, discounted=60000)
    create_snapshot(hidden, date(2026, 5, 16), "DISCOUNTED", base=90000, discounted=30000)

    deals = get_latest_deals()

    assert [deal.product.product_id for deal in deals] == ["P-DISCOUNT"]
    assert deals[0].snapshot.normalized_state == "DISCOUNTED"
    assert deals[0].discount_percent == 50


@pytest.mark.django_db
def test_get_latest_deals_sorts_by_discount_percent_descending() -> None:
    lower = create_product("P-LOWER", "Lower")
    higher = create_product("P-HIGHER", "Higher")

    create_snapshot(lower, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=75000)
    create_snapshot(higher, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=40000)

    deals = get_latest_deals()

    assert [deal.product.product_id for deal in deals] == ["P-HIGHER", "P-LOWER"]
    assert [deal.discount_percent for deal in deals] == [60, 25]


@pytest.mark.django_db
def test_get_latest_deals_searches_product_and_concept_name() -> None:
    product_match = create_product("P-PRODUCT", "Final Fantasy")
    concept_match = create_product("P-CONCEPT", "Some Edition", concept_name="Monster Hunter")
    miss = create_product("P-MISS", "Gran Turismo")

    create_snapshot(product_match, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=60000)
    create_snapshot(concept_match, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=50000)
    create_snapshot(miss, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=40000)

    assert [deal.product.product_id for deal in get_latest_deals(query="fantasy")] == ["P-PRODUCT"]
    assert [deal.product.product_id for deal in get_latest_deals(query="hunter")] == ["P-CONCEPT"]


@pytest.mark.django_db
def test_get_product_detail_returns_latest_snapshot_and_regular_historical_low() -> None:
    product = create_product("P-DETAIL", "Detail")

    create_snapshot(product, date(2026, 5, 14), "PAID", base=120000)
    create_snapshot(product, date(2026, 5, 15), "PS_PLUS", base=120000, discounted=20000)
    create_snapshot(product, date(2026, 5, 16), "DISCOUNTED", base=120000, discounted=70000)

    detail = get_product_detail("P-DETAIL")

    assert detail.product.product_id == "P-DETAIL"
    assert detail.latest_snapshot.snapshot_date == date(2026, 5, 16)
    assert detail.current_price_amount_cents == 70000
    assert detail.current_price_display is None
    assert detail.regular_low_amount_cents == 70000
    assert detail.regular_low_date == date(2026, 5, 16)
    assert [snapshot.snapshot_date for snapshot in detail.snapshots] == [
        date(2026, 5, 16),
        date(2026, 5, 15),
        date(2026, 5, 14),
    ]


@pytest.mark.django_db
def test_get_product_detail_regular_low_ignores_free_and_unavailable_states() -> None:
    product = create_product("P-REGULAR-LOW", "Regular Low")

    create_snapshot(product, date(2026, 5, 14), "FREE", base=0)
    create_snapshot(product, date(2026, 5, 15), "UNKNOWN", base=100000, discounted=50000)
    create_snapshot(product, date(2026, 5, 16), "PAID", base=90000)

    detail = get_product_detail("P-REGULAR-LOW")

    assert detail.regular_low_amount_cents == 90000
    assert detail.regular_low_date == date(2026, 5, 16)


@pytest.mark.django_db
def test_get_product_detail_handles_product_without_snapshots() -> None:
    product = create_product("P-NO-SNAPSHOT", "No Snapshot")

    detail = get_product_detail("P-NO-SNAPSHOT")

    assert detail.latest_snapshot is None
    assert detail.regular_low_amount_cents is None
    assert detail.regular_low_date is None
    assert detail.snapshots == []


@pytest.mark.django_db
def test_get_watchlist_rows_marks_discounted_product_as_reached() -> None:
    product = create_product("P-WATCH-REACHED", "Reached")
    create_snapshot(product, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=50000)
    watch(product, 59000)

    rows = get_watchlist_rows()

    assert [(row.product.product_id, row.status) for row in rows] == [("P-WATCH-REACHED", WatchStatus.REACHED)]
    assert rows[0].general_purchase_price_cents == 50000


@pytest.mark.django_db
def test_get_watchlist_rows_marks_paid_product_as_not_reached() -> None:
    product = create_product("P-WATCH-NOT-REACHED", "Not Reached")
    create_snapshot(product, date(2026, 5, 16), "PAID", base=90000)
    watch(product, 59000)

    rows = get_watchlist_rows()

    assert rows[0].status == WatchStatus.NOT_REACHED
    assert rows[0].general_purchase_price_cents == 90000


@pytest.mark.django_db
def test_get_watchlist_rows_excludes_ps_plus_and_free_from_general_purchase_price() -> None:
    plus = create_product("P-WATCH-PLUS", "Plus")
    free = create_product("P-WATCH-FREE", "Free")
    create_snapshot(plus, date(2026, 5, 16), "PS_PLUS", base=90000, discounted=10000)
    create_snapshot(free, date(2026, 5, 16), "FREE", base=0, discounted=0)
    watch(plus, 59000)
    watch(free, 59000)

    rows = get_watchlist_rows()

    assert [(row.product.product_id, row.status, row.general_purchase_price_cents) for row in rows] == [
        ("P-WATCH-FREE", WatchStatus.NO_GENERAL_PURCHASE_PRICE, None),
        ("P-WATCH-PLUS", WatchStatus.NO_GENERAL_PURCHASE_PRICE, None),
    ]


@pytest.mark.django_db
def test_get_watchlist_rows_keeps_hidden_products_and_sorts_by_status_then_name() -> None:
    reached = create_product("P-SORT-REACHED", "B Reached", is_visible=False)
    not_reached = create_product("P-SORT-NOT", "A Not Reached")
    no_target = create_product("P-SORT-NO-TARGET", "A No Target")
    no_price = create_product("P-SORT-NO-PRICE", "A No Price")
    create_snapshot(reached, date(2026, 5, 16), "DISCOUNTED", base=100000, discounted=50000)
    create_snapshot(not_reached, date(2026, 5, 16), "PAID", base=90000)
    create_snapshot(no_target, date(2026, 5, 16), "PAID", base=90000)
    create_snapshot(no_price, date(2026, 5, 16), "UNKNOWN", base=None)
    watch(reached, 59000)
    watch(not_reached, 59000)
    watch(no_target, None)
    watch(no_price, 59000)

    rows = get_watchlist_rows()

    assert [(row.product.product_id, row.status) for row in rows] == [
        ("P-SORT-REACHED", WatchStatus.REACHED),
        ("P-SORT-NOT", WatchStatus.NOT_REACHED),
        ("P-SORT-NO-TARGET", WatchStatus.NO_TARGET_PRICE),
        ("P-SORT-NO-PRICE", WatchStatus.NO_GENERAL_PURCHASE_PRICE),
    ]


@pytest.mark.django_db
def test_get_watchlist_rows_sorts_by_product_id_when_status_and_name_are_same() -> None:
    same_name_a = create_product("P-SORT-ID-B", "Same Name")
    same_name_b = create_product("P-SORT-ID-A", "Same Name")
    create_snapshot(same_name_a, date(2026, 5, 16), "PAID", base=90000)
    create_snapshot(same_name_b, date(2026, 5, 16), "PAID", base=90000)
    watch(same_name_a, 59000)
    watch(same_name_b, 59000)

    rows = get_watchlist_rows()

    assert [row.product.product_id for row in rows[:2]] == ["P-SORT-ID-A", "P-SORT-ID-B"]
