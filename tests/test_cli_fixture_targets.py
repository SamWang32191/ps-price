import json
import sys
from typing import Any

from ps_price_crawler import cli
from ps_price_crawler.models import CatalogItem, CatalogPage, PriceInfo


def _price(
    *,
    base_price: str | None = None,
    discounted_price: str | None = None,
    discount_text: str | None = None,
    is_free: bool = False,
    is_exclusive: bool = False,
    is_tied_to_subscription: bool = False,
    service_branding: tuple[str, ...] = (),
    upsell_text: str | None = None,
) -> PriceInfo:
    return PriceInfo(
        base_price=base_price,
        discounted_price=discounted_price,
        discount_text=discount_text,
        is_free=is_free,
        is_exclusive=is_exclusive,
        is_tied_to_subscription=is_tied_to_subscription,
        service_branding=service_branding,
        upsell_text=upsell_text,
    )


def _item(concept_id: str, name: str, price: PriceInfo | None) -> CatalogItem:
    return CatalogItem(
        concept_id=concept_id,
        name=name,
        product_ids=(f"PRODUCT-{concept_id}",),
        image_url=None,
        price=price,
    )


def _page(page_number: int, items: tuple[CatalogItem, ...]) -> CatalogPage:
    return CatalogPage(
        source_url=f"https://store.playstation.com/zh-hant-tw/category/test/{page_number}",
        category_id="test",
        total_count=len(items),
        offset=(page_number - 1) * 24,
        size=24,
        is_last=False,
        items=items,
    )


class FakeClient:
    def __init__(self, pages: dict[int, CatalogPage]) -> None:
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def fetch_catalog_page(self, page_number: int) -> tuple[str, str]:
        page = self.pages[page_number]
        return page.source_url, f"html-page-{page_number}"

    def fetch_concept(self, concept_id: str):
        raise AssertionError("fixture-targets must not fetch concept detail pages")


def _run_fixture_targets(
    monkeypatch,
    tmp_path,
    pages: dict[int, CatalogPage],
    page_count: int = 1,
    failing_html: set[str] | None = None,
) -> tuple[int, dict[str, Any] | None]:
    output_path = tmp_path / "fixture-targets.json"
    parsed_by_html = {f"html-page-{page_number}": page for page_number, page in pages.items()}
    failing_html = failing_html or set()
    unexpected_exception: dict[str, Any] | None = None

    def fake_parse_catalog_page(html: str, source_url: str):
        if html in failing_html:
            raise ValueError("Catalog page does not contain a CategoryGrid entry")
        return parsed_by_html[html]

    monkeypatch.setattr(cli, "PlayStationStoreClient", lambda: FakeClient(pages))
    monkeypatch.setattr(cli, "parse_catalog_page", fake_parse_catalog_page)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ps-price-crawler",
            "fixture-targets",
            "--pages",
            str(page_count),
            "--output",
            str(output_path),
        ],
    )

    try:
        cli.main()
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        exit_code = 99
        unexpected_exception = {"exception": f"{type(exc).__name__}: {exc}"}
    else:
        exit_code = 0
        unexpected_exception = None

    if not output_path.exists():
        return exit_code, unexpected_exception
    return exit_code, json.loads(output_path.read_text(encoding="utf-8"))


def test_fixture_targets_classifies_all_required_catalog_categories(monkeypatch, tmp_path):
    pages = {
        1: _page(
            1,
            (
                _item("1001", "Free Game", _price(base_price="免費", discounted_price="免費", is_free=True)),
                _item("1002", "Paid Game", _price(base_price="NT$1,990", discounted_price="NT$1,990")),
                _item(
                    "1003",
                    "Discount Game",
                    _price(base_price="NT$1,990", discounted_price="NT$1,490", discount_text="限時折扣"),
                ),
                _item(
                    "1004",
                    "Plus Game",
                    _price(base_price="NT$1,990", discounted_price="NT$1,990", service_branding=("PS_PLUS",)),
                ),
                _item("1005", "Unavailable Game", _price(base_price="暫無售價", discounted_price="暫無售價")),
            ),
        )
    }

    exit_code, payload = _run_fixture_targets(monkeypatch, tmp_path, pages)

    assert exit_code == 0
    assert payload is not None
    assert {key: payload[key]["concept_id"] for key in payload} == {
        "free": "1001",
        "paid_full_price": "1002",
        "discounted_paid": "1003",
        "ps_plus_candidate": "1004",
        "missing_or_unavailable_candidate": "1005",
    }
    assert payload["discounted_paid"]["price_fields"]["discountText"] == "限時折扣"
    assert payload["ps_plus_candidate"]["reason"] == "catalog price normalized as PS_PLUS"


def test_fixture_targets_exits_two_and_writes_nulls_when_categories_missing(monkeypatch, tmp_path):
    pages = {
        1: _page(
            1,
            (
                _item("1001", "Free Game", _price(base_price="免費", discounted_price="免費", is_free=True)),
                _item("1002", "Paid Game", _price(base_price="NT$1,990", discounted_price="NT$1,990")),
            ),
        )
    }

    exit_code, payload = _run_fixture_targets(monkeypatch, tmp_path, pages)

    assert exit_code == 2
    assert payload is not None
    assert payload["free"]["concept_id"] == "1001"
    assert payload["paid_full_price"]["concept_id"] == "1002"
    assert payload["discounted_paid"] is None
    assert payload["ps_plus_candidate"] is None
    assert payload["missing_or_unavailable_candidate"] is None


def test_fixture_targets_uses_roblox_free_fallback_only_when_no_free_catalog_item(monkeypatch, tmp_path):
    pages = {
        1: _page(
            1,
            (
                _item("1002", "Paid Game", _price(base_price="NT$1,990", discounted_price="NT$1,990")),
                _item(
                    "1003",
                    "Discount Game",
                    _price(base_price="NT$1,990", discounted_price="NT$1,490", discount_text="限時折扣"),
                ),
                _item(
                    "1004",
                    "Plus Game",
                    _price(base_price="NT$1,990", discounted_price="NT$1,990", is_exclusive=True),
                ),
                _item("1005", "Unavailable Game", None),
            ),
        )
    }

    exit_code, payload = _run_fixture_targets(monkeypatch, tmp_path, pages)

    assert exit_code == 0
    assert payload is not None
    assert payload["free"]["concept_id"] == "223118"
    assert payload["free"]["name"] == "Roblox"
    assert payload["free"]["reason"] == "known free fallback used after catalog scan found no free item"


def test_fixture_targets_skips_unparseable_catalog_pages_and_continues(monkeypatch, tmp_path):
    pages = {
        1: _page(1, ()),
        2: _page(
            2,
            (
                _item("1001", "Free Game", _price(base_price="免費", discounted_price="免費", is_free=True)),
                _item("1002", "Paid Game", _price(base_price="NT$1,990", discounted_price="NT$1,990")),
                _item(
                    "1003",
                    "Discount Game",
                    _price(base_price="NT$1,990", discounted_price="NT$1,490", discount_text="限時折扣"),
                ),
                _item(
                    "1004",
                    "Plus Game",
                    _price(base_price="NT$1,990", discounted_price="NT$1,990", is_tied_to_subscription=True),
                ),
                _item("1005", "Unavailable Game", _price(base_price="不可購買", discounted_price="不可購買")),
            ),
        ),
    }

    exit_code, payload = _run_fixture_targets(
        monkeypatch,
        tmp_path,
        pages,
        page_count=2,
        failing_html={"html-page-1"},
    )

    assert exit_code == 0
    assert payload is not None
    assert payload["free"]["concept_id"] == "1001"
    assert payload["missing_or_unavailable_candidate"]["concept_id"] == "1005"
