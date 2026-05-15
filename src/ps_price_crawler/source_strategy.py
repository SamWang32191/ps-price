from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ps_price_crawler.models import CatalogItem
from ps_price_crawler.price_contract import NormalizedPrice, PriceState


SnapshotSource = Literal["catalog", "concept_detail"]

CATALOG_SNAPSHOT_STATES = frozenset({PriceState.FREE, PriceState.PAID, PriceState.DISCOUNTED})
CONCEPT_DETAIL_STATES = frozenset(
    {
        PriceState.UNKNOWN,
        PriceState.PS_PLUS,
        PriceState.UNAVAILABLE,
        PriceState.NOT_PURCHASABLE,
    }
)
FUTURE_METADATA_FIELDS = ("publisher_name", "release_date", "top_category")


@dataclass(frozen=True)
class SnapshotSourceDecision:
    source: SnapshotSource
    reason: str
    reason_codes: tuple[str, ...]
    normalized_state: PriceState
    product_ids: tuple[str, ...]
    missing_metadata_fields: tuple[str, ...] = ()


def choose_snapshot_source(
    catalog_item: CatalogItem,
    normalized_price: NormalizedPrice,
) -> SnapshotSourceDecision:
    product_ids = tuple(catalog_item.product_ids)
    reason_codes: list[str] = []

    if not product_ids:
        reason_codes.append("missing_product_ids")

    if normalized_price.state in CONCEPT_DETAIL_STATES:
        reason_codes.append(f"price_state_{normalized_price.state.value.lower()}")

    missing_metadata_fields = _missing_applicable_metadata_fields(catalog_item)
    if missing_metadata_fields:
        reason_codes.append("missing_metadata")

    if reason_codes:
        return SnapshotSourceDecision(
            source="concept_detail",
            reason=reason_codes[0],
            reason_codes=tuple(reason_codes),
            normalized_state=normalized_price.state,
            product_ids=product_ids,
            missing_metadata_fields=missing_metadata_fields,
        )

    if normalized_price.state in CATALOG_SNAPSHOT_STATES:
        return SnapshotSourceDecision(
            source="catalog",
            reason="catalog_price_snapshot",
            reason_codes=("clear_catalog_price", "product_ids_present"),
            normalized_state=normalized_price.state,
            product_ids=product_ids,
            missing_metadata_fields=(),
        )

    fallback_reason = f"price_state_{normalized_price.state.value.lower()}"
    return SnapshotSourceDecision(
        source="concept_detail",
        reason=fallback_reason,
        reason_codes=(fallback_reason,),
        normalized_state=normalized_price.state,
        product_ids=product_ids,
        missing_metadata_fields=missing_metadata_fields,
    )


def _missing_applicable_metadata_fields(catalog_item: CatalogItem) -> tuple[str, ...]:
    missing_fields = []

    for field_name in FUTURE_METADATA_FIELDS:
        if not hasattr(catalog_item, field_name):
            continue

        value = getattr(catalog_item, field_name)
        if value is None or value == "":
            missing_fields.append(field_name)

    return tuple(missing_fields)
