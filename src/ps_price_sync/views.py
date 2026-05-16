from __future__ import annotations

from django.shortcuts import get_object_or_404, render

from .models import StoreProduct


def dashboard(request):
    return render(request, "ps_price_sync/dashboard.html")


def product_list(request):
    return render(request, "ps_price_sync/product_list.html", {"products": []})


def product_detail(request, product_id: str):
    product = get_object_or_404(StoreProduct, product_id=product_id)
    return render(request, "ps_price_sync/product_detail.html", {"product": product})
