from dataclasses import dataclass

from ps_price_crawler.models import CatalogItem, PriceInfo
from ps_price_crawler.price_contract import NormalizedPrice, PriceState
from ps_price_crawler.source_strategy import choose_snapshot_source


def _catalog_item(*, product_ids: tuple[str, ...] = ("EP0001-PPSA00001_00-GAME000000000001",)) -> CatalogItem:
    return CatalogItem(
        concept_id="10002075",
        name="PRAGMATA",
        product_ids=product_ids,
        image_url="https://example.test/image.jpg",
        price=PriceInfo(
            base_price="NT$1,690",
            discounted_price="NT$1,690",
            discount_text=None,
            is_free=False,
            is_exclusive=False,
            is_tied_to_subscription=False,
        ),
    )


@dataclass(frozen=True)
class EnrichedCatalogItem:
    concept_id: str = "10002075"
    name: str = "PRAGMATA"
    product_ids: tuple[str, ...] = ("EP0001-PPSA00001_00-GAME000000000001",)
    image_url: str | None = "https://example.test/image.jpg"
    price: PriceInfo | None = None
    publisher_name: str | None = "Capcom"
    release_date: str | None = "2026-01-01"
    top_category: str | None = "GAME"


def _normalized_price(state: PriceState) -> NormalizedPrice:
    return NormalizedPrice(
        state=state,
        currency="TWD",
        base_amount_cents=169000,
        discounted_amount_cents=169000,
        plus_amount_cents=None,
        base_display="NT$1,690",
        discounted_display="NT$1,690",
        discount_text=None,
        service_branding=(),
        upsell_text=None,
        source="catalog",
        raw_missing_reason=None,
    )


def test_clear_catalog_price_states_use_catalog_snapshot_source():
    for state in (PriceState.FREE, PriceState.PAID, PriceState.DISCOUNTED):
        decision = choose_snapshot_source(_catalog_item(), _normalized_price(state))

        assert decision.source == "catalog"
        assert decision.reason == "catalog_price_snapshot"
        assert decision.reason_codes == ("clear_catalog_price", "product_ids_present")
        assert decision.normalized_state == state
        assert decision.product_ids == ("EP0001-PPSA00001_00-GAME000000000001",)
        assert decision.missing_metadata_fields == ()


def test_ambiguous_or_non_snapshot_catalog_states_fetch_concept_detail():
    expected_reason_codes = {
        PriceState.UNKNOWN: "price_state_unknown",
        PriceState.PS_PLUS: "price_state_ps_plus",
        PriceState.UNAVAILABLE: "price_state_unavailable",
        PriceState.NOT_PURCHASABLE: "price_state_not_purchasable",
    }

    for state, reason_code in expected_reason_codes.items():
        decision = choose_snapshot_source(_catalog_item(), _normalized_price(state))

        assert decision.source == "concept_detail"
        assert decision.reason == reason_code
        assert decision.reason_codes == (reason_code,)
        assert decision.normalized_state == state


def test_missing_product_ids_fetches_concept_detail_even_with_clear_price():
    decision = choose_snapshot_source(
        _catalog_item(product_ids=()),
        _normalized_price(PriceState.PAID),
    )

    assert decision.source == "concept_detail"
    assert decision.reason == "missing_product_ids"
    assert decision.reason_codes == ("missing_product_ids",)
    assert decision.product_ids == ()


def test_missing_future_django_metadata_fetches_concept_detail_when_metadata_is_applicable():
    item = EnrichedCatalogItem(
        publisher_name="",
        release_date=None,
        top_category="GAME",
    )

    decision = choose_snapshot_source(item, _normalized_price(PriceState.PAID))

    assert decision.source == "concept_detail"
    assert decision.reason == "missing_metadata"
    assert decision.reason_codes == ("missing_metadata",)
    assert decision.missing_metadata_fields == ("publisher_name", "release_date")


def test_complete_future_django_metadata_allows_catalog_snapshot_for_clear_price():
    item = EnrichedCatalogItem()

    decision = choose_snapshot_source(item, _normalized_price(PriceState.DISCOUNTED))

    assert decision.source == "catalog"
    assert decision.reason_codes == ("clear_catalog_price", "product_ids_present")
    assert decision.missing_metadata_fields == ()
