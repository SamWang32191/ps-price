from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Max, Q

from ps_price_sync.models import PriceSnapshot, StoreProduct


@dataclass(frozen=True)
class DealRow:
    product: StoreProduct
    snapshot: PriceSnapshot
    discount_percent: int


def _discount_percent(base_amount_cents: int, discounted_amount_cents: int) -> int:
    discount = Decimal(base_amount_cents - discounted_amount_cents) / Decimal(base_amount_cents)
    return int((discount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def get_latest_deals(query: str = "") -> list[DealRow]:
    products = StoreProduct.objects.exclude(is_visible=False)
    search = query.strip()
    if search:
        products = products.filter(Q(product_name__icontains=search) | Q(concept_name__icontains=search))

    latest_dates = (
        PriceSnapshot.objects.filter(store_product__in=products)
        .values("store_product_id")
        .annotate(latest_date=Max("snapshot_date"))
    )
    latest_lookup = {row["store_product_id"]: row["latest_date"] for row in latest_dates}

    snapshots = (
        PriceSnapshot.objects.select_related("store_product")
        .filter(
            store_product_id__in=latest_lookup.keys(),
            normalized_state="DISCOUNTED",
            base_amount_cents__isnull=False,
            discounted_amount_cents__isnull=False,
        )
        .order_by("store_product__product_name", "store_product__product_id")
    )

    deals: list[DealRow] = []
    for snapshot in snapshots:
        if latest_lookup.get(snapshot.store_product_id) != snapshot.snapshot_date:
            continue
        base = snapshot.base_amount_cents
        discounted = snapshot.discounted_amount_cents
        if base is None or discounted is None or base <= 0 or discounted >= base:
            continue
        deals.append(
            DealRow(
                product=snapshot.store_product,
                snapshot=snapshot,
                discount_percent=_discount_percent(base, discounted),
            )
        )

    return sorted(deals, key=lambda deal: (-deal.discount_percent, deal.product.product_name, deal.product.product_id))
