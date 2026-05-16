from __future__ import annotations

from django import template


register = template.Library()


@register.filter
def twd_cents(value: int | None) -> str:
    if value is None:
        return "-"
    return f"NT${value // 100:,}"
