from ps_price_crawler.models import PriceInfo
from ps_price_crawler.price_contract import NormalizedPrice, PriceState, normalize_price_info


def _price_info(
    *,
    base_price: str | None = None,
    discounted_price: str | None = None,
    discount_text: str | None = None,
    is_free: bool = False,
    is_exclusive: bool = False,
    is_tied_to_subscription: bool = False,
    service_branding: tuple[str, ...] = (),
    upsell_text: str | None = None,
) -> PriceInfo:
    return PriceInfo(
        base_price=base_price,
        discounted_price=discounted_price,
        discount_text=discount_text,
        is_free=is_free,
        is_exclusive=is_exclusive,
        is_tied_to_subscription=is_tied_to_subscription,
        service_branding=service_branding,
        upsell_text=upsell_text,
    )


def _assert_twd_price(normalized: NormalizedPrice, cents: int):
    assert normalized.currency == "TWD"
    assert normalized.base_amount_cents == cents
    assert normalized.discounted_amount_cents == cents


def test_missing_raw_price_returns_unknown_with_reason():
    normalized = normalize_price_info(
        None,
        source="catalog",
        raw_missing_reason="Price block missing from API payload",
    )

    assert normalized.state == PriceState.UNKNOWN
    assert normalized.source == "catalog"
    assert normalized.raw_missing_reason == "Price block missing from API payload"
    assert normalized.base_display is None
    assert normalized.discounted_display is None


def test_free_price_from_chinese_free_text():
    normalized = normalize_price_info(
        _price_info(base_price="免費", discounted_price="免費", is_free=True),
        source="catalog",
    )

    assert normalized.state == PriceState.FREE
    assert normalized.base_display == "免費"
    assert normalized.discounted_display == "免費"
    assert normalized.base_amount_cents == 0
    assert normalized.discounted_amount_cents == 0
    assert normalized.discount_text is None
    _assert_twd_price(normalized, 0)


def test_paid_price_keeps_twd_text_display_and_parsed_amounts():
    normalized = normalize_price_info(
        _price_info(base_price="NT$1,990", discounted_price="NT$1,990"),
        source="catalog",
    )

    assert normalized.state == PriceState.PAID
    assert normalized.base_display == "NT$1,990"
    assert normalized.discounted_display == "NT$1,990"
    assert normalized.base_amount_cents == 199000
    assert normalized.discounted_amount_cents == 199000


def test_discounted_price_detected_by_price_delta():
    normalized = normalize_price_info(
        _price_info(
            base_price="NT$1,990",
            discounted_price="NT$1,690",
            discount_text="限時折扣",
        ),
        source="catalog",
    )

    assert normalized.state == PriceState.DISCOUNTED
    assert normalized.base_display == "NT$1,990"
    assert normalized.discounted_display == "NT$1,690"
    assert normalized.base_amount_cents == 199000
    assert normalized.discounted_amount_cents == 169000
    assert normalized.discount_text == "限時折扣"


def test_discounted_price_detected_by_discount_text_even_with_equal_prices():
    normalized = normalize_price_info(
        _price_info(
            base_price="NT$1,690",
            discounted_price="NT$1,690",
            discount_text="買一送一",
        ),
        source="product",
    )

    assert normalized.state == PriceState.DISCOUNTED
    assert normalized.discount_text == "買一送一"
    assert normalized.base_amount_cents == 169000
    assert normalized.discounted_amount_cents == 169000


def test_ps_plus_detected_from_tied_to_subscription():
    normalized = normalize_price_info(
        _price_info(
            base_price="NT$0",
            discounted_price="NT$0",
            is_tied_to_subscription=True,
        ),
        source="catalog",
    )

    assert normalized.state == PriceState.PS_PLUS
    assert normalized.base_display == "NT$0"
    assert normalized.discounted_display == "NT$0"
    assert normalized.base_amount_cents == 0


def test_ps_plus_detected_from_exclusive_flag():
    normalized = normalize_price_info(
        _price_info(
            base_price="NT$1,990",
            discounted_price="NT$1,990",
            is_exclusive=True,
        ),
        source="catalog",
    )

    assert normalized.state == PriceState.PS_PLUS


def test_ps_plus_detected_from_service_branding():
    normalized = normalize_price_info(
        _price_info(
            base_price="NT$0",
            discounted_price="NT$0",
            service_branding=("PLAYSTATION_PLUS",),
        ),
        source="product",
    )

    assert normalized.state == PriceState.PS_PLUS


def test_ps_plus_detected_from_upsell_text():
    normalized = normalize_price_info(
        _price_info(
            base_price="NT$1,690",
            discounted_price="NT$1,690",
            upsell_text="加入 PlayStation Plus 即可享優惠",
        ),
        source="product",
    )

    assert normalized.state == PriceState.PS_PLUS


def test_unavailable_state_from_unavailable_price_display():
    normalized = normalize_price_info(
        _price_info(
            base_price="暫無售價",
            discounted_price="暫無售價",
        ),
        source="catalog",
    )

    assert normalized.state == PriceState.UNAVAILABLE


def test_not_purchasable_state_from_unpurchasable_display():
    normalized = normalize_price_info(
        _price_info(
            base_price="不可購買",
            discounted_price="不可購買",
        ),
        source="catalog",
    )

    assert normalized.state == PriceState.NOT_PURCHASABLE
