from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from math import ceil

from django.db.models import Max, Prefetch, Q

from ps_price_sync.models import PriceSnapshot, StoreProduct, SyncError, SyncRun


GENERAL_PRICE_STATES = frozenset({"PAID", "DISCOUNTED"})


@dataclass(frozen=True)
class PriceSummary:
    current_snapshot: PriceSnapshot | None
    general_low_amount_cents: int | None
    general_low_date: date | None
    plus_low_amount_cents: int | None
    plus_low_date: date | None
    is_current_discounted: bool


@dataclass(frozen=True)
class ProductListFilters:
    query: str = ""
    state: str = ""
    sale_only: bool = False
    visibility: str = ""
    top_category: str = ""
    page: int = 1
    page_size: int = 50


@dataclass(frozen=True)
class ProductListRow:
    product: StoreProduct
    price_summary: PriceSummary


@dataclass(frozen=True)
class ProductListResult:
    products: list[ProductListRow]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    filters: ProductListFilters
    state_options: tuple[str, ...]
    category_options: tuple[str, ...]


@dataclass(frozen=True)
class ChartPoint:
    snapshot_date: date
    amount_cents: int
    x: float
    y: float


@dataclass(frozen=True)
class ProductDetail:
    product: StoreProduct
    price_summary: PriceSummary
    snapshots: list[PriceSnapshot]
    chart_points: list[ChartPoint]


@dataclass(frozen=True)
class DashboardSummary:
    total_products: int
    visible_products: int
    current_discounted_products: int
    latest_snapshot_date: date | None
    latest_sync_run: SyncRun | None
    latest_sync_summary: dict[str, object]
    unresolved_error_count: int
    recent_errors: list[SyncError]


def get_current_snapshot(product: StoreProduct) -> PriceSnapshot | None:
    return (
        PriceSnapshot.objects.filter(store_product=product)
        .order_by("-snapshot_date", "-updated_at", "-id")
        .first()
    )


def _general_amount(snapshot: PriceSnapshot) -> int | None:
    if snapshot.currency != "TWD":
        return None
    if snapshot.normalized_state not in GENERAL_PRICE_STATES:
        return None
    if snapshot.discounted_amount_cents is not None:
        return snapshot.discounted_amount_cents
    return snapshot.base_amount_cents


def _calculate_price_summary_from_snapshots(snapshots: list[PriceSnapshot]) -> PriceSummary:
    if not snapshots:
        return PriceSummary(
            current_snapshot=None,
            general_low_amount_cents=None,
            general_low_date=None,
            plus_low_amount_cents=None,
            plus_low_date=None,
            is_current_discounted=False,
        )

    ordered = sorted(snapshots, key=lambda snapshot: (snapshot.snapshot_date, snapshot.updated_at, snapshot.id))
    current_snapshot = ordered[-1]
    general_low_amount: int | None = None
    general_low_date: date | None = None
    plus_low_amount: int | None = None
    plus_low_date: date | None = None

    for snapshot in snapshots:
        general_amount = _general_amount(snapshot)
        if general_amount is not None and (general_low_amount is None or general_amount < general_low_amount):
            general_low_amount = general_amount
            general_low_date = snapshot.snapshot_date
        if snapshot.plus_amount_cents is not None and (
            plus_low_amount is None or snapshot.plus_amount_cents < plus_low_amount
        ):
            plus_low_amount = snapshot.plus_amount_cents
            plus_low_date = snapshot.snapshot_date

    return PriceSummary(
        current_snapshot=current_snapshot,
        general_low_amount_cents=general_low_amount,
        general_low_date=general_low_date,
        plus_low_amount_cents=plus_low_amount,
        plus_low_date=plus_low_date,
        is_current_discounted=current_snapshot is not None and current_snapshot.normalized_state == "DISCOUNTED",
    )


def calculate_price_summary(product: StoreProduct) -> PriceSummary:
    snapshots = list(PriceSnapshot.objects.filter(store_product=product).order_by("snapshot_date", "updated_at", "id"))
    return _calculate_price_summary_from_snapshots(snapshots)


def _parse_positive_int(value: int, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed >= 1 else fallback


def _parse_bounded_int(value: int, fallback: int, *, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    if parsed < min_value:
        return min_value
    if parsed > max_value:
        return max_value
    return parsed


def normalize_filters(params) -> ProductListFilters:
    return ProductListFilters(
        query=str(params.get("q", "")).strip(),
        state=str(params.get("state", "")).strip(),
        sale_only=str(params.get("sale", "")).strip() == "1",
        visibility=str(params.get("visibility", "")).strip(),
        top_category=str(params.get("top_category", "")).strip(),
        page=_parse_positive_int(params.get("page", 1), 1),
        page_size=_parse_bounded_int(params.get("page_size", 50), 50, min_value=1, max_value=100),
    )


def list_products(filters: ProductListFilters) -> ProductListResult:
    latest_date = PriceSnapshot.objects.aggregate(value=Max("snapshot_date"))["value"]
    queryset = StoreProduct.objects.all().order_by("product_name", "product_id").prefetch_related(
        Prefetch("snapshots", queryset=PriceSnapshot.objects.order_by("snapshot_date", "updated_at", "id"))
    )

    if filters.query:
        queryset = queryset.filter(
            Q(product_name__icontains=filters.query)
            | Q(concept_name__icontains=filters.query)
            | Q(product_id__icontains=filters.query)
        )
    if filters.visibility == "visible":
        queryset = queryset.filter(is_visible=True)
    elif filters.visibility == "hidden":
        queryset = queryset.filter(is_visible=False)
    elif filters.visibility == "unknown":
        queryset = queryset.filter(is_visible__isnull=True)
    if filters.top_category:
        queryset = queryset.filter(top_category=filters.top_category)

    products = list(queryset)
    base_rows = [
        ProductListRow(
            product=product,
            price_summary=_calculate_price_summary_from_snapshots(list(product.snapshots.all())),
        )
        for product in products
    ]
    rows = list(base_rows)
    state_options = tuple(
        sorted(
            {
                row.price_summary.current_snapshot.normalized_state
                for row in base_rows
                if row.price_summary.current_snapshot is not None
            }
        )
    )

    if filters.state:
        rows = [
            row
            for row in rows
            if row.price_summary.current_snapshot is not None
            and row.price_summary.current_snapshot.normalized_state == filters.state
        ]
    if filters.sale_only:
        rows = [row for row in rows if row.price_summary.is_current_discounted]

    if latest_date is not None:
        rows.sort(
            key=lambda row: (
                row.price_summary.current_snapshot is None,
                row.product.product_name.lower(),
                row.product.product_id,
            )
        )

    total_count = len(rows)
    total_pages = max(1, ceil(total_count / filters.page_size))
    page = min(filters.page, total_pages)
    start = (page - 1) * filters.page_size
    end = start + filters.page_size

    return ProductListResult(
        products=rows[start:end],
        total_count=total_count,
        page=page,
        page_size=filters.page_size,
        total_pages=total_pages,
        filters=ProductListFilters(
            query=filters.query,
            state=filters.state,
            sale_only=filters.sale_only,
            visibility=filters.visibility,
            top_category=filters.top_category,
            page=page,
            page_size=filters.page_size,
        ),
        state_options=state_options,
        category_options=tuple(
            StoreProduct.objects.exclude(top_category__isnull=True)
            .exclude(top_category="")
            .order_by("top_category")
            .values_list("top_category", flat=True)
            .distinct()
        ),
    )


def build_chart_points(snapshots: list[PriceSnapshot]) -> list[ChartPoint]:
    priced = [(snapshot, _general_amount(snapshot)) for snapshot in snapshots]
    priced = [(snapshot, amount) for snapshot, amount in priced if amount is not None]
    if not priced:
        return []

    amounts = [amount for _, amount in priced]
    min_amount = min(amounts)
    max_amount = max(amounts)
    span = max(max_amount - min_amount, 1)
    point_count = max(len(priced) - 1, 1)

    return [
        ChartPoint(
            snapshot_date=snapshot.snapshot_date,
            amount_cents=amount,
            x=round((index / point_count) * 100, 2),
            y=round(100 - ((amount - min_amount) / span) * 100, 2),
        )
        for index, (snapshot, amount) in enumerate(priced)
    ]


def get_product_detail(product: StoreProduct) -> ProductDetail:
    snapshots = list(product.snapshots.order_by("-snapshot_date", "-id"))
    chart_snapshots = list(reversed(snapshots))
    return ProductDetail(
        product=product,
        price_summary=calculate_price_summary(product),
        snapshots=snapshots,
        chart_points=build_chart_points(chart_snapshots),
    )


def _load_summary(summary_text: str | None) -> dict[str, object]:
    if not summary_text:
        return {}
    try:
        parsed = json.loads(summary_text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def get_dashboard_summary() -> DashboardSummary:
    latest_sync_run = SyncRun.objects.order_by("-started_at", "-created_at", "-id").first()
    latest_snapshot_date = PriceSnapshot.objects.aggregate(value=Max("snapshot_date"))["value"]
    discounted_product_ids = (
        set(
            PriceSnapshot.objects.filter(snapshot_date=latest_snapshot_date, normalized_state="DISCOUNTED").values_list(
                "store_product_id", flat=True
            )
        )
        if latest_snapshot_date is not None
        else set()
    )

    return DashboardSummary(
        total_products=StoreProduct.objects.count(),
        visible_products=StoreProduct.objects.filter(is_visible=True).count(),
        current_discounted_products=len(discounted_product_ids),
        latest_snapshot_date=latest_snapshot_date,
        latest_sync_run=latest_sync_run,
        latest_sync_summary=_load_summary(latest_sync_run.summary if latest_sync_run else None),
        unresolved_error_count=SyncError.objects.filter(resolved_at__isnull=True).count(),
        recent_errors=list(SyncError.objects.filter(resolved_at__isnull=True).order_by("-created_at", "-id")[:5]),
    )
