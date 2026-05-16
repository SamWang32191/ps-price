from __future__ import annotations

from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("products/", views.product_list, name="product-list"),
    path("products/<path:product_id>/", views.product_detail, name="product-detail"),
]
