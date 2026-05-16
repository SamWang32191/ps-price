from __future__ import annotations

from django import template

from ps_price_web.formatting import format_money_twd, format_raw_json_list


register = template.Library()


@register.filter
def money_twd(value, display_text=""):
    return format_money_twd(value, display_text if display_text else None)


@register.filter
def raw_json_list(value):
    return format_raw_json_list(value)

