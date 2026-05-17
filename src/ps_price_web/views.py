from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ps_price_sync.models import StoreProduct
from ps_price_web.models import WatchedProduct
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


def _parse_target_price(raw_value: str) -> tuple[int | None, str | None]:
    value = raw_value.strip()
    if value == "":
        return None, None
    if not value.isdecimal():
        return None, "target price 必須是正整數台幣元"
    amount = int(value)
    if amount <= 0:
        return None, "target price 必須是正整數台幣元"
    return amount * 100, None


def _target_price_value(detail: object) -> str:
    watched_product = detail.watched_product
    if watched_product is None or watched_product.target_price_cents is None:
        return ""
    return str(watched_product.target_price_cents // 100)


def product_detail_view(request: HttpRequest, product_id: str) -> HttpResponse:
    product = get_object_or_404(StoreProduct, product_id=product_id)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "remove_watch":
            WatchedProduct.objects.filter(store_product=product).delete()
            return redirect("ps_price_web:product_detail", product_id=product.product_id)
        if action == "save_watch":
            target_price_cents, error = _parse_target_price(request.POST.get("target_price", ""))
            if error is not None:
                return render(
                    request,
                    "ps_price_web/product_detail.html",
                    {
                        "detail": get_product_detail(product_id),
                        "watch_error": error,
                        "target_price_value": request.POST.get("target_price", ""),
                    },
                )
            WatchedProduct.objects.update_or_create(
                store_product=product,
                defaults={"target_price_cents": target_price_cents},
            )
            return redirect("ps_price_web:product_detail", product_id=product.product_id)

    detail = get_product_detail(product_id)
    return render(
        request,
        "ps_price_web/product_detail.html",
        {"detail": detail, "target_price_value": _target_price_value(detail)},
    )
