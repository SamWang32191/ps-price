import json
import sys
from pathlib import Path
from typing import Any

from ps_price_crawler import cli
from ps_price_crawler.errors import MissingEmbeddedStateError, MissingRequiredFieldError
from ps_price_crawler.models import CatalogItem, CatalogPage, PriceInfo, ProductDetail


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


def _catalog_item(
    concept_id: str = "1001",
    *,
    product_ids: tuple[str, ...] = ("PRODUCT-1001",),
    price: PriceInfo | None = None,
) -> CatalogItem:
    return CatalogItem(
        concept_id=concept_id,
        name=f"Game {concept_id}",
        product_ids=product_ids,
        image_url="https://example.test/image.jpg",
        price=price or _price(base_price="NT$1,690", discounted_price="NT$1,690"),
    )


def _catalog_page(page_number: int, items: tuple[CatalogItem, ...]) -> CatalogPage:
    return CatalogPage(
        source_url=f"https://store.playstation.com/zh-hant-tw/category/test/{page_number}",
        category_id="test",
        total_count=len(items),
        offset=(page_number - 1) * 24,
        size=24,
        is_last=False,
        items=items,
    )


def _detail(*, concept_id: str = "223118", product_id: str = "PRODUCT-223118") -> ProductDetail:
    return ProductDetail(
        concept_id=concept_id,
        concept_name="Roblox",
        product_id=product_id,
        product_name="Roblox",
        publisher_name="Roblox Corporation",
        release_date="2026-01-01T00:00:00Z",
        platforms=("PS5",),
        top_category="GAME",
        price=_price(base_price="免費", discounted_price="免費", is_free=True),
    )


class FakeClient:
    def __init__(self, *, catalog_pages: dict[int, str] | None = None, concept_html: str = "concept-html") -> None:
        self.catalog_pages = catalog_pages or {}
        self.concept_html = concept_html

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def fetch_catalog_page(self, page_number: int) -> tuple[str, str]:
        return (
            f"https://store.playstation.com/zh-hant-tw/category/test/{page_number}",
            self.catalog_pages[page_number],
        )

    def fetch_concept(self, concept_id: str) -> tuple[str, str]:
        return f"https://store.playstation.com/zh-hant-tw/concept/{concept_id}", self.concept_html


def _run_cli(monkeypatch, argv: list[str]) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["ps-price-crawler", *argv])
    try:
        cli.main()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1, ""
    return 0, ""


def test_catalog_json_reports_items_strategy_and_page_parser_errors(monkeypatch, capsys):
    parsed_pages = {
        "catalog-page-1": _catalog_page(1, (_catalog_item(),)),
    }

    def fake_parse_catalog_page(html: str, source_url: str) -> CatalogPage:
        if html == "catalog-page-2":
            raise MissingEmbeddedStateError("Catalog page does not contain a CategoryGrid entry")
        return parsed_pages[html]

    monkeypatch.setattr(
        cli,
        "PlayStationStoreClient",
        lambda: FakeClient(catalog_pages={1: "catalog-page-1", 2: "catalog-page-2"}),
    )
    monkeypatch.setattr(cli, "parse_catalog_page", fake_parse_catalog_page)

    exit_code, _ = _run_cli(monkeypatch, ["catalog", "--pages", "2", "--format", "json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert len(payload["pages"]) == 2
    assert payload["pages"][0]["parser_error"] is None
    assert payload["pages"][1]["parser_error"] == {
        "type": "MissingEmbeddedStateError",
        "message": "Catalog page does not contain a CategoryGrid entry",
    }
    assert payload["items"][0]["concept_id"] == "1001"
    assert payload["items"][0]["product_ids"] == ["PRODUCT-1001"]
    assert payload["items"][0]["price"]["state"] == "PAID"
    assert payload["items"][0]["source_strategy"]["source"] == "catalog"
    assert payload["items"][0]["source_strategy"]["reason_codes"] == [
        "clear_catalog_price",
        "product_ids_present",
    ]


def test_concept_json_reports_price_and_source_limitation_without_catalog_context(monkeypatch, capsys):
    monkeypatch.setattr(cli, "PlayStationStoreClient", lambda: FakeClient())
    monkeypatch.setattr(cli, "parse_product_detail", lambda html, concept_id: _detail(concept_id=concept_id))

    exit_code, _ = _run_cli(monkeypatch, ["concept", "223118", "--format", "json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["concept_id"] == "223118"
    assert payload["product_id"] == "PRODUCT-223118"
    assert payload["product_ids"] == ["PRODUCT-223118"]
    assert payload["price"]["state"] == "FREE"
    assert payload["source_strategy"]["source"] == "concept_detail"
    assert payload["source_strategy"]["reason_codes"] == ["no_catalog_item_context"]
    assert "catalog item" in payload["source_strategy"]["limitations"][0]
    assert payload["parser_error"] is None


def test_concept_json_outputs_parser_error_without_traceback(monkeypatch, capsys):
    def fake_parse_product_detail(html: str, concept_id: str) -> ProductDetail:
        raise MissingRequiredFieldError("Missing required Product.price")

    monkeypatch.setattr(cli, "PlayStationStoreClient", lambda: FakeClient())
    monkeypatch.setattr(cli, "parse_product_detail", fake_parse_product_detail)

    exit_code, _ = _run_cli(monkeypatch, ["concept", "999", "--format", "json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["concept_id"] == "999"
    assert payload["product_id"] is None
    assert payload["product_ids"] == []
    assert payload["price"] is None
    assert payload["parser_error"] == {
        "type": "MissingRequiredFieldError",
        "message": "Missing required Product.price",
    }


def test_fixture_report_reads_committed_fixture_shape_offline(monkeypatch, tmp_path):
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "concept_free_1001.html").write_text("success-html", encoding="utf-8")
    (fixtures_dir / "concept_unknown_1002.html").write_text("broken-html", encoding="utf-8")
    _write_fixture(
        fixtures_dir / "concept_free_1001.json",
        target_key="free",
        concept_id="1001",
        normalized_state="FREE",
        raw_html_fixture="concept_free_1001.html",
        price_fields={"basePrice": "免費", "discountedPrice": "免費", "isFree": True},
    )
    _write_fixture(
        fixtures_dir / "concept_unknown_1002.json",
        target_key="missing_or_unavailable_candidate",
        concept_id="1002",
        normalized_state="UNKNOWN",
        raw_html_fixture="concept_unknown_1002.html",
        price_fields={"basePrice": None, "discountedPrice": None, "isFree": None},
    )
    output_path = tmp_path / "report.json"

    def fake_parse_product_detail(
        html: str,
        concept_id: str,
        *,
        catalog_price: PriceInfo | None = None,
    ) -> ProductDetail:
        if html == "broken-html":
            raise MissingRequiredFieldError("Missing required Concept.defaultProduct")
        return _detail(concept_id=concept_id, product_id="PRODUCT-1001")

    monkeypatch.setattr(cli, "parse_product_detail", fake_parse_product_detail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ps-price-crawler",
            "fixture-report",
            "--fixtures",
            str(fixtures_dir),
            "--output",
            str(output_path),
        ],
    )

    cli.main()

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["fixtures_dir"] == str(fixtures_dir)
    assert report["coverage"]["states_present"] == ["FREE", "UNKNOWN"]
    assert len(report["fixtures"]) == 2
    by_concept = {item["concept_id"]: item for item in report["fixtures"]}
    assert by_concept["1001"]["product_ids"] == ["PRODUCT-1001"]
    assert by_concept["1001"]["price"]["state"] == "FREE"
    assert by_concept["1001"]["source_strategy"]["source"] == "catalog"
    assert by_concept["1002"]["parser_error"] == {
        "type": "MissingRequiredFieldError",
        "message": "Missing required Concept.defaultProduct",
    }
    assert by_concept["1002"]["source_strategy"]["source"] == "concept_detail"


def _write_fixture(
    path: Path,
    *,
    target_key: str,
    concept_id: str,
    normalized_state: str,
    raw_html_fixture: str,
    price_fields: dict[str, Any],
) -> None:
    payload = {
        "target_key": target_key,
        "concept_id": concept_id,
        "name": f"Game {concept_id}",
        "source_url": f"https://store.playstation.com/zh-hant-tw/concept/{concept_id}",
        "catalog_source_url": "https://store.playstation.com/zh-hant-tw/category/test/1",
        "catalog_price_fields": {
            "basePrice": price_fields["basePrice"],
            "discountText": None,
            "discountedPrice": price_fields["discountedPrice"],
            "isExclusive": False if price_fields["isFree"] is not None else None,
            "isFree": price_fields["isFree"],
            "isTiedToSubscription": False if price_fields["isFree"] is not None else None,
            "normalizedState": normalized_state,
            "rawMissingReason": "Catalog item price block missing" if price_fields["basePrice"] is None else None,
            "serviceBranding": [],
            "upsellText": None,
        },
        "normalized_state": normalized_state,
        "parser_error": None,
        "product_detail": None,
        "raw_html_committed": True,
        "raw_html_fixture": raw_html_fixture,
        "raw_html_omitted_reason": None,
        "raw_html_sha256": "0" * 64,
        "raw_html_size_bytes": 10,
        "target_reason": f"catalog price normalized as {normalized_state}",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
