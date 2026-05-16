from __future__ import annotations

from django import template


register = template.Library()


@register.filter
def twd_cents(value: int | None) -> str:
    if value is None:
        return "-"
    return f"NT${value // 100:,}"


@register.filter
def snapshot_price_display(snapshot) -> str:
    if snapshot is None:
        return "-"

    discounted_display = getattr(snapshot, "discounted_display", None)
    if discounted_display:
        return discounted_display

    base_display = getattr(snapshot, "base_display", None)
    if base_display:
        return base_display

    if getattr(snapshot, "discounted_amount_cents", None) is not None:
        return twd_cents(snapshot.discounted_amount_cents)

    return twd_cents(snapshot.base_amount_cents)
