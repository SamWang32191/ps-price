from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from ps_price_sync.models import StoreProduct
from ps_price_web.queries import get_latest_deals, get_product_detail, get_watchlist_rows


def deals_view(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "")
    deals = get_latest_deals(query=query)
    return render(
        request,
        "ps_price_web/deals.html",
        {"deals": deals, "query": query},
    )


def watchlist_view(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "ps_price_web/watchlist.html",
        {"rows": get_watchlist_rows()},
    )


def product_detail_view(request: HttpRequest, product_id: str) -> HttpResponse:
    get_object_or_404(StoreProduct, product_id=product_id)
    return render(
        request,
        "ps_price_web/product_detail.html",
        {"detail": get_product_detail(product_id)},
    )
