from __future__ import annotations

from django.db import models


class StoreProduct(models.Model):
    product_id = models.CharField(max_length=128, unique=True)
    concept_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    product_name = models.TextField()
    concept_name = models.TextField(blank=True, default="")
    publisher_name = models.TextField(null=True, blank=True)
    release_date_raw = models.TextField(null=True, blank=True)
    top_category = models.TextField(null=True, blank=True)
    image_url = models.URLField(max_length=500, null=True, blank=True)
    source_url = models.URLField(max_length=500, null=True, blank=True)
    platforms_raw = models.TextField(default="[]")
    is_visible = models.BooleanField(null=True, blank=True)
    missing_count = models.PositiveIntegerField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PriceSnapshot(models.Model):
    store_product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name="snapshots")
    snapshot_date = models.DateField()
    normalized_state = models.CharField(max_length=32)
    currency = models.CharField(max_length=16, null=True, blank=True)
    base_amount_cents = models.IntegerField(null=True, blank=True)
    discounted_amount_cents = models.IntegerField(null=True, blank=True)
    plus_amount_cents = models.IntegerField(null=True, blank=True)
    base_display = models.TextField(null=True, blank=True)
    discounted_display = models.TextField(null=True, blank=True)
    discount_text = models.TextField(null=True, blank=True)
    service_branding_raw = models.TextField(default="[]")
    upsell_text = models.TextField(null=True, blank=True)
    source_strategy_source = models.CharField(max_length=32)
    source_strategy_reason = models.CharField(max_length=64)
    source_strategy_reason_codes_raw = models.TextField(default="[]")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["store_product", "snapshot_date"],
                name="unique_snapshot_per_product_per_day",
            )
        ]


class SyncRun(models.Model):
    sync_type = models.CharField(max_length=32)
    status = models.CharField(max_length=32)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    success_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    summary = models.TextField(default="{}")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SyncError(models.Model):
    sync_run = models.ForeignKey(SyncRun, on_delete=models.CASCADE, related_name="errors")
    stage = models.CharField(max_length=32)
    product_id = models.CharField(max_length=128, null=True, blank=True)
    concept_id = models.CharField(max_length=64, null=True, blank=True)
    source_url = models.URLField(max_length=500, null=True, blank=True)
    error_type = models.CharField(max_length=128)
    error_message = models.TextField()
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
