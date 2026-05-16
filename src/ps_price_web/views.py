from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from ps_price_web.queries import get_latest_deals

from ps_price_sync.views import product_detail as _product_detail


def deals_view(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "")
    deals = get_latest_deals(query=query)
    return render(
        request,
        "ps_price_web/deals.html",
        {"deals": deals, "query": query},
    )


def product_detail_view(request: HttpRequest, product_id: str) -> HttpResponse:
    return _product_detail(request, product_id)
