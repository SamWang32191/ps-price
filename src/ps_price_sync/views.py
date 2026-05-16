from __future__ import annotations

from django.shortcuts import get_object_or_404, render

from .services.query_views import get_dashboard_summary, get_product_detail, list_products, normalize_filters
from .models import StoreProduct


def dashboard(request):
    return render(request, "ps_price_sync/dashboard.html", {"summary": get_dashboard_summary()})


def product_list(request):
    result = list_products(normalize_filters(request.GET))
    return render(request, "ps_price_sync/product_list.html", {"result": result})


def product_detail(request, product_id: str):
    product = get_object_or_404(StoreProduct, product_id=product_id)
    detail = get_product_detail(product)
    return render(request, "ps_price_sync/product_detail.html", {"detail": detail})
