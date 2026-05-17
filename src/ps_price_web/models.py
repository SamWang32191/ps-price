from __future__ import annotations

from django.db import models

from ps_price_sync.models import StoreProduct


class WatchedProduct(models.Model):
    store_product = models.OneToOneField(StoreProduct, on_delete=models.CASCADE, related_name="watch")
    target_price_cents = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["store_product__product_name", "store_product__product_id"]
