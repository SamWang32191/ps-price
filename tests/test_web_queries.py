from __future__ import annotations

from ps_price_web.formatting import format_money_twd, format_raw_json_list


def test_format_money_twd_formats_integer_cents() -> None:
    assert format_money_twd(59000, "NT$590") == "NT$590"
    assert format_money_twd(0, "Free") == "NT$0"


def test_format_money_twd_falls_back_to_display_text() -> None:
    assert format_money_twd(None, "NT$1,490") == "NT$1,490"
    assert format_money_twd(None, None) == "-"


def test_format_raw_json_list_formats_json_arrays() -> None:
    assert format_raw_json_list("[\"PS5\", \"PS4\"]") == "PS5, PS4"
    assert format_raw_json_list("[]") == "-"


def test_format_raw_json_list_falls_back_to_raw_text() -> None:
    assert format_raw_json_list("not-json") == "not-json"
    assert format_raw_json_list("") == "-"
