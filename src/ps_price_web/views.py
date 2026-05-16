from __future__ import annotations

from django.http import HttpResponse

from ps_price_sync.views import product_detail as _product_detail


def deals_view(request):
    return HttpResponse("deals")


def product_detail_view(request, product_id: str):
    return _product_detail(request, product_id)
