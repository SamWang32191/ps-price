from __future__ import annotations

from datetime import date
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Max, Q

from ps_price_sync.models import PriceSnapshot, StoreProduct


@dataclass(frozen=True)
class DealRow:
    product: StoreProduct
    snapshot: PriceSnapshot
    discount_percent: int


@dataclass(frozen=True)
class ProductDetail:
    product: StoreProduct
    latest_snapshot: PriceSnapshot | None
    snapshots: list[PriceSnapshot]
    current_price_amount_cents: int | None
    current_price_display: str | None
    regular_low_amount_cents: int | None
    regular_low_date: date | None


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


def _regular_snapshot_price(snapshot: PriceSnapshot | None) -> int | None:
    if snapshot is None:
        return None
    if snapshot.normalized_state == "DISCOUNTED":
        return snapshot.discounted_amount_cents
    if snapshot.normalized_state == "PAID":
        return snapshot.base_amount_cents
    return None


def _current_snapshot_price(snapshot: PriceSnapshot | None) -> tuple[int | None, str | None]:
    if snapshot is None:
        return (None, None)
    if snapshot.normalized_state == "DISCOUNTED":
        return snapshot.discounted_amount_cents, snapshot.discounted_display
    if snapshot.normalized_state == "PS_PLUS":
        return snapshot.plus_amount_cents, None
    return snapshot.base_amount_cents, snapshot.base_display


def get_product_detail(product_id: str) -> ProductDetail:
    product = StoreProduct.objects.get(product_id=product_id)
    snapshots = list(product.snapshots.order_by("-snapshot_date", "-id"))
    latest_snapshot = snapshots[0] if snapshots else None
    current_price_amount_cents, current_price_display = _current_snapshot_price(latest_snapshot)

    regular_low_amount_cents = None
    regular_low_date = None
    for snapshot in snapshots:
        regular_amount = _regular_snapshot_price(snapshot)
        if regular_amount is None:
            continue
        if regular_low_amount_cents is None or regular_amount < regular_low_amount_cents:
            regular_low_amount_cents = regular_amount
            regular_low_date = snapshot.snapshot_date

    return ProductDetail(
        product=product,
        latest_snapshot=latest_snapshot,
        snapshots=snapshots,
        current_price_amount_cents=current_price_amount_cents,
        current_price_display=current_price_display,
        regular_low_amount_cents=regular_low_amount_cents,
        regular_low_date=regular_low_date,
    )
