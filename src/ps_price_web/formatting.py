from __future__ import annotations

import json
from typing import Any


def format_money_twd(amount_cents: int | None, display_text: str | None = None) -> str:
    if amount_cents is not None:
        return f"NT${amount_cents // 100:,}"
    if display_text:
        return display_text
    return "-"


def format_raw_json_list(raw_value: str | None) -> str:
    if not raw_value:
        return "-"
    try:
        parsed: Any = json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value
    if not isinstance(parsed, list):
        return raw_value
    values = [str(item) for item in parsed if item is not None and str(item)]
    if not values:
        return "-"
    return ", ".join(values)
