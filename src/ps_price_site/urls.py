from __future__ import annotations

from django.urls import include, path

urlpatterns = [
    path("", include("ps_price_web.urls")),
    path("", include("ps_price_sync.urls")),
]
