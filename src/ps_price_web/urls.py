from __future__ import annotations

from django.urls import path

from . import views

app_name = "ps_price_web"

urlpatterns = [
    path("deals/", views.deals_view, name="deals"),
    path("products/<str:product_id>/", views.product_detail_view, name="product_detail"),
]
